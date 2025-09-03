import json
import os

from tkinter import filedialog
import re
import pdfplumber
import pandas as pd
from django.http import JsonResponse
from agregator.models import GeojsonData
from agregator.processing.coordinates_tables import convert_proj4, convert_to_wgs84, dms_to_decimal
from agregator.geo_utils import calculate_polygons_area

COORDINATES_SAMPLE = {'Шурфы': {}}


def choose_file() -> str:
    # Открываем окно выбора файла
    # file_path = filedialog.askopenfilename(title="Выберите PDF файл", filetypes=[("PDF файлы", "*.pdf")])
    file_path = filedialog.askdirectory(title="Выберите папку")
    if file_path:
        return file_path


def list_contains_string(lst, target):
    for item in lst:
        if isinstance(item, list):
            if list_contains_string(item, target):
                return True
        else:
            if item == target:
                return True
    return False


def extract_coordinates(file, document, page_number, folder, coordinates) -> None:
    found_table = False
    points_type = None
    coords_system = None

    page = document[page_number]
    text = page.get_text()
    if page_number < len(document) - 1:
        next_page = document[page_number + 1]
        text += next_page.get_text()
    if not found_table:
        points_type = re.search(r'Пункты\s+фотофиксации\.\s+Система\s+координат\S*\s+\S+\d+(?:,\s*зона\s*\d+)?\b', text,
                                re.IGNORECASE | re.MULTILINE)
        if not points_type:
            points_type = re.search(
                r'Каталог\s+координат\s+Участка\.\s+Система\s+координат\S*\s+\S+\d+(?:,\s*зона\s*\d+)?\b', text,
                re.IGNORECASE | re.MULTILINE)
        if points_type:
            points_type = points_type.group(0)
            coords_system = re.search(r'\b(?:wgs|мск)-?\d+(?:,\s*зона\s*\d+)?\b', points_type,
                                      re.IGNORECASE | re.MULTILINE)
            if coords_system:
                coords_system = coords_system.group(0).lower().replace(' ', '').replace('-', '').replace(',',
                                                                                                         '').replace(
                    ':', '')
    if points_type or found_table:
        if points_type not in coordinates.keys():
            coordinates[points_type] = {}
        with pdfplumber.open(file) as pdf:
            page_tables = pdf.pages[page_number].extract_tables()
        if not page_tables:
            found_table = False
        elif list_contains_string(page_tables, 'Северная широта') or list_contains_string(page_tables,
                                                                                          'Восточная долгота'):
            found_table = True
        print("page_tables: " + str(page_tables))
        if page_tables and len(page_tables[0]) > 1 and len(page_tables[0][0]) > 1:
            # print(page_tables[0][0], page_tables[0][1])
            if 'Северная широта' in page_tables[0][1][1] or 'Восточная долгота' in page_tables[0][0][
                1] or re.search(r'\bX\b', page_tables[0][0][1], re.IGNORECASE) or re.search(r'\bY\b',
                                                                                            page_tables[0][0][
                                                                                                1]) or \
                    ('°' in page_tables[0][1][1] and '\'' in page_tables[0][1][1] and '"' in page_tables[0][1][
                        1] and
                     ('N' in page_tables[0][1][1] or 'E' in page_tables[0][1][1] or 'W' in page_tables[0][1][
                         1] or 'S' in page_tables[0][1])):
                df_new = pd.DataFrame(page_tables[0], columns=['№', 'Северная широта', 'Восточная долгота'])

                for index, row in df_new.iterrows():
                    if row is None or not row['Северная широта'] or not row['Восточная долгота']:
                        continue
                    if row['Северная широта'] and row['Восточная долгота'] and (
                            'Северная широта' in row['Северная широта'] or 'Восточная долгота' in row[
                        'Северная широта'] or \
                            'Северная широта' in row['Восточная долгота'] or 'Восточная долгота' in row[
                                'Восточная долгота'] or re.search(r'\bX\b', row['Северная широта'],
                                                                  re.IGNORECASE) or re.search(r'\bY\b', row[
                        'Восточная долгота'])):
                        continue
                    point_number = row['№']
                    lat = row['Северная широта']
                    lon = row['Восточная долгота']
                    if 'wgs84' in coords_system:
                        lat = dms_to_decimal(lat)
                        lon = dms_to_decimal(lon)
                        coordinates[points_type]['coordinate_system'] = 'wgs84'
                    else:
                        lat, lon = convert_to_wgs84(lat, lon, coords_system)
                        coordinates[points_type]['coordinate_system'] = coords_system

                    if 'S' in row['Северная широта']:
                        lat = -lat
                    if 'W' in row['Восточная долгота']:
                        lon = -lon

                    coordinates[points_type][point_number] = [lat, lon]

    calculate_polygons_area(coordinates)

    pits_coordinates = re.findall(
        r'Шурф\s№\s\d+[\s\S]+?Координаты\s+шурфа\s+в\s+системе\s+WGS-\d+:*\s+[NS]\d+°\d+\'\d+[\.,]\d+";*\s+[EW]\d+°\d+\'\d+[\.,]\d+"',
        text, re.IGNORECASE)
    # r'([NS])(\d{1,2})°(\d{1,2})\'(\d{1,2}\.\d{1,2})"\s+([EW])(\d{1,3})°(\d{1,2})\'(\d{1,2}\.\d{1,2})"'
    for coord in pits_coordinates:
        pit_number = re.search(r'Шурф\s+№\s+\d+', coord, re.IGNORECASE).group(0)
        lat = dms_to_decimal(re.search(r'[NS]\d+°\d+\'\d+[\.,]\d+"', coord, re.IGNORECASE).group(0))
        lon = dms_to_decimal(re.search(r'[EW]\d+°\d+\'\d+[\.,]\d+"', coord, re.IGNORECASE).group(0))
        coordinates['Шурфы'][pit_number] = [lat, lon]


