import json
import os
import logging
import traceback
from datetime import datetime
from tkinter import filedialog

from celery import shared_task
from docx import Document

from agregator.processing.files_saving import load_raw_commercial_offers
from agregator.processing.hash_utils import check_duplicates
from agregator.models import CommercialOffers
from agregator.redis_config import redis_client
from agregator.celery_task_template import process_documents, progress_update, get_expected_time, CONVERTATION_PART, \
    PROCESSING_PART, ALL_PARTS
from agregator.processing.coordinates_tables import extract_tables_from_pdf, analyze_coordinates_in_tables_from_pdf, \
    extract_coordinates_from_docx_table, extract_coordinates_xlsx, format_coordinates
from agregator.redis_config import get_progress_json, create_progress_json

logger = logging.getLogger(__name__)


def choose_file() -> str:
    # Открываем окно выбора файла
    file_path = filedialog.askopenfilename(title="Выберите DOC или DOCX файл")
    if file_path:
        return file_path


@shared_task(bind=True, acks_late=True, max_retries=3)
def process_commercial_offers(self, commercial_offers_ids, user_id, is_reprocess=False):
    document_type = 'commercial_offers'
    progress_json = get_progress_json(self.request.id)
    if progress_json is None:
        progress_json = create_progress_json(
            user_id,
            document_type,
            task_id=self.request.id,
            task_name=self.name,
            args=[commercial_offers_ids, user_id, is_reprocess],
            kwargs={}
        )
    return process_documents(self, commercial_offers_ids, user_id, document_type, model_class=CommercialOffers,
                             load_function=load_raw_commercial_offers,
                             process_function=extract_coordinates, progress_json=progress_json,
                             is_reprocess=is_reprocess)


def extract_coordinates(file, progress_recorder, pages_count, total_processed,
                        commercial_offer_id, progress_json, task_id, time_on_start, is_reprocess):
    coordinates = {}
    current_commercial_offer = CommercialOffers.objects.get(id=commercial_offer_id)

    check_duplicates(is_reprocess, file, progress_json['file_groups'][str(commercial_offer_id)]['origin_filename'],
                     current_commercial_offer, delete_current=True)

    pages_processed = total_processed[0] + pages_count.get(current_commercial_offer.source_dict[0].path, 0)
    progress_json['expected_time'] = get_expected_time(time_on_start, pages_processed, pages_count)
    progress_update(progress_recorder, task_id, progress_json,
                    CONVERTATION_PART + PROCESSING_PART * (pages_processed / sum(pages_count.values())),
                    ALL_PARTS)

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
