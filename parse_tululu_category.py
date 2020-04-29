import requests, os, sys
from bs4 import BeautifulSoup
import pathlib

from pathvalidate import sanitize_filename
from urllib.parse import urljoin
from time import sleep
import json
import argparse
import logging

logger = logging.getLogger('logger')

def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

def get_page(url):
    response = requests.get(url, allow_redirects=False)
    response.raise_for_status()
    result = None
    if response.status_code != 302:
        result = response
    return result


def get_title_author(soup):
    title_text = soup.select_one('h1').text
    title, author = [a.strip() for a in title_text.split('::')]
    return (title, author)


def parse_img(soup):
    img_path = soup.select_one('.bookimage img')['src']
    return img_path


def parse_comments(soup):
    comments_tag = soup.select('.texts .black')
    comments =[comment.text for comment in comments_tag]
    return(comments)


def get_txt_url(soup):
    urls = soup.select('.d_book a')
    for url in urls:
        if url.text == 'скачать txt':
            return url['href']


def parse_genre(soup):
    genres_tags = soup.select('span.d_book a')
    genres = [genre.text for genre in genres_tags]
    return genres


def download_txt(url, filename, folder='books'):
    response = requests.get(url, allow_redirects=False)
    response.raise_for_status()
    filename = os.path.join(folder, sanitize_filename(filename))
    with open(filename, 'w') as file:
        file.write(response.text)
    return filename


def download_img(url, filename, folder='images'):
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
        if response.status_code == 301: #условие означает достижение несуществующей (после последней) страницы в пагинаторе
            return book_urls
        soup = BeautifulSoup(response.text, 'lxml')
        books = soup.select('.d_book')
        for book in books:
            book_link = book.find('a')['href']
            book_urls.append(urljoin(base_url, book_link))
    return book_urls


def get_book(page, skip_imgs, skip_txt, img_folder, txt_folder):
    soup = BeautifulSoup(page.text, 'lxml')
    txt_url = get_txt_url(soup)
    book_path = None
    img_src = None
    if txt_url:
        title, author = get_title_author(soup)
        id = txt_url.split('=')[-1]
        filename = f'{id} {title}.txt'
        txt_url = urljoin(base_url, txt_url)
        if not skip_txt:
            book_path = download_txt(txt_url, filename, txt_folder)
        img_url = parse_img(soup)
        img_filename = img_url.split('/')[-1]
        img_filename = f'{id} {img_filename}'
        img_url = urljoin(base_url, img_url)
        if not skip_imgs:
            img_src = download_img(img_url, img_filename, img_folder)

        book = {
            'title': title,
            'author': author,
            'img_src': img_src,
            'book_path': book_path,
            'comments': parse_comments(soup),
            'genres': parse_genre(soup)
        }
        return book
    else:
        return None


logging.basicConfig(level=logging.INFO)
base_url = 'http://tululu.org/'
category = 'l55/'
img_subfolder = 'images'
txt_subfolder = 'books'
timeout = 10

if __name__ =='__main__':
    logger.setLevel(logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--start_page",  default=1, type=int,
                        help="номер страницы с которой начать скачивание")
    parser.add_argument("--end_page",  default=2, type=int,
                        help="номер страницы, ДО которой закончить скачивание")
    parser.add_argument("--skip_imgs",  action='store_true',
                        help="не скачивать картинки")
    parser.add_argument("--skip_txt",  action='store_true',
                        help="не скачивать книги")
    parser.add_argument("--dest_folder", default=os.path.abspath(os.curdir),
                        help="путь к каталогу с результатами парсинга: картинкам, книгами, JSON")
    parser.add_argument("--json_path", default='books.json',
                        help="указать свой путь к *.json файлу с результатами")
    args = parser.parse_args()

    img_folder = os.path.join(args.dest_folder, img_subfolder)
    txt_folder = os.path.join(args.dest_folder, txt_subfolder)
    if args.json_path:
        json_file = sanitize_filename(args.json_path)

    pathlib.Path(txt_folder).mkdir(parents=True, exist_ok=True)
    pathlib.Path(img_folder).mkdir(parents=True, exist_ok=True)

    books = []
    book_urls = get_book_url_from_pages(base_url, category, args.start_page, args.end_page)
    logger.info(f'Подготовлено {len(book_urls)} ссылок')

    for page_url in book_urls:
        local_timeout = timeout
        while local_timeout < 100:
            try:
                page = get_page(page_url)
                if not page:
                    break
                book = get_book(page, args.skip_imgs, args.skip_txt, img_folder, txt_folder)
                if not book:
                    logger.info(f'{page_url} книги нет на сайте')
                    break
                logger.info(f"{page_url}, {book['title']}, {book['author']}")
                books.append(book)
            except requests.HTTPError:
                eprint('HTTPError. Соединение потеряно')
                local_timeout += 10
                sleep(local_timeout)
            except ConnectionError:
                eprint('Соединение потеряно')
                local_timeout += 10
                sleep(local_timeout)
            finally:
                break


    with open(json_file, "w", encoding='utf8') as json_file:
        json.dump(books, json_file, ensure_ascii=False)
