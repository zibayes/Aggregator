import copy
import os
import random
import re
import shutil
import ssl
import traceback
import urllib.request
from pathlib import Path
import time
from time import sleep
from datetime import datetime
from typing import List
from urllib.parse import quote

import pandas as pd

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
from rapidfuzz import fuzz

from agregator.processing.account_cards_processing import connect_account_card_to_heritage
from agregator.processing.acts_processing import process_acts
from agregator.processing.error_handler import error_handler
from .batch_kml_utils import KMLParser
from .files_saving import raw_reports_save
from agregator.models import User, Act, UserTasks, ArchaeologicalHeritageSite, IdentifiedArchaeologicalHeritageSite, \
    DocumentFile, ObjectAccountCard
from agregator.processing.utils import clean_path_component, get_file_size
from agregator.processing.hash_utils import calculate_file_hash
from agregator.processing.external_acts_download_report import generate_download_report, generate_interrupted_report, \
    generate_final_report, generate_intermediate_report, handle_interrupts
from agregator.processing.utils import get_unique_filename
from agregator.processing.archive_utils import unzip_rar, unzip_7z, unzip_zip, untar_tgz
from agregator.processing.hash_utils import has_duplicates_in_db
from agregator.views.utils import get_heritage_list_path
from archeology.settings import HERITAGES_LISTS_PATH

logger = logging.getLogger(__name__)

session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=0.5,
    status_forcelist=[500, 502, 503, 504],  # 429
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
session.mount("http://", adapter)
session.mount("https://", adapter)
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (email: 4y6y7q3v5bbt@mail.ru)'
})
document_cache = {}
download_lock = threading.Lock()
MAX_WORKERS = 5

ORDER_TEXT_PATTERN = re.compile(r'\D+?(?= от )', re.IGNORECASE | re.MULTILINE)
ORDER_NUMBER_PATTERN = re.compile(r'№\s+\d+-*\d*', re.IGNORECASE | re.MULTILINE)
ORDER_DATE_PATTERN = re.compile(r'\d{2}\.\d{2}\.\d{4}', re.IGNORECASE | re.MULTILINE)
AKT_GIKE_PATTERN = re.compile(r'акт|гикэ', re.IGNORECASE | re.MULTILINE)  # r'акт\s+гикэ'

ACTS_QUERY_EXCLUDE = [
    'архитектурно-художественного',
    'проекта изменений зон охраны',
    'Проекта зон охраны объекта',
    'выполнение работ по оценке технического состояния',
]

OAN_REQUIRED_COLUMNS = {
    'name': 'Наименование объекта согласно документу о постановке на государственную охрану, датировка объекта',
    'place': 'Район местонахождения/местонахождение',
    'doc': 'Документ о постановке на государственную охрану',
    'number': 'Регистрационный номер в едином государственном реестре объектов культурного наследия с реквизитами приказа Министерства культуры РФ о регистрации объекта, вид объекта (памятник, ансамбль)'
}
VOAN_REQUIRED_COLUMNS = {
    'name': 'Наименование выявленного объекта культурного наследия',
    'address': 'Адрес объекта (или описание местоположения объекта)*',
    'obj_info': 'Сведения об историко-культурной ценности объекта',
    'doc': 'Документ о включении в перечень выявленных объектов'
}

ACTS_SAVING_PATH = Path('uploaded_files/Акты ГИКЭ/ООКН/')

OAN_DISTRICT_MAPPING = {
    'Абанский': 'Абанский район',
    'Ачинский': 'Ачинский район',
    'Балахтинский': 'Балахтинский район',
    'Берёзовский': 'Берёзовский район',
    'Бирилюсский': 'Бирилюсский район',
    'Боготольский': 'Боготольский район',
    'Богучанский': 'Богучанский район',
    'Большемуртинский': 'Большемуртинский район',
    'Большемуртинско-Сухобузимский': 'Большемуртинско-Сухобузимский муниципальный округ',
    'Большеулуйский': 'Большеулуйский район',
    'г. Ачинск': 'г. Ачинск',
    'город Дивногорск': 'г. Дивногорск',
    'г. Канск': 'г. Канск',
    'город Красноярск': 'г. Красноярск',
    'г. Сосновоборск': 'г. Сосновоборск',
    'Емельяновский': 'Емельяновский район',
    'Енисейский': 'Енисейский район',
    'Ермаковский район': 'Ермаковский район',
    'Идринский район': 'Идринский район',
    'Иланский район': 'Иланский район',
    'Ирбейский район': 'Ирбейский район',
    'Казачинский район': 'Казачинский район',
    'Канский район': 'Канский район',
    'Каратузский район': 'Каратузский район',
    'Кежемский район': 'Кежемский район',
    'Краснотуранский район': 'Краснотуранский район',
    'Курагинский район': 'Курагинский район',
    'Минусинский район': 'Минусинский район',
    'Мотыгинский район': 'Мотыгинский район',
    'Назаровский район': 'Назаровский район',
    'Нижнеингашский район': 'Нижнеингашский район',
    'Новосёловский район': 'Новосёловский район',
    'Саянский район': 'Саянский район',
    'Сухобузимский район': 'Сухобузимский район',
    'Тасеевский район': 'Тасеевский район',
    'Туруханский район': 'Туруханский район',
    'Ужурский': 'Ужурский район',
    'Шарыповский': 'Шарыповский район',
    'Шушенский': 'Шушенский район',
    'Эвенкийский район': 'Эвенкийский район',
}

