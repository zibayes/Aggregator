import os
import concurrent.futures
import logging
import time
import redis
from pathlib import Path
import json
import hashlib
from collections import defaultdict
from agregator.redis_config import REDIS_HOST, REDIS_PORT, REDIS_DB
from agregator.hash import calculate_file_hash
from agregator.models import Act, ScientificReport, TechReport, ObjectAccountCard
from agregator.processing.hash_utils import check_file_hash_in_sources
from agregator.processing.batch_file_organizer import FileOrganizer
from agregator.processing.batch_registry_utils import RegistryManager
from agregator.processing.batch_kml_utils import KMLParser

logger = logging.getLogger(__name__)

try:
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3
    )
    # Проверяем подключение
    redis_client.ping()
    REDIS_AVAILABLE = True
    logger.info("Redis подключен успешно")
except Exception as e:
    logger.warning(f"Redis недоступен: {e}. Будет использоваться in-memory кеш")
    REDIS_AVAILABLE = False
    redis_client = None


class FileScannerCache:
    """Кеш для сканирования файлов"""

    @staticmethod
    def get_model_hashes_cache_key(model_class):
        return f"file_scanner:{model_class.__name__}:hashes"

    @staticmethod
    def get_model_paths_cache_key(model_class):
        return f"file_scanner:{model_class.__name__}:paths"

    @staticmethod
    def warmup_cache(model_class, force_refresh=False):
        """Прогрев кеша для модели"""
        if not REDIS_AVAILABLE:
            return None

        cache_key_hashes = FileScannerCache.get_model_hashes_cache_key(model_class)
        cache_key_paths = FileScannerCache.get_model_paths_cache_key(model_class)

        # Проверяем, есть ли актуальный кеш (кеш на 1 час)
        if not force_refresh and redis_client.exists(cache_key_hashes):
            logger.info("Используем кешированные данные")
            return True

        logger.info("Обновляем кеш данных из БД")
        start_time = time.time()

        records = model_class.objects.exclude(source__isnull=True).only('id', 'source')
        existing_hashes = set()
        existing_paths = set()

        for record in records.iterator(chunk_size=1000):
            if record.source:
                try:
                    source_data = record.source
                    if isinstance(source_data, list):
                        for item in source_data:
                            if isinstance(item, dict):
                                if 'file_hash' in item and item['file_hash']:
                                    existing_hashes.add(item['file_hash'])
                                if 'path' in item and item['path']:
                                    # Сохраняем нормализованный путь
                                    abs_path = os.path.abspath(item['path'])
                                    existing_paths.add(abs_path)
                except Exception as e:
                    logger.warning(f"Ошибка парсинга source для записи {record.id}: {e}")

        # Сохраняем в Redis (на 1 час)
        try:
            if existing_hashes:
                redis_client.sadd(cache_key_hashes, *existing_hashes)
                redis_client.expire(cache_key_hashes, 3600)

            if existing_paths:
                redis_client.sadd(cache_key_paths, *existing_paths)
                redis_client.expire(cache_key_paths, 3600)

            logger.info(f"Кеш обновлен за {time.time() - start_time:.2f}с")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения в Redis: {e}")
            return False

    @staticmethod
    def get_cached_data(model_class):
        """Получение данных из кеша"""
        if not REDIS_AVAILABLE:
            return set(), set()

        try:
            cache_key_hashes = FileScannerCache.get_model_hashes_cache_key(model_class)
            cache_key_paths = FileScannerCache.get_model_paths_cache_key(model_class)

            existing_hashes = redis_client.smembers(cache_key_hashes) or set()
            existing_paths = redis_client.smembers(cache_key_paths) or set()

            return existing_hashes, existing_paths
        except Exception as e:
            logger.error(f"Ошибка получения данных из Redis: {e}")
            return set(), set()

    @staticmethod
    def invalidate_cache(model_class):
        """Инвалидация кеша для модели"""
        if not REDIS_AVAILABLE:
            return

        try:
            cache_key_hashes = FileScannerCache.get_model_hashes_cache_key(model_class)
            cache_key_paths = FileScannerCache.get_model_paths_cache_key(model_class)

            redis_client.delete(cache_key_hashes, cache_key_paths)
            logger.info(f"Кеш для {model_class.__name__} инвалидирован")
        except Exception as e:
            logger.error(f"Ошибка инвалидации кеша: {e}")


def discover_files(base_directory, extensions=None, limit=None):
    """
    Рекурсивно находит все файлы в указанной директории
    """
    if extensions is None:
        extensions = ['.pdf', '.doc', '.docx', '.odt']

    file_list = []
    base_path = Path(base_directory)

    logger.info(f"Scanning directory: {base_directory}")
    logger.info(f"Base path exists: {base_path.exists()}")

    if not base_path.exists():
        logger.error(f"Директория не существует: {base_directory}")
        return file_list

    for extension in extensions:
        pattern = f"*{extension}"
        logger.info(f"Searching for: {pattern}")

        files_found = 0
        for file_path in base_path.rglob(pattern):
            # Если достигли лимита - прерываем
            if limit and files_found >= limit:
                logger.info(f"Достигнут лимит в {limit} файлов для расширения {extension}")
                break

            # Пропускаем временные файлы и скрытые файлы
            if file_path.name.startswith('~') or file_path.name.startswith('.'):
                continue

            file_list.append({
                # 'path': str(file_path.absolute()),
                'path': str(file_path),
                'name': file_path.name,
                'relative_path': str(file_path.relative_to(base_path)),
                'size': file_path.stat().st_size,
                'extension': extension.lower()
            })
            files_found += 1

    logger.info(f"Total files found: {len(file_list)}")
    return file_list


def create_act_from_existing_file(file_info, user, is_public=False):
    """
    Создает запись Act для существующего файла с проверкой дубликатов
    ОРГАНИЗАЦИЯ ФАЙЛОВ ПРОИСХОДИТ ДО СОЗДАНИЯ ЗАПИСИ В БД!
    """
    try:
        # ОРГАНИЗУЕМ ФАЙЛЫ ПЕРЕД ВСЕМ!
        original_path = file_info['path']
        logger.info(f"Организация файла ПЕРЕД обработкой: {original_path}")

        # Проверяем дубликат по хешу (уже по новому пути)
        is_duplicate, file_hash = check_file_hash_in_sources(original_path, Act)
        if is_duplicate:
            logger.info(f"Файл уже существует в БД: {file_info['path']}")
            return None

        # ИСПОЛЬЗУЕМ СУЩЕСТВУЮЩИЙ FILEORGANIZER
        new_path, was_organized = FileOrganizer.create_organized_structure(original_path, 'act')
        new_path = new_path.replace('/app/uploaded_files/', 'uploaded_files/')
        original_path = original_path.replace('/app/uploaded_files/', 'uploaded_files/')

        # Обновляем информацию о файле
        file_info['path'] = new_path
        file_info['original_path'] = original_path
        file_info['was_organized'] = was_organized

        if was_organized:
            logger.info(f"Файл организован: {original_path} -> {new_path}")

        # Создаем запись - ТОЛЬКО обязательные поля
        act = Act(
            user_id=user.id,
            is_public=is_public,
            is_processing=True
        )
        act.save()

        # Создаем source с хешем и информацией об организации
        source_content = [{
            'type': 'all',
            'path': file_info['path'],  # новый путь после организации
            'original_path': original_path,  # оригинальный путь
            'origin_filename': file_info['name'],
            'file_hash': file_hash,
            'was_organized': was_organized
        }]
        act.source = source_content

        # Сохраняем upload_source отдельно
        act.upload_source = {'source': 'Пользовательский файл'}
        act.save()

        logger.info(f"Создан акт {act.id} для файла: {file_info['path']}")
        return act.id

    except Exception as e:
        logger.error(f"Ошибка при создании акта для {file_info['path']}: {e}")
        return None


