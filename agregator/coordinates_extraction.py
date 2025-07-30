import json
import os

from tkinter import filedialog
import re
import pdfplumber
import pandas as pd
from django.http import JsonResponse
from pyproj import Proj, transform
from .models import GeojsonData

COORDINATES_SAMPLE = {'Шурфы': {}}

projections = {
    "wgs84": Proj(proj='latlong', datum='WGS84'),
    "мск162": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=78 +k=1 +x_0=62728.20 +y_0=-7546013.80 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск163": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=81 +k=1 +x_0=65425.70 +y_0=-7434483.20 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск164": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=84 +k=1 +x_0=86209.80 +y_0=-6542783.50 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск165": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=87 +k=1 +x_0=105295.80 +y_0=-5652185.00 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск166": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=90 +k=1 +x_0=107543.30 +y_0=-5540944.50 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск167": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=93 +k=1 +x_0=106797.80 +y_0=-5578022.50 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск168": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=96 +k=1 +x_0=108285.20 +y_0=-5503868.60 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск169": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=99 +k=1 +x_0=117308.60 +y_0=-5503868.60 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск170": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=102 +k=1 +x_0=90338.90 +y_0=-6357146.10 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск171": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=105 +k=1 +x_0=87870.50 +y_0=-6468522.70 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск24зона1": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=81.51666667 +k=1 +x_0=1500000 +y_0=-5416586.442 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск24зона2": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=87.51666667 +k=1 +x_0=2500000 +y_0=-5416586.442 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск24зона3": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=93.51666667 +k=1 +x_0=3500000 +y_0=-5416586.442 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск24зона4": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=99.51666667 +k=1 +x_0=4500000 +y_0=-5416586.442 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск24зона5": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=105.51666667 +k=1 +x_0=5500000 +y_0=-5416586.442 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск24зона6": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=111.51666667 +k=1 +x_0=6500000 +y_0=-5416586.442 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "гск2011": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=81 +k=1 +x_0=14500000 +y_0=0 +ellps=GSK2011 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs +type=crs'),
}


def convert_to_wgs84(x, y, system):
    y, x = transform(projections[system], projections['wgs84'], y, x)
    return x, y


def convert_proj4(x, y, init_system, final_system):
    y, x = transform(projections[init_system], projections[final_system], y, x)
    return x, y


def choose_file() -> str:
    # Открываем окно выбора файла
    # file_path = filedialog.askopenfilename(title="Выберите PDF файл", filetypes=[("PDF файлы", "*.pdf")])
    file_path = filedialog.askdirectory(title="Выберите папку")
    if file_path:
        return file_path


def normalize_coordinates(coord: str) -> str:
    coord = coord.strip()
    coord = coord.replace(' 0', ' ').replace(' ', '"')
    coord = coord[1:] if coord[0] == '0' else coord
    return coord


def dms_to_decimal(dms):
    """Преобразует координаты из формата DMS в десятичный формат."""
    dms = dms.replace(',', '.')
    dms = re.sub(r'[^\d°\'".]', '', dms)
    print('!!' + str(dms))
    parts = re.split('[°\'"]+', dms)
    print('!!' + str(parts))

    degrees = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])

    decimal = degrees + minutes / 60 + seconds / 3600
    return decimal


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
        else:
            found_table = True
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
    for dirpath, dirnames, filenames in os.walk(geojson_folder):
        for filename in filenames:
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
            point_name, x, y = [x.strip() for x in value.split(';')]
            coordinates[current_group][point_name] = [x, y]
    for group, polygon in coordinates.items():
        if polygon['coordinate_system'] == 'None':
            continue
        elif group in entity.coordinates.keys():
            if 'coordinate_system' not in entity.coordinates[group]:
                entity.coordinates[group]['coordinate_system'] = polygon['coordinate_system']
                coordinates[group]['coordinate_system'] = 'wgs84'
            if polygon['coordinate_system'] != entity.coordinates[group]['coordinate_system']:
                for point_name, coords in polygon.items():
                    if point_name == 'coordinate_system':
                        continue
                    lat, lon = convert_proj4(coords[0], coords[1],
                                             entity.coordinates[group]['coordinate_system'],
                                             coordinates[group]['coordinate_system'])
                    coordinates[group][point_name] = [lat, lon]
    return coordinates
