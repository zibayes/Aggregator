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
from django.core.cache import cache

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

ACTS_QUERY_EXCLUDE = [
    'архитектурно-художественного',
    'проекта изменений зон охраны',
    'Проекта зон охраны объекта',
    'выполнение работ по оценке технического состояния',
]


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

    # Получаем данные один раз
    admin = User.objects.get(is_superuser=True)

    # Создаем множество для быстрого поиска
    downloaded_files = get_downloaded_files_cache(admin.id)

    # Определяем игнорирование SSL с использованием сессии
    ignore_ssl = False
    try:
        response = session.get("https://ookn.ru/experts/", timeout=30)
        response.raise_for_status()
    except requests.exceptions.SSLError:
        logger.warning("SSL Error, ignore certificate verification")
        ignore_ssl = True
        # Для SSL ошибок создаем отдельную сессию без верификации
        ssl_session = requests.Session()
        ssl_session.verify = False
        response = ssl_session.get("https://ookn.ru/experts/", timeout=30)
    except requests.RequestException as e:
        logger.error(f"Ошибка при подключении: {e}")
        return {
            'current': 0,
            'total': 1,
            'type': 'page_progress',
            'message': f'Ошибка подключения: {e}'
        }

    # Получаем общее количество страниц
    soup = BeautifulSoup(response.text, features="html.parser")
    total_pages = 1

    pagination = soup.find('div', class_='news-list')
    if pagination:
        end_link = pagination.find('a', string='Конец')
        if end_link:
            total_pages_href = end_link.get('href', '')
            if total_pages_href:
                try:
                    total_pages = int(total_pages_href[total_pages_href.rfind('=') + 1:])
                except (ValueError, IndexError):
                    logger.warning(f"Не удалось распарсить количество страниц: {total_pages_href}")

    # Используем правильную сессию в зависимости от SSL
    current_session = ssl_session if ignore_ssl else session

    for page in range(1, total_pages + 1):
        self.update_state(
            state='PROGRESS',
            meta={
                'current': page,
                'total': total_pages,
                'type': 'page_progress',
                'message': f'Обработка страницы {page} из {total_pages}'
            }
        )

        logger.info(f"Обработка страницы {page}")

        try:
            response = current_session.get(
                f"https://ookn.ru/experts/?PAGEN_1={page}",
                timeout=30
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Ошибка при получении страницы {page}: {e}")
            continue

        soup = BeautifulSoup(response.text, features="html.parser")
        page_files = []

        future_to_file = {}
        # Обрабатываем элементы страницы
        for item in soup.find_all('p', class_='news-item'):
            try:
                # Проверка исключений
                if any(query in item.text for query in ACTS_QUERY_EXCLUDE):
                    continue

                # Проверка даты
                if start_date and end_date:
                    match = ORDER_DATE_PATTERN.search(item.text)
                    if not match:
                        continue

                    date_str = match.group(0)
                    try:
                        day, month, year = map(int, date_str.split('.'))
                        current_date = [year, month, day]
                        if not (start_date <= current_date <= end_date):
                            continue
                    except (ValueError, IndexError):
                        continue

                # Поиск ссылки
                link = item.find('a', href=True)
                if not link or '/upload/iblock/' not in link['href']:
                    continue

                if not ('акт' in link['href'].lower() or 'гикэ' in link['href'].lower()):
                    continue

                file = link['href'][link['href'].rfind('/') + 1:]

                # Пропускаем уже скачанные или ненужные файлы
                if (file in downloaded_files or
                        file.endswith(('.sig', '.png', '.jpg', '.bmp', '.tiff'))):
                    continue

                # Формируем URL
                href = link['href'][:link['href'].rfind('/')]
                params = urllib.parse.urlencode({'address': file})
                url = (href + params).replace('address=', '/').replace('+', '%20').replace('%28', '(').replace(
                    '%29',
                    ')')
                url = f"https://ookn.ru{url}"

                # Добавление файла в очередь
                path_to_download = f'uploaded_files/Акты ГИКЭ/{file}'
                page_files.append((path_to_download, url, file))

            except Exception as e:
                logger.error(f"Ошибка при обработке элемента: {e}")
                continue

        # Параллельное скачивание файлов с одной страницы
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_file = {
                executor.submit(download_file, url, path): (path, url, file)
                for path, url, file in page_files
            }

            page_files = []
            for future in as_completed(future_to_file):
                path, url, file = future_to_file[future]
                if future.result():
                    page_files.append((path, url, file))

        # Обрабатываем скачанные файлы
        process_downloaded_files(page_files, admin, select_text, select_image, select_coord)

    return {
        'current': page,
        'total': total_pages,
        'type': 'page_progress',
        'message': 'Сканирование всех страниц завершено.'
    }


def get_downloaded_files_cache(admin_id):
    cache_key = f'downloaded_files_{admin_id}'
    downloaded_files = cache.get(cache_key)

    if downloaded_files is None:
        acts = Act.objects.filter(user_id=admin_id)
        downloaded_files = set()
        for act in acts:
            if act.upload_source_dict and act.upload_source_dict['source'] != 'Пользовательский файл':
                for source in act.source_dict:
                    if 'origin_filename' in source:
                        downloaded_files.add(source['origin_filename'])
        cache.set(cache_key, downloaded_files, timeout=3600)  # 1 час

    return downloaded_files


def process_downloaded_files(files_data, admin, select_text, select_image, select_coord):
    """Обрабатывает скачанные файлы с использованием ThreadPoolExecutor для архивов"""
    for path_to_download, url, original_filename in files_data:
        try:
            archive_files = []
            folder = None

            if path_to_download.lower().endswith(('.zip', '.rar')):
                folder = path_to_download[:path_to_download.rfind('.')]
                os.makedirs(folder, exist_ok=True)

                try:
                    patoolib.extract_archive(path_to_download, outdir=folder)

                    # Используем ThreadPool для поиска файлов в архиве
                    with ThreadPoolExecutor(max_workers=5) as executor:
                        future_to_file = {
                            executor.submit(find_pdf_files, root, files): (root, files)
                            for root, dirs, files in os.walk(folder)
                        }

                        for future in as_completed(future_to_file):
                            root, files = future_to_file[future]
                            try:
                                pdf_files = future.result()
                                archive_files.extend(pdf_files)
                            except Exception as e:
                                logger.error(f"Ошибка при поиске PDF в {root}: {e}")

                except patoolib.util.PatoolError as e:
                    logger.error(f'Ошибка при разархивировании {path_to_download}: {e}')
                    continue

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

        except Exception as e:
            logger.error(f"Ошибка при обработке файла {path_to_download}: {e}")
            continue


def find_pdf_files(root, files):
    """Вспомогательная функция для поиска PDF файлов"""
    pdf_files = []
    for file in files:
        if (file.lower().endswith('.pdf') and
                not re.search(r'проверк[\s\S]+подпис[\S]+', file, re.IGNORECASE)):
            pdf_files.append(os.path.join(root, file))
    return pdf_files


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


@shared_task(bind=True)
def process_voan_list(self, progress_key=None):
    """Обработка перечня выявленных объектов культурного наследия"""
    try:
        # Шаг 1: Получение данных с сайта
        try:
            r = requests.get("https://ookn.ru/gosohrana/", verify=False, timeout=30)
            r.raise_for_status()
        except Exception as e:
            logger.error(f"Ошибка подключения к сайту ООКН: {e}")
            return {
                'current': 0,
                'total': 1,
                'type': 'page_progress',
                'message': f'Ошибка подключения к сайту ООКН: {e}'
            }

        # Шаг 2: Парсинг
        soup = BeautifulSoup(r.text, 'html.parser')
        current_lists = 'uploaded_files/Памятники/current_lists.txt'
        Path('uploaded_files/Памятники/').mkdir(exist_ok=True)

        # Шаг 3: Очистка старых файлов

        _clean_old_files(current_lists, 'list_voan')

        # Шаг 4: Поиск и скачивание файла
        file_path = None
        for item in soup.find_all('p', class_='news-item'):
            title = item.find('b').get_text(strip=True) if item.find('b') else ''
            if title != 'Перечень выявленных объектов культурного наследия':
                continue

            link = item.find('a', href=True)
            if link and '/upload/iblock/' in link['href']:
                file_path = _download_file(link['href'], title, current_lists)
                break

        if not file_path:
            logger.error("Файл перечня ВОАН не найден")
            return {
                'current': 0,
                'total': 1,
                'type': 'page_progress',
                'message': f'Файл перечня ВОАН не найден'
            }

        # Шаг 5: Извлечение таблиц
        tables = extract_tables_from_docx(file_path)
        dataframes = tables_to_dataframes(tables)

        # Шаг 6: Обработка данных
        existing_sites = IdentifiedArchaeologicalHeritageSite.objects.all()
        existing_sites_set = set(
            (site.name, site.address, site.obj_info, site.document) for site in existing_sites
        )

        processed = 0
        total_rows = sum(len(df) for df in dataframes)

        for i, df in enumerate(dataframes):
            df.columns = df.columns.str.replace('\n', '', regex=True)

            if 'Адрес объекта (или описание местоположения объекта)*' not in df.columns:
                continue

            for index, row in df.iterrows():
                # Обработка каждой строки
                _process_voan_row(row, existing_sites_set)

                processed += 1
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': processed,
                        'total': total_rows,
                        'type': 'page_progress',
                        'message': f'Обработка памятника {processed} из {total_rows}'
                    }
                )

        # Шаг 7: Помечаем удаленные объекты
        for site in existing_sites:
            if (site.name, site.address, site.obj_info, site.document) not in existing_sites_set:
                site.is_excluded = True
                site.save()

        return {
            'current': processed,
            'total': total_rows,
            'type': 'page_progress',
            'message': 'Сканирование всех страниц завершено.'
        }

    except Exception as e:
        logger.exception("Ошибка в процессе обработки ВОАН")
        return {
            'current': 0,
            'total': 1,
            'type': 'page_progress',
            'message': f'Ошибка в процессе обработки ВОАН: {e}'
        }


@shared_task(bind=True)
def process_oan_list(self, progress_key=None):
    """Обработка перечня объектов археологического наследия"""
    try:
        # Шаг 1: Получение данных с сайта
        try:
            r = requests.get("https://ookn.ru/gosohrana/", verify=False, timeout=30)
            r.raise_for_status()
        except Exception as e:
            logger.error(f"Ошибка подключения к сайту ООКН для ОАН: {e}")
            return {
                'current': 0,
                'total': 1,
                'type': 'page_progress',
                'message': f'Ошибка подключения к сайту ООКН: {e}'
            }

        # Шаг 2: Парсинг HTML
        soup = BeautifulSoup(r.text, 'html.parser')
        current_lists = 'uploaded_files/Памятники/current_lists.txt'
        Path('uploaded_files/Памятники/').mkdir(exist_ok=True)

        # Шаг 3: Очистка старых файлов ОАН
        _clean_old_files(current_lists, 'list_oan')

        # Шаг 4: Поиск и скачивание файла перечня ОАН
        file_path = None
        for item in soup.find_all('p', class_='news-item'):
            title = item.find('b').get_text(strip=True) if item.find('b') else ''
            if title != 'Перечень объектов археологического наследия':
                continue

            link = item.find('a', href=True)
            if link and '/upload/iblock/' in link['href']:
                file_path = _download_file(link['href'], title, current_lists)
                break

        if not file_path:
            logger.error("Файл перечня ОАН не найден")
            return {
                'current': 0,
                'total': 1,
                'type': 'page_progress',
                'message': f'Файл перечня ОАН не найден'
            }

        # Шаг 5: Извлечение таблиц из документа
        tables = extract_tables_from_docx(file_path)
        dataframes = tables_to_dataframes(tables)

        if not dataframes:
            logger.error("Не удалось извлечь таблицы из файла ОАН")
            return {
                'current': 0,
                'total': 1,
                'type': 'page_progress',
                'message': f'Не удалось извлечь таблицы из файла ОАН'
            }

        # Шаг 6: Обработка данных ОАН
        # Получаем существующие объекты для сравнения
        existing_sites = ArchaeologicalHeritageSite.objects.all()
        existing_sites_set = set(
            (site.doc_name, site.district, site.document, site.register_num)
            for site in existing_sites
        )

        processed = 0
        total_rows = sum(len(df) for df in dataframes)

        # Шаг 7: Обработка каждой таблицы и строки
        for i, df in enumerate(dataframes):
            # Очищаем названия колонок от переносов строк
            df.columns = df.columns.str.replace('\n', '', regex=True)

            # Проверяем наличие необходимых колонок
            required_columns = [
                'Наименование объекта согласно документу о постановке на государственную охрану, датировка объекта',
                'Район местонахождения',
                'Документ о постановке на государственную охрану',
                'Регистрационный номер в едином государственном реестре объектов культурного наследия с реквизитами приказа Министерства культуры РФ о регистрации объекта, вид объекта (памятник, ансамбль)'
            ]

            if not all(col in df.columns for col in required_columns):
                logger.warning(f"Таблица {i + 1} не содержит всех необходимых колонок для ОАН")
                continue

            # Обрабатываем каждую строку в таблице
            for index, row in df.iterrows():
                try:
                    # Обработка одной строки данных ОАН
                    document_source = []

                    # Создаем или получаем объект археологического наследия
                    archaeological_site, created = ArchaeologicalHeritageSite.objects.get_or_create(
                        doc_name=row[
                            'Наименование объекта согласно документу о постановке на государственную охрану, датировка объекта'],
                        district=row['Район местонахождения'],
                        document=row['Документ о постановке на государственную охрану'],
                        register_num=row[
                            'Регистрационный номер в едином государственном реестре объектов культурного наследия с реквизитами приказа Министерства культуры РФ о регистрации объекта, вид объекта (памятник, ансамбль)'],
                        defaults={
                            'source': ''
                        }
                    )

                    # Если объект создан впервые, создаем папку и скачиваем документы
                    if created:
                        folder = f'uploaded_files/Памятники/ОАН/{row["Район местонахождения"]}/{clean_path_component(row["Наименование объекта согласно документу о постановке на государственную охрану, датировка объекта"])}'
                        nested_folders = Path(folder)
                        nested_folders.mkdir(parents=True, exist_ok=True)

                        archaeological_site.source = str(nested_folders)
                        external_orders_download(archaeological_site.document, archaeological_site.source,
                                                 document_source)
                        archaeological_site.document_source = document_source
                        archaeological_site.save()

                        # Связываем с учетной карточкой
                        connect_account_card_to_heritage(archaeological_site.doc_name)

                    # Если объект уже существовал, но нет документов - скачиваем
                    elif not archaeological_site.document_source_dict:
                        external_orders_download(archaeological_site.document, archaeological_site.source,
                                                 document_source)
                        archaeological_site.document_source = document_source
                        archaeological_site.save()

                    # Удаляем из множества для последующего определения удаленных объектов
                    site_key = (
                        archaeological_site.doc_name,
                        archaeological_site.district,
                        archaeological_site.document,
                        archaeological_site.register_num
                    )
                    if site_key in existing_sites_set:
                        existing_sites_set.remove(site_key)

                except Exception as row_error:
                    logger.error(f"Ошибка обработки строки {index} в таблице {i + 1}: {row_error}")
                    continue

                # Обновляем прогресс
                processed += 1
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'current': processed,
                        'total': total_rows,
                        'type': 'page_progress',
                        'message': f'Обработка памятника {processed} из {total_rows}'
                    }
                )

        # Шаг 8: Помечаем удаленные объекты ОАН
        marked_excluded = 0
        for site in existing_sites:
            site_key = (site.doc_name, site.district, site.document, site.register_num)
            if site_key in existing_sites_set:
                site.is_excluded = True
                site.save()
                marked_excluded += 1

        logger.info(f"Помечено как исключенных: {marked_excluded} объектов ОАН")

        # Шаг 9: Финализация
        logger.info(f"Обработка перечня ОАН завершена успешно. Обработано: {processed} объектов")
        return {
            'current': processed,
            'total': total_rows,
            'type': 'page_progress',
            'message': 'Обработка всех ОАН завершена.'
        }

    except Exception as e:
        logger.exception("Ошибка в процессе обработки ОАН")
        return {
            'current': 0,
            'total': 1,
            'type': 'page_progress',
            'message': f'Ошибка в процессе обработки ОАН: {e}'
        }


# Вспомогательная функция для обработки строк ОАН (может быть вынесена отдельно)
def _process_oan_row(row, existing_sites_set):
    """Обработка одной строки данных объектов археологического наследия"""
    try:
        document_source = []

        # Поиск существующего объекта или создание нового
        archaeological_site, created = ArchaeologicalHeritageSite.objects.get_or_create(
            doc_name=row[
                'Наименование объекта согласно документу о постановке на государственную охрану, датировка объекта'],
            district=row['Район местонахождения'],
            document=row['Документ о постановке на государственную охрану'],
            register_num=row[
                'Регистрационный номер в едином государственном реестре объектов культурного наследия с реквизитами приказа Министерства культуры РФ о регистрации объекта, вид объекта (памятник, ансамбль)'],
            defaults={
                'source': ''
            }
        )

        # Если объект новый - создаем структуру папок и скачиваем документы
        if created:
            folder = f'uploaded_files/Памятники/ОАН/{row["Район местонахождения"]}/{clean_path_component(row["Наименование объекта согласно документу о постановке на государственную охрану, датировка объекта"])}'
            nested_folders = Path(folder)
            nested_folders.mkdir(parents=True, exist_ok=True)

            archaeological_site.source = str(nested_folders)
            external_orders_download(archaeological_site.document, archaeological_site.source, document_source)
            archaeological_site.document_source = document_source
            archaeological_site.save()

            # Связываем с учетной карточкой
            connect_account_card_to_heritage(archaeological_site.doc_name)

        # Если объект уже существует, но нет документов - скачиваем
        elif not archaeological_site.document_source_dict:
            external_orders_download(archaeological_site.document, archaeological_site.source, document_source)
            archaeological_site.document_source = document_source
            archaeological_site.save()

        # Удаляем из множества для определения удаленных объектов
        site_key = (
            archaeological_site.doc_name,
            archaeological_site.district,
            archaeological_site.document,
            archaeological_site.register_num
        )
        if site_key in existing_sites_set:
            existing_sites_set.remove(site_key)

        return True

    except Exception as e:
        logger.error(f"Ошибка обработки строки ОАН: {e}")
        return False


def _clean_old_files(current_lists, prefix):
    """Очистка старых файлов"""
    try:
        with open(current_lists, 'a+', encoding='utf-8') as file:
            file.seek(0)
            text = file.read()
            lines = [line for line in text.split('\n') if line.strip()]
            file.seek(0)
            file.truncate()

            for line in lines:
                if f'{prefix} - ' in line:
                    file_path = line.replace(f'{prefix} - ', '')
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except PermissionError as e:
                            logger.warning(f"Не удалось удалить файл {file_path}: {e}")
                else:
                    file.write(line + '\n')

    except Exception as e:
        logger.error(f"Ошибка при очистке файлов: {e}")


def _download_file(href, title, current_lists):
    """Скачивание файла"""
    file_name = href[href.rfind('/') + 1:]
    file_encoded = file_name.replace(' ', '%20')
    path_to_download = f'uploaded_files/Памятники/{file_encoded}'

    # Формирование URL для скачивания
    base_href = href[:href.rfind('/')]
    params = urllib.parse.urlencode({'address': file_name})
    download_url = f"https://ookn.ru{(base_href + params).replace('address=', '/').replace('+', '%20').replace('%28', '(').replace('%29', ')')}"

    # Скачивание
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(download_url, context=context) as response:
        with open(path_to_download, 'wb') as out_file:
            out_file.write(response.read())

    # Запись в current_lists
    with open(current_lists, 'a', encoding='utf-8') as file:
        if title == 'Перечень выявленных объектов культурного наследия':
            file.write(f'list_voan - {path_to_download}\n')
        elif title == 'Перечень объектов археологического наследия':
            file.write(f'list_oan - {path_to_download}\n')

    return path_to_download