def create_account_card_from_existing_file(file_info, user, is_public=False):
    """
    Создаёт или дополняет учётную карту для файла.
    - Если файл уже существует в БД (по хешу), ничего не делает.
    - Если в БД есть учётная карта, у которой хотя бы один файл лежит в той же папке,
      что и новый файл, то новый файл добавляется к этой карте (в source и upload_source).
    - Иначе создаётся новая учётная карта.

    Возвращает:
        int или None: ID учётной карты (существующей или новой) или None при ошибке/дубликате.
    """
    try:
        original_path = file_info['path']
        folder = os.path.dirname(original_path)
        logger.info(f"Обработка файла: {original_path}, папка: {folder}")

        # 1. Проверка дубликата по хешу (глобально)
        is_duplicate, file_hash = check_file_hash_in_sources(original_path, ObjectAccountCard)
        if is_duplicate:
            logger.info(f"Файл уже существует в БД: {original_path}")
            return None

        # Если хеш не был вычислен внутри check_file_hash_in_sources, вычисляем явно
        if file_hash is None:
            file_hash = calculate_file_hash(original_path)

        # 2. Поиск учётной карты, привязанной к этой папке
        target_card = None
        # Загружаем все карты, у которых source не пустой
        cards = ObjectAccountCard.objects.exclude(source__isnull=True).exclude(source='').only('id', 'source')
        for card in cards:
            try:
                for item in card.source_dict:
                    if isinstance(item, dict) and 'path' in item:
                        item_folder = os.path.dirname(item['path'])
                        if item_folder == folder:
                            target_card = card
                            logger.info(f"Найдена карта {card.id} для папки {folder}")
                            break
                if target_card:
                    break
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Ошибка парсинга source карты {card.id}: {e}")
                continue

        # 3. Если карта найдена — добавляем файл к ней
        if target_card:
            new_entry = {
                'path': original_path,
                'original_path': original_path,
                'origin_filename': file_info['name'],
                'file_hash': file_hash,
            }
            source_dict = target_card.source_dict
            source_dict.append(new_entry)
            target_card.source = source_dict

            target_card.save()
            logger.info(f"Файл добавлен к существующей карте {target_card.id}: {original_path}")
            return target_card.id

        # 4. Карта не найдена — создаём новую
        account_card = ObjectAccountCard(
            user=user,
            is_public=is_public,
            is_processing=True
        )
        account_card.save()

        source_content = [{
            'type': 'all',
            'path': original_path,
            'original_path': original_path,
            'origin_filename': file_info['name'],
            'file_hash': file_hash,
            'was_organized': False
        }]
        account_card.source = json.dumps(source_content, ensure_ascii=False)

        account_card.upload_source = {'source': 'Пользовательский файл'}
        account_card.save()

        logger.info(f"Создана новая учётная карта {account_card.id} для файла: {original_path}")
        return account_card.id

    except Exception as e:
        logger.error(f"Ошибка при обработке файла {file_info['path']}: {e}")
        return None


def scan_and_prepare_batch(directory, file_type, user, limit=10000, use_cache=True, max_workers=8):
    """
    Умное сканирование с автоматическим выбором стратегии
    """
    type_config = {
        'act': {
            'model': Act,
            'extensions': ['.pdf', '.doc', '.docx', '.odt'],
            'creation_func': create_act_from_existing_file
        },
        'scientific_report': {
            'model': ScientificReport,
            'extensions': ['.pdf', '.doc', '.docx', '.odt'],
            'creation_func': None
        },
        'tech_report': {
            'model': TechReport,
            'extensions': ['.pdf', '.doc', '.docx', '.odt'],
            'creation_func': None
        },
        'account_card': {
            'model': ObjectAccountCard,
            'extensions': ['.pdf', '.doc', '.docx', '.odt'],  # 'kml'
            'creation_func': create_account_card_from_existing_file
        }
    }

    config = type_config.get(file_type)
    if not config:
        raise ValueError(f"Неизвестный тип файла: {file_type}")

    # Сканируем файлы
    files = discover_files(directory, config['extensions'], limit=limit)
    logger.info(f"Найдено файлов: {len(files)}")

    # Загружаем ВСЕ данные из БД - и пути, и хеши
    existing_data = _preload_existing_data(config['model'])
    existing_paths = existing_data['paths']
    existing_hashes = existing_data['hashes']

    result_files = []
    existing_files = []

    logger.debug(f'existing_paths: {existing_paths}')
    for file_info in files:
        file_info['path'] = file_info['path'].replace('/app/uploaded_files/', 'uploaded_files/')
        file_path = file_info['path']
        abs_path = os.path.abspath(file_path)
        logger.debug(f'file_path: {file_path}')
        logger.debug(f'abs_path: {abs_path}')

        # Простая проверка - есть ли такой путь в БД
        exists_in_db = abs_path in existing_paths or file_path in existing_paths

        if exists_in_db:
            existing_files.append({
                **file_info,
                'exists_in_db': exists_in_db,
                'file_hash': None,  # Хеш не вычисляем
                'can_process': not exists_in_db,
                'needs_organization': None,
                'was_organized': False,
                'final_location': file_info['path']
            })
        else:
            result_files.append({
                **file_info,
                'exists_in_db': exists_in_db,
                'file_hash': None,  # Хеш не вычисляем
                'can_process': not exists_in_db,
                'needs_organization': None,
                'was_organized': False,
                'final_location': file_info['path']
            })

    all_count = len(files)
    new_count = all_count - len(existing_files)

    logger.info(f"Smart scan completed: {all_count} files, {new_count} new")

    return {
        'files': result_files,
        'total_scanned': all_count,
        'new_files_count': new_count,
        'existing_files_count': all_count - new_count,
        'strategy': 'smart_with_hashes'
    }


