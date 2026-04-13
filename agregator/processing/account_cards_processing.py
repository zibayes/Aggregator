import copy
import io
import json
import os
import re
import shutil
import traceback
import zipfile
from datetime import datetime
from tkinter import filedialog
from typing import List, Dict, Optional, Tuple, Any

import cv2
import fitz
import numpy as np
import pytesseract
from PIL import Image
from celery import shared_task
from docx import Document
from pytesseract import Output
import logging

# ------------------- PyTorch и модель -------------------
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

import torch
import torchvision
from torchvision import transforms as T
from fuzzywuzzy import fuzz  # или rapidfuzz

from agregator.processing.files_saving import load_raw_account_cards
from agregator.hash import calculate_file_hash
from agregator.models import ObjectAccountCard, IdentifiedArchaeologicalHeritageSite, ArchaeologicalHeritageSite
from agregator.redis_config import redis_client
from agregator.celery_task_template import process_documents
from agregator.processing.geo_utils import calculate_polygons_area, dms_to_decimal, normalize_coordinates
from agregator.processing.batch_kml_utils import KMLParser

logger = logging.getLogger(__name__)
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'  # 'C:/Program Files/Tesseract-OCR/tesseract.exe'

min_area = 80000
symbol_config = r'--oem 3 --psm 3 -c tessedit_char_whitelist=+'

# ------------------- КОНФИГУРАЦИЯ МОДЕЛИ -------------------
MODEL_PATH = "account_cards_segmenter.pth"  # укажите правильный путь
DEVICE = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
CONFIDENCE_THRESHOLD = 0.5
NUM_CLASSES = 6

CATEGORY_ID_TO_NAME = {
    1: "text",
    2: "table",
    3: "image",
    4: "image_caption",
    5: "compile_date"
}

SECTION_KEYWORDS = {
    "NAME": ["наименование объекта"],
    "CREATION_TIME": ["время создания", "возникновения"],
    "ADDRESS": ["адрес", "местонахождение"],
    "OBJECT_TYPE": ["вид объекта"],
    "GENERAL_CLASSIFICATION": ["общая видовая принадлежность"],
    "DESCRIPTION": ["общее описание объекта"],
    "USAGE": ["использование объекта"],
    "DISCOVERY_INFO": ["сведения о дате", "обнаружения объекта"],
    "COMPILER": ["составитель"],
    "COMPILE_DATE": ["дата составления"],
    "COORDINATES": ["каталог координат", "углов"],
}

# ------------------- ЗАГРУЗКА МОДЕЛИ -------------------
_model = None


def get_model():
    global _model
    if _model is None:
        logger.info(f"Загрузка модели {MODEL_PATH} на {DEVICE}")
        model = torchvision.models.detection.fasterrcnn_resnet50_fpn(
            weights=None,
            box_detections_per_img=50,
            box_nms_thresh=0.2,
            box_score_thresh=0.001,
        )
        in_features = model.roi_heads.box_predictor.cls_score.in_features
        model.roi_heads.box_predictor = torchvision.models.detection.faster_rcnn.FastRCNNPredictor(
            in_features, NUM_CLASSES
        )
        model.roi_heads.score_thresh = 0.05
        model.roi_heads.nms_thresh = 0.2
        model.rpn.nms_thresh = 0.5
        model.rpn.pre_nms_top_n_train = 2000
        model.rpn.post_nms_top_n_train = 2000
        model.roi_heads.fg_iou_thresh = 0.7
        model.roi_heads.bg_iou_thresh = 0.3

        state_dict = torch.load(MODEL_PATH, map_location=DEVICE)
        model.load_state_dict(state_dict)
        model.to(DEVICE)
        model.eval()
        _model = model
        logger.info("Модель загружена")
    return _model


def detect_regions(pil_image: Image.Image):
    model = get_model()
    transform = T.Compose([T.ToTensor()])
    image_tensor = transform(pil_image).to(DEVICE)
    with torch.no_grad():
        prediction = model([image_tensor])[0]
    keep = prediction['scores'] > CONFIDENCE_THRESHOLD
    boxes = prediction['boxes'][keep].cpu().numpy()
    labels = prediction['labels'][keep].cpu().numpy()
    scores = prediction['scores'][keep].cpu().numpy()
    regions = []
    for box, label, score in zip(boxes, labels, scores):
        class_id = int(label)
        class_name = CATEGORY_ID_TO_NAME.get(class_id, "unknown")
        x1, y1, x2, y2 = box.astype(int)
        regions.append({'box': [x1, y1, x2, y2], 'class': class_name, 'score': score})
    return regions


# ------------------- OCR ВСЕЙ СТРАНИЦЫ -------------------
def ocr_full_page(image_rgb: np.ndarray) -> List[Dict]:
    gray = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    data = pytesseract.image_to_data(thresh, lang='rus+eng', output_type=Output.DICT)
    words = []
    n = len(data['text'])
    for i in range(n):
        text = data['text'][i].strip()
        if not text:
            continue
        if len(text) < 2 and not text.isdigit():
            continue
        conf = int(data['conf'][i]) if data['conf'][i] != '-1' else 100
        if conf < 30:
            continue
        words.append({
            'text': text,
            'left': data['left'][i],
            'top': data['top'][i],
            'width': data['width'][i],
            'height': data['height'][i],
            'conf': conf
        })
    return words


