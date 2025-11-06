import os
import logging
from pathlib import Path
from agregator.hash import calculate_file_hash
from agregator.models import Act, ScientificReport, TechReport
from agregator.processing.hash_utils import check_file_hash_in_sources
from agregator.processing.batch_file_organizer import FileOrganizer
from agregator.processing.batch_registry_utils import RegistryManager, KMLParser

logger = logging.getLogger(__name__)


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
                'path': str(file_path.absolute()),
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

        # ИСПОЛЬЗУЕМ СУЩЕСТВУЮЩИЙ FILEORGANIZER
        new_path, was_organized = FileOrganizer.create_organized_structure(original_path, 'act')

        # Обновляем информацию о файле
        file_info['path'] = new_path
        file_info['original_path'] = original_path
        file_info['was_organized'] = was_organized

        if was_organized:
            logger.info(f"Файл организован: {original_path} -> {new_path}")

        # Проверяем дубликат по хешу (уже по новому пути)
        is_duplicate, file_hash = check_file_hash_in_sources(file_info['path'], Act)
        if is_duplicate:
            logger.info(f"Файл уже существует в БД: {file_info['path']}")
            return None

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


def scan_and_prepare_batch(directory, file_type, user, limit=10000):
    """
    Сканирует директорию и подготавливает файлы для пакетной обработки
    Возвращает ТОЛЬКО файлы, которых нет в БД
    """
    # Маппинг типов файлов на модели и расширения
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
        }
    }

    config = type_config.get(file_type)
    if not config:
        raise ValueError(f"Неизвестный тип файла: {file_type}")

    # Сканируем файлы
    files = discover_files(directory, config['extensions'], limit=limit)
    logger.info(f"Найдено файлов: {len(files)}")

    # Проверяем каждый файл на дубликаты и фильтруем ТОЛЬКО те, которых нет в БД
    new_files = []
    for file_info in files:
        is_duplicate, file_hash = check_file_hash_in_sources(file_info['path'], config['model'])

        # Проверяем нужно ли организовывать файл (для информации в интерфейсе)
        needs_organization = FileOrganizer.should_reorganize(file_info['path'], FileOrganizer.ROOT_FOLDERS['act'])

        # Добавляем только если файла нет в БД
        if not is_duplicate:
            new_files.append({
                **file_info,
                'exists_in_db': False,
                'file_hash': file_hash,
                'can_process': True,
                'needs_organization': needs_organization,
                'was_organized': False,  # Будет установлено при создании
                'final_location': file_info['path']  # Будет обновлено при создании
            })

    return {
        'files': new_files,
        'total_scanned': len(files),
        'new_files_count': len(new_files),
        'existing_files_count': len(files) - len(new_files)
    }