def _preload_existing_data(model_class):
    """Загружаем все данные из БД - пути и хеши"""
    records = model_class.objects.exclude(source__isnull=True).only('source')
    existing_paths = set()
    existing_hashes = set()

    for record in records.iterator(chunk_size=1000):
        if record.source:
            try:
                source_data = record.source_dict
                logger.debug(f"Source data for record {record.id}: {source_data}")  # ДЕБАГ

                # Обрабатываем разные форматы source
                items = []
                if isinstance(source_data, list):
                    items = source_data
                elif isinstance(source_data, dict):
                    items = [source_data]
                else:
                    logger.warning(f"Неизвестный формат source для записи {record.id}: {type(source_data)}")
                    continue

                for item in items:
                    if isinstance(item, dict):
                        # Добавляем путь
                        if 'path' in item and item['path']:
                            # abs_path = os.path.abspath(item['path'])
                            # existing_paths.add(abs_path)
                            existing_paths.add(item['path'])
                        # Добавляем хеш
                        if 'file_hash' in item and item['file_hash']:
                            existing_hashes.add(item['file_hash'])
            except Exception as e:
                logger.warning(f"Ошибка парсинга source для записи {record.id}: {e}")
                continue

    logger.info(f"Загружено {len(existing_paths)} путей и {len(existing_hashes)} хешей из БД")
    return {'paths': existing_paths, 'hashes': existing_hashes}


def _scan_with_cache(directory, config, limit, max_workers=8):
    """Сканирование с использованием Redis кеша и параллельным хешированием"""
    logger.info("Используем стратегию с Redis кешем и параллельным хешированием")

    # Прогрев кеша
    FileScannerCache.warmup_cache(config['model'])

    # Получаем данные из кеша
    existing_hashes, existing_paths = FileScannerCache.get_cached_data(config['model'])

    # Сканируем файлы
    files = discover_files(directory, config['extensions'], limit=limit)
    logger.info(f"Найдено файлов: {len(files)}")

    # РАЗДЕЛЯЕМ ФАЙЛЫ СРАЗУ - не вычисляем хеши для всех подряд
    result_files = []
    files_to_hash = []  # Только файлы, которых нет по путям
    file_paths_to_hash = []

    for file_info in files:
        file_path = file_info['path']
        abs_path = os.path.abspath(file_path)

        # Быстрая проверка по путям
        if abs_path in existing_paths:
            result_files.append({
                **file_info,
                'exists_in_db': True,
                'file_hash': None,
                'can_process': False,
                'needs_organization': None,
                'was_organized': False,
                'final_location': file_info['path']
            })
        else:
            files_to_hash.append(file_info)
            file_paths_to_hash.append(file_path)

    logger.info(f"Файлов для проверки по хешам: {len(files_to_hash)}")

    # ПАРАЛЛЕЛЬНОЕ ВЫЧИСЛЕНИЕ ХЕШЕЙ для оставшихся файлов
    if files_to_hash:
        hash_start = time.time()
        hash_results = calculate_hashes_parallel(file_paths_to_hash, max_workers=max_workers)
        logger.info(f"Параллельное хеширование заняло {time.time() - hash_start:.2f}с")

        for file_info in files_to_hash:
            file_path = file_info['path']
            file_hash = hash_results.get(file_path)

            if file_hash and file_hash in existing_hashes:
                result_files.append({
                    **file_info,
                    'exists_in_db': True,
                    'file_hash': file_hash,
                    'can_process': False,
                    'needs_organization': None,
                    'was_organized': False,
                    'final_location': file_info['path']
                })
            elif file_hash:
                result_files.append({
                    **file_info,
                    'exists_in_db': False,
                    'file_hash': file_hash,
                    'can_process': True,
                    'needs_organization': None,
                    'was_organized': False,
                    'final_location': file_info['path']
                })
            else:
                # Ошибка хеширования
                result_files.append({
                    **file_info,
                    'exists_in_db': True,
                    'file_hash': None,
                    'can_process': False,
                    'needs_organization': None,
                    'was_organized': False,
                    'final_location': file_info['path']
                })

    return {
        'files': result_files,
        'total_scanned': len(files),
        'new_files_count': len([f for f in result_files if not f['exists_in_db']]),
        'existing_files_count': len([f for f in result_files if f['exists_in_db']]),
        'cache_strategy': 'redis_parallel'
    }