VOAN_DISTRICT_MAPPING = {
    'Абанский': 'Абанский район',
    'Ачинский': 'Ачинский район',
    'Балахтинский район': 'Балахтинский район',
    'Берёзовский': 'Берёзовский район',
    'Боготольский': 'Боготольский район',
    'Богучанский': 'Богучанский район',
    'Большемуртинский район': 'Большемуртинский район',
    'Большеулуйский': 'Большеулуйский район',
    'г. Ачинск': 'г. Ачинск',
    'г. Дивногорск': 'г. Дивногорск',
    'г. Енисейск': 'г. Енисейск',
    'г. Заозёрный': 'г. Заозёрный',
    'г. Канск': 'г. Канск',
    'город Красноярск': 'г. Красноярск',
    'г. Красноярск': 'г. Красноярск',
    'г. Лесосибирск': 'г. Лесосибирск',
    'г. Минусинск': 'г. Минусинск',
    'г. Назарово': 'г. Назарово',
    'г. Норильск': 'г. Норильск',
    'г. Шарыпово': 'г. Шарыпово',
    'Дзержинский район': 'Дзержинский район',
    'Емельяновский': 'Емельяновский район',
    'Енисейский район': 'Енисейский район',
    'Ермаковский район': 'Ермаковский район',
    'ЗАТО г. Железногорск': 'ЗАТО г. Железногорск',
    'ЗАТО г. Зеленогорск': 'ЗАТО г. Зеленогорск',
    'Идринский район': 'Идринский район',
    'Иланский район': 'Иланский район',
    'Ирбейский район': 'Ирбейский район',
    'Казачинский район': 'Казачинский район',
    'Канский': 'Канский район',
    'Каратузский район': 'Каратузский район',
    'Кежемский район': 'Кежемский район',
    'Козульский район': 'Козульский район',
    'Краснотуранский район': 'Краснотуранский район',
    'Курагинский': 'Курагинский район',
    'Манский': 'Манский район',
    'Минусинский район': 'Минусинский район',
    'Мотыгинский район': 'Мотыгинский район',
    'Назаровский район': 'Назаровский район',
    'Нижнеингашский район': 'Нижнеингашский район',
    'Новосёловский район': 'Новосёловский район',
    'Партизанский район': 'Партизанский район',
    'Рыбинский район': 'Рыбинский район',
    'Саянский район': 'Саянский район',
    'Северо-Енисейский район': 'Северо-Енисейский район',
    'Сухобузимский район': 'Сухобузимский район',
    'Таймырский Долгано-Ненецкий': 'Таймырский Долгано-Ненецкий район',
    'Тасеевский район': 'Тасеевский район',
    'Туруханский': 'Туруханский район',
    'Ужурский': 'Ужурский район',
    'Уярский': 'Уярский район',
    'Шарыповский': 'Шарыповский район',
    'Шушенский': 'Шушенский район',
    'Эвенкийский район': 'Эвенкийский район',
}


def get_admin():
    try:
        admin = User.objects.filter(is_superuser=True)[0]
        return admin
    except Exception as e:
        logger.error(f"Админ не найден!: {e}")
        logger.error(traceback.format_exc())
    return None


def create_note_file(output_path: str, order_text: str = None) -> None:
    """Создает файл Примечание.txt в указанной папке"""
    note_path = os.path.join(output_path, "Примечание.txt")
    try:
        with open(note_path, 'w', encoding='utf-8') as note_file:
            if order_text:
                # Форматируем текст: название приказа + сообщение
                note_file.write(f"{order_text}\nНет приказа на сайте службы")
            else:
                note_file.write("Нет приказа о включении объекта в перечень")
        logger.info(f"Создан файл примечания: {note_path}")
        if order_text:
            logger.info(f"Текст приказа в примечании: {order_text[:100]}...")  # Логируем первые 100 символов
    except Exception as e:
        logger.error(f"Ошибка при создании файла примечания в {output_path}: {e}")
        logger.error(traceback.format_exc())


