import os
import logging
from agregator.hash import calculate_file_hash

logger = logging.getLogger(__name__)


def check_file_hash_in_sources(file_path, model_class):
    """
    Проверяет, существует ли файл с таким хешем в source любой записи указанной модели
    """
    try:
        file_hash = calculate_file_hash(file_path)
        logger.info(f"Checking hash {file_hash} for file {file_path}")

        # Проверяем все записи модели
        for record in model_class.objects.all():
            if record.source_dict:
                for source_item in record.source_dict:
                    existing_hash = source_item.get('file_hash')
                    if existing_hash == file_hash:
                        logger.info(f"Found duplicate: record {record.id}")
                        return True, file_hash

                    # Дополнительная проверка: сравниваем пути файлов
                    existing_path = source_item.get('path', '')
                    if existing_path and os.path.exists(existing_path) and os.path.exists(file_path):
                        if os.path.samefile(existing_path, file_path):
                            logger.info(f"Found duplicate by path: {existing_path}")
                            return True, file_hash

        logger.info(f"No duplicates found for {file_path}")
        return False, file_hash

    except Exception as e:
        logger.error(f"Ошибка при проверке хеша файла {file_path}: {e}")
        return False, None


def add_hash_to_source(record):
    """
    Добавляет хеши ко всем файлам в source записи
    """
    if not record.source_dict:
        return

    updated_sources = []
    for source_item in record.source_dict:
        if 'file_hash' not in source_item and 'path' in source_item:
            try:
                file_hash = calculate_file_hash(source_item['path'])
                source_item['file_hash'] = file_hash
            except Exception as e:
                logger.error(f"Ошибка при вычислении хеша для {source_item['path']}: {e}")
                source_item['file_hash'] = None
        updated_sources.append(source_item)

    record.source = updated_sources
    record.save()


def migrate_existing_hashes(model_class):
    """
    Миграция: добавляет хеши ко всем существующим записям модели
    """
    for record in model_class.objects.all():
        add_hash_to_source(record)