def _scan_fast(directory, config, limit):
    """Быстрое сканирование без кеша (in-memory)"""
    logger.info("Используем быструю in-memory стратегию с параллельным хешированием")

    # Сканируем файлы
    files = discover_files(directory, config['extensions'], limit=limit)
    logger.info(f"Найдено файлов: {len(files)}")

    # Предзагружаем данные из БД
    start_time = time.time()
    existing_hashes, existing_paths = _preload_db_data(config['model'])
    logger.info(f"Загрузка данных из БД заняла {time.time() - start_time:.2f}с")

    # Разделяем файлы
    result_files = []
    files_to_hash = []
    file_paths_to_hash = []

    for file_info in files:
        file_path = file_info['path']
        abs_path = os.path.abspath(file_path)

        if abs_path in existing_paths:
            result_files.append({
                **file_info,
                'exists_in_db': True,
                'file_hash': None,
                'can_process': False,
                'needs_organization': None,
                'was_organized': False,
                'final_location': file_info['path']
            })
        else:
            files_to_hash.append(file_info)
            file_paths_to_hash.append(file_path)

    logger.info(f"Файлов для проверки по хешам: {len(files_to_hash)}")

    # ПАРАЛЛЕЛЬНОЕ ВЫЧИСЛЕНИЕ ХЕШЕЙ
    if files_to_hash:
        hash_start = time.time()
        hash_results = calculate_hashes_parallel(file_paths_to_hash, max_workers=10)
        logger.info(f"Параллельное хеширование заняло {time.time() - hash_start:.2f}с")

        for file_info in files_to_hash:
            file_path = file_info['path']
            file_hash = hash_results.get(file_path)

            if file_hash and file_hash in existing_hashes:
                result_files.append({
                    **file_info,
                    'exists_in_db': True,
                    'file_hash': file_hash,
                    'can_process': False,
                    'needs_organization': None,
                    'was_organized': False,
                    'final_location': file_info['path']
                })
            elif file_hash:
                result_files.append({
                    **file_info,
                    'exists_in_db': False,
                    'file_hash': file_hash,
                    'can_process': True,
                    'needs_organization': None,
                    'was_organized': False,
                    'final_location': file_info['path']
                })
            else:
                # Ошибка хеширования
                result_files.append({
                    **file_info,
                    'exists_in_db': True,  # На всякий случай не обрабатываем
                    'file_hash': None,
                    'can_process': False,
                    'needs_organization': None,
                    'was_organized': False,
                    'final_location': file_info['path']
                })

    return {
        'files': result_files,
        'total_scanned': len(files),
        'new_files_count': len([f for f in result_files if not f['exists_in_db']]),
        'existing_files_count': len([f for f in result_files if f['exists_in_db']]),
        'cache_strategy': 'memory_parallel'
    }


def calculate_hashes_parallel(file_paths, max_workers=16):
    """Параллельное вычисление хешей с прогресс-баром"""
    hash_results = {}
    completed = 0
    total = len(file_paths)

    def calculate_single_hash(file_path):
        try:
            return file_path, calculate_file_hash(file_path)
        except Exception as e:
            logger.error(f"Ошибка при вычислении хеша {file_path}: {e}")
            return file_path, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {executor.submit(calculate_single_hash, path): path for path in file_paths}

        for future in concurrent.futures.as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                file_path, file_hash = future.result()
                hash_results[file_path] = file_hash
            except Exception as e:
                logger.error(f"Ошибка в потоке для {file_path}: {e}")
                hash_results[file_path] = None

            completed += 1
            if completed % 50 == 0:  # Логируем каждые 50 файлов
                logger.info(f"Вычислены хеши для {completed}/{total} файлов")

    return hash_results


def _preload_db_data(model_class):
    """Предзагрузка данных из БД в память"""
    records = model_class.objects.exclude(source__isnull=True).only('id', 'source')
    existing_hashes = set()
    existing_paths = set()

    for record in records.iterator(chunk_size=1000):
        if record.source:
            try:
                source_data = record.source
                if isinstance(source_data, list):
                    for item in source_data:
                        if isinstance(item, dict):
                            if 'file_hash' in item and item['file_hash']:
                                existing_hashes.add(item['file_hash'])
                            if 'path' in item and item['path']:
                                abs_path = os.path.abspath(item['path'])
                                existing_paths.add(abs_path)
            except Exception as e:
                logger.warning(f"Ошибка парсинга source для записи {record.id}: {e}")

    return existing_hashes, existing_paths
