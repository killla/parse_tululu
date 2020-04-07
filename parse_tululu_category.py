import requests, os
from bs4 import BeautifulSoup
import pathlib

from pathvalidate import sanitize_filename
from urllib.parse import urljoin
import json
import argparse


def perebor():
    for id in range(1, 11):
        print(id)
        url = 'http://tululu.org/txt.php?id='+str(id)
        response = requests.get(url, allow_redirects=False)
        response.raise_for_status()

        if response.status_code == 302:
            print(response.status_code, response.headers['Location'])
        else:
            print(response.status_code)

            filename = 'books/'+ str(id)+'.txt'
            with open(filename, 'w') as file:
                file.write(response.text)

def page_exist(url):
    response = requests.get(url, allow_redirects=False)
    response.raise_for_status()
    return response.status_code != 302


def parse_title_author(url):
    response = requests.get(url, allow_redirects=False)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'lxml')
    title_text = soup.select_one('h1').text
    title, author = [a.strip() for a in title_text.split('::')]

    return(title, author)

def parse_img(url):
    response = requests.get(url, allow_redirects=False)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'lxml')
    img_path = soup.select_one('.bookimage img')['src']
    return img_path


def parse_comments(url):
    response = requests.get(url, allow_redirects=False)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'lxml')
    comments_tag = soup.select('.texts .black')
    comments =[comment.text for comment in comments_tag]
    return(comments)


def parse_txt_url(url):
    response = requests.get(url, allow_redirects=False)
    response.raise_for_status()
    txt_url = False

    soup = BeautifulSoup(response.text, 'lxml')
    urls = soup.select('.d_book a')
    for url in urls:
        if url.text == 'скачать txt':
            txt_url = url['href']
    return txt_url


def parse_genre(url):
    response = requests.get(url, allow_redirects=False)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'lxml')
    genres_tags = soup.select('span.d_book a')
    genres = [genre.text for genre in genres_tags]

    return genres


def download_txt(url, filename, folder='books/'):
    response = requests.get(url, allow_redirects=False)
    response.raise_for_status()

    filename = os.path.join(folder, sanitize_filename(filename))
    with open(filename, 'w') as file:
        file.write(response.text)
    return filename


def download_img(url, filename, folder='images/'):
    response = requests.get(url, allow_redirects=False)
    response.raise_for_status()

    filename = os.path.join(folder, sanitize_filename(filename))
    with open(filename, 'wb') as file:
        file.write(response.content)
    return filename


def get_book_url_from_pages(base_url, category, start_page, end_page):
    category_url = urljoin(base_url, category)
    book_urls = []
    for page in range(start_page, end_page):
        url = urljoin(category_url, str(page))

        response = requests.get(url, allow_redirects=False)
        response.raise_for_status()
        if response.status_code == (301 or 302):
            return book_urls

        soup = BeautifulSoup(response.text, 'lxml')

        books = soup.select('.d_book')

        for book in books:

            book_link = book.find('a')['href']

            print(urljoin(url, book_link))
            book_urls.append(urljoin(base_url, book_link))
    return book_urls


parser = argparse.ArgumentParser()
parser.add_argument("--start_page",  type=int,
                    help="номер страницы с которой начать скачивание")
parser.add_argument("--end_page",  type=int,
                    help="номер страницы, ДО которой закончить скачивание")
parser.add_argument("--skip_imgs",  action='store_true',
                    help="не скачивать картинки")
parser.add_argument("--skip_txt",  action='store_true',
                    help="не скачивать книги")
parser.add_argument("--dest_folder",
                    help=" путь к каталогу с результатами парсинга: картинкам, книгами, JSON")
parser.add_argument("--json_path",
                    help="указать свой путь к *.json файлу с результатами")
args = parser.parse_args()

start_page = args.start_page or 1
end_page = args.end_page or 1000
skip_imgs = args.skip_imgs
skip_txt = args.skip_txt
dest_folder = args.dest_folder
json_path = args.json_path

img_folder = 'images/'
txt_folder = 'books/'
json_file = 'books.json'

if dest_folder:
    if os.path.isdir(dest_folder):
        img_folder = os.path.join(dest_folder, img_folder)
        txt_folder = os.path.join(dest_folder, txt_folder)
if json_path:
    if os.path.isfile(json_path):
        json_file = sanitize_filename(json_path)

pathlib.Path(txt_folder).mkdir(parents=True, exist_ok=True)
pathlib.Path(img_folder).mkdir(parents=True, exist_ok=True)

base_url = 'http://tululu.org/'
category = 'l55/'
category_url = urljoin(base_url, category)

books = []
book_url = []

book_urls = get_book_url_from_pages(base_url, category, start_page, end_page)

for page_url in book_urls:
    if page_exist(page_url):
        txt_url = parse_txt_url(page_url)
        if txt_url:
            title, author = parse_title_author(page_url)
            filename = f'{title}.txt'
            txt_url = urljoin(base_url, txt_url)
            if (not skip_txt):
                book_path = download_txt(txt_url, filename)
            else:
                book_path = ''

            img_url = parse_img(page_url)
            img_path = img_url.split('/')[-1]
            img_url = urljoin(base_url, img_url)
            if (not skip_imgs):
                img_src = download_img(img_url, img_path)
            else:
                img_src = ''

            genres = parse_genre(page_url)
            comments = parse_comments(page_url)

            book={
                'title':title,
                'author': author,
                'img_src': img_src,
                'book_path' : book_path,
                'comments' : comments,
                'genres' : genres
            }
            print(book)
            books.append(book)

print(books)
with open(json_file, "w", encoding='utf8') as json_file:
    json.dump(books, json_file, ensure_ascii=False)