@shared_task(bind=True, acks_late=True, max_retries=3)
@handle_interrupts
def external_sources_processing(self, task_state, start_date, end_date, start_page, end_page, select_text,
                                select_enrich, select_image,
                                select_coord):
    logger.info(
        f"🎬 НАЧАЛО СКАНИРОВАНИЯ. Параметры: start_date={start_date}, end_date={end_date}, start_page={start_page}, end_page={end_page}")

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
    # admin = User.objects.get(is_superuser=True)
    admin = get_admin()

    # Создаем множество для быстрого поиска
    downloaded_files = get_downloaded_files_cache(admin.id)

    # Определяем игнорирование SSL с использованием сессии
    ignore_ssl = False
    ssl_session = None

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
        logger.error(traceback.format_exc())
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

    # КОРРЕКТНО ОБРАБАТЫВАЕМ ДИАПАЗОН СТРАНИЦ
    if start_page is None or start_page <= 0:
        start_page = 1

    if end_page is None or end_page <= 0:
        end_page = total_pages
    else:
        end_page = min(end_page, total_pages)

    if start_page > end_page:
        start_page, end_page = end_page, start_page

    logger.info(f"📄 ДИАПАЗОН СТРАНИЦ: {start_page}-{end_page} из {total_pages}")

    # Используем правильную сессию в зависимости от SSL
    current_session = ssl_session if ignore_ssl else session

    # ОБНОВЛЯЕМ TASK_STATE С ПРАВИЛЬНЫМИ ПАРАМЕТРАМИ - ДОБАВЛЯЕМ ВСЕ ДАННЫЕ СРАЗУ
    task_state.update(
        total_pages=total_pages,
        start_date=start_date,
        end_date=end_date,
        start_page=start_page,
        end_page=end_page,
        start_time=datetime.now().strftime('%d.%m.%Y %H:%M:%S')  # ОБНОВЛЯЕМ ВРЕМЯ ЗАПУСКА ТОЖЕ!
    )

    # ГЕНЕРИРУЕМ ПЕРВЫЙ ПРОМЕЖУТОЧНЫЙ ОТЧЕТ СРАЗУ С АКТУАЛЬНЫМИ ДАННЫМИ
    logger.info("🔄 ГЕНЕРАЦИЯ ПЕРВОГО ПРОМЕЖУТОЧНОГО ОТЧЕТА")
    generate_intermediate_report(task_state.get_data())

    # Обрабатываем только заданный диапазон страниц
    actual_pages_to_process = end_page - start_page + 1
    current_processed = 0

    for page in range(start_page, end_page + 1):
        current_processed += 1

        # ОБНОВЛЯЕМ ВСЕ ДАННЫЕ СРАЗУ, А НЕ ПООЧЕРЕДНО
        task_state.update(
            processed_pages=current_processed,
            total_pages=total_pages,  # ДУБЛИРУЕМ НА ВСЯКИЙ СЛУЧАЙ
            start_date=start_date,
            end_date=end_date,
            start_page=start_page,
            end_page=end_page
        )

        self.update_state(
            state='PROGRESS',
            meta={
                'current': current_processed,
                'total': actual_pages_to_process,
                'type': 'page_progress',
                'message': f'Обработка страницы {page} из {end_page} (всего страниц на сайте: {total_pages})'
            }
        )

        logger.info(f"📖 ОБРАБОТКА СТРАНИЦЫ {page}")

        try:
            response = current_session.get(
                f"https://ookn.ru/experts/?PAGEN_1={page}",
                timeout=30
            )
            response.raise_for_status()
        except requests.RequestException as e:
            logger.error(f"Ошибка при получении страницы {page}: {e}")
            logger.error(traceback.format_exc())
            continue

        soup = BeautifulSoup(response.text, features="html.parser")
        page_files = []

        # Обрабатываем элементы страницы
        for item in soup.find_all('p', class_='news-item'):
            # Получаем заголовок
            title_elem = item.find('b')
            title = title_elem.get_text(strip=True) if title_elem else 'Без названия'

            # Получаем подзаголовок (весь текст после <b> до <small>)
            full_text = item.get_text()
            small_elem = item.find('small')
            small_text = small_elem.get_text() if small_elem else ''

            # Извлекаем подзаголовок
            subtitle = full_text.replace(title, '').replace(small_text, '').strip()
            # Убираем лишние пробелы и переносы
            import re
            subtitle = re.sub(r'\s+', ' ', subtitle)

            file_info = {
                'page': page,
                'title': title,
                'subtitle': subtitle,
                'filename': '',
                'url': '',
                'status': 'в обработке',
                'reason': ''
            }

            try:
                # Поиск ссылки
                link = item.find('a', href=True)
                if not link or '/upload/iblock/' not in link['href']:
                    file_info.update({'status': 'пропущен', 'reason': 'Не найдена подходящая ссылка'})
                    task_state.add_file_info(file_info)
                    continue

                origin_file = link['href'][link['href'].rfind('/') + 1:]
                file = get_unique_filename(ACTS_SAVING_PATH, origin_file, [file for path, url, file in page_files])
                file_lower = file.lower()

                # Формируем URL
                href = link['href'][:link['href'].rfind('/')]
                params = urllib.parse.urlencode({'address': origin_file})
                url = (href + params).replace('address=', '/').replace('+', '%20').replace('%28', '(').replace(
                    '%29',
                    ')')
                url = f"https://ookn.ru{url}"

                file_info.update({
                    'filename': file,
                    'url': url,
                })

                # Проверка исключений
                if any(query in item.text for query in ACTS_QUERY_EXCLUDE):
                    file_info.update({'status': 'пропущен', 'reason': 'Исключение по фильтру'})
                    task_state.add_file_info(file_info)
                    continue

                # Проверка даты
                if start_date and end_date:
                    match = ORDER_DATE_PATTERN.search(item.text)
                    if not match:
                        file_info.update({'status': 'пропущен', 'reason': 'Не подходит по дате (дата не найдена)'})
                        task_state.add_file_info(file_info)
                        continue

                    date_str = match.group(0)
                    try:
                        day, month, year = map(int, date_str.split('.'))
                        current_date = [year, month, day]
                        if not (start_date <= current_date <= end_date):
                            file_info.update({'status': 'пропущен', 'reason': 'Не подходит по дате'})
                            task_state.add_file_info(file_info)
                            continue
                    except (ValueError, IndexError):
                        file_info.update({'status': 'пропущен', 'reason': 'Ошибка парсинга даты'})
                        task_state.add_file_info(file_info)
                        continue

                if not ('акт' in link['href'].lower() or 'гикэ' in link['href'].lower()) and not (
                        'акт' in item.text.lower() or 'гикэ' in item.text.lower()):
                    file_info.update({'status': 'пропущен', 'reason': 'Не является актом ГИКЭ'})
                    task_state.add_file_info(file_info)
                    continue

                # Пропускаем уже скачанные или ненужные файлы
                if file in downloaded_files:
                    file_info.update({'status': 'пропущен', 'reason': 'Файл уже скачан'})
                    task_state.add_file_info(file_info)
                    continue
                if file_lower.endswith(('.sig', '.png', '.jpg', '.bmp', '.tiff')):
                    file_info.update(
                        {'status': 'пропущен', 'reason': 'У файла неподходящий формат: .sig/.png/.jpg/.bmp/.tiff'})
                    task_state.add_file_info(file_info)
                    continue
                if not is_act_file(file_lower):
                    file_info.update(
                        {'status': 'пропущен', 'reason': 'Файл электронной подписи'})
                    task_state.add_file_info(file_info)
                    continue

                # Обновляем информацию о файле
                file_info.update({
                    'filename': file,
                    'url': url,
                    'status': 'в очереди на скачивание',
                    'reason': 'Добавлен в очередь скачивания'
                })
                task_state.add_file_info(file_info)

                # Добавление файла в очередь
                ACTS_SAVING_PATH.mkdir(exist_ok=True)
                path_to_download = f'{ACTS_SAVING_PATH}/{file}'
                page_files.append((path_to_download, url, file))

            except Exception as e:
                logger.error(f"Ошибка при обработке элемента: {e}")
                logger.error(traceback.format_exc())
                file_info.update({'status': 'ошибка', 'reason': f'Ошибка обработки: {str(e)}'})
                task_state.add_file_info(file_info)
                continue

        # ГЕНЕРИРУЕМ ПРОМЕЖУТОЧНЫЙ ОТЧЕТ ПОСЛЕ КАЖДОЙ СТРАНИЦЫ
        logger.info(f"🔄 ГЕНЕРАЦИЯ ПРОМЕЖУТОЧНОГО ОТЧЕТА ПОСЛЕ СТРАНИЦЫ {page}")
        generate_intermediate_report(task_state.get_data())

        # Параллельное скачивание файлов с одной страницы
        if page_files:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_file = {
                    executor.submit(download_file, url, path): (path, url, file)
                    for path, url, file in page_files
                }

                downloaded_page_files = []
                for future in as_completed(future_to_file):
                    path, url, file = future_to_file[future]
                    try:
                        result = future.result()
                        if result:
                            downloaded_page_files.append((path, url, file))
                            # Обновляем статус в task_state
                            for info in task_state.data['files_info']:
                                if info.get('filename') == file and info.get('page') == page:
                                    info.update({'status': 'скачан', 'reason': 'Успешно скачан'})
                                    break
                        else:
                            # Обновляем статус на ошибку
                            for info in task_state.data['files_info']:
                                if info.get('filename') == file and info.get('page') == page:
                                    info.update({'status': 'ошибка', 'reason': 'Ошибка при скачивании'})
                                    break
                    except Exception as e:
                        logger.error(f"Ошибка при скачивании файла: {e}")
                        logger.error(traceback.format_exc())
                        # Обновляем статус на ошибку
                        for info in task_state.data['files_info']:
                            if info.get('filename') == file and info.get('page') == page:
                                info.update({'status': 'ошибка', 'reason': f'Ошибка скачивания: {str(e)}'})
                                break

                # Обрабатываем скачанные файлы
                if downloaded_page_files:
                    processed_acts = process_downloaded_files(downloaded_page_files, admin, select_text, select_enrich,
                                                              select_image,
                                                              select_coord, task_state)
                    for info in task_state.data['files_info']:
                        if info.get('filename') in processed_acts and processed_acts[info['filename']]:
                            info['act_id'] = processed_acts[info['filename']]

        # Снова генерируем промежуточный отчет после обработки файлов страницы
        logger.info(f"🔄 ГЕНЕРАЦИЯ ПРОМЕЖУТОЧНОГО ОТЧЕТА ПОСЛЕ ОБРАБОТКИ ФАЙЛОВ СТРАНИЦЫ {page}")
        generate_intermediate_report(task_state.get_data())
        time.sleep(random.uniform(2, 5))  # Задержка для снижения нагрузки на сайт ООКН

    logger.info("✅ СКАНИРОВАНИЕ ЗАВЕРШЕНО")
    return {
        'current': actual_pages_to_process,
        'total': actual_pages_to_process,
        'type': 'page_progress',
        'message': f'Сканирование завершено. Обработано страниц: {actual_pages_to_process} из {total_pages}',
        'report_data': task_state.get_data()
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
                    if source.origin_filename:
                        downloaded_files.add(source.origin_filename)
        cache.set(cache_key, downloaded_files, timeout=3600)  # 1 час

    return downloaded_files


def process_downloaded_files(files_data, admin, select_text, select_enrich, select_image, select_coord, task_state):
    """Обрабатывает скачанные файлы с использованием ThreadPoolExecutor для архивов"""
    processed_acts = {}
    all_acts_ids = []
    upload_source = {'source': 'ООКН', 'link': None}
    for path_to_download, url, original_filename in files_data:
        upload_source['link'] = url
        try:
            archive_files = []
            folder = None
            path_to_download_lower = path_to_download.lower()

            if path_to_download_lower.endswith(
                    ('.zip', '.rar', '.7z', '.tar.gz', '.tgz', '.tar.xz', '.txz', '.tar.bz2', '.tbz2', '.tar')):
                folder = path_to_download[:path_to_download.rfind('.')]
                while folder.endswith('.'):
                    folder = folder[:-1]
                os.makedirs(folder, exist_ok=True)

                try:
                    # patoolib.extract_archive(path_to_download, outdir=folder)
                    if path_to_download_lower.endswith('.rar'):
                        unzip_rar(path_to_download, folder)
                    elif path_to_download_lower.endswith('.zip'):
                        unzip_zip(path_to_download, folder)
                    elif path_to_download_lower.endswith('.7z'):
                        unzip_7z(path_to_download, folder)
                    elif path_to_download_lower.endswith(('.tar.gz', '.tgz')):
                        untar_tgz(path_to_download, folder, 'r:gz')
                    elif path_to_download_lower.endswith(('.tar.xz', '.txz')):
                        untar_tgz(path_to_download, folder, 'r:xz')
                    elif path_to_download_lower.endswith(('.tar.bz2', '.tbz2')):
                        untar_tgz(path_to_download, folder, 'r:bz2')
                    elif path_to_download_lower.endswith('.tar'):
                        untar_tgz(path_to_download, folder, 'r:')

                    # Используем ThreadPool для поиска файлов в архиве
                    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
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
                                logger.error(traceback.format_exc())
                                for info in task_state.data['files_info']:
                                    if info.get('filename') == original_filename:
                                        info.update({'status': 'ошибка', 'reason': f'Ошибка скачивания: {str(e)}'})

                except Exception as e:
                    logger.error(f'Ошибка при разархивировании {path_to_download}: {e}')
                    logger.error(traceback.format_exc())
                    for info in task_state.data['files_info']:
                        if info.get('filename') == original_filename:
                            info.update({'status': 'ошибка', 'reason': f'Ошибка разархивирования: {str(e)}'})
                    continue

            files_to_save = []
            file_groups = {}
            if archive_files:
                file_groups['fully'] = []
                types_convert = {'текст': 'text', 'приложение': 'images', 'иллюстрации': 'images', 'прил.': 'images',
                                 'альбом': 'images', 'илл.': 'images'}
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
            acts_ids = raw_reports_save(file_groups, files_to_save, Act, admin.id, True, upload_source)
            if acts_ids and len(acts_ids) > 0:
                processed_acts[original_filename] = acts_ids[0]
                all_acts_ids.extend(acts_ids)
            else:
                processed_acts[original_filename] = None
            if folder is not None:
                shutil.rmtree(folder)
            os.remove(path_to_download)

        except Exception as e:
            logger.error(f"Ошибка при обработке файла {path_to_download}: {e}")
            logger.error(traceback.format_exc())
            processed_acts[original_filename] = None
            for info in task_state.data['files_info']:
                if info.get('filename') == original_filename:
                    info.update({'status': 'ошибка', 'reason': f'Ошибка обработки: {str(e)}'})
            continue
    if all_acts_ids:
        task = process_acts.apply_async(
            (all_acts_ids, admin.id, select_text, select_enrich, select_image, select_coord),
            link_error=error_handler.s('act'))
        # Создаем UserTasks для всей задачи (или для каждого, если нужно)
        user_task = UserTasks(user_id=admin.id, task_id=task.task_id, files_type='act',
                              upload_source=upload_source)
        user_task.save()

    return processed_acts


def is_act_file(filename: str) -> bool:
    if (not (re.search(r'проверк[\s\S]+[подп]?\S+', filename, re.IGNORECASE) or re.search(r'электр\S+\s*подп\S+',
                                                                                          filename,
                                                                                          re.IGNORECASE))) and not (
            'протокол' in filename or 'report' in filename):
        return True
    return False


def find_pdf_files(root, files):
    """Вспомогательная функция для поиска PDF файлов"""
    pdf_files = []
    for file in files:
        file_lower = file.lower()
        if is_act_file(file_lower) and file_lower.endswith('.pdf'):
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


@shared_task(bind=True, acks_late=True, max_retries=3)
def process_voan_list(self, orders_download=False, use_local_register=False, search_account_cards=False,
                      progress_key=None):
    """Обработка перечня выявленных объектов культурного наследия"""
    current_folder = f'uploaded_files/Памятники/ВОАН/'
    Path(current_folder).mkdir(parents=True, exist_ok=True)
    try:
        # Шаг 1: Получение данных с сайта
        try:
            r = requests.get("https://ookn.ru/gosohrana/", verify=False, timeout=30)
            r.raise_for_status()
        except Exception as e:
            logger.error(f"Ошибка подключения к сайту ООКН: {e}")
            logger.error(traceback.format_exc())
            return {
                'current': 0,
                'total': 1,
                'type': 'page_progress',
                'message': f'Ошибка подключения к сайту ООКН: {e}'
            }

        # Шаг 2: Парсинг
        soup = BeautifulSoup(r.text, 'html.parser')

        if use_local_register is True:
            file_path = get_heritage_list_path('voan')
        else:
            # Шаг 3: Очистка старых файлов
            _clean_old_files('list_voan')

            # Шаг 4: Поиск и скачивание файла
            file_path = None
            for item in soup.find_all('p', class_='news-item'):
                title = item.find('b').get_text(strip=True) if item.find('b') else ''
                if title != 'Перечень выявленных объектов культурного наследия':
                    continue

                link = item.find('a', href=True)
                if link and '/upload/iblock/' in link['href']:
                    file_path = _download_file(link['href'], title)
                    break

        if not file_path:
            logger.error("Файл перечня ВОАН не найден")
            logger.error(traceback.format_exc())
            return {
                'current': 0,
                'total': 1,
                'type': 'page_progress',
                'message': f'Файл перечня ВОАН не найден'
            }

        # Шаг 5: Извлечение таблиц
        tables = extract_tables_from_docx(file_path)
        dataframes = tables_to_dataframes(tables)

        # Шаг 6: Получаем ВСЕ существующие объекты ВОАН
        existing_sites = IdentifiedArchaeologicalHeritageSite.objects.all()

        # Создаем множество для отслеживания объектов из нового перечня
        new_sites_set = set()

        processed = 0
        total_rows = sum(len(df) for df in dataframes)

        for i, df in enumerate(dataframes):
            df.columns = df.columns.str.replace('\n', '', regex=True)

            if 'Адрес объекта (или описание местоположения объекта)*' not in df.columns:
                continue

            for index, row in df.iterrows():
                # Обработка каждой строки и добавление в множество новых объектов
                site_key = _process_voan_row(row, orders_download, search_account_cards)
                if site_key:
                    new_sites_set.add(site_key)

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
        # Те объекты, которые есть в БД, но отсутствуют в новом перечне
        marked_excluded = 0
        for site in existing_sites:
            site_key = (site.name, site.document)
            if site_key not in new_sites_set:
                site.is_excluded = True
                site.save()
                marked_excluded += 1

        logger.info(f"Помечено как исключенных: {marked_excluded} объектов ВОАН")

        return {
            'current': processed,
            'total': total_rows,
            'type': 'page_progress',
            'message': f'Сканирование завершено. Исключено объектов: {marked_excluded}'
        }

    except Exception as e:
        logger.error(f"Ошибка в процессе обработки ВОАН: {e}")
        logger.error(traceback.format_exc())
        return {
            'current': 0,
            'total': 1,
            'type': 'page_progress',
            'message': f'Ошибка в процессе обработки ВОАН: {e}'
        }


@shared_task(bind=True, acks_late=True, max_retries=3)
def process_oan_list(self, orders_download=False, use_local_register=False, search_account_cards=False,
                     progress_key=None):
    """Обработка перечня объектов археологического наследия"""
    heritage_type = 'ArchaeologicalHeritageSite'
    current_folder = f'uploaded_files/Памятники/ОАН/'
    Path(current_folder).mkdir(parents=True, exist_ok=True)
    try:
        if use_local_register is True:
            file_path = get_heritage_list_path('oan')
        else:
            # Шаг 1: Получение данных с сайта
            try:
                r = requests.get("https://ookn.ru/gosohrana/", verify=False, timeout=30)
                r.raise_for_status()
            except Exception as e:
                logger.error(f"Ошибка подключения к сайту ООКН для ОАН: {e}")
                logger.error(traceback.format_exc())
                return {
                    'current': 0,
                    'total': 1,
                    'type': 'page_progress',
                    'message': f'Ошибка подключения к сайту ООКН: {e}'
                }

            # Шаг 2: Парсинг HTML
            soup = BeautifulSoup(r.text, 'html.parser')

            # Шаг 3: Очистка старых файлов ОАН
            _clean_old_files('list_oan')

            # Шаг 4: Поиск и скачивание файла перечня ОАН
            file_path = None
            for item in soup.find_all('p', class_='news-item'):
                title = item.find('b').get_text(strip=True) if item.find('b') else ''
                if title != 'Перечень объектов археологического наследия':
                    continue

                link = item.find('a', href=True)
                if link and '/upload/iblock/' in link['href']:
                    file_path = _download_file(link['href'], title)
                    break

        if not file_path:
            logger.error("Файл перечня ОАН не найден")
            logger.error(traceback.format_exc())
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
            logger.error(traceback.format_exc())
            return {
                'current': 0,
                'total': 1,
                'type': 'page_progress',
                'message': f'Не удалось извлечь таблицы из файла ОАН'
            }

        # Шаг 6: Получаем ВСЕ существующие объекты ОАН
        existing_sites = ArchaeologicalHeritageSite.objects.all()

        # Создаем множество для отслеживания объектов из нового перечня
        new_sites_set = set()

        processed = 0
        total_rows = sum(len(df) for df in dataframes)

        # Шаг 7: Обработка каждой таблицы и строки
        for i, df in enumerate(dataframes):
            df.columns = df.columns.str.replace('\n', '', regex=True)

            if not all(col.strip() in df.columns for col in OAN_REQUIRED_COLUMNS.values()):
                logger.warning(f"Таблица {i + 1} не содержит всех необходимых колонок для ОАН")
                continue

            for index, row in df.iterrows():
                try:
                    # Получаем текст приказа из таблицы
                    order_text = row['Документ о постановке на государственную охрану']
                    logger.info(f"📄 Текст приказа ОАН из таблицы: {order_text}")

                    # Обработка одной строки данных ОАН
                    document_source = []

                    # Создаем или получаем объект археологического наследия
                    archaeological_site, created = ArchaeologicalHeritageSite.objects.get_or_create(
                        doc_name=row[OAN_REQUIRED_COLUMNS['name']],
                        district=row[OAN_REQUIRED_COLUMNS['place']],
                        document=order_text,  # Используем переменную order_text
                        register_num=row[OAN_REQUIRED_COLUMNS['number']],
                        defaults={
                            'source': '',
                            'is_excluded': False  # Новые объекты не исключены
                        }
                    )

                    # Если объект создан впервые, создаем папку и скачиваем документы
                    if created:  #
                        district_folder = row[OAN_REQUIRED_COLUMNS['place']]
                        for pattern, name in OAN_DISTRICT_MAPPING.items():
                            if pattern in district_folder:
                                district_folder = name
                                break
                        folder = get_full_path_to_heritage_on_disk('ОАН', district_folder, clean_path_component(row[
                                                                                                                    OAN_REQUIRED_COLUMNS[
                                                                                                                        'name']]))  # f'uploaded_files/Памятники/ОАН/{district_folder}/{clean_path_component(row[OAN_REQUIRED_COLUMNS['name']])}'
                        nested_folders = Path(folder)
                        folder_exists = nested_folders.is_dir()
                        nested_folders.mkdir(parents=True, exist_ok=True)
                        if not folder_exists:
                            with open(os.path.join(nested_folders, "Файлы памятника не найдены.txt"), 'w',
                                      encoding='utf-8') as note_file:
                                note_file.write(
                                    f"Исходные данные памятника:\n{row[OAN_REQUIRED_COLUMNS['place']]}\n{row[OAN_REQUIRED_COLUMNS['name']]}\n\nИспользованный путь:\n{folder}")

                        '''
                        folder_source = DocumentFile(
                            document_id=archaeological_site.id,
                            document_type='ArchaeologicalHeritageSite',
                            file_type='folder',
                            path=str(nested_folders),
                            origin_filename=str(nested_folders).split('/')[-1],
                        )
                        folder_source.save()
                        '''
                        archaeological_site.source = str(nested_folders)
                        if orders_download:
                            external_orders_download(archaeological_site.document, archaeological_site.source,
                                                     document_source)
                        else:
                            local_orders_search(archaeological_site.source, document_source)

                        # ДОБАВЛЯЕМ ПРОВЕРКУ: если документы не найдены, создаем файл примечания
                        if orders_download and not document_source:
                            create_note_file(archaeological_site.source, order_text)

                        save_document_source(archaeological_site.id, heritage_type, 'document',
                                             document_source)
                        archaeological_site.document_source = document_source
                    else:
                        # Если объект уже существовал, но нет документов - скачиваем
                        if not archaeological_site.document_source_dict:
                            if orders_download:
                                external_orders_download(archaeological_site.document, archaeological_site.source,
                                                         document_source)
                            else:
                                local_orders_search(archaeological_site.source, document_source)

                            # ДОБАВЛЯЕМ ПРОВЕРКУ: если документы не найдены, создаем файл примечания
                            if orders_download and not document_source:
                                create_note_file(archaeological_site.source, order_text)

                            save_document_source(archaeological_site.id, heritage_type, 'document',
                                                 document_source)
                            archaeological_site.document_source = document_source

                    archaeological_site.save()

                    # Связываем с учетной карточкой
                    # connect_account_card_to_heritage(archaeological_site.doc_name)
                    if search_account_cards:
                        admin = get_admin()
                        account_cards_connection(archaeological_site.source, admin,
                                                 archaeological_site.doc_name,
                                                 heritage_type,
                                                 archaeological_site.id)

                    # Добавляем в множество новых объектов
                    site_key = (
                        archaeological_site.doc_name,
                        archaeological_site.register_num
                    )
                    new_sites_set.add(site_key)

                except Exception as row_error:
                    logger.error(f"Ошибка обработки строки {index} в таблице {i + 1}: {row_error}")
                    logger.error(traceback.format_exc())
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
        # Те объекты, которые есть в БД, но отсутствуют в новом перечне
        marked_excluded = 0
        for site in existing_sites:
            site_key = (site.doc_name, site.register_num)
            if site_key not in new_sites_set:
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
            'message': f'Обработка всех ОАН завершена. Исключено объектов: {marked_excluded}'
        }

    except Exception as e:
        logger.error(f"Ошибка в процессе обработки ОАН: {e}")
        logger.error(traceback.format_exc())
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

        # Получаем текст приказа из таблицы
        order_text = row['Документ о постановке на государственную охрану']
        logger.info(f"📄 Текст приказа ОАН из таблицы: {order_text}")

        # Поиск существующего объекта или создание нового
        archaeological_site, created = ArchaeologicalHeritageSite.objects.get_or_create(
            doc_name=row[OAN_REQUIRED_COLUMNS['name']],
            district=row[OAN_REQUIRED_COLUMNS['place']],
            document=order_text,  # Используем переменную
            register_num=row[OAN_REQUIRED_COLUMNS['number']],
            defaults={
                'source': ''
            }
        )

        # Если объект новый - создаем структуру папок и скачиваем документы
        if created:
            district_folder = row[OAN_REQUIRED_COLUMNS['place']]
            for pattern, name in OAN_DISTRICT_MAPPING.items():
                if pattern in district_folder:
                    district_folder = name
                    break
            folder = get_full_path_to_heritage_on_disk('ОАН', district_folder,
                                                       clean_path_component(row[OAN_REQUIRED_COLUMNS[
                                                           'name']]))  # f'uploaded_files/Памятники/ОАН/{district_folder}/{clean_path_component(row[OAN_REQUIRED_COLUMNS['name']])}'
            nested_folders = Path(folder)
            nested_folders.mkdir(parents=True, exist_ok=True)

            '''
            folder_source = DocumentFile(
                document_id=archaeological_site.id,
                document_type='ArchaeologicalHeritageSite',
                file_type='folder',
                path=str(nested_folders),
                origin_filename=str(nested_folders).split('/')[-1],
            )
            folder_source.save()
            '''
            archaeological_site.source = str(nested_folders)

            # Скачиваем документы
            external_orders_download(archaeological_site.document, archaeological_site.source, document_source)

            # ДОБАВЛЯЕМ ПРОВЕРКУ: если документы не найдены, создаем файл примечания
            if not document_source:
                create_note_file(archaeological_site.source, order_text)

            save_document_source(archaeological_site.id, 'ArchaeologicalHeritageSite', 'document', document_source)
            archaeological_site.document_source = document_source
            archaeological_site.save()

            # Связываем с учетной карточкой
            connect_account_card_to_heritage(archaeological_site.doc_name)

        # Если объект уже существует, но нет документов - скачиваем
        elif not archaeological_site.document_source_dict:
            # Скачиваем документы
            external_orders_download(archaeological_site.document, archaeological_site.source, document_source)

            # ДОБАВЛЯЕМ ПРОВЕРКУ: если документы не найдены, создаем файл примечания
            if not document_source:
                create_note_file(archaeological_site.source, order_text)

            save_document_source(archaeological_site.id, 'ArchaeologicalHeritageSite', 'document', document_source)
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
        logger.error(traceback.format_exc())
        return False


