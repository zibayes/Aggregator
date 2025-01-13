import os
import ssl
import urllib.request
from urllib.parse import quote
from bs4 import BeautifulSoup
import requests
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile

from .acts_processing import external_storage_acts_processing, process_acts, error_handler_acts
from celery import shared_task
from time import sleep
import fitz

from .files_saving import raw_reports_save
from .models import User, Act, UserTasks


@shared_task(bind=True)
def external_sources_processing(self):
    page = 1
    pages = [str(page)]
    ignore_ssl = False
    while str(page) in pages:
        print(f"PAGE={page}")
        try:
            r = requests.get(f"https://ookn.ru/experts/?PAGEN_1={page}")
        except requests.exceptions.SSLError:
            print(f"SSL Error, ignore certificate verification")
            r = requests.get(f"https://ookn.ru/experts/?PAGEN_1={page}", verify=False)
            ignore_ssl = True
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
                file = href[href.rfind('/') + 1:]

                file_encoded = file.replace(' ', '%20')
                if file_encoded in downloaded_files:
                    continue
                else:
                    new_files.append(file_encoded)

                print(href)
                href = href[:href.rfind('/')]

                params = urllib.parse.urlencode({'address': file})
                href = (href + params).replace('address=', '/').replace('+', '%20').replace('%28', '(').replace('%29',
                                                                                                                ')')
                url = f"https://ookn.ru{href}"
                path_to_download = 'uploaded_files/acts/' + file_encoded

                file_not_found = False

                if ignore_ssl is False:
                    try:
                        urllib.request.urlretrieve(url, path_to_download)
                    except Exception:
                        print("Файл не найден")
                        file_not_found = True
                else:
                    context = ssl._create_unverified_context()
                    with urllib.request.urlopen(url, context=context) as response:
                        with open(path_to_download, 'wb') as out_file:
                            out_file.write(response.read())

                while file_not_found is False:
                    sleep(1.5)
                    # try:
                    with fitz.open(path_to_download) as pdf_doc:
                        print('PAGES! ' + str(len(pdf_doc)))
                    file_to_save = convert_file_to_uploaded_file(path_to_download)
                    admin = User.objects.get(is_superuser=True)
                    upload_source = {'source': 'ООКН', 'link': url}
                    acts_ids, origin_filenames = raw_reports_save({}, [file_to_save], Act, admin.id, upload_source)
                    task = process_acts.apply_async((acts_ids, origin_filenames, admin.id),
                                                    link_error=error_handler_acts.s())
                    user_task = UserTasks(user_id=admin.id, task_id=task.task_id, files_type='act',
                                          upload_source=upload_source)
                    user_task.save()
                    external_storage_acts_processing([file_encoded])
                    break
                    # except Exception as e:
                    #     continue
        # external_storage_files_processing(new_files)
        page += 1


def convert_file_to_uploaded_file(file_path):
    with open(file_path, 'rb') as f:
        file_content = f.read()
        file_name = os.path.basename(file_path)
        content_file = ContentFile(file_content, name=file_name)
        uploaded_file = InMemoryUploadedFile(
            file=content_file,
            field_name=None,
            name=file_name,
            content_type='application/octet-stream',
            size=len(file_content),
            charset=None
        )
    return uploaded_file
