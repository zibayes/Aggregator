import copy
import os
import re
import shutil
import ssl
import urllib.request
from pathlib import Path
import time
from time import sleep
from typing import List
from urllib.parse import quote

import pandas as pd
import patoolib
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from celery import shared_task
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from docx import Document
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from agregator.processing.account_cards_processing import connect_account_card_to_heritage
from agregator.processing.acts_processing import process_acts, error_handler_acts
from .files_saving import raw_reports_save
from agregator.models import User, Act, UserTasks, ArchaeologicalHeritageSite, IdentifiedArchaeologicalHeritageSite
from agregator.processing.utils import clean_path_component

logger = logging.getLogger(__name__)

session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=0.1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
session.mount("http://", adapter)
session.mount("https://", adapter)
document_cache = {}
download_lock = threading.Lock()

ORDER_TEXT_PATTERN = re.compile(r'\D+?(?= от )', re.IGNORECASE | re.MULTILINE)
ORDER_NUMBER_PATTERN = re.compile(r'№\s+\d+-*\d*', re.IGNORECASE | re.MULTILINE)
ORDER_DATE_PATTERN = re.compile(r'\d{2}\.\d{2}\.\d{4}', re.IGNORECASE | re.MULTILINE)
AKT_GIKE_PATTERN = re.compile(r'акт\s+гикэ', re.IGNORECASE | re.MULTILINE)


@shared_task(bind=True)
def external_sources_processing(self, start_date, end_date, select_text, select_image, select_coord):
    self.update_state(
        state='PROGRESS',
        meta={
            'current': 0,
            'total': 1,
            'type': 'page_progress',
            'message': 'Начинаем сканирование',
        }
    )

    ignore_ssl = False
    try:
        r = requests.get("https://ookn.ru/experts/")
    except requests.exceptions.SSLError:
        print(f"SSL Error, ignore certificate verification")
        r = requests.get(f"https://ookn.ru/experts/", verify=False)
        ignore_ssl = True
    data = r.text
    soup = BeautifulSoup(data, features="html.parser")

    pagination = soup.find('div', class_='news-list')
    if pagination:
        end_link = pagination.find('a', string='Конец')
        print('pagination: ' + str(pagination))
        print('end_link: ' + str(end_link))
        total_pages = str(end_link.get('href'))
        print('total_pages: ' + str(total_pages))
        total_pages = int(total_pages[total_pages.rfind('=') + 1:])
        print('total_pages: ' + str(total_pages))
    else:
        total_pages = 1

    page = 1
    pages = [str(page)]

    admin = User.objects.get(is_superuser=True)
    acts = Act.objects.filter(user_id=admin.id)
    downloaded_files = [y['origin_filename'] for x in acts if x.upload_source_dict is not None and
                        x.upload_source_dict['source'] != 'Пользовательский файл' for y in x.source_dict]
    # while str(page) in pages:
    while page <= total_pages:
        self.update_state(
            state='PROGRESS',
            meta={
                'current': page,
                'total': total_pages,
                'type': 'page_progress',
                'message': f'Обработка страницы {page} из {total_pages}'
            }
        )

        print(f"PAGE={page}")
        if ignore_ssl is False:
            r = requests.get(f"https://ookn.ru/experts/?PAGEN_1={page}")
        elif ignore_ssl is True:
            print(f"SSL Error, ignore certificate verification")
            r = requests.get(f"https://ookn.ru/experts/?PAGEN_1={page}", verify=False)
        data = r.text
        soup = BeautifulSoup(data, features="html.parser")
        new_files = []

        '''
        for root, dirs, files in os.walk('.'):
            for file in files:
                if file.lower().endswith('.pdf') or file.lower().endswith('.zip') or file.lower().endswith('.rar'):
                    downloaded_files.append(file)
        '''

        for item in soup.find_all('p', class_='news-item'):
            if start_date is not None and end_date is not None:
                title = item.find('b').get_text(strip=True) if item.find('b') else ''

                match = ORDER_DATE_PATTERN.search(title)
                if match:
                    date_str = match.group(0)
                    current_date = [int(x) for x in date_str.split('.')][::-1]
                    print('start_date+: ' + str(start_date))
                    print('current_date+: ' + str(current_date))
                    print('end_date+: ' + str(end_date))
                    print('start_date <= current_date <= end_date: ' + str(start_date <= current_date <= end_date))
                    if not (start_date <= current_date <= end_date):
                        continue
                else:
                    continue
            print('PROSHLO PROVERKUUU')

            link = item.find('a', href=True)
            if link and '/upload/iblock/' in link['href'] and (
                    'акт' in link['href'].lower() or 'гикэ' in link['href'].lower()):
                file = link['href'][link['href'].rfind('/') + 1:]
                href = link['href']

                if file in downloaded_files or file.endswith('.sig'):
                    continue

                file_encoded = file.replace(' ', '%20')
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
                    '''
                    context = ssl._create_unverified_context()
                    with urllib.request.urlopen(url, context=context) as response:
                        with open(path_to_download, 'wb') as out_file:
                            out_file.write(response.read())
                    '''
                    try:
                        response = requests.get(url, verify=False)
                        with open(path_to_download, 'wb') as out_file:
                            out_file.write(response.content)
                    except Exception:
                        print("Файл не найден")
                        file_not_found = True

                while file_not_found is False:
                    sleep(1.5)

                    folder = None
                    archive_files = []
                    if path_to_download.lower().endswith(('.zip', '.rar')):
                        folder = path_to_download[:path_to_download.rfind('.')]
                        Path(folder).mkdir(exist_ok=True)
                        try:
                            patoolib.extract_archive(path_to_download, outdir=folder)
                        except patoolib.util.PatoolError as e:
                            print(f'Ошибка при разархивировании: {e}')
                        for root, dirs, files in os.walk(os.getcwd() + '/' + folder):
                            for file in files:
                                if file.lower().endswith('.pdf') and not re.search(r'проверк[\s\S]+подпис[\S]+', file,
                                                                                   re.IGNORECASE):
                                    archive_files.append(os.path.join(root, file))

                    '''
                    try:
                        with fitz.open(path_to_download) as pdf_doc:
                            print('PAGES! ' + str(len(pdf_doc)))
                    '''

                    files_to_save = []
                    file_groups = {}
                    if archive_files:
                        file_groups['fully'] = []
                        types_convert = {'текст': 'text', 'приложение': 'images', 'иллюстрации': 'images'}
                        for file in archive_files:
                            filename = file.lower()
                            report_type = 'all'
                            for typename in types_convert.keys():
                                if typename in filename:
                                    index = filename.find(typename)
                                    if index >= 0:
                                        report_type = types_convert[typename]
                                        break
                            file_groups['fully'].append(
                                {'type': report_type, 'file': convert_file_to_uploaded_file(file)})
                    else:
                        files_to_save = [convert_file_to_uploaded_file(path_to_download)]
                    admin = User.objects.get(is_superuser=True)
                    upload_source = {'source': 'ООКН', 'link': url}
                    acts_ids = raw_reports_save(file_groups, files_to_save, Act, admin.id, True, upload_source)
                    if folder is not None:
                        shutil.rmtree(folder)
                    os.remove(path_to_download)
                    task = process_acts.apply_async((acts_ids, admin.id, select_text, select_image, select_coord),
                                                    link_error=error_handler_acts.s())
                    user_task = UserTasks(user_id=admin.id, task_id=task.task_id, files_type='act',
                                          upload_source=upload_source)
                    user_task.save()
                    break
                    # except Exception as e:
                    #     continue
        # external_storage_files_processing(new_files)
        page += 1
    return {
        'current': page,
        'total': total_pages,
        'type': 'page_progress',
        'message': 'Сканирование всех страниц завершено.'
    }


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


def extract_tables_from_docx(docx_file):
    doc = Document(docx_file)
    tables = []
    for table in doc.tables:
        data = []
        for row in table.rows:
            data.append([cell.text.strip() for cell in row.cells])
        tables.append(data)

    return tables


def tables_to_dataframes(tables):
    dataframes = []
    for table in tables:
        df = pd.DataFrame(table[1:], columns=table[0])
        dataframes.append(df)
    return dataframes


def external_voan_list_processing():
    try:
        r = requests.get(f"https://ookn.ru/gosohrana/", verify=False)
    except Exception as e:
        logger.debug(f"Ошибка полкючения к сайту ООКН: {e}")
        return
    data = r.text
    soup = BeautifulSoup(data, 'html.parser')
    current_lists = 'uploaded_files/Памятники/current_lists.txt'
    Path('uploaded_files/Памятники/').mkdir(exist_ok=True)

    with open(current_lists, 'a+', encoding='utf-8') as file:
        file.seek(0)
        text = file.read()
        lines = [line for line in text.split('\n') if line.strip()]
        file.seek(0)
        file.truncate()
        for line in lines:
            if 'list_voan - ' in line:
                line = line.replace('list_voan - ', '')
                if os.path.exists(line):
                    try:
                        os.remove(line)
                    except PermissionError as e:
                        logger.debug(f"Ошибка удаления перечня ВОАН: {e}")
                        return
            elif 'list_oan - ' in line:
                line = line.replace('list_oan - ', '')
                if os.path.exists(line):
                    try:
                        os.remove(line)
                    except PermissionError as e:
                        logger.debug(f"Ошибка удаления перечня ОАН: {e}")
                        return

    for item in soup.find_all('p', class_='news-item'):
        title = item.find('b').get_text(strip=True) if item.find('b') else ''
        if title not in (
                'Перечень объектов археологического наследия', 'Перечень выявленных объектов культурного наследия'):
            continue

        link = item.find('a', href=True)
        if link and '/upload/iblock/' in link['href']:
            file = link['href'][link['href'].rfind('/') + 1:]

            file_encoded = file.replace(' ', '%20')
            path_to_download = 'uploaded_files/Памятники/' + file_encoded

            logger.debug(f"Заголовок: {title}")
            logger.debug(f"Ссылка: {link['href']}")

            href = link['href'][:link['href'].rfind('/')]
            params = urllib.parse.urlencode({'address': file})
            href = (href + params).replace('address=', '/').replace('+', '%20').replace('%28', '(').replace('%29', ')')
            url = f"https://ookn.ru{href}"

            context = ssl._create_unverified_context()
            logger.debug(f'URLLL: {url}')
            logger.debug(context)
            try:
                urllib.request.urlopen(url, context=context)
            except urllib.error.URLError as e:
                logger.debug(f'Ошибка подключения: {e}')
                continue
            with urllib.request.urlopen(url, context=context) as response:
                with open(path_to_download, 'wb') as out_file:
                    out_file.write(response.read())

                with open(current_lists, 'a+', encoding='utf-8') as file:
                    if title == 'Перечень выявленных объектов культурного наследия':
                        file.write('list_voan - ' + path_to_download + '\n')
                    elif title == 'Перечень объектов археологического наследия':
                        file.write('list_oan - ' + path_to_download + '\n')
                tables = extract_tables_from_docx(path_to_download)
                dataframes = tables_to_dataframes(tables)
                for i, df in enumerate(dataframes):
                    # df = df.replace('\n', '', regex=True)
                    df.columns = df.columns.str.replace('\n', '', regex=True)
                    '''
                    print(f"Таблица {i + 1}:")
                    print(df)
                    print("\n")
                    '''

                    if title == 'Перечень выявленных объектов культурного наследия' and 'Адрес объекта (или описание местоположения объекта)*' in df.columns:
                        # df['Адрес объекта (или описание местоположения объекта)*'].str.contains('ВОАН', na=False)
                        existing_sites = IdentifiedArchaeologicalHeritageSite.objects.all()
                        existing_sites_set = set(
                            (site.name, site.address, site.obj_info, site.document) for site in existing_sites)
                        for index, row in df.iterrows():
                            logger.debug('Log-test:')
                            logger.debug(row)
                            logger.debug(row['Адрес объекта (или описание местоположения объекта)*'])
                            logger.debug(type(row['Адрес объекта (или описание местоположения объекта)*']))
                            address = row['Адрес объекта (или описание местоположения объекта)*']
                            if isinstance(address, str):
                                address = address.strip()
                            elif isinstance(address, pd.Series):
                                if len(address) > 1 and isinstance(address.iloc[1], str) and address.iloc[1].strip() != \
                                        row['Наименование выявленного объекта культурного наследия']:
                                    address = address.iloc[1].strip()
                                elif len(address) > 0 and isinstance(address.iloc[0], str) and address.iloc[
                                    0].strip() != row['Наименование выявленного объекта культурного наследия']:
                                    address = address.iloc[0].strip()
                                else:
                                    address = ''
                            logger.debug(f'Итоговый адрес: {address}')
                            document_source = []
                            identified_site = IdentifiedArchaeologicalHeritageSite(
                                name=row['Наименование выявленного объекта культурного наследия'],
                                address=address,
                                obj_info=row['Сведения об историко-культурной ценности объекта'],
                                document=row['Документ о включении в перечень выявленных объектов'],
                            )
                            if not IdentifiedArchaeologicalHeritageSite.objects.filter(
                                    name=identified_site.name,
                                    address=identified_site.address,
                                    obj_info=identified_site.obj_info,
                                    document=identified_site.document,
                            ).exists():
                                folder = 'uploaded_files/Памятники/ВОАН/' + address + '/' + clean_path_component(row[
                                                                                                                     'Наименование выявленного объекта культурного наследия'])
                                nested_folders = Path(folder)
                                nested_folders.mkdir(parents=True, exist_ok=True)
                                folder = str(nested_folders)
                                identified_site.source = folder
                                external_orders_download(identified_site.document, folder, document_source)
                                identified_site.document_source = document_source
                                identified_site.save()
                                connect_account_card_to_heritage(identified_site.name)
                            elif not identified_site.document_source_dict:
                                external_orders_download(identified_site.document, folder, document_source)
                                identified_site.document_source = document_source
                                identified_site.save()

                            for site in existing_sites:
                                if (site.name, site.address, site.obj_info, site.document) not in existing_sites_set:
                                    site.is_excluded = True
                                    site.save()

                    elif title == 'Перечень объектов археологического наследия':
                        for index, row in df.iterrows():
                            document_source = []
                            archaeological_site = ArchaeologicalHeritageSite.objects.filter(
                                doc_name=row[
                                    'Наименование объекта согласно документу о постановке на государственную охрану, датировка объекта'],
                                district=row['Район местонахождения'],
                                document=row['Документ о постановке на государственную охрану'],
                                register_num=row[
                                    'Регистрационный номер в едином государственном реестре объектов культурного наследия с реквизитами приказа Министерства культуры РФ о регистрации объекта, вид объекта (памятник, ансамбль)'],
                            )
                            if not archaeological_site.exists():
                                folder = 'uploaded_files/Памятники/ОАН/' + row[
                                    'Район местонахождения'] + '/' + clean_path_component(row[
                                                                                              'Наименование объекта согласно документу о постановке на государственную охрану, датировка объекта'])
                                nested_folders = Path(folder)
                                nested_folders.mkdir(parents=True, exist_ok=True)
                                folder = str(nested_folders)
                                archaeological_site = ArchaeologicalHeritageSite(
                                    doc_name=row[
                                        'Наименование объекта согласно документу о постановке на государственную охрану, датировка объекта'],
                                    district=row['Район местонахождения'],
                                    document=row['Документ о постановке на государственную охрану'],
                                    register_num=row[
                                        'Регистрационный номер в едином государственном реестре объектов культурного наследия с реквизитами приказа Министерства культуры РФ о регистрации объекта, вид объекта (памятник, ансамбль)'],
                                    source=folder,
                                )
                                external_orders_download(archaeological_site.document, folder, document_source)
                                archaeological_site.document_source = document_source
                                archaeological_site.save()
                                connect_account_card_to_heritage(archaeological_site.doc_name)
                            elif not archaeological_site[0].document_source_dict:
                                external_orders_download(archaeological_site.document, folder, document_source)
                                archaeological_site.document_source = document_source
                                archaeological_site.save()


def external_orders_download(query: str, output_path: str, document_source: List) -> None:
    if not query.strip():
        return

    cache_key = query.lower().strip()
    if cache_key in document_cache:
        document_source.extend(document_cache[cache_key])
        for doc in document_source:
            if os.path.isdir(output_path) and os.path.isfile(doc['path']):
                path_to_download = output_path + doc['path'][doc['path'].rfind('/'):]
                shutil.copy(doc['path'], path_to_download)
        return

    order_text = ORDER_TEXT_PATTERN.search(query)
    if order_text:
        order_text = order_text.group(0).strip().lower()
    order_number = ORDER_NUMBER_PATTERN.findall(query)
    order_number = [x.strip().replace(' ', '').replace('№', '').lower() for x in order_number]
    len_order_number = len(order_number)
    order_date = ORDER_DATE_PATTERN.findall(query)
    order_date = [x.strip().replace(' ', '').lower() for x in order_date]
    len_order_date = len(order_date)
    logger.debug(f'order_text: {order_text}')
    logger.debug(f'order_number: {order_number}')
    logger.debug(f'order_date: {order_date}')
    query_set = ([query] + [order_date[i] + ' ' + order_number[i] for i in range(len_order_date) if
                            i < len_order_number and i < len_order_date] +
                 [order_date[i] for i in range(len_order_date)] +
                 [order_number[i] for i in range(len_order_number)])
    downloaded_counter = 0

    for query_value in query_set:
        try:
            r = session.get(f"https://ookn.ru/docs/?section=&q={query_value}",
                            verify=False, timeout=30)
            r.raise_for_status()
        except Exception as e:
            logger.debug(f"Ошибка загрузки приказов: {e}")
            return
        data = r.text
        soup = BeautifulSoup(data, 'html.parser')  # Убедитесь, что указали парсер

        for item in soup.find_all('a', href=lambda href: href and "/docs/?ELEMENT_ID=" in href):
            # Извлекаем заголовок
            href_text = item.text.lower()
            title = item.find_next_sibling().get_text().lower() if item.find_next_sibling() else ''
            logger.debug(f'item.text: {item.text}')
            logger.debug(f'title: {title}')

            if order_text and order_text in query_value.lower() and order_text not in href_text and order_text not in title:
                continue
            if order_number and not any([number in href_text for number in order_number]) and not any(
                    [number in title for number in order_number]):
                continue
            if order_date and not any([number in href_text for number in order_date]) and not any(
                    [number in title for number in order_date]):
                continue
            if AKT_GIKE_PATTERN.search(href_text) or AKT_GIKE_PATTERN.search(title):
                continue

            try:
                doc_request = requests.get('https://ookn.ru' + item['href'], verify=False)
                doc_request.raise_for_status()
            except ConnectionError as e:
                logger.debug(f"Ошибка подключения к {item['href']}: {e}")
                continue
            except requests.HTTPError as e:
                logger.debug(f"HTTP ошибка: {e}")
                continue
            except Exception as e:
                logger.debug(f"Неизвестная ошибка подключения: {e}")
                continue

            doc_data = doc_request.text
            if doc_data:
                logger.debug(f'GOT DOC PAGE!')
            doc_soup = BeautifulSoup(doc_data, 'html.parser')
            download_tasks = []
            for doc_item in doc_soup.find_all('div', class_='docs_list'):
                link = doc_item.find('a', href=True)
                logger.debug(f'Link: {link}')
                if link and '/upload/iblock/' in link['href']:
                    logger.debug(f'NASHLI LINKU!: {link}')
                    file = link['href'][link['href'].rfind('/') + 1:]

                    logger.debug(f"Ссылка: {link['href']}")

                    href = link['href'][:link['href'].rfind('/')]
                    params = urllib.parse.urlencode({'address': file})
                    href = (href + params).replace('address=', '/').replace('+', '%20').replace('%28', '(').replace(
                        '%29',
                        ')')
                    url = f"https://ookn.ru{href}"

                    path_to_download = os.path.join(output_path, file)
                    if os.path.exists(path_to_download):
                        document_source.append({'path': path_to_download})
                        continue
                    download_tasks.append((url, path_to_download))

            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_url = {
                    executor.submit(download_file, url, path): (url, path)
                    for url, path in download_tasks
                }

                for future in as_completed(future_to_url):
                    url, path = future_to_url[future]
                    try:
                        if future.result():
                            with download_lock:
                                document_source.append({'path': path})
                                document_cache[cache_key] = copy.deepcopy(document_source)
                                downloaded_counter += 1
                    except Exception as e:
                        logger.debug(f"Ошибка при скачивании {url}: {e}")

        if downloaded_counter >= len_order_number and downloaded_counter >= len_order_date:
            break


def download_file(url, path_to_download):
    try:
        with session.get(url, verify=False, timeout=30) as response:
            response.raise_for_status()
            with open(path_to_download, 'wb') as out_file:
                out_file.write(response.content)
            return True
    except Exception as e:
        logger.debug(f"Ошибка скачивания {url}: {e}")
        return False