def _clean_old_files(prefix):
    """Очистка старых файлов"""
    try:
        with open(HERITAGES_LISTS_PATH, 'a+', encoding='utf-8') as file:
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
        logger.error(traceback.format_exc())


def _download_file(href, title):
    """Скачивание файла"""
    file_name = href[href.rfind('/') + 1:]
    file_encoded = file_name.replace(' ', '%20')
    path_to_download = f'uploaded_files/Памятники/{file_name}'

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
    with open(HERITAGES_LISTS_PATH, 'a', encoding='utf-8') as file:
        if title == 'Перечень выявленных объектов культурного наследия':
            file.write(f'list_voan - {path_to_download}\n')
        elif title == 'Перечень объектов археологического наследия':
            file.write(f'list_oan - {path_to_download}\n')

    return path_to_download


def _process_voan_row(row, orders_download, search_account_cards):
    """Обработка одной строки данных ВОАН"""
    heritage_type = 'IdentifiedArchaeologicalHeritageSite'
    try:
        address = row[VOAN_REQUIRED_COLUMNS['address']]
        logger.info(f'address = {address}')
        if isinstance(address, str):
            address = address.strip()
            logger.info(f'address_str = {address}')
        elif isinstance(address, pd.Series):
            logger.info(f'address_series = {address}')
            if len(address) > 1 and isinstance(address.iloc[1], str) and address.iloc[1].strip() != row[
                VOAN_REQUIRED_COLUMNS['name']]:
                logger.info(f'address.iloc[1] = {address}')
                address = address.iloc[1].strip()
            elif len(address) > 0 and isinstance(address.iloc[0], str) and address.iloc[0].strip() != row[
                VOAN_REQUIRED_COLUMNS['name']]:
                logger.info(f'address.iloc[0] = {address}')
                address = address.iloc[0].strip()
            else:
                address = ''

        document_source = []

        # Получаем текст приказа из таблицы
        order_text = row['Документ о включении в перечень выявленных объектов']
        logger.info(f"📄 Текст приказа ВОАН из таблицы: {order_text}")

        # Проверяем существование
        identified_site, created = IdentifiedArchaeologicalHeritageSite.objects.get_or_create(
            name=row[VOAN_REQUIRED_COLUMNS['name']],
            address=address,
            obj_info=row[VOAN_REQUIRED_COLUMNS['obj_info']],
            document=row[VOAN_REQUIRED_COLUMNS['doc']],
        )

        if created:
            district_folder = address
            for pattern, name in VOAN_DISTRICT_MAPPING.items():
                if pattern in district_folder:
                    district_folder = name
                    break
            folder = get_full_path_to_heritage_on_disk('ВОАН', district_folder,
                                                       clean_path_component(row[VOAN_REQUIRED_COLUMNS[
                                                           'name']]))  # f'uploaded_files/Памятники/ВОАН/{district_folder}/{clean_path_component(row[VOAN_REQUIRED_COLUMNS['name']])}'
            logger.info(folder)
            folder_path = Path(folder)
            folder_exists = folder_path.is_dir()
            folder_path.mkdir(parents=True, exist_ok=True)
            if not folder_exists:
                with open(os.path.join(folder, "Файлы памятника не найдены.txt"), 'w',
                          encoding='utf-8') as note_file:
                    note_file.write(
                        f"Исходные данные памятника:\n{row[OAN_REQUIRED_COLUMNS['place']]}\n{row[OAN_REQUIRED_COLUMNS['name']]}\n\nИспользованный путь:\n{folder}")

            '''
            folder_source = DocumentFile(
                document_id=identified_site.id,
                document_type='IdentifiedArchaeologicalHeritageSite',
                file_type='folder',
                path=str(folder),
                origin_filename=str(folder).split('/')[-1],
            )
            folder_source.save()
            '''
            identified_site.source = str(folder)
        if not identified_site.document_source_dict:
            # Скачиваем документы
            logger.info(f'identified_site.source = {identified_site.source}')
            if orders_download:
                external_orders_download(identified_site.document, identified_site.source, document_source)
            else:
                local_orders_search(identified_site.source, document_source)

            # ДОБАВЛЯЕМ ПРОВЕРКУ: если документы не найдены, создаем файл примечания
            if orders_download and not document_source:
                create_note_file(identified_site.source, order_text)

            save_document_source(identified_site.id, heritage_type, 'document',
                                 document_source)
            identified_site.document_source = document_source
            identified_site.save()

        if search_account_cards:
            admin = get_admin()
            account_cards_connection(identified_site.source, admin, identified_site.name, heritage_type,
                                     identified_site.id)

        return (identified_site.name, identified_site.document)

    except Exception as e:
        logger.error(f"Ошибка обработки строки ВОАН: {e}")
        logger.error(traceback.format_exc())
        return None


