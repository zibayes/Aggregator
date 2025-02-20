import os

from tkinter import filedialog
import re
import pdfplumber
import pandas as pd
import simplekml

COORDINATES_SAMPLE = {'Шурфы': {}}


def choose_file() -> str:
    # Открываем окно выбора файла
    # file_path = filedialog.askopenfilename(title="Выберите PDF файл", filetypes=[("PDF файлы", "*.pdf")])
    file_path = filedialog.askdirectory(title="Выберите папку")
    if file_path:
        return file_path


def dms_to_decimal(dms):
    """Преобразует координаты из формата DMS в десятичный формат."""
    dms = dms.replace(',', '.')
    dms = re.sub(r'[^\d°\'".]', '', dms)
    parts = re.split('[°\'"]+', dms)

    degrees = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])

    decimal = degrees + minutes / 60 + seconds / 3600
    return decimal


def convert_msk164_to_wgs84(x, y):
    # Здесь должна быть ваша логика преобразования
    # Например, просто возвращаем фиктивные значения
    return y / 1000000 + 55, x / 1000000 + 37


def extract_coordinates(file, document, page_number, folder, coordinates) -> None:
    found_table = False

    page = document[page_number]
    text = page.get_text()
    if page_number < len(document) - 1:
        next_page = document[page_number + 1]
        text += next_page.get_text()
    if not found_table:
        points_type = re.search(r'Пункты\s+фотофиксации\.\s+Система\s+координат\S*\s+\S+\d+', text,
                                re.IGNORECASE | re.MULTILINE)
        if not points_type:
            points_type = re.search(r'Каталог\s+координат\s+Участка\.\s+Система\s+координат\S*\s+\S+\d+', text,
                                    re.IGNORECASE | re.MULTILINE)
        if points_type:
            points_type = points_type.group(0)
    if points_type or found_table:
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
                    if 'WGS-84' in points_type or 'WGS84' in points_type or 'WGS 84' in points_type:
                        lat = dms_to_decimal(lat)
                        lon = dms_to_decimal(lon)

                    if 'S' in row['Северная широта']:
                        lat = -lat
                    if 'W' in row['Восточная долгота']:
                        lon = -lon

                    if points_type not in coordinates.keys():
                        coordinates[points_type] = {}
                    coordinates[points_type][point_number] = [lat, lon]

    pits_coordinates = re.findall(
        r'Шурф\s№\s\d+[\s\S]+?Координаты\s+шурфа\s+в\s+системе\s+WGS-\d+:\s+[NS]\d+°\d+\'\d+[\.,]\d+"\s+[EW]\d+°\d+\'\d+[\.,]\d+"',
        text, re.IGNORECASE)
    # r'([NS])(\d{1,2})°(\d{1,2})\'(\d{1,2}\.\d{1,2})"\s+([EW])(\d{1,3})°(\d{1,2})\'(\d{1,2}\.\d{1,2})"'
    for coord in pits_coordinates:
        pit_number = re.search(r'Шурф\s+№\s+\d+', coord, re.IGNORECASE).group(0)
        lat = dms_to_decimal(re.search(r'[NS]\d+°\d+\'\d+[\.,]\d+"', coord, re.IGNORECASE).group(0))
        lon = dms_to_decimal(re.search(r'[EW]\d+°\d+\'\d+[\.,]\d+"', coord, re.IGNORECASE).group(0))
        coordinates['Шурфы'][pit_number] = [lat, lon]
