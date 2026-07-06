import os
import logging
from agregator.hash import calculate_file_hash
from agregator.models import DocumentFile
from django.apps import apps

logger = logging.getLogger(__name__)


def check_duplicates(is_reprocess, file, filename, instance, delete_current=False, delete_found=False):
    if is_reprocess is False:
        class_name = instance.__class__.__name__
        has_duplicates, objects, _ = has_duplicates_in_db(file, class_name, instance.id)
        if has_duplicates:
            duplicate_id = objects[0].document_id
            if delete_current:
                if any(file == source.path for source in objects):
                    instance._raw_delete = True
                instance.delete()
            if delete_found:
                for obj in objects:
                    model = apps.get_model('agregator', obj.document_type)
                    found = model.objects.filter(id=obj.document_id)
                    for doc in found:
                        # doc._raw_delete = True
                        doc.delete()
            raise FileExistsError(
                f"Такой файл уже загружен в систему ({class_name}.id={duplicate_id}): {filename}")


def has_duplicates_in_db(file: str, document_type: str = None, doc_id: int = None) -> tuple:
    file_hash = calculate_file_hash(file)
    if document_type is None or doc_id is None:
        obj = DocumentFile.objects.filter(file_hash=file_hash)
    else:
        obj = DocumentFile.objects.filter(file_hash=file_hash).exclude(document_type=document_type, document_id=doc_id)
    if len(obj) == 0:
        return False, None, file_hash
    return True, obj, file_hash


def add_hash_to_source(record):
    """
    Добавляет хеши ко всем файлам в source записи
    """
    if not record.source_dict:
        return

    updated_sources = []
    for source_item in record.source_dict:
        if not source_item.file_hash and source_item.path:
            try:
                file_hash = calculate_file_hash(source_item.path)
                source_item.file_hash = file_hash
            except Exception as e:
                logger.error(f"Ошибка при вычислении хеша для {source_item.path}: {e}")
                source_item.file_hash = None
        updated_sources.append(source_item)

    record.source = updated_sources
    record.save()


def migrate_existing_hashes(model_class):
    """
    Миграция: добавляет хеши ко всем существующим записям модели
    """
    for record in model_class.objects.all():
        add_hash_to_source(record)