def account_cards_connection(output_path: str, user, heritage_name: str, heritage_type: str, heritage_id: int) -> None:
    account_cards_patterns = ['Паспорт *.pdf', 'УК *.pdf', 'УК *.doc', 'УК *.docx']
    for ac_pattern in account_cards_patterns:
        for file_path in Path(output_path).glob(f'{ac_pattern}', case_sensitive=False):  # rglob
            file_path_str = str(file_path)
            # Пропускаем временные и скрытые файлы
            if file_path.name.startswith('~') or file_path.name.startswith('.'):
                continue
            has_duplicates, objects, _ = has_duplicates_in_db(file_path_str)
            if has_duplicates:  # or len(ObjectAccountCard.objects.filter(name=heritage_name)) > 0
                for obj in objects:
                    if isinstance(obj.document, ObjectAccountCard) and (
                            not obj.document.heritage_id or not obj.document.heritage_type):
                        obj.document.heritage_id = heritage_id
                        obj.document.heritage_type = heritage_type
                        obj.document.save()
                continue
            account_card = ObjectAccountCard(
                user=user,
                is_public=True,
                is_processing=False,
                upload_source={'source': 'Пользовательский файл'},
                name=heritage_name,
                heritage_type=heritage_type,
                heritage_id=heritage_id,
            )
            compile_date = re.search(r'\d{2}\.\d{2}\.\d{2,4}', file_path_str)
            if compile_date:
                account_card.compile_date = compile_date.group(0)

            kml_path = KMLParser.find_kml_for_pdf(file_path_str, True, is_account_card=True)
            if kml_path:
                logger.info(f"📌 Найден KML файл: {kml_path}")

                kml_coordinates = {}
                try:
                    if isinstance(kml_path, list):
                        for path in kml_path:
                            kml_coordinates.update(KMLParser.parse_kml_file(path))
                    else:
                        kml_coordinates = KMLParser.parse_kml_file(kml_path)
                except Exception as e:
                    logger.error(f"❌ Не удалось извлечь координаты из KML: {e}")

                if kml_coordinates:
                    account_card.coordinates = kml_coordinates

            account_card.save()

            new_entry = DocumentFile(
                document_id=account_card.id,
                document_type='ObjectAccountCard',
                file_type='all',
                path=file_path_str,
                origin_filename=file_path_str.split('/')[-1],
            )
            new_entry.save()


def local_orders_search(output_path: str, document_source: List) -> None:
    patterns = ['приказ', 'решение', 'закон', 'постановление']
    for pattern in patterns:
        for file_path in Path(output_path).rglob(f'*{pattern}*', case_sensitive=False):
            # Пропускаем временные и скрытые файлы
            if file_path.name.startswith('~') or file_path.name.startswith('.'):
                continue
            document_source.append({'path': str(file_path)})


def get_full_path_to_heritage_on_disk(heritage_type, district_folder, name_folder):
    folder = f'uploaded_files/Памятники/{heritage_type}/'
    logger.info(f'district_folder = {district_folder}')
    found_exact = None
    if not Path(folder + district_folder).is_dir():
        found = [x.name for x in list(Path(folder).glob('*')) if x.is_dir()]
        logger.info(f'found district_folder = {found}')
        for threshold in [95, 90]:
            found_exact = sorted([x for x in found if fuzz.ratio(x, district_folder) > threshold],
                                 key=lambda x: fuzz.ratio(x, district_folder))
            if len(found_exact) > 0:
                logger.info(f'found_exact district_folder = {found_exact}')
                district_folder = found_exact[0]
                break
    if not Path(folder + district_folder + '/' + name_folder).is_dir():
        found = [x.name for x in list(Path(folder + district_folder).glob('*')) if x.is_dir()]
        logger.info(f'found name_folder = {found}')
        for threshold in [95, 90, 85]:
            found_exact = sorted([x for x in found if ratio_with_digit_weight(x, name_folder) > threshold],
                                 key=lambda x: ratio_with_digit_weight(x, name_folder))
            if len(found_exact) > 0:
                logger.info(f'found_exact name_folder = {found_exact}')
                name_folder = found_exact[0]
                break
    nested_folders = Path(folder + district_folder + '/' + name_folder)
    logger.info(f'nested_folders = {nested_folders}')
    logger.info(f'nested_folders.is_dir() = {nested_folders.is_dir()}')
    return folder + district_folder + '/' + name_folder


def ratio_with_digit_weight(s1, s2, digit_weight=0.1):
    # 1. Основное сравнение строк
    base_score = fuzz.ratio(s1, s2)

    # 2. Извлекаем цифровые последовательности
    digits1 = re.findall(r'\d+', s1)
    digits2 = re.findall(r'\d+', s2)
    digit_score = 0
    if digits1 and digits2:
        # Сравниваем "строки цифр" (можно использовать и другие метрики)
        digit_score = fuzz.ratio(''.join(digits1), ''.join(digits2))
    elif not digits1 and not digits2:
        digit_score = 1

    # 3. Возвращаем взвешенный результат
    return base_score * (1 - digit_weight) + digit_score * digit_weight


def external_orders_download(query: str, output_path: str, document_source: List) -> None:
    if not query.strip():
        return

    cache_key = query.lower().strip()
    if cache_key in document_cache:
        document_source.extend(document_cache[cache_key])
        for doc in document_source:
            if output_path is not None and os.path.isdir(output_path) and os.path.isfile(doc['path']):
                path_to_download = output_path + doc['path'][doc['path'].rfind('/'):]
                shutil.copy(doc['path'], path_to_download)
                doc['path'] = path_to_download
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

                    logger.info(f'output_path = {output_path}')
                    logger.info(f'file = {file}')
                    path_to_download = os.path.join(output_path, file)
                    if os.path.exists(path_to_download) and path_to_download not in [source['path'] for source in
                                                                                     document_source]:
                        document_source.append({'path': path_to_download})
                        continue
                    download_tasks.append((url, path_to_download))

            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                future_to_url = {
                    executor.submit(download_file, url, path): (url, path)
                    for url, path in download_tasks
                }

                for future in as_completed(future_to_url):
                    url, path = future_to_url[future]
                    try:
                        if future.result():
                            with download_lock:
                                if path not in [source['path'] for source in document_source]:
                                    document_source.append({'path': path})
                                    document_cache[cache_key] = copy.deepcopy(document_source)
                                    downloaded_counter += 1
                    except Exception as e:
                        logger.debug(f"Ошибка при скачивании {url}: {e}")

        if downloaded_counter >= len_order_number and downloaded_counter >= len_order_date:
            break


def download_file(url, path_to_download):
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with session.get(url, verify=False, timeout=30) as response:
                if response.status_code == 429:
                    # Сервер просит подождать – берём паузу из заголовка Retry-After
                    retry_after = int(response.headers.get('Retry-After', 30))
                    logger.warning(f"Получен 429, ждём {retry_after} сек")
                    time.sleep(retry_after)
                    continue
                response.raise_for_status()
                with open(path_to_download, 'wb') as out_file:
                    out_file.write(response.content)
                return True
        except requests.exceptions.RetryError as e:
            logger.error(f"Превышено число повторных попыток: {e}")
            return False
        except Exception as e:
            logger.error(f"Ошибка скачивания {url}: {e}")
            logger.error(traceback.format_exc())
            # Экспоненциальная задержка перед повторной попыткой
            time.sleep(2 ** attempt)
    return False


def save_document_source(obj_id, document_type, file_type, document_source):
    for doc in document_source:
        file_hash = file_size = None
        origin_filename = doc['path']
        if file_type != 'folder':
            file_hash = calculate_file_hash(doc['path'])
            file_size = get_file_size(doc['path'])
        if '/' in doc['path']:
            origin_filename = doc['path'].split('/')[-1]
        doc_source = DocumentFile(
            document_id=obj_id,
            document_type=document_type,
            file_type=file_type,
            path=doc['path'],
            origin_filename=origin_filename,
            file_hash=file_hash,
            file_size=file_size,
        )
        doc_source.save()
