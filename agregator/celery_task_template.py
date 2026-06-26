import json
import traceback
from datetime import datetime

from celery_progress.backend import ProgressRecorder

from .redis_config import redis_client
from agregator.processing.error_handler import delete_instances_on_task_revoke
import logging

logger = logging.getLogger(__name__)

CONVERTATION_PART = 20
PROCESSING_PART = 80
ALL_PARTS = 100


def progress_update(progress_recorder, task_id, progress_json, total_processed, max_val):
    """Функция обновления прогресс бара"""
    redis_client.set(task_id, json.dumps(progress_json))
    progress_recorder.set_progress(total_processed, max_val, progress_json)


def get_expected_time(time_on_start, pages_processed, pages_count):
    expected_time = ((datetime.now() - time_on_start) / (pages_processed if pages_processed > 0 else 1)) * (
            sum(
                pages_count.values()) - pages_processed)
    total_seconds = int(expected_time.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def process_documents(
        self,
        document_ids,
        user_id,
        document_type,
        model_class=None,
        load_function=None,
        process_function=None,
        select_text=None,
        select_enrich=None,
        select_image=None,
        select_coord=None,
        progress_json=None,
        is_reprocess=False,
        additional_params=None
):
    """
    Обобщенная функция для обработки документов разных типов.

    Args:
        self: celery task context
        document_ids: список ID документов для обработки
        user_id: ID пользователя
        document_type: тип документа (для progress_json)
        model_class: класс модели (для load_raw_reports)
        load_function: функция загрузки документов (если отличается от load_raw_reports)
        process_function: функция обработки документов
        select_text: флаг извлечения текста
        select_enrich: флаг сопостовления с реестром
        select_image: флаг извлечения изображений
        select_coord: флаг извлечения координат
        additional_params: дополнительные параметры для process_function
    """
    task_id = self.request.id
    logger.info(f'task_id = {task_id}')

    if 'status' in progress_json:
        if progress_json['status'] == 'success':
            return progress_json
        elif progress_json['status'] == 'convertation':
            delete_instances_on_task_revoke(task_id, raw_delete=True)

    progress_recorder = ProgressRecorder(self)
    progress_recorder.set_progress(0, ALL_PARTS, progress_json)

    progress_json['status'] = 'convertation'

    # Загрузка документов
    if document_type in ['scientific_reports', 'acts', 'tech_reports']:
        documents, pages_count = load_function(document_ids, model_class, progress_recorder, progress_json, task_id)
    else:
        documents, pages_count = load_function(document_ids, progress_recorder, progress_json, task_id)

    progress_json['status'] = 'processing'
    total_processed = [0]
    file_groups = {}

    # Подготовка структуры file_groups в зависимости от типа документа
    if 'file_groups' not in progress_json:
        if document_type in ['scientific_reports', 'acts', 'tech_reports']:
            for doc in documents:
                for source in doc.source_dict:
                    file = source.copy()
                    file['processed'] = 'False'
                    file['pages'] = {'processed': '0', 'all': pages_count[source['path']]}
                    print('file=' + str(file))
                    if str(doc.id) in file_groups:
                        file_groups[str(doc.id)].append(file)
                    else:
                        file_groups[str(doc.id)] = [file]
        else:
            for doc in documents:
                source_path = origin_filename = None
                if document_type == 'account_cards':
                    if doc.source_dict and len(doc.source_dict) > 0:
                        if '.doc' in doc.source:
                            for source in doc.source_dict:
                                if '.doc' in source['path']:
                                    source_path = source['path']
                                    origin_filename = source['origin_filename']
                                    break
                        else:
                            source_path = doc.source_dict[0]['path']
                            origin_filename = doc.source_dict[0]['origin_filename']
                else:
                    source_path = doc.source.path if hasattr(doc, 'source') and hasattr(doc.source,
                                                                                        'path') else f'uploaded_files/{doc.source}' if 'uploaded_files/' not in doc.source else doc.source  # doc.source if hasattr(doc, 'source') else f'uploaded_files/{doc.source.name}'
                    source_path = source_path.replace('/app/uploaded_files/', 'uploaded_files/')
                    origin_filename = doc.origin_filename
                file = {
                    'path': source_path,
                    'origin_filename': origin_filename,
                    'processed': 'False',
                    'pages': {'processed': '0', 'all': pages_count.get(str(doc.id), pages_count.get(source_path, 0))}
                }
                print('file=' + str(file))
                file_groups[str(doc.id)] = file

        progress_json['file_groups'] = file_groups

    progress_update(progress_recorder, task_id, progress_json,
                    CONVERTATION_PART + PROCESSING_PART * (total_processed[0] / sum(pages_count.values())), ALL_PARTS)

    # Обработка документов
    for doc in documents:
        i = 0
        for source in (doc.source_dict if hasattr(doc, 'source_dict') else [
            {'path': doc.source if hasattr(doc, 'source') else doc.source.name}]):
            print('isinstance(source, dict): ' + str(isinstance(source, dict)))
            path = source['path'] if isinstance(source, dict) else source.path
            path = path if isinstance(path, str) else path.path
            print('PATH= ' + str(path))

            # Проверка расширения файла
            if not path.lower().endswith(('.pdf', '.doc', '.docx', '.odt', '.xlsx', '.xls', '.kml', '.kmz')):
                continue

            if document_type in ['scientific_reports', 'acts', 'tech_reports']:
                if progress_json['file_groups'][str(doc.id)][i]['processed'] == 'True':
                    continue
                progress_json['file_groups'][str(doc.id)][i]['processed'] = 'Processing'
            else:
                if progress_json['file_groups'][str(doc.id)]['processed'] == 'True':
                    continue
                progress_json['file_groups'][str(doc.id)]['processed'] = 'Processing'

            # Вызов функции обработки
            error_text = None
            try:
                if process_function:
                    if document_type == 'acts':
                        process_function(
                            path, progress_recorder, pages_count, total_processed,
                            progress_json, doc.id, i, task_id, user_id,
                            getattr(doc, 'is_public', False), select_text, select_enrich, select_image, select_coord,
                            is_reprocess
                        )
                    elif document_type in ['commercial_offers', 'account_cards', 'open_lists', 'geo_objects']:
                        time_on_start = datetime.now()
                        process_function(
                            path, progress_recorder, pages_count, total_processed,
                            doc.id, progress_json, task_id, time_on_start, is_reprocess
                        )
                    else:
                        process_function(
                            doc, path, progress_recorder, pages_count, total_processed,
                            progress_json, doc.id, i, task_id, user_id,
                            getattr(doc, 'is_public', False), select_text, select_enrich, select_image, select_coord,
                            is_reprocess
                        )
                else:
                    raise Exception('NO PROCESS_FUNCTION PASSED AS ARGUMENT')
                processed = 'True'
            except Exception as e:
                logger.exception(f'DOCUMENTS PROCESSING ERROR: {e}')
                processed = 'Error'
                error_text = str(e)

            if document_type in ['scientific_reports', 'acts', 'tech_reports']:
                progress_json['file_groups'][str(doc.id)][i]['pages']['processed'] = \
                    progress_json['file_groups'][str(doc.id)][i]['pages']['all']
                progress_json['file_groups'][str(doc.id)][i]['processed'] = processed
                progress_json['file_groups'][str(doc.id)][i]['error_text'] = error_text
            else:
                progress_json['file_groups'][str(doc.id)]['pages']['processed'] = \
                    progress_json['file_groups'][str(doc.id)]['pages']['all']
                progress_json['file_groups'][str(doc.id)]['processed'] = processed
                progress_json['file_groups'][str(doc.id)]['error_text'] = error_text

            progress_update(progress_recorder, task_id, progress_json,
                            CONVERTATION_PART + PROCESSING_PART * (total_processed[0] / sum(pages_count.values())),
                            ALL_PARTS)
            i += 1

    progress_json['status'] = 'success'
    progress_json['time_ended'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return progress_json