def find_section_headers(words: List[Dict], used_sections: set) -> List[Dict]:
    lines = {}
    for w in words:
        y = w['top']
        key = round(y / 20) * 20
        if key not in lines:
            lines[key] = []
        lines[key].append(w)
    sorted_lines = []
    for y_key in sorted(lines.keys()):
        line_words = sorted(lines[y_key], key=lambda w: w['left'])
        line_text = ' '.join([w['text'] for w in line_words]).lower()
        x_min = min(w['left'] for w in line_words)
        y_min = min(w['top'] for w in line_words)
        x_max = max(w['left'] + w['width'] for w in line_words)
        y_max = max(w['top'] + w['height'] for w in line_words)
        sorted_lines.append({
            'text': line_text,
            'bbox': [x_min, y_min, x_max, y_max],
            'y_center': (y_min + y_max) / 2
        })
    headers = []
    for line in sorted_lines:
        line_text = line['text']
        for section, keywords in SECTION_KEYWORDS.items():
            if section in used_sections:
                continue
            found = False
            for threshold in [95, 90, 80]:
                for kw in keywords:
                    ratio = fuzz.partial_ratio(kw, line_text)
                    if ratio >= threshold:
                        headers.append({
                            'section': section,
                            'bbox': line['bbox'],
                            'text': line_text,
                            'y_center': line['y_center'],
                            'match_ratio': ratio
                        })
                        used_sections.add(section)
                        found = True
                        break
                if found:
                    break
            if found:
                break
        if len(used_sections) == len(SECTION_KEYWORDS):
            break
    unique_headers = {}
    for hdr in headers:
        sec = hdr['section']
        if sec not in unique_headers or hdr['bbox'][1] < unique_headers[sec]['bbox'][1]:
            unique_headers[sec] = hdr
    return list(unique_headers.values())


def assign_blocks_to_sections(blocks: List[Dict], headers: List[Dict], max_vertical_gap: int = 200) -> List[Dict]:
    assigned = []
    for blk in blocks:
        x1, y1, x2, y2 = blk['box']
        block_top, block_bottom = y1, y2
        intersecting = [h for h in headers if not (h['bbox'][3] < block_top or h['bbox'][1] > block_bottom)]
        if intersecting:
            best_hdr = None
            min_dist = float('inf')
            for hdr in intersecting:
                hx1, hy1, hx2, hy2 = hdr['bbox']
                if x1 >= hx2:
                    h_dist = x1 - hx2
                elif hx1 >= x2:
                    h_dist = hx1 - x2
                else:
                    h_dist = 0
                if h_dist < min_dist:
                    min_dist = h_dist
                    best_hdr = hdr
            section = best_hdr['section']
            header_text = best_hdr['text']
            dist = min_dist
        else:
            best_hdr = None
            min_dist = float('inf')
            for hdr in headers:
                if hdr['bbox'][3] < block_top:
                    d = block_top - hdr['bbox'][3]
                    if d < min_dist and d <= max_vertical_gap:
                        min_dist = d
                        best_hdr = hdr
            section = best_hdr['section'] if best_hdr else 'UNKNOWN'
            header_text = best_hdr['text'] if best_hdr else None
            dist = min_dist if best_hdr else None
        assigned.append({**blk, 'assigned_section': section, 'header_text': header_text, 'distance': dist})
    return assigned


# ------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (старые) -------------------
def choose_file() -> str:
    file_path = filedialog.askopenfilename(title="Выберите DOC или DOCX файл")
    if file_path:
        return file_path


def extract_text_from_image(image: cv2.UMat, psm_conf: str) -> str:
    custom_config = f'--oem 3 --psm {psm_conf}'
    extracted_text = pytesseract.image_to_string(image, lang='rus+eng', config=custom_config)
    return extracted_text


def sort_contours_custom(contours):
    bounding_boxes = [cv2.boundingRect(c) for c in contours]
    sorted_contours = sorted(zip(contours, bounding_boxes), key=lambda b: b[1][1])
    for i in range(len(sorted_contours) - 1):
        c1, box1 = sorted_contours[i]
        c2, box2 = sorted_contours[i + 1]
        top_left_1 = box1[1]
        bottom_left_1 = box1[1] + box1[3]
        top_left_2 = box2[1]
        bottom_left_2 = box2[1] + box2[3]
        if ((top_left_1 <= bottom_left_2 and top_left_1 >= top_left_2) or
            (top_left_2 <= bottom_left_1 and top_left_2 >= top_left_1)) and (box1[0] > box2[0]):
            sorted_contours[i], sorted_contours[i + 1] = sorted_contours[i + 1], sorted_contours[i]
    return [c[0] for c in sorted_contours]