def save_geojson_polygons_to_db():
    geojson_folder = os.path.join(os.getcwd(), 'uploaded_files/regions_polygons')
    if not os.path.exists(geojson_folder):
        print(f"Папка {geojson_folder} не существует!")
        return

    for dirpath, dirnames, filenames in os.walk(geojson_folder):
        for filename in filenames:
            print('file: ' + filename)
            if filename.endswith('.geojson'):
                short_filename = filename[:filename.rfind('.')]
                file_path = os.path.join(dirpath, filename)
                with open(file_path, 'r', encoding='utf-8') as file:
                    try:
                        data = json.load(file)
                    except json.JSONDecodeError:
                        return JsonResponse({'error': f'Ошибка при чтении файла {filename}'}, status=400)

                    for feature in data.get('features', []):
                        geojson_data, created = GeojsonData.objects.get_or_create(
                            name=feature.get('properties', {}).get('name', short_filename),
                            defaults={'geojson': feature}
                        )

                        if not created:
                            geojson_data.geojson = feature
                            geojson_data.save()


def process_coords_from_edit_page(request, entity) -> dict:
    print('TESSTAAA')
    entity.coordinates = entity.coordinates_dict
    coordinates = {}
    current_group = None
    for key, value in request.POST.dict().items():
        if 'group[' in key:
            current_group = value
        elif 'coordinate_system[' in key:
            if current_group not in coordinates.keys():
                coordinates[current_group] = {}
            coordinates[current_group]['coordinate_system'] = value
        elif 'point[' in key:
            if current_group not in coordinates.keys():
                coordinates[current_group] = {}
            val = value.split(';')
            if len(val) != 3:
                continue
            point_name, x, y = [x.strip() for x in val]
            coordinates[current_group][point_name] = [x, y]
    for group, polygon in coordinates.items():
        if polygon['coordinate_system'] == 'None':
            continue
        elif group in entity.coordinates.keys():
            if 'coordinate_system' not in entity.coordinates[group]:
                entity.coordinates[group]['coordinate_system'] = polygon['coordinate_system']
                coordinates[group]['coordinate_system'] = 'wgs84'
            if coordinates[group]['coordinate_system'] != entity.coordinates[group]['coordinate_system']:
                for point_name, coords in polygon.items():
                    if point_name == 'coordinate_system':
                        continue
                    lat, lon = convert_proj4(coords[0], coords[1],
                                             entity.coordinates[group]['coordinate_system'],
                                             coordinates[group]['coordinate_system'])
                    coordinates[group][point_name] = [lat, lon]
    print('TESSTAAA11')
    calculate_polygons_area(coordinates)
    return coordinates
