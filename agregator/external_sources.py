import os
import urllib.request
from urllib.parse import quote
from bs4 import BeautifulSoup
import requests
from .acts_processing import external_storage_acts_processing
from celery import shared_task
from time import sleep
import fitz

@shared_task(bind=True)
def external_sources_processing(self):
    page = 1
    pages = [str(page)]
    while str(page) in pages:
        print(page)
        r = requests.get(f"https://ookn.ru/experts/?PAGEN_1={page}")
        data = r.text
        soup = BeautifulSoup(data, features="html.parser")
        downloaded_files = []
        new_files = []

        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.lower().endswith('.pdf') or file.lower().endswith('.zip') or file.lower().endswith('.rar'):
                    downloaded_files.append(file)


        for link in soup.find_all('a'):
            href = link.get('href')
            if '/experts/?PAGEN_1=' in href:
                page_num = href.replace('/experts/?PAGEN_1=', '')
                if page_num not in pages:
                    pages.append(page_num)
            if '/upload/iblock/' in href and 'акт' in href.lower() or 'гикэ' in href.lower():
                file = href[href.rfind('/')+1:]

                file_encoded = file.replace(' ', '%20')
                if file_encoded in downloaded_files:
                    continue
                else:
                    new_files.append(file_encoded)

                print(href)
                href = href[:href.rfind('/')]

                params = urllib.parse.urlencode({'address': file})
                href = (href + params).replace('address=', '/').replace('+', '%20').replace('%28', '(').replace('%29', ')')
                file_not_found = False

                try:
                    urllib.request.urlretrieve(f"https://ookn.ru{href}", 'uploaded_files/' + file_encoded)
                except Exception:
                    print("Файл не найден")
                    file_not_found = True

                while file_not_found is False:
                    sleep(1.5)
                    try:
                        with fitz.open('uploaded_files/' + file_encoded) as pdf_doc:
                            print('PAGES! ' + str(len(pdf_doc)))
                        external_storage_acts_processing([file_encoded])
                        break
                    except:
                        continue
        # external_storage_files_processing(new_files)
        page += 1