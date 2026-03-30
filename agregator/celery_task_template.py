import json
import traceback
from datetime import datetime

from celery_progress.backend import ProgressRecorder

from .redis_config import redis_client


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
    progress_recorder = ProgressRecorder(self)
    progress_recorder.set_progress(0, 100, '')

    # Загрузка документов
    if document_type in ['scientific_reports', 'acts', 'tech_reports']:
        documents, pages_count = load_function(document_ids, model_class)
    else:
        documents, pages_count = load_function(document_ids)

    total_processed = [0]
    file_groups = {}

    # Подготовка структуры file_groups в зависимости от типа документа
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

    progress_json = {
        'user_id': user_id,
        'file_groups': file_groups,
        'file_types': document_type,
        'time_started': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    redis_client.set(self.request.id, json.dumps(progress_json))
    progress_recorder.set_progress(total_processed[0], sum(pages_count.values()), progress_json)

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
                progress_json['file_groups'][str(doc.id)][i]['processed'] = 'Processing'
            else:
                progress_json['file_groups'][str(doc.id)]['processed'] = 'Processing'

            # Вызов функции обработки
            try:
                if process_function:
                    if document_type == 'acts':
                        process_function(
                            path, progress_recorder, pages_count, total_processed,
                            progress_json, doc.id, i, self.request.id, user_id,
                            getattr(doc, 'is_public', False), select_text, select_enrich, select_image, select_coord
                        )
                    elif document_type in ['commercial_offers', 'account_cards', 'open_lists', 'geo_objects']:
                        time_on_start = datetime.now()
                        process_function(
                            path, progress_recorder, pages_count, total_processed,
                            doc.id, progress_json, self.request.id, time_on_start
                        )
                    else:
                        process_function(
                            doc, path, progress_recorder, pages_count, total_processed,
                            progress_json, doc.id, i, self.request.id, user_id,
                            getattr(doc, 'is_public', False), select_text, select_enrich, select_image, select_coord
                        )
                else:
                    raise Exception('NO PROCESS_FUNCTION PASSED AS ARGUMENT')
                processed = 'True'
            except Exception:
                traceback.print_exc()
                processed = 'Error'

            if document_type in ['scientific_reports', 'acts', 'tech_reports']:
                progress_json['file_groups'][str(doc.id)][i]['pages']['processed'] = \
                    progress_json['file_groups'][str(doc.id)][i]['pages']['all']
                progress_json['file_groups'][str(doc.id)][i]['processed'] = processed
            else:
                progress_json['file_groups'][str(doc.id)]['pages']['processed'] = \
                    progress_json['file_groups'][str(doc.id)]['pages']['all']
                progress_json['file_groups'][str(doc.id)]['processed'] = processed

            redis_client.set(self.request.id, json.dumps(progress_json))
            progress_recorder.set_progress(total_processed[0], sum(pages_count.values()), progress_json)
            i += 1

    progress_json['time_ended'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return progress_json
