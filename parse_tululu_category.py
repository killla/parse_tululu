import requests, os
from bs4 import BeautifulSoup
import pathlib

from pathvalidate import sanitize_filename
from urllib.parse import urljoin
import json
import argparse
import logging


def get_page(url):
    response = requests.get(url, allow_redirects=False)
    response.raise_for_status()
    result = None
    if response.status_code != 302:
        result = response
    return result


def parse_title_author(page):
    soup = BeautifulSoup(page.text, 'lxml')
    title_text = soup.select_one('h1').text
    title, author = [a.strip() for a in title_text.split('::')]
    return (title, author)


def parse_img(page):
    soup = BeautifulSoup(page.text, 'lxml')
    img_path = soup.select_one('.bookimage img')['src']
    return img_path


def parse_comments(page):
    soup = BeautifulSoup(page.text, 'lxml')
    comments_tag = soup.select('.texts .black')
    comments =[comment.text for comment in comments_tag]
    return(comments)


def parse_txt_url(page):
    txt_url = False
    soup = BeautifulSoup(page.text, 'lxml')
    urls = soup.select('.d_book a')
    for url in urls:
        if url.text == 'скачать txt':
            txt_url = url['href']
            break
    return txt_url


def parse_genre(page):
    soup = BeautifulSoup(page.text, 'lxml')
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
            book_urls.append(urljoin(base_url, book_link))
    return book_urls


def get_book(page, skip_imgs, skip_txt, img_folder, txt_folder):
    txt_url = parse_txt_url(page)
    book_path = None
    img_src = None
    if txt_url:
        title, author = parse_title_author(page)
        filename = f"{txt_url.split('=')[-1]} {title}.txt"
        txt_url = urljoin(base_url, txt_url)
        if (not skip_txt):
            book_path = download_txt(txt_url, filename, txt_folder)
        img_url = parse_img(page)
        img_path = img_url.split('/')[-1]
        img_url = urljoin(base_url, img_url)
        if (not skip_imgs):
            img_src = download_img(img_url, img_path, img_folder)

        book = {
            'title': title,
            'author': author,
            'img_src': img_src,
            'book_path': book_path,
            'comments': parse_comments(page),
            'genres': parse_genre(page)
        }
        return book
    else:
        return None


logging.basicConfig(level=logging.INFO)
base_url = 'http://tululu.org/'
category = 'l55/'
img_folder = 'images/'
txt_folder = 'books/'
json_file = 'books.json'


if __name__ =='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_page",  default=1, type=int,
                        help="номер страницы с которой начать скачивание")
    parser.add_argument("--end_page",  default=1000, type=int,
                        help="номер страницы, ДО которой закончить скачивание")
    parser.add_argument("--skip_imgs",  action='store_true',
                        help="не скачивать картинки")
    parser.add_argument("--skip_txt",  action='store_true',
                        help="не скачивать книги")
    parser.add_argument("--dest_folder",
                        help="путь к каталогу с результатами парсинга: картинкам, книгами, JSON")
    parser.add_argument("--json_path",
                        help="указать свой путь к *.json файлу с результатами")
    args = parser.parse_args()

    if args.dest_folder and os.path.isdir(args.dest_folder):
        img_folder = os.path.join(args.dest_folder, img_folder)
        txt_folder = os.path.join(args.dest_folder, txt_folder)
    if args.json_path:
        json_file = sanitize_filename(args.json_path)

    pathlib.Path(txt_folder).mkdir(parents=True, exist_ok=True)
    pathlib.Path(img_folder).mkdir(parents=True, exist_ok=True)

    books = []

    book_urls = get_book_url_from_pages(base_url, category, args.start_page, args.end_page)
    logging.info(f'Подготовлено {len(book_urls)} ссылок')

    for page_url in book_urls:
        page = get_page(page_url)
        if page:
            book = get_book(page, args.skip_imgs, args.skip_txt, img_folder, txt_folder)
            if book:
                logging.info(f"{page_url}, {book['title']}, {book['author']}")
                books.append(book)
            else:
                logging.info(f'{page_url} пропущено')

    with open(json_file, "w", encoding='utf8') as json_file:
        json.dump(books, json_file, ensure_ascii=False)