def smart_detect_table_structure(table: List[List[str]]) -> Tuple[Optional[int], Optional[int], Optional[int], int]:
    if not table or len(table) < 2:
        return None, None, None, 0
    point_keywords = [r'№', r'номер', r'точк', r'угол', r'поворот', r'обозначение', r'характерн', r'point', r'центр']
    lat_keywords = [r'широт', r'latitude', r'lat', r'с\.ш\.', r'северн', r'north', r'с\. ш\.', r'с.ш', r'широты',
                    r'северной']
    lon_keywords = [r'долгот', r'longitude', r'lon', r'в\.д\.', r'восточн', r'east', r'в\. д\.', r'в.д', r'долготы',
                    r'восточной']
    data_start_row = 0
    for i, row in enumerate(table):
        if i > 5:
            break
        has_coords = False
        for cell in row:
            if isinstance(cell, str) and re.search(r'\d+°\d+\'', cell, re.IGNORECASE | re.MULTILINE):
                has_coords = True
                break
        if has_coords:
            data_start_row = i
            break
    header_rows = table[:data_start_row] if data_start_row > 0 else []
    max_cols = max(len(row) for row in table[:data_start_row + 3]) if table else 0
    column_titles = [''] * max_cols
    for row in header_rows:
        for col_idx, cell in enumerate(row):
            if col_idx < max_cols and cell and str(cell).strip():
                column_titles[col_idx] += ' ' + str(cell).strip()
    column_titles = [title.strip() for title in column_titles]
    point_idx = lat_idx = lon_idx = None
    for col_idx, title in enumerate(column_titles):
        title_lower = title.lower()
        if any(re.search(kw, title_lower, re.IGNORECASE | re.MULTILINE) for kw in point_keywords):
            point_idx = col_idx
        if any(re.search(kw, title_lower, re.IGNORECASE | re.MULTILINE) for kw in lat_keywords):
            lat_idx = col_idx
        if any(re.search(kw, title_lower, re.IGNORECASE | re.MULTILINE) for kw in lon_keywords):
            lon_idx = col_idx
    if lat_idx is None or lon_idx is None:
        sample_rows = table[data_start_row:data_start_row + 3]
        if sample_rows:
            for col_idx in range(max_cols):
                has_lat_format = has_lon_format = False
                for row in sample_rows:
                    if col_idx < len(row):
                        cell = str(row[col_idx]).strip()
                        if re.search(r'\d+°\d+\'', cell, re.IGNORECASE | re.MULTILINE):
                            if re.match(r'^5[0-9]', cell, re.IGNORECASE | re.MULTILINE):
                                has_lat_format = True
                            elif re.match(r'^9[0-9]', cell, re.IGNORECASE | re.MULTILINE):
                                has_lon_format = True
                if has_lat_format and lat_idx is None:
                    lat_idx = col_idx
                if has_lon_format and lon_idx is None:
                    lon_idx = col_idx
    if point_idx is None and lat_idx is not None and lon_idx is not None:
        for col_idx in range(max_cols):
            if col_idx != lat_idx and col_idx != lon_idx:
                point_idx = col_idx
                break
    return point_idx, lat_idx, lon_idx, data_start_row


def is_data_row(row: List[str], point_idx: int, lat_idx: int, lon_idx: int) -> bool:
    if not row:
        return False
    max_idx = max(point_idx or 0, lat_idx or 0, lon_idx or 0)
    if len(row) <= max_idx:
        return False
    test_cells = []
    if point_idx is not None and point_idx < len(row):
        test_cells.append(str(row[point_idx]).lower())
    if lat_idx is not None and lat_idx < len(row):
        test_cells.append(str(row[lat_idx]).lower())
    if lon_idx is not None and lon_idx < len(row):
        test_cells.append(str(row[lon_idx]).lower())
    forbidden_terms = ['широта', 'долгота', 'latitude', 'longitude', 'lat', 'lon', 'угол', 'поворот', '№', 'номер',
                       'north', 'east', 'точк', 'северн', 'восточн', 'с.ш.', 'в.д.', 'координат']
    for cell in test_cells:
        for term in forbidden_terms:
            if term in cell:
                return False
    if lat_idx is not None and lat_idx < len(row):
        if '°' not in str(row[lat_idx]):
            return False
    if lon_idx is not None and lon_idx < len(row):
        if '°' not in str(row[lon_idx]):
            return False
    return True


def normalize_coordinates_better(coord_str: str) -> str:
    if not coord_str or not isinstance(coord_str, str):
        return ""
    coord_str = coord_str.strip()
    coord_str = coord_str.replace('"', '"').replace('"', '"')
    coord_str = coord_str.replace("'", "'").replace("`", "'")
    coord_str = coord_str.replace("″", '"').replace("′′", '"')
    match = re.search(r'(\d+)°\s*(\d+)[\'′]\s*([\d,]+\.?\d*)', coord_str)
    if match:
        degrees = match.group(1)
        minutes = match.group(2)
        seconds = match.group(3).replace(',', '.')
        coord_str = f"{degrees}°{minutes}'{seconds}\""
    return coord_str


def dms_to_decimal_robust(dms_str: str) -> Optional[float]:
    try:
        if not dms_str:
            return None
        dms_str = normalize_coordinates_better(dms_str)
        dms_str = re.sub(r'\s+', '', dms_str)
        patterns = [
            r'(-?\d+)°(\d+)[\'′](\d+\.?\d*?)["″]?([NSEW])?',
            r'(-?\d+)°(\d+)\.(\d+\.?\d*)',
            r'(-?\d+)°(\d+)[\'′](\d+\.?\d*)',
            r'(-?\d+)°(\d+)[\'′](\d+)[\"″](\d+\.?\d*)',
        ]
        for pattern in patterns:
            match = re.search(pattern, dms_str, re.IGNORECASE)
            if match:
                degrees = float(match.group(1))
                minutes = float(match.group(2))
                seconds = float(match.group(3)) if len(match.groups()) >= 3 else 0
                decimal = degrees + minutes / 60 + seconds / 3600
                if len(match.groups()) >= 4 and match.group(4):
                    direction = match.group(4).upper()
                    if direction in ['S', 'W']:
                        decimal = -decimal
                return round(decimal, 10)
        try:
            clean = re.sub(r'[^\d\.\-]', '', dms_str)
            if clean:
                return float(clean)
        except:
            pass
        return None
    except Exception as e:
        logger.error(f"Ошибка преобразования координаты {dms_str}: {e}")
        return None


def extract_points_from_table(table: List[List[str]]) -> Dict[str, List[float]]:
    points = {}
    if not table:
        return points
    point_idx, lat_idx, lon_idx, data_start = smart_detect_table_structure(table)
    if lat_idx is None or lon_idx is None:
        logger.warning("Не удалось определить столбцы с координатами в таблице")
        return points
    logger.info(f"Определена структура: точка={point_idx}, широта={lat_idx}, долгота={lon_idx}, старт={data_start}")
    for row_idx, row in enumerate(table[data_start:], start=data_start):
        if not is_data_row(row, point_idx, lat_idx, lon_idx):
            continue
        try:
            point_key = ""
            if point_idx is not None and point_idx < len(row):
                point_key = str(row[point_idx]).strip()
            if not point_key:
                point_key = f"point_{len(points) + 1}"
            lat_str = str(row[lat_idx]).strip() if lat_idx < len(row) else ""
            lon_str = str(row[lon_idx]).strip() if lon_idx < len(row) else ""
            if not lat_str or not lon_str:
                continue
            lat = dms_to_decimal_robust(lat_str)
            lon = dms_to_decimal_robust(lon_str)
            if lat is not None and lon is not None:
                points[point_key] = [lat, lon]
                logger.debug(f"Добавлена точка {point_key}: {lat}, {lon}")
            else:
                logger.warning(f"Не удалось преобразовать координаты: {lat_str}, {lon_str}")
        except Exception as e:
            logger.error(f"Ошибка обработки строки {row_idx}: {row}, ошибка: {e}")
            continue
    return points


def process_all_tables_universal(nested_tables: List[List[List[str]]]) -> Dict[str, Any]:
    coordinates = {'Каталог координат': {}}
    all_points = {}
    logger.info(f"Начинаем обработку {len(nested_tables)} таблиц")
    for table_idx, table in enumerate(nested_tables):
        if not table:
            continue
        logger.info(f"Обработка таблицы {table_idx + 1}/{len(nested_tables)}")
        try:
            points = extract_points_from_table(table)
            if points:
                logger.info(f"  Извлечено {len(points)} точек")
                for key, value in points.items():
                    if key in all_points:
                        suffix = 1
                        while f"{key}_{suffix}" in all_points:
                            suffix += 1
                        all_points[f"{key}_{suffix}"] = value
                    else:
                        all_points[key] = value
            else:
                logger.warning(f"  Не удалось извлечь точки из таблицы {table_idx + 1}")
        except Exception as e:
            logger.error(f"Критическая ошибка при обработке таблицы {table_idx + 1}: {e}")
            continue
    coordinates['Каталог координат'] = all_points
    if coordinates['Каталог координат']:
        coordinates['Каталог координат']['coordinate_system'] = 'wgs84'
    logger.info(f"Обработка завершена. Всего точек: {len(all_points)}")
    return coordinates


def ccw(A, B, C):
    return (C[0] - A[0]) * (B[1] - A[1]) > (B[0] - A[0]) * (C[1] - A[1])


def intersect(A, B, C, D):
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)


def connect_account_card_to_heritage(object_name, progress_json=None):
    account_card = ObjectAccountCard.objects.filter(name=object_name)
    heritage = IdentifiedArchaeologicalHeritageSite.objects.filter(name=object_name)
    if not heritage:
        heritage = ArchaeologicalHeritageSite.objects.filter(doc_name=object_name)
    if account_card and heritage:
        account_card = account_card[0]
        heritage = heritage[0]
        folder_to_move = account_card.source[:account_card.source.rfind('/')]
        destination_path = os.path.join(heritage.source, os.path.basename(folder_to_move))
        new_destination = destination_path[:destination_path.rfind('/') + 1] + 'Учётная карта'
        if os.path.exists(new_destination):
            return
        heritage.account_card_id = account_card.id
        heritage.save()
        shutil.move(folder_to_move, destination_path)
        os.rename(destination_path, new_destination)
        account_card.source = new_destination + account_card.source[account_card.source.rfind('/'):]
        account_card_supplement = copy.deepcopy(account_card.supplement_dict)
        for category, images in account_card_supplement.items():
            for i in range(len(images)):
                image_name = account_card_supplement[category][i]['source']
                account_card_supplement[category][i]['source'] = new_destination + '/Изображения' + image_name[
                                                                                                    image_name.rfind(
                                                                                                        '/'):]
        folder = account_card.source[:account_card.source.rfind('/') + 1]
        new_source = folder + account_card.origin_filename[
                              :account_card.origin_filename.rfind('.')] + account_card.source[
                                                                          account_card.source.rfind('.'):]
        os.rename(account_card.source, new_source)
        account_card.source = new_source
        account_card.supplement = account_card_supplement
        account_card.save()
        if progress_json is not None:
            progress_json['file_groups'][str(account_card.id)]['path'] = account_card.source


# ------------------- ОСНОВНАЯ ФУНКЦИЯ ОБРАБОТКИ -------------------
@shared_task(bind=True)
def process_account_cards(self, account_cards_ids, user_id):
    return process_documents(self, account_cards_ids, user_id, 'account_cards', model_class=ObjectAccountCard,
                             load_function=load_raw_account_cards,
                             process_function=extract_text_tables_and_images)


