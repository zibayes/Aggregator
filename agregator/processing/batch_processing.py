import os
import logging
from pathlib import Path
from agregator.hash import calculate_file_hash
from agregator.models import Act, ScientificReport, TechReport
from agregator.processing.hash_utils import check_file_hash_in_sources

logger = logging.getLogger(__name__)


def discover_files(base_directory, extensions=None):
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

        for file_path in base_path.rglob(pattern):
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
            logger.info(f"Found file: {file_path.name}")

    logger.info(f"Total files found: {len(file_list)}")
    return file_list


def create_act_from_existing_file(file_info, user, is_public=False):
    """
    Создает запись Act для существующего файла с проверкой дубликатов
    """
    try:
        # Проверяем дубликат по хешу
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

        # Создаем source с хешем
        source_content = [{
            'type': 'all',
            'path': file_info['path'],  # абсолютный путь
            'origin_filename': file_info['name'],
            'file_hash': file_hash
        }]
        act.source = source_content

        # Сохраняем upload_source отдельно
        act.upload_source = {'source': 'Пакетная загрузка из файловой системы'}
        act.save()

        logger.info(f"Создан акт {act.id} для файла: {file_info['path']}")
        return act.id

    except Exception as e:
        logger.error(f"Ошибка при создании акта для {file_info['path']}: {e}")
        return None


def scan_and_prepare_batch(directory, file_type, user):
    """
    Сканирует директорию и подготавливает файлы для пакетной обработки
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
            'creation_func': None  # TODO: добавить функцию
        },
        'tech_report': {
            'model': TechReport,
            'extensions': ['.pdf', '.doc', '.docx', '.odt'],
            'creation_func': None  # TODO: добавить функцию
        }
    }

    config = type_config.get(file_type)
    if not config:
        raise ValueError(f"Неизвестный тип файла: {file_type}")

    # Сканируем файлы
    files = discover_files(directory, config['extensions'])

    # Проверяем каждый файл на дубликаты
    processed_files = []
    for file_info in files:
        is_duplicate, file_hash = check_file_hash_in_sources(file_info['path'], config['model'])

        processed_files.append({
            **file_info,
            'exists_in_db': is_duplicate,
            'file_hash': file_hash,
            'can_process': not is_duplicate
        })

    return processed_files
