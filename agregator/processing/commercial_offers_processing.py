import json
import os
import logging
import traceback
from datetime import datetime
from tkinter import filedialog

from celery import shared_task
from docx import Document

from agregator.processing.files_saving import load_raw_commercial_offers
from agregator.hash import calculate_file_hash
from agregator.models import CommercialOffers
from agregator.redis_config import redis_client
from agregator.celery_task_template import process_documents
from agregator.processing.coordinates_tables import extract_tables_from_pdf, analyze_coordinates_in_tables_from_pdf, \
    extract_coordinates_from_docx_table, extract_coordinates_xlsx, format_coordinates

logger = logging.getLogger(__name__)


def choose_file() -> str:
    # Открываем окно выбора файла
    file_path = filedialog.askopenfilename(title="Выберите DOC или DOCX файл")
    if file_path:
        return file_path


@shared_task(bind=True)
def process_commercial_offers(self, commercial_offers_ids, user_id):
    return process_documents(self, commercial_offers_ids, user_id, 'commercial_offers', model_class=CommercialOffers,
                             load_function=load_raw_commercial_offers,
                             process_function=extract_coordinates)


def extract_coordinates(file, progress_recorder, pages_count, total_processed,
                        commercial_offer_id, progress_json, task_id, time_on_start):
    coordinates = {}

    commercial_offers = CommercialOffers.objects.all()
    for commercial_offer in commercial_offers:
        if commercial_offer.source and commercial_offer.id != commercial_offer_id and os.path.isfile(
                commercial_offer.source):
            file_hash = calculate_file_hash(file)
            open_list_hash = calculate_file_hash(commercial_offer.source)
            if file_hash == open_list_hash:
                raise FileExistsError(
                    f"Такой файл уже загружен в систему: {progress_json['file_groups'][str(commercial_offer_id)]['origin_filename']}")

    current_commercial_offer = CommercialOffers.objects.get(id=commercial_offer_id)

    '''
    extracted_images = []
    current_part = 0
    time_on_start = datetime.now()
    for page_number in range(len(document)):
        pages_processed = total_processed[0] + page_number
        progress_json['file_groups'][str(act_id)][source_index]['pages']['processed'] = page_number
        expected_time = ((datetime.now() - time_on_start) / (pages_processed if pages_processed > 0 else 1)) * (sum(
            pages_count.values()) - pages_processed)
        total_seconds = int(expected_time.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        progress_json['expected_time'] = f"{hours:02}:{minutes:02}:{seconds:02}"
        redis_client.set(task_id, json.dumps(progress_json))
        progress_recorder.set_progress(pages_processed, sum(pages_count.values()),
                                       progress_json)
    '''

    folder = file[:file.rfind(".")]
    if not os.path.exists(folder):
        os.makedirs(folder)

    results = coordinate_systems = []

    file_lower = file.lower()
    if file_lower.endswith('.pdf'):
        tables = extract_tables_from_pdf(file)
        results, coordinate_systems, _ = analyze_coordinates_in_tables_from_pdf(tables, file)
    elif file_lower.endswith(('.doc', '.docx', '.odt')):
        doc = Document(file)
        results = []
        for table in doc.tables:
            result, coordinate_system = extract_coordinates_from_docx_table(table, doc)
            if result is None or coordinate_system is None:
                continue
            results.append(result)
            for sys in coordinate_system:
                coordinate_systems.append(sys)
        results = [item for sublist in results for item in sublist]
    elif file_lower.endswith(('.xlsx', '.xls')):
        results, coordinate_systems = extract_coordinates_xlsx(file)

    if results is not None:
        logger.info(results)
        coordinates = format_coordinates(results, coordinate_systems)

    current_commercial_offer.coordinates = coordinates
    current_commercial_offer.is_processing = False
    current_commercial_offer.save()