def _process_voan_row(row, existing_sites_set):
    """Обработка одной строки данных ВОАН"""
    address = row['Адрес объекта (или описание местоположения объекта)*']
    if isinstance(address, str):
        address = address.strip()
    elif isinstance(address, pd.Series):
        if len(address) > 1 and isinstance(address.iloc[1], str) and address.iloc[1].strip() != row[
            'Наименование выявленного объекта культурного наследия']:
            address = address.iloc[1].strip()
        elif len(address) > 0 and isinstance(address.iloc[0], str) and address.iloc[0].strip() != row[
            'Наименование выявленного объекта культурного наследия']:
            address = address.iloc[0].strip()
        else:
            address = ''

    document_source = []
    identified_site = IdentifiedArchaeologicalHeritageSite(
        name=row['Наименование выявленного объекта культурного наследия'],
        address=address,
        obj_info=row['Сведения об историко-культурной ценности объекта'],
        document=row['Документ о включении в перечень выявленных объектов'],
    )

    # Проверяем существование
    site_exists = IdentifiedArchaeologicalHeritageSite.objects.filter(
        name=identified_site.name,
        address=identified_site.address,
        obj_info=identified_site.obj_info,
        document=identified_site.document,
    ).exists()

    if not site_exists:
        folder = f'uploaded_files/Памятники/ВОАН/{address}/{clean_path_component(row["Наименование выявленного объекта культурного наследия"])}'
        Path(folder).mkdir(parents=True, exist_ok=True)

        identified_site.source = folder
        external_orders_download(identified_site.document, folder, document_source)
        identified_site.document_source = document_source
        identified_site.save()
        connect_account_card_to_heritage(identified_site.name)
    else:
        # Обновляем существующий
        existing_site = IdentifiedArchaeologicalHeritageSite.objects.get(
            name=identified_site.name,
            address=identified_site.address,
            obj_info=identified_site.obj_info,
            document=identified_site.document,
        )
        if not existing_site.document_source_dict:
            external_orders_download(existing_site.document, existing_site.source, document_source)
            existing_site.document_source = document_source
            existing_site.save()

    # Удаляем из множества для последующего определения удаленных
    site_key = (identified_site.name, identified_site.address, identified_site.obj_info, identified_site.document)
    if site_key in existing_sites_set:
        existing_sites_set.remove(site_key)


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