def extract_text_tables_and_images(file, progress_recorder, pages_count, total_processed,
                                   account_card_id, progress_json, task_id, time_on_start):
    supplement_content = {"address": [], "description": []}
    coordinates = {}

    # Проверка дубликатов
    account_cards = ObjectAccountCard.objects.all()
    for account_card in account_cards:
        if account_card.source and account_card.id != account_card_id and os.path.isfile(account_card.source):
            if calculate_file_hash(file) == calculate_file_hash(account_card.source):
                raise FileExistsError(
                    f"Такой файл уже загружен в систему: {progress_json['file_groups'][str(account_card_id)]['origin_filename']}")

    current_account_card = ObjectAccountCard.objects.get(id=account_card_id)

    folder = file[:file.rfind("/") + 1] + 'Изображения'
    os.makedirs(folder, exist_ok=True)

    try:
        if file.endswith(('.doc', '.docx')):
            doc = Document(file)
            text = []
            for paragraph in doc.paragraphs:
                text.append(paragraph.text)
            full_text = []
            tables = []
            nested_tables = []
            for table in doc.tables:
                table_data = []
                nested_table_data = []
                for row in table.rows:
                    row_data = []
                    for cell in row.cells:
                        row_data.append(cell.text)
                        full_text.append(cell.text.strip())
                        if cell.tables:
                            nested_table = cell.tables[0]
                            for nested_row in nested_table.rows:
                                nested_table_data.append([cell.text for cell in nested_row.cells])
                            nested_tables.append(nested_table_data)
                    table_data.append(row_data)
                tables.append(table_data)

            i = 0
            for table in tables:
                if i == 1 and len(table) == 1:
                    current_account_card.name = table[0][0]
                elif i == 2 and len(table) == 1:
                    current_account_card.creation_time = table[0][1]
                elif i == 3 and len(table) == 1:
                    current_account_card.address = table[0][0]
                elif i == 4 and len(table) == 2:
                    current_account_card.object_type = table[table[1].index('+')][0]
                elif i == 5 and len(table) == 2:
                    current_account_card.general_classification = table[table[1].index('+')][0]
                elif i == 6 and len(table) == 2:
                    current_account_card.description = table[0][0]
                elif i == 7 and len(table) == 9:
                    for row in table:
                        if '+' in row:
                            current_account_card.usage = row[row.index('+') - 1]
                            break
                elif i == 8 and len(table) == 1:
                    current_account_card.discovery_info = table[0][0]
                elif i == 9 and len(table) == 2:
                    current_account_card.compiler = table[0][0] + ' ' + table[0][2]
                elif i == 11 and len(table) == 1:
                    current_account_card.compile_date = ''
                    for digit in table[0]:
                        current_account_card.compile_date += digit
                i += 1

            image_captions = {}
            is_first = True
            with zipfile.ZipFile(file, 'r') as zip_file:
                for file_zip in sorted(zip_file.namelist()):
                    if file_zip.startswith('word/media/'):
                        image_name = os.path.basename(file_zip)
                        image_path = os.path.join(folder, image_name)
                        with open(image_path, 'wb') as img_file:
                            img_file.write(zip_file.read(file_zip))
                        image_captions[image_name] = None
                        category = 'address'
                        for img_name in image_captions:
                            for txt in full_text:
                                for part in txt.split('\n'):
                                    part = part.strip()
                                    center = re.search(
                                        r'Координат[\S ]+?центр[\S ]+?WGS-\d+\)*\s*–*—*\s*[NS]\s*\d+[°\s]+\d+[\'\s]+\d+[\.,]\d+["\s]+;*\s*[EW]\s*\d+[°\s]+\d+[\'\s]+\d+[\.,]\d+"*',
                                        part, re.IGNORECASE)
                                    if center:
                                        center = center.group(0)
                                        lat = dms_to_decimal(
                                            normalize_coordinates(
                                                re.search(r'[NS]\s*\d+[°\s]+\d+[\'\s]+\d+[\.,]\d+"*', center,
                                                          re.IGNORECASE).group(0).replace('N ', '').replace('S ',
                                                                                                            '').strip()))
                                        lon = dms_to_decimal(
                                            normalize_coordinates(
                                                re.search(r'[EW]\s*\d+[°\s]+\d+[\'\s]+\d+[\.,]\d+"*', center,
                                                          re.IGNORECASE).group(0).replace('E ', '').replace('W ',
                                                                                                            '').strip()))
                                        if lat is not None and lon is not None:
                                            coordinates['Центр объекта'] = {}
                                            coordinates['Центр объекта']['Центр объекта'] = [lat, lon]
                                    if 'объект расположен' in part.lower():
                                        category = 'description'
                                        continue
                                    if current_account_card.name in part and part not in image_captions.values():
                                        if not is_first:
                                            image_captions[img_name] = part
                                            break
                                        else:
                                            is_first = False
                                if image_captions[img_name]:
                                    break
                        supplement_content[category].append({"label": image_captions[img_name], "source": image_path})

            coordinates['Каталог координат'] = {}
            coordinates = process_all_tables_universal(nested_tables)
            i = 0
            while not coordinates['Каталог координат'] and i < len(tables):
                coordinates = process_all_tables_universal(tables[i])
                i += 1
            points = [x for x in list(coordinates['Каталог координат'].keys()) if
                      x not in ('coordinate_system', 'area')]
            if 'Каталог координат' in coordinates and len(points) == 4:
                if intersect(coordinates['Каталог координат'][points[0]], coordinates['Каталог координат'][points[1]],
                             coordinates['Каталог координат'][points[2]],
                             coordinates['Каталог координат'][points[3]]) or \
                        intersect(coordinates['Каталог координат'][points[1]],
                                  coordinates['Каталог координат'][points[2]],
                                  coordinates['Каталог координат'][points[3]],
                                  coordinates['Каталог координат'][points[0]]):
                    coordinates['Каталог координат'][points[2]], coordinates['Каталог координат'][points[3]] = \
                        coordinates['Каталог координат'][points[3]], coordinates['Каталог координат'][points[2]]
                    coordinates['Каталог координат'] = {k: coordinates['Каталог координат'][k] for k in
                                                        sorted(coordinates['Каталог координат'])}
            calculate_polygons_area(coordinates)

        elif file.endswith('.pdf'):
            doc = fitz.open(file)
            global_used_sections = set()
            all_headers = []
            # Первый проход: собираем все заголовки со всех страниц
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=300)
                pil_img = Image.open(io.BytesIO(pix.tobytes("png")))
                img_rgb = np.array(pil_img)
                words = ocr_full_page(img_rgb)
                headers = find_section_headers(words, global_used_sections)
                all_headers.extend(headers)

            # Второй проход: обработка страниц с привязкой к собранным заголовкам
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(dpi=300)
                pil_img = Image.open(io.BytesIO(pix.tobytes("png")))
                img_rgb = np.array(pil_img)

                # Детекция блоков
                blocks = detect_regions(pil_img)
                # Привязка
                assigned = assign_blocks_to_sections(blocks, all_headers)
                assigned.sort(key=lambda b: b['box'][1])

                # Разделим блоки на текстовые и изображения/подписи
                text_blocks = [b for b in assigned if b['class'] == 'text']
                image_blocks = [b for b in assigned if b['class'] == 'image']
                caption_blocks = [b for b in assigned if b['class'] == 'image_caption']
                table_blocks = [b for b in assigned if b['class'] == 'table']
                compile_date_blocks = [b for b in assigned if b['class'] == 'compile_date']

                # Привязываем подписи к изображениям: для каждой подписи ищем ближайшее сверху изображение
                for cap in caption_blocks:
                    cap_x1, cap_y1, cap_x2, cap_y2 = cap['box']
                    best_img = None
                    min_dist = float('inf')
                    for img in image_blocks:
                        img_x1, img_y1, img_x2, img_y2 = img['box']
                        if img_y2 < cap_y1:  # изображение выше подписи
                            dist = cap_y1 - img_y2
                            if dist < min_dist and dist <= 300:
                                min_dist = dist
                                best_img = img
                    if best_img is not None:
                        cap['linked_image'] = best_img
                        best_img['linked_caption'] = cap

                for blk in table_blocks:
                    x1, y1, x2, y2 = blk['box']
                    crop = img_rgb[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue

                    # OCR таблицы как текст и преобразование в структуру (упрощённо)
                    table_text = pytesseract.image_to_string(crop, lang='rus+eng', config='--oem 3 --psm 6').strip()
                    rows = [row.split() for row in table_text.split('\n') if row.strip()]
                    if rows:
                        # Преобразуем в формат, ожидаемый process_all_tables_universal
                        nested = [[[cell for cell in row] for row in rows]]
                        coords = process_all_tables_universal(nested)
                        # Объединяем с существующими координатами
                        if coords.get('Каталог координат'):
                            if 'Каталог координат' not in coordinates:
                                coordinates['Каталог координат'] = {}
                            for k, v in coords['Каталог координат'].items():
                                if k != 'coordinate_system':
                                    coordinates['Каталог координат'][k] = v
                            if 'coordinate_system' in coords['Каталог координат']:
                                coordinates['Каталог координат']['coordinate_system'] = coords['Каталог координат'][
                                    'coordinate_system']

                # Обработка текстовых блоков и таблиц
                for blk in text_blocks:
                    x1, y1, x2, y2 = blk['box']
                    crop = img_rgb[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue
                    psm = '1' if blk['class'] == 'text' else '6'
                    block_text = pytesseract.image_to_string(crop, lang='rus+eng',
                                                             config=f'--oem 3 --psm {psm}').strip()
                    section = blk['assigned_section']
                    logger.info(f"Блок {blk['class']} привязан к секции {section}, текст: {block_text[:80]}")

                    if section == 'NAME' and not current_account_card.name:
                        current_account_card.name = block_text
                    elif section == 'CREATION_TIME' and not current_account_card.creation_time:
                        current_account_card.creation_time = block_text
                    elif section == 'ADDRESS' and not current_account_card.address:
                        current_account_card.address = block_text
                        # Извлечение координат центра
                        address_clean = block_text.replace('’', "'").replace('”', '"').replace('""', '"').replace('М',
                                                                                                                  'N').replace(
                            'M', 'N').replace('Е', 'E')
                        center = re.search(
                            r'Координат[\S ]+?центр[\S ]+?WGS-\d+\)*\s*–*—*\s*[NS]\s*\d+[\'’"°\s]+\d+[\'’"°\s]+\d+[\.,]\d+[\'’"°\s]+;*\s*[EW]\s*\d+[\'’"°\s]+\d+[\'’"°\s]+\d+[\.,]\d+[\'’"°]*',
                            address_clean, re.IGNORECASE)
                        if center:
                            center = center.group(0)
                            lat = dms_to_decimal(
                                normalize_coordinates(
                                    re.search(r'[NS]\s*\d+[\'’"°\s]+\d+[\'’"°\s]+\d+[\.,]\d+[\'’"°]*', center,
                                              re.IGNORECASE).group(0).replace('N ', '').replace('S ', '').strip()))
                            lon = dms_to_decimal(
                                normalize_coordinates(
                                    re.search(r'[EW]\s*\d+[\'’"°\s]+\d+[\'’"°\s]+\d+[\.,]\d+[\'’"°]*', center,
                                              re.IGNORECASE).group(0).replace('E ', '').replace('W ', '').strip()))
                            if lat is not None and lon is not None:
                                coordinates['Центр объекта'] = {}
                                coordinates['Центр объекта']['Центр объекта'] = [lat, lon]
                                coordinates['Центр объекта']['coordinate_system'] = 'wgs84'
                    elif section == 'OBJECT_TYPE' and not current_account_card.object_type:
                        gray_roi = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
                        _, thresh_roi = cv2.threshold(gray_roi, 150, 255, cv2.THRESH_BINARY)
                        data = pytesseract.image_to_data(thresh_roi, config='--oem 3 --psm 6', lang='rus',
                                                         output_type=Output.DICT)
                        for idx in range(len(data['text'])):
                            if data['text'][idx] == '+':
                                x_pos = data['left'][idx]
                                w = crop.shape[1]
                                third = w // 3
                                if x_pos <= third:
                                    current_account_card.object_type = 'Памятник'
                                elif third < x_pos <= third * 2:
                                    current_account_card.object_type = 'Ансамбль'
                                else:
                                    current_account_card.object_type = 'Достопримечательное место'
                                break
                    elif section == 'GENERAL_CLASSIFICATION' and not current_account_card.general_classification:
                        gray_roi = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
                        _, thresh_roi = cv2.threshold(gray_roi, 150, 255, cv2.THRESH_BINARY)
                        data = pytesseract.image_to_data(thresh_roi, config=symbol_config, lang='rus',
                                                         output_type=Output.DICT)
                        for idx in range(len(data['text'])):
                            if data['text'][idx] == '+':
                                x_pos = data['left'][idx]
                                w = crop.shape[1]
                                fourth = w // 4
                                if x_pos <= fourth:
                                    current_account_card.general_classification = 'Памятник археологии'
                                elif fourth < x_pos <= fourth * 2:
                                    current_account_card.general_classification = 'Памятник истории'
                                elif fourth * 2 < x_pos <= fourth * 3:
                                    current_account_card.general_classification = 'Памятник градостроительства и архитектуры'
                                else:
                                    current_account_card.general_classification = 'Памятник монументального искусства'
                                break
                    elif section == 'DESCRIPTION':
                        if not current_account_card.description:
                            current_account_card.description = block_text
                        # Извлечение координат из описания
                        data = pytesseract.image_to_data(crop, config='--oem 3 --psm 3', lang='rus',
                                                         output_type=Output.DICT)
                        north_x = east_x = north_y = east_y = lat = lon = None
                        max_offset = 100
                        j = 0
                        for i_idx in range(len(data['text']) - 1):
                            text_to_check = (data['text'][i_idx] + ' ' + data['text'][i_idx + 1]).lower().replace('\n',
                                                                                                                  '')
                            if 'северная широта' in text_to_check or 'восточная долгота' in text_to_check:
                                y_pos = data['top'][i_idx]
                                image_type = crop[y_pos:, :]
                                gray1 = cv2.cvtColor(image_type, cv2.COLOR_RGB2GRAY)
                                _, thresh1 = cv2.threshold(gray1, 170, 255, cv2.THRESH_BINARY)
                                data2 = pytesseract.image_to_data(thresh1, config='--oem 3 --psm 3',
                                                                  lang='rus', output_type=Output.DICT)
                                for k in range(len(data2['text'])):
                                    text_lower2 = data2['text'][k].strip().lower()
                                    if 'северная' in text_lower2:
                                        north_x = data2['left'][k]
                                    elif 'восточная' in text_lower2:
                                        east_x = data2['left'][k]
                                    if north_x and north_x - max_offset <= data2['left'][k] <= north_x + max_offset:
                                        lat = data2['text'][k]
                                        north_y = data2['top'][k]
                                        if len(lat) < 12 and k + 1 < len(data2['text']):
                                            if 11 <= len(lat) + len(
                                                    data2['text'][k + 1]) <= 12 and north_y - max_offset <= \
                                                    data2['top'][k + 1] <= north_y + max_offset:
                                                lat += data2['text'][k + 1]
                                    elif east_x and east_x - max_offset <= data2['left'][k] <= east_x + max_offset:
                                        lon = data2['text'][k]
                                        east_y = data2['top'][k]
                                        if len(lon) < 12 and k + 1 < len(data2['text']):
                                            if 11 <= len(lon) + len(
                                                    data2['text'][k + 1]) <= 12 and east_y - max_offset <= data2['top'][
                                                k + 1] <= east_y + max_offset:
                                                lon += data2['text'][k + 1]
                                    if lat and lon and re.search(r'\d+[\'’"°\s]+\d+[\'’"°\s]+\d+[\.,]\d+[\'’"°\s]+',
                                                                 lat) and \
                                            re.search(r'\d+[\'’"°\s]+\d+[\'’"°\s]+\d+[\.,]\d+[\'’"°\s]+', lon) and \
                                            north_y - max_offset <= east_y <= north_y + max_offset:
                                        if 'Каталог координат' not in coordinates:
                                            coordinates['Каталог координат'] = {}
                                        lat_dec = dms_to_decimal(normalize_coordinates(lat.strip()))
                                        lon_dec = dms_to_decimal(normalize_coordinates(lon.strip()))
                                        if lat_dec is not None and lon_dec is not None:
                                            coordinates['Каталог координат'][str(j + 1)] = [lat_dec, lon_dec]
                                            coordinates['Каталог координат']['coordinate_system'] = 'wgs84'
                                            lat = lon = None
                                            j += 1
                    elif section == 'USAGE' and not current_account_card.usage:
                        gray_roi = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
                        _, thresh_roi = cv2.threshold(gray_roi, 150, 255, cv2.THRESH_BINARY)
                        data = pytesseract.image_to_data(thresh_roi, config='--oem 3 --psm 6', lang='rus',
                                                         output_type=Output.DICT)
                        for idx in range(len(data['text'])):
                            if data['text'][idx] == '+':
                                x_pos = data['left'][idx]
                                y_pos = data['top'][idx]
                                h, w = crop.shape[:2]
                                x_second = w // 2
                                y_tenth = h // 10
                                if x_pos <= x_second:
                                    if y_tenth < y_pos <= y_tenth * 2:
                                        current_account_card.usage = 'Музеи, архивы, библиотеки'
                                    elif y_tenth * 2 < y_pos <= y_tenth * 3:
                                        current_account_card.usage = 'Организации науки и образования'
                                    elif y_tenth * 3 < y_pos <= y_tenth * 4:
                                        current_account_card.usage = 'Театрально-зрелищные организации'
                                    elif y_tenth * 4 < y_pos <= y_tenth * 5:
                                        current_account_card.usage = 'Органы власти и управления'
                                    elif y_tenth * 5 < y_pos <= y_tenth * 6:
                                        current_account_card.usage = 'Воинские части'
                                    elif y_tenth * 6 < y_pos <= y_tenth * 7:
                                        current_account_card.usage = 'Религиозные организации'
                                    elif y_tenth * 7 < y_pos <= y_tenth * 8:
                                        current_account_card.usage = 'Организации здравоохранения'
                                    elif y_tenth * 8 < y_pos <= y_tenth * 9:
                                        current_account_card.usage = 'Организации транспорта'
                                    elif y_tenth * 9 < y_pos <= y_tenth * 10:
                                        current_account_card.usage = 'Производственные организации'
                                else:
                                    if y_tenth < y_pos <= y_tenth * 2:
                                        current_account_card.usage = 'Организации торговли'
                                    elif y_tenth * 2 < y_pos <= y_tenth * 3:
                                        current_account_card.usage = 'Организации общественного питания'
                                    elif y_tenth * 3 < y_pos <= y_tenth * 4:
                                        current_account_card.usage = 'Гостиницы, отели'
                                    elif y_tenth * 4 < y_pos <= y_tenth * 5:
                                        current_account_card.usage = 'Офисные помещения'
                                    elif y_tenth * 5 < y_pos <= y_tenth * 6:
                                        current_account_card.usage = 'Жилье'
                                    elif y_tenth * 6 < y_pos <= y_tenth * 7:
                                        current_account_card.usage = 'Парки, сады'
                                    elif y_tenth * 7 < y_pos <= y_tenth * 8:
                                        current_account_card.usage = 'Некрополи, захоронения'
                                    elif y_tenth * 8 < y_pos <= y_tenth * 9:
                                        current_account_card.usage = 'Не используется'
                                    elif y_tenth * 9 < y_pos <= y_tenth * 10:
                                        current_account_card.usage = 'Иное'
                    elif section == 'DISCOVERY_INFO' and not current_account_card.discovery_info:
                        current_account_card.discovery_info = block_text
                    elif section == 'COMPILER' and not current_account_card.compiler:
                        current_account_card.compiler = block_text
                    elif section == 'COMPILE_DATE' and not current_account_card.compile_date:
                        current_account_card.compile_date = block_text

                for blk in compile_date_blocks:
                    x1, y1, x2, y2 = blk['box']
                    crop = img_rgb[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue
                    date_text = pytesseract.image_to_string(crop, lang='rus+eng', config='--oem 3 --psm 7').strip()
                    if not current_account_card.compile_date and date_text:
                        current_account_card.compile_date = date_text

                # Обработка изображений и их подписей
                for img in image_blocks:
                    x1, y1, x2, y2 = img['box']
                    crop = img_rgb[y1:y2, x1:x2]
                    if crop.size == 0:
                        continue
                    section = img['assigned_section']
                    caption_text = ''
                    linked_cap = img.get('linked_caption')
                    if linked_cap:
                        cap_x1, cap_y1, cap_x2, cap_y2 = linked_cap['box']
                        cap_crop = img_rgb[cap_y1:cap_y2, cap_x1:cap_x2]
                        if cap_crop.size > 0:
                            caption_text = pytesseract.image_to_string(cap_crop, lang='rus+eng',
                                                                       config='--oem 3 --psm 6').strip()
                    # Определяем категорию для supplement
                    if section in ('ADDRESS',):
                        category = 'address'
                    elif section in ('DESCRIPTION', 'USAGE', 'DISCOVERY_INFO', 'OBJECT_TYPE'):
                        category = 'description'
                    else:
                        category = 'description'  # по умолчанию
                    img_path = os.path.join(folder, f"img_{page_num}_{x1}.png")
                    cv2.imwrite(img_path, cv2.cvtColor(crop, cv2.COLOR_RGB2BGR))
                    supplement_content[category].append({"label": caption_text, "source": img_path})
                    logger.info(f"Изображение сохранено в {category}: {img_path}")

            # Если каталог координат не заполнен, попробуем извлечь из таблиц (если модель их нашла)
            if not coordinates.get('Каталог координат'):
                # Можно попытаться найти таблицы и обработать их через старый алгоритм
                # Для простоты оставим как есть, координаты будут только из описания или KML
                pass

    except Exception:
        logger.error("ACCOUNT CARDS FATAL ERROR")
        logger.error(traceback.format_exc())

    # Постобработка KML
    kml_path = KMLParser.find_kml_for_pdf(file, True)
    if kml_path:
        logger.info(f"📌 Найден KML файл: {kml_path}")
        kml_coordinates = {}
        try:
            if isinstance(kml_path, list):
                for path in kml_path:
                    kml_coordinates.update(KMLParser.parse_kml_file(path))
            else:
                kml_coordinates = KMLParser.parse_kml_file(kml_path)
        except Exception as e:
            traceback.print_exc()
            logger.warning(f"❌ Не удалось извлечь координаты из KML: {e}")
        if kml_coordinates:
            coordinates = kml_coordinates
            logger.info("✅ Координаты успешно заменены на достоверные из KML")
        else:
            logger.warning("❌ Не удалось извлечь координаты из KML")
    else:
        logger.info("ℹ️ KML файл не найден, используем координаты из PDF")

    current_account_card.supplement = supplement_content
    current_account_card.coordinates = coordinates
    current_account_card.is_processing = False
    current_account_card.save()
    if current_account_card.name:
        connect_account_card_to_heritage(current_account_card.name, progress_json)


@shared_task
def error_handler_account_cards(task, exception, exception_desc):
    logger.error(f"Задача {task.id} завершилась с ошибкой: {exception} {exception_desc}")
    progress_json = redis_client.get(task.id)
    if progress_json is None:
        progress_json = redis_client.get('celery-task-meta-' + str(task.id))
    progress_json = json.loads(progress_json)
    for account_card_id, source in progress_json['file_groups'].items():
        if source['processed'] != 'True':
            account_card = ObjectAccountCard.objects.get(id=account_card_id)
            account_card.delete()
    progress_json['time_ended'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raise type(exception)({"error_text": str(exception), "progress_json": progress_json}) from exception


if __name__ == "__main__":
    # Для локального тестирования (заглушка)
    pass
