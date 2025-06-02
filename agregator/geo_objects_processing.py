import copy
from datetime import datetime

import fitz
import openpyxl
import pandas as pd
import pdfplumber
from docx import Document
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import os
import zipfile
from celery import shared_task
from celery_progress.backend import ProgressRecorder
import redis
import requests
import json
import re
from .models import GeoObject
from .files_saving import delete_files_in_directory, load_raw_geo_objects
from .coordinates_extraction import projections, convert_to_wgs84, normalize_coordinates, dms_to_decimal
from .hash import calculate_file_hash
import zipfile
import xml.etree.ElementTree as ET

redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)

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


@shared_task(bind=True)
def process_geo_objects(self, geo_objects_ids, user_id):
    progress_recorder = ProgressRecorder(self)
    progress_recorder.set_progress(1, 100, '')
    geo_objects, pages_count = load_raw_geo_objects(geo_objects_ids)
    # delete_files_in_directory('uploaded_files/users/' + str(user_id), uploaded_files)
    total_processed = [0]
    folder = 'uploaded_files/'
    file_groups = {}
    print("---" + str(pages_count))
    for geo_object in geo_objects:
        file = {'path': geo_object.source, 'origin_filename': geo_object.origin_filename,
                'processed': 'False', 'pages': {'processed': '0', 'all': pages_count[geo_object.source]}}
        file_groups[str(geo_object.id)] = file
    progress_json = {'user_id': user_id, 'file_groups': file_groups, 'file_types': 'geo_objects',
                     'time_started': datetime.now().strftime(
                         "%Y-%m-%d %H:%M:%S")}
    redis_client.set(self.request.id, json.dumps(progress_json))
    progress_recorder.set_progress(total_processed[0], sum(pages_count.values()), progress_json)
    for geo_object in geo_objects:
        progress_json['file_groups'][str(geo_object.id)]['processed'] = 'Processing'
        if not geo_object.source.endswith(('.kml', '.kmz')):
            continue
        time_on_start = datetime.now()
        extract_coordinates(geo_object.source, progress_recorder, pages_count,
                            total_processed, geo_object.id, progress_json, self.request.id,
                            time_on_start)
        progress_json['file_groups'][str(geo_object.id)]['pages']['processed'] = \
            progress_json['file_groups'][str(geo_object.id)]['pages']['all']
        progress_json['file_groups'][str(geo_object.id)]['processed'] = 'True'
        redis_client.set(self.request.id, json.dumps(progress_json))
        progress_recorder.set_progress(total_processed[0], sum(pages_count.values()), progress_json)
    progress_json['time_ended'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return progress_json


def extract_coordinates(file, progress_recorder, pages_count, total_processed,
                        geo_object_id, progress_json, task_id, time_on_start):
    coordinates = {}

    geo_objects = GeoObject.objects.all()
    for geo_object in geo_objects:
        if geo_object.source and geo_object.id != geo_object_id and os.path.isfile(
                geo_object.source):
            file_hash = calculate_file_hash(file)
            open_list_hash = calculate_file_hash(geo_object.source)
            if file_hash == open_list_hash:
                raise FileExistsError(
                    f"Такой файл уже загружен в систему: {progress_json['file_groups'][str(geo_object_id)]['origin_filename']}")

    current_geo_object = GeoObject.objects.get(id=geo_object_id)

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


@shared_task
def error_handler_geo_objects(task, exception, exception_desc):
    print(f"Задача {task.id} завершилась с ошибкой: {exception} {exception_desc}")
    progress_json = json.loads(redis_client.get(task.id))
    for geo_object_id, source in progress_json['file_groups'].items():
        print(geo_object_id, source)
        if source['processed'] != 'True':
            geo_object = GeoObject.objects.get(id=geo_object_id)
            geo_object.delete()
    progress_json['time_ended'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raise type(exception)({"error_text": str(exception), "progress_json": progress_json}) from exception
