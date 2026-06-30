import json
import os
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
import logging

logger = logging.getLogger(__name__)

from celery import shared_task

from agregator.processing.files_saving import load_raw_geo_objects
from agregator.processing.hash_utils import check_duplicates
from agregator.models import GeoObject
from agregator.celery_task_template import process_documents, progress_update, get_expected_time, CONVERTATION_PART, \
    PROCESSING_PART, ALL_PARTS
from agregator.redis_config import get_progress_json, create_progress_json

COORDINATE_SYSTEMS = [
    r'wgs.*?\d+',
    r'мск.*?\d+',
    r'гск.*?\d+',
]
COORDINATE_MARKS = {
    ('север', 'вост'): False,
    ('широт', 'долг'): False,
    ('x', 'y'): False,
    ('n', 'e'): False,
}
COORDINATE_TYPES = [
    r'[NS]+\d+°\s*\d+\'\s*\d+[\.,]\d+"|\d+°\s*\d+\'\s*\d+[\.,]\d+"[СЮ]+',
    r'[EW]+\d+°\s*\d+\'\s*\d+[\.,]\d+"|\d+°\s*\d+\'\s*\d+[\.,]\d+"[ВЗ]+',
    r'\d+°\s*\d+\'\s*\d+[\.,]\d+"',

    r'\d+[.,]+\d+',
]


def choose_file() -> str:
    # Открываем окно выбора файла
    file_path = filedialog.askopenfilename(title="Выберите DOC или DOCX файл")
    if file_path:
        return file_path


def extract_kml_from_kmz(kmz_file: str) -> str:
    """Извлечение KML файла из KMZ"""
    with zipfile.ZipFile(kmz_file, 'r') as zip_ref:
        zip_ref.extractall(Path(kmz_file).parent)
        for file in zip_ref.namelist():
            if file.endswith('.kml'):
                return str(Path(kmz_file).parent / file)
    return None


def parse_kml(file_path: str) -> dict:
    """Парсинг KML файла и извлечение координат"""
    coordinates_dict = {"Центр объекта": {'coordinate_system': 'wgs84'}}

    tree = ET.parse(file_path)
    root = tree.getroot()

    # Возможные пространства имен KML
    namespaces = {
        'kml': 'http://www.opengis.net/kml/2.2',
        'google_kml': 'http://earth.google.com/kml/2.2'
    }

    for ns_key, ns_value in namespaces.items():
        # Ищем все Placemarks в KML
        for placemark in root.findall(f'.//{ns_key}:Placemark', namespaces):
            placemark_name = placemark.find(f'{ns_key}:name', namespaces).text
            coords = placemark.find(f'.//{ns_key}:coordinates', namespaces)
            if coords is not None:
                coord_list = [list(map(float, coord.split(','))) for coord in coords.text.strip().split()]
                coord_list = coord_list[0] if len(coord_list) > 0 else coord_list
                coord_list = coord_list[:2][::-1] if len(coord_list) > 2 else coord_list
                coordinates_dict["Центр объекта"][placemark_name] = coord_list

    '''
    for ns_key, ns_value in namespaces.items():
        for folder in root.findall(f'.//{ns_key}:Folder', namespaces):
            folder_name = folder.find(f'{ns_key}:name', namespaces).text
            coordinates_dict[folder_name] = {'coordinate_system': 'wgs84'}

            for placemark in folder.findall(f'{ns_key}:Placemark', namespaces):
                placemark_name = placemark.find(f'{ns_key}:name', namespaces).text
                coords = placemark.find(f'.//{ns_key}:coordinates', namespaces)
                if coords is not None:
                    coord_list = [list(map(float, coord.split(','))) for coord in coords.text.strip().split()]
                    coord_list = coord_list[0] if len(coord_list) > 0 else coord_list
                    coord_list = coord_list[:2][::-1] if len(coord_list) > 2 else coord_list
                    coordinates_dict[folder_name][placemark_name] = coord_list
    '''

    return coordinates_dict


@shared_task(bind=True, acks_late=True, max_retries=3)
def process_geo_objects(self, geo_objects_ids, user_id, is_reprocess=False):
    document_type = 'geo_objects'
    progress_json = get_progress_json(self.request.id)
    if progress_json is None:
        progress_json = create_progress_json(
            user_id,
            document_type,
            task_id=self.request.id,
            task_name=self.name,
            args=[geo_objects_ids, user_id, is_reprocess],
            kwargs={}
        )
    return process_documents(self, geo_objects_ids, user_id, document_type, model_class=GeoObject,
                             load_function=load_raw_geo_objects,
                             process_function=extract_coordinates, progress_json=progress_json,
                             is_reprocess=is_reprocess)


def extract_coordinates(file, progress_recorder, pages_count, total_processed,
                        geo_object_id, progress_json, task_id, time_on_start, is_reprocess):
    coordinates = {}
    current_geo_object = GeoObject.objects.get(id=geo_object_id)

    check_duplicates(is_reprocess, file, progress_json['file_groups'][str(geo_object_id)]['origin_filename'],
                     current_geo_object, delete_current=True)

    pages_processed = total_processed[0] + pages_count.get(current_geo_object.source, 0)
    progress_json['expected_time'] = get_expected_time(time_on_start, pages_processed, pages_count)
    progress_update(progress_recorder, task_id, progress_json,
                    CONVERTATION_PART + PROCESSING_PART * (pages_processed / sum(pages_count.values())),
                    ALL_PARTS)

    folder = file[:file.rfind(".")]
    if not os.path.exists(folder):
        os.makedirs(folder)

    file_lower = file.lower()
    kml_file_path = None
    if file_lower.endswith('.kml'):
        kml_file_path = file_lower
    elif file_lower.endswith('.kmz'):
        kml_file_path = extract_kml_from_kmz(file_lower)
        if not kml_file_path:
            print("Не удалось извлечь KML файл из KMZ.")

    if kml_file_path is not None:
        coordinates = parse_kml(kml_file_path)

    current_geo_object.coordinates = coordinates
    current_geo_object.is_processing = False
    current_geo_object.save()
