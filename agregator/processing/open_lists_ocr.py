import io
import json
import os
import re
import tkinter as tk
from datetime import datetime
from tkinter import filedialog
from typing import List, Optional, Dict, Tuple
import traceback
import time

import Levenshtein
import cv2
import fitz
import numpy as np
import pandas as pd
import pytesseract
import requests
from PIL import Image
from celery import shared_task
from celery_progress.backend import ProgressRecorder
from fuzzywuzzy import fuzz
from language_tool_python.utils import _4_bytes_encoded_positions, Match
from skimage import filters
from transliterate import translit

# Установка переменных окружения для PyTorch до импорта torch
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"

# ------------------- PyTorch и модель -------------------
import torch
import torchvision
from torchvision import transforms as T

from .files_saving import load_raw_open_lists
from agregator.hash import calculate_file_hash
from agregator.models import OpenLists
from agregator.redis_config import redis_client
from agregator.celery_task_template import process_documents

# ------------------- ЛОГГИРОВАНИЕ -------------------
import logging

logger = logging.getLogger(__name__)

# Конфигурация модели (должна совпадать с обучением)
NUM_CLASSES = 7  # 6 классов + фон
DEVICE = torch.device('cuda') if torch.cuda.is_available() else torch.device('cpu')
CONFIDENCE_THRESHOLD = 0.5  # порог уверенности для детекций

# Путь к сохранённым весам модели (необходимо указать актуальный путь)
MODEL_WEIGHTS_PATH = "open_lists_segmenter.pth"

# Маппинг id классов (из обучения) в имена
CATEGORY_ID_TO_NAME = {
    1: "number",
    2: "holder",
    3: "object",
    4: "works",
    5: "start_date",
    6: "end_date"
}

# ------------------------------------------------------------------
# Глобальные константы и настройки (из оригинального кода)
# ------------------------------------------------------------------
FRAME_BORDERS = [204, 800, 48, 545]
FIO_BORDERS = [390, 512, 40, 550]
WORKS_BORDERS = [415, 602, 40, 550]
OBJECT_BORDERS = [295, 472, 40, 550]
DATES_BORDERS = [515, 622, 240, 530]
LIST_NUMBER_BORDERS = [183, 240, 180, 420]
FIO_SKLON_BORDERS = [235, 300, 160, 445]

MAX_VAL = 255
UPSCALE = [1]
MONTHS = {'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04', 'мая': '05', 'июня': '06', 'июля': '07',
          'августа': '08', 'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12'}
WORKS_TYPES = [
    'археологические раскопки на указанном объекте археологического наследия в целях его изучения и сохранения.',
    'археологические раскопки на указанном объекте культурного наследия в целях его изучения и сохранения.',
    'археологические наблюдения на указанном объекте археологического наследия.',
    'археологические разведки с осуществлением локальных земляных работ на указанной '
    'территории в целях выявления объектов археологического наследия, уточнения сведений о '
    'них и планирования мероприятий по обеспечению их сохранности.',
]
WORDS_TO_CHECK = ['участке', 'территории', 'объект', 'Красноярского', 'края', 'археологического', 'строительство']
WORKS_TYPES_SHORTLY = ['раскопки', 'разведки', 'наблюдения']
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'


# language_tool = language_tool_python.LanguageTool('ru-RU')

# ------------------------------------------------------------------
# Вспомогательные функции (без изменений)
# ------------------------------------------------------------------
def choose_image_file() -> str:
    file_path = filedialog.askdirectory(title="Выберите папку")
    if file_path:
        return file_path


def cutting(bin_img, img):
    rows_to_delete = []
    img_len = len(img)
    img_line_len = len(img[0])
    is_white = 250
    is_black = 15
    gray_deviation = 8
    for i in range(img_len):
        red_component = img[i][:, 0]
        green_component = img[i][:, 1]
        blue_component = img[i][:, 2]

        is_trash = np.sum(((red_component >= is_black - 1) & (red_component <= is_white - 1) &
                           (green_component >= is_black - 1) & (green_component <= is_white - 1) &
                           (blue_component >= is_black - 1) & (blue_component <= is_white - 1) &
                           (abs(red_component - green_component) <= gray_deviation) & (
                                   abs(green_component - blue_component) <= gray_deviation) & (
                                   abs(green_component - blue_component) <= gray_deviation)) |
                          ((red_component >= is_white) & (green_component >= is_white) & (blue_component >= is_white)) |
                          ((red_component <= is_black) & (green_component <= is_black) & (blue_component <= is_black)))
        is_trash = (is_trash / img_line_len) * 100
        if is_trash >= 50:
            rows_to_delete.append(i)
    if rows_to_delete:
        bin_img = np.delete(bin_img, rows_to_delete, axis=0)
        img = np.delete(img, rows_to_delete, axis=0)
    return bin_img, img


def cut_one_dimension_and_transpose(bin_img, img):
    bin_img, img = cutting(bin_img, img)

    np.flipud(bin_img)
    np.flipud(img)
    bin_img, img = cutting(bin_img, img)
    np.flipud(bin_img)
    np.flipud(img)

    bin_img = np.transpose(bin_img)
    img = np.transpose(img, (1, 0, 2))

    return bin_img, img


def borders_cut(bin_img, img):
    bin_img, img = cut_one_dimension_and_transpose(bin_img, img)
    bin_img, img = cut_one_dimension_and_transpose(bin_img, img)
    return bin_img, img


def rotate_image(image, angle):
    height, width = image.shape[:2]
    center = (width / 2, height / 2)
    scale = 1
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, scale)
    new_width = int(abs(width * np.cos(np.radians(angle))) + abs(height * np.sin(np.radians(angle))))
    new_height = int(abs(height * np.cos(np.radians(angle))) + abs(width * np.sin(np.radians(angle))))
    rotation_matrix[0, 2] += (new_width / 2) - center[0]
    rotation_matrix[1, 2] += (new_height / 2) - center[1]
    rotated_image = cv2.warpAffine(image, rotation_matrix, (new_width, new_height))
    return rotated_image


def line_slope_degrees(point1: tuple, point2: tuple) -> float:
    if point2[0] - point1[0] == 0:
        return 90.0
    slope = (point2[1] - point1[1]) / (point2[0] - point1[0])
    angle_rad = np.arctan(slope)
    angle_deg = np.degrees(angle_rad)
    return angle_deg


def get_image_angle(image: np.ndarray) -> Optional[float]:
    height, width = image.shape[:2]
    koef = (width / 596 + height / 842) / 2
    min_area = 596 * 842 * koef // 3
    min_long_len = height // 3 * 2
    image_copy = image.copy()
    spread_boarders = int(30 * koef)

    image_copy = cv2.copyMakeBorder(image_copy, spread_boarders, spread_boarders, spread_boarders,
                                    spread_boarders, cv2.BORDER_CONSTANT, None, value=[255, 255, 255])
    gray = cv2.cvtColor(image_copy, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY_INV)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if contours:
        angles = []
        length_groups = {'short': [], 'long': [], 'undefined': []}
        epsilon_factor = 0.001
        for cnt in contours:
            epsilon = epsilon_factor * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            area = cv2.contourArea(approx)
            if area < min_area:
                continue

            max_len = 0
            for i in range(len(approx)):
                if i != len(approx) - 1:
                    sec_ind = i + 1
                else:
                    sec_ind = 0
                line_len = np.sqrt(
                    (approx[sec_ind][0][0] - approx[i][0][0]) ** 2 + (approx[sec_ind][0][1] - approx[i][0][1]) ** 2)
                if max_len < line_len:
                    max_len = line_len
            if max_len > min_long_len:
                long_line_len = max_len - int(80 * koef)
            else:
                long_line_len = int(760 * koef)

            for i in range(len(approx)):
                if i != len(approx) - 1:
                    sec_ind = i + 1
                else:
                    sec_ind = 0
                line_len = np.sqrt(
                    (approx[sec_ind][0][0] - approx[i][0][0]) ** 2 + (approx[sec_ind][0][1] - approx[i][0][1]) ** 2)
                if long_line_len - int(230 * koef) <= line_len <= long_line_len - int(160 * koef):
                    length_groups['short'].append((approx[i][0], approx[sec_ind][0]))
                elif line_len >= long_line_len:
                    length_groups['long'].append((approx[i][0], approx[sec_ind][0]))
                elif max_len - 80 * koef <= line_len:
                    length_groups['undefined'].append((approx[i][0], approx[sec_ind][0]))
        for line in length_groups['long']:
            angle = line_slope_degrees(line[0], line[1])
            if angle < 0:
                angle += 180
            angles.append(angle - 90)
        for line in length_groups['short']:
            angle = line_slope_degrees(line[0], line[1])
            angles.append(angle)
        if not angles:
            for line in length_groups['undefined']:
                angle = line_slope_degrees(line[0], line[1])
                if 135 <= angle <= 45:
                    angles.append(angle - 90)
                elif -135 <= angle <= -45:
                    angle += 180
                    angles.append(angle - 90)
                elif 45 > angle >= 0:
                    angles.append(angle)
                elif 180 <= angle <= 135:
                    angle -= 180
                    angles.append(angle)
                elif -180 <= angle <= -135:
                    angle += 180
                    angles.append(angle)
        if len(angles) > 0:
            return sum(angles) / len(angles)
        else:
            return None
    else:
        return None


def sauvola_binarization(img: np.ndarray) -> np.ndarray:
    threshold = filters.threshold_sauvola(img, window_size=35, k=0.35)
    bin_img = img > threshold
    return bin_img.astype(np.uint8) * 255


def image_binarization_plain(img: np.ndarray, threshold: int = None) -> tuple:
    height, width = img.shape[:2]
    if width <= 598 and height <= 845:
        UPSCALE[0] = 8
        img = cv2.resize(img, None, fx=UPSCALE[0], fy=UPSCALE[0], interpolation=cv2.INTER_LANCZOS4)
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, bin_img = cv2.threshold(img_gray, threshold, MAX_VAL, cv2.THRESH_BINARY)
    return img, bin_img


def extract_text_from_image(image: np.ndarray, psm_conf: str) -> str:
    custom_config = f'--oem 3 --psm {psm_conf}'
    extracted_text = pytesseract.image_to_string(image, lang='rus', config=custom_config)
    return extracted_text


def extract_fio_from_image(image: np.ndarray, koef: float):
    line_length = 490
    line_color_thresh = 18
    return extract_data_by_lines(image, koef, line_length, line_color_thresh)


def extract_dates_from_image(image: np.ndarray, koef: float):
    line_length = 112
    line_color_thresh = 18
    return extract_data_by_lines(image, koef, line_length, line_color_thresh)


def bresenham(x1, y1, x2, y2):
    points = []
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx - dy

    while True:
        points.append((x1, y1))
        if x1 == x2 and y1 == y2:
            break
        err2 = err * 2
        if err2 > -dy:
            err -= dy
            x1 += sx
        if err2 < dx:
            err += dx
            y1 += sy

    return points


def extract_data_by_lines(image: np.ndarray, koef: float, line_length: int, line_color_thresh: int,
                          find_sloped_lines: bool = True) -> List[tuple[int, int]]:
    lines = []
    is_long_line = line_length > 470
    line_length = int(line_length * koef)
    short_check = int(15 * koef)
    len_image = len(image)
    line_deviation = int(3 * koef)
    is_black = 30
    for i in range(0, len_image):
        j = 0
        while j < len(image[i]) - line_length:
            if image[i][j:j + line_length].sum() / len(image[i][j:j + line_length]) < line_color_thresh:
                lines.append((i, j))
                j += line_length
            elif find_sloped_lines and is_long_line and i > line_deviation and i + line_deviation < len_image - 3:
                for k in range(-line_deviation, line_deviation + 1):
                    if len(image[i + k]) < j + line_length:
                        break
                    if image[i][j] < is_black and image[i + k][j + line_length] < is_black:
                        line_points = bresenham(i, j, i + k, j + line_length)
                        pixel_sum = sum(
                            image[x][y] for x, y in line_points)
                        if pixel_sum / len(line_points) <= line_color_thresh:
                            lines.append((i, j))
                            i += line_deviation
                            j += line_length
                            break
            j += 1

    final_list = []
    for line in lines:
        if not final_list and line[0] >= short_check:
            final_list.append(line)
            continue
        acceptance = []
        for val in final_list:
            if abs(line[0] - val[0]) < short_check and abs(line[1] - val[1]) < line_length:
                acceptance.append(False)
            else:
                acceptance.append(True)
        if all(acceptance) and line[0] >= short_check:
            final_list.append(line)
    return final_list


def check_lines(lines: List, koef: float):
    if 5 <= len(lines) <= 6:
        if not 38 * koef <= lines[0][0] <= 58 * koef:
            return False
        if not 59 * koef <= lines[1][0] <= 80 * koef:
            return False
        if not 132 * koef <= lines[2][0] <= 207 * koef:
            return False
        if not 182 * koef <= lines[3][0] <= 282 * koef:
            return False
        if not 257 * koef <= lines[4][0] <= 432 * koef:
            return False
        if len(lines) == 6 and not 407 * koef <= lines[5][0] <= 762 * koef:
            return False
        if not 20 * koef <= lines[1][0] - lines[0][0] <= 24 * koef:
            return False
        if not 57 * koef <= lines[3][0] - lines[2][0] <= 63 * koef:
            return False
        if len(lines) == 6 and not 152 * koef <= lines[5][0] - lines[4][0] <= 156 * koef:
            return False
        return lines
    elif len(lines) > 6:
        new_list = []
        for line in lines:
            if len(new_list) == 0 and 56 * koef <= line[0] <= 71 * koef:
                new_list.append(line)
                continue
            if len(new_list) == 1 and 77 * koef <= line[0] <= 93 * koef and 20 * koef <= line[0] - new_list[0][
                0] <= 24 * koef:
                new_list.append(line)
                continue
            if len(new_list) == 2 and 150 * koef <= line[0] <= 225 * koef:
                new_list.append(line)
                continue
            if len(new_list) == 3 and 200 * koef <= line[0] <= 250 * koef and 57 * koef <= line[0] - new_list[2][
                0] <= 63 * koef:
                new_list.append(line)
                continue
            if len(new_list) == 4 and 275 * koef <= line[0] <= 325 * koef:
                new_list.append(line)
                continue
            if len(new_list) == 5 and 425 * koef <= line[0] <= 525 * koef and 152 * koef <= line[0] - new_list[4][
                0] <= 156 * koef:
                new_list.append(line)
                break
        if len(new_list) == 6:
            return new_list
        return False


def cut_dates_from_image(image: np.ndarray, final_list: List, koef: float):
    line_length = int(130 * koef)
    height = int(15 * koef)
    left_margin = int(5 * koef)
    dates = []
    for date in final_list:
        img = image[date[0] - height:date[0], date[1] + left_margin:date[1] + line_length]
        dates.append(img)
    return dates


def cut_fio_from_image(image: np.ndarray, final_list: List, koef: float):
    line_length = int(490 * koef)
    left_border = int(18 * koef)
    right_border = int(20 * koef)
    pieces = []
    for date in final_list:
        img = image[date[0] - left_border:date[0], date[1] + right_border:date[1] + line_length]
        pieces.append(img)
    return pieces


def date_check(date: str) -> bool:
    date_form = re.search(r'«*\d+»* *.[^ ]+ \d{4}', date, re.IGNORECASE)
    if date_form:
        date_form = date_form.group(0)
        month = re.search(r'[а-яА-ЯёЁ]+', date_form)
        if month:
            month = month.group(0)
            if month in MONTHS.keys():
                numbers = re.findall(r'\d+', date_form)
                if len(numbers) == 2 and len(numbers[0]) <= 2 and len(numbers[1]) == 4:
                    if 0 <= int(numbers[0]) <= 31 and 1980 <= int(numbers[1]) <= 2099:
                        return True
    return False


def date_to_dots_format(date: str) -> str:
    day = re.search(r'(?<!\d)\d{1,2}(?!\d)', date, re.MULTILINE)
    if day:
        day = day.group(0)
        if len(day) < 2:
            day = '0' + day
    else:
        day = '-'
    year = re.search(r'\d{4}', date)
    if year:
        year = year.group(0)
    else:
        year = '-'
    month = re.search(r'[а-яА-ЯёЁ]+', date)
    if month:
        month = month.group(0)
    if month in MONTHS.keys():
        month = MONTHS[month]
    elif month:
        min_dist = 99
        min_dist_month = ''
        for month_in_list in MONTHS.keys():
            dist = Levenshtein.distance(month, month_in_list)
            if dist < min_dist and dist < 5:
                min_dist = dist
                min_dist_month = MONTHS[month_in_list]
        if min_dist_month:
            month = min_dist_month
    else:
        month = '-'
    return day + '.' + month + '.' + year


def get_gaps(image: np.ndarray, koef: float, thresh: int) -> List:
    img = image.copy()
    i = 0
    gaps = []
    gap_size = int(11 * koef)
    while i < len(image):
        if img[i:i + gap_size].sum() / (len(img[i]) * gap_size) > thresh:
            gaps.append(i)
            i += gap_size
        i += 1
    return gaps


def change_img_perspect(img, dst_pts, src_pts=None, shift=0):
    h, w = img.shape[:2]
    if src_pts is None:
        src_pts = np.array([[0, 0], [w, 0], [0, h], [w, h]], dtype=np.float32)
    return cv2.warpPerspective(src=img,
                               M=cv2.getPerspectiveTransform(src_pts, dst_pts),
                               dsize=(w + shift, h))


def change_brightness_and_perspect(img, koef):
    '''
    h, w = img.shape[:2]
    shift = int(koef * 12)
    # 1. Перспектива
    img = change_img_perspect(img, dst_pts=np.array(
        [[-0.02 * w + shift, 0], [0.99 * w + shift, 0], [0 + shift, h], [w + shift, h]],
        dtype=np.float32), shift=shift)
    # 2. Обрезаем чёрные артефакты warp (левые и правые края)
    img = crop_warp_borders(img, shift)
    # 3. Подавление синего фонового шума
    img = remove_blue_noise(img)
    # 4. Бинаризация методом Оцу
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    _, img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # 5. Обратно в RGB (трёхканальное) для совместимости с OCR
    img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
    '''
    return img


def crop_to_main_text(region_rgb: np.ndarray, confidence_threshold: int = 30, padding: int = 5,
                      psm: str = '6') -> np.ndarray:
    """
    Обрезает регион сверху и снизу по границам надёжно распознанных слов (черновой OCR).
    Параметры:
        confidence_threshold: минимальная уверенность слова для учёта (0-100)
        padding: отступ в пикселях от крайних слов
        psm: режим page segmentation для Tesseract
    Возвращает обрезанный RGB регион (или исходный, если обрезка невозможна).
    """
    if region_rgb.size == 0:
        return region_rgb

    config = f'--psm {psm} --oem 3'
    data = pytesseract.image_to_data(region_rgb, lang='rus+eng', config=config,
                                     output_type=pytesseract.Output.DICT)
    valid_ys = []
    n = len(data['text'])
    for i in range(n):
        text = data['text'][i].strip()
        if not text:
            continue
        conf = int(data['conf'][i]) if data['conf'][i] != '-1' else 100
        if conf < confidence_threshold:
            continue
        if len(text) < 2 and not text.isdigit():
            continue
        y = data['top'][i]
        h = data['height'][i]
        valid_ys.append((y, y + h))

    if not valid_ys:
        return region_rgb

    top = min(y for y, _ in valid_ys)
    bottom = max(y for _, y in valid_ys)

    top = max(0, top - padding)
    bottom = min(region_rgb.shape[0], bottom + padding)

    return region_rgb[top:bottom, :]


def crop_warp_borders(img: np.ndarray, margin: int) -> np.ndarray:
    """
    Обрезает левый и правый края на margin пикселей (убирает чёрные артефакты warp),
    сохраняя нетронутыми верхние/нижние границы.
    """
    h, w = img.shape[:2]
    # Обрезаем по ширине: от margin до w - margin//3 (как в predictor)
    return img[:, margin:w - margin // 3]


def remove_blue_noise(image_rgb: np.ndarray) -> np.ndarray:
    """
    Заменяет синие и голубые пиксели (фоновое оформление) на белый цвет.
    Использует HSV: Hue в диапазоне синего, насыщенность выше порога.
    Возвращает копию RGB-изображения.
    """
    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
    lower_blue = np.array([90, 60, 60])
    upper_blue = np.array([140, 255, 255])
    mask = cv2.inRange(hsv, lower_blue, upper_blue)

    # Морфологическое расширение маски (опционально) – убрано, можно добавить при необходимости
    result = image_rgb.copy()
    result[mask > 0] = [255, 255, 255]
    return result


def preprocess_string(string: str) -> str:
    string = string.replace('=', '').replace('’', '').replace('`', '').replace('^', '').replace('‘', '') \
        .replace('!', '').replace('|', '').replace('$', '').replace('@', 'а').replace('_', '').replace('&', '').strip()
    return string


def preprocess_date(string: str) -> str:
    string = string.replace('20242.', '2024  г.').replace('20252.', '2025  г.').replace('2924', '2024') \
        .replace('/', '1').replace('З', '3').strip()
    return string


def preprocess_list_number(string: str) -> str:
    string = string.upper().replace('О', '0').replace('()', '0').replace('З', '3')
    return string


def preprocess_number(string: str) -> str:
    string = string.replace('/', '1').replace('!', '1').replace('|', '1') \
        .replace('Г', '1').replace('[', '1').replace('О', '0').replace('()', '0') \
        .replace('З', '3').replace('б', '6').replace('Б', '6')
    return string


def correct(text: str, matches: List[Match]) -> str:
    for match in matches:
        match.offset -= sum(1 for i in _4_bytes_encoded_positions(text) if i <= match.offset)
    ltext = list(text)
    matches = [match for match in matches if match.replacements]
    errors = [ltext[match.offset:match.offset + match.errorLength]
              for match in matches]
    correct_offset = 0
    for n, match in enumerate(matches):
        frompos, topos = (correct_offset + match.offset,
                          correct_offset + match.offset + match.errorLength)
        if ltext[frompos:topos] != errors[n]:
            continue
        repl = match.replacements[0]
        ltext[frompos:topos] = list(repl)
        correct_offset += len(repl) - len(errors[n])
    return ''.join(ltext)


def spell_check(string: str) -> Optional[str]:
    url = 'http://localhost:8010/v2/check'
    payload = {
        'text': string,
        'language': 'ru'
    }

    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            data = response.json()
            matches = data['matches']
            matches = [Match(match) for match in matches]
            return correct(string, matches)
        return string
    except Exception as exception:
        logger.warning(f'Spell checker error: {exception}')
    finally:
        return string


def pil_to_cv2(pil_img):
    cv2_img = np.array(pil_img)
    if len(cv2_img.shape) == 3:
        if cv2_img.shape[2] == 3:
            cv2_img = cv2.cvtColor(cv2_img, cv2.COLOR_RGB2BGR)
        elif cv2_img.shape[2] == 4:
            cv2_img = cv2.cvtColor(cv2_img, cv2.COLOR_RGBA2BGR)
    return cv2_img


def cv2_to_pil(cv2_img):
    if len(cv2_img.shape) == 3:
        cv2_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(cv2_img)


def compare_two_texts(extracted_text, extracted_text_twin):
    extracted_len = len(extracted_text) >= 45
    twin_len = len(extracted_text_twin) >= 45
    if extracted_len and not twin_len:
        return spell_check(extracted_text)
    elif not extracted_len and twin_len:
        return spell_check(extracted_text_twin)
    else:
        extracted_len = []
        twin_len = []
        for word in WORDS_TO_CHECK:
            extracted_len.append(fuzz.partial_ratio(word, extracted_text))
            twin_len.append(fuzz.partial_ratio(word, spell_check(extracted_text_twin)))
        if sum(extracted_len) > sum(twin_len):
            return spell_check(extracted_text)
        else:
            return spell_check(extracted_text_twin)


# ------------------------------------------------------------------
# Функции загрузки и использования модели
# ------------------------------------------------------------------
def load_model(weights_path: str, num_classes: int, device: torch.device):
    logger.info(f"Загрузка модели из {weights_path} на устройство {device}")
    try:
        if not os.path.isfile(weights_path):
            raise FileNotFoundError(f"Файл модели не найден: {weights_path}")

        start_time = time.time()
        logger.debug("Импорт torchvision.models.detection...")
        # Принудительно импортируем заранее, чтобы избежать проблем с многопоточностью
        from torchvision.models.detection import fasterrcnn_resnet50_fpn, FasterRCNN_ResNet50_FPN_Weights

        logger.debug("Создание архитектуры модели...")
        model = fasterrcnn_resnet50_fpn(
            weights=None,  # Не загружаем предобученные веса
            box_detections_per_img=50,
            box_nms_thresh=0.2,
            box_score_thresh=0.001,
        )
        logger.debug(f"Архитектура создана за {time.time() - start_time:.2f} сек")

        in_features = model.roi_heads.box_predictor.cls_score.in_features
        model.roi_heads.box_predictor = torchvision.models.detection.faster_rcnn.FastRCNNPredictor(
            in_features, num_classes
        )
        model.roi_heads.score_thresh = 0.05
        model.roi_heads.nms_thresh = 0.2
        model.rpn.nms_thresh = 0.5
        model.rpn.pre_nms_top_n_train = 2000
        model.rpn.post_nms_top_n_train = 2000
        model.roi_heads.fg_iou_thresh = 0.7
        model.roi_heads.bg_iou_thresh = 0.3

        logger.debug("Загрузка весов из файла...")
        state_dict = torch.load(weights_path, map_location=device)
        logger.debug(f"Веса загружены за {time.time() - start_time:.2f} сек")

        logger.debug("Применение весов к модели...")
        model.load_state_dict(state_dict)
        logger.debug(f"Состояние загружено за {time.time() - start_time:.2f} сек")

        model.to(device)
        model.eval()
        logger.info(f"Модель успешно загружена (всего {time.time() - start_time:.2f} сек)")
        return model

    except Exception as e:
        logger.error(f"Ошибка при загрузке модели: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        raise


# Загружаем модель один раз при старте модуля
_model = None


def get_model():
    global _model
    if _model is None:
        _model = load_model(MODEL_WEIGHTS_PATH, NUM_CLASSES, DEVICE)
    return _model


def detect_regions(pil_image: Image.Image, confidence_threshold: float = CONFIDENCE_THRESHOLD) -> Dict[str, np.ndarray]:
    try:
        model = get_model()
        transform = T.Compose([T.ToTensor()])
        image_tensor = transform(pil_image).to(DEVICE)

        logger.debug("Выполнение инференса...")
        with torch.no_grad():
            prediction = model([image_tensor])[0]

        keep = prediction['scores'] > confidence_threshold
        boxes = prediction['boxes'][keep].cpu().numpy()
        labels = prediction['labels'][keep].cpu().numpy()
        scores = prediction['scores'][keep].cpu().numpy()

        logger.info(f"Детектировано {len(boxes)} объектов с уверенностью > {confidence_threshold}")

        img_np = np.array(pil_image)
        result = {k: None for k in CATEGORY_ID_TO_NAME.values()}

        class_boxes = {}
        for box, label, score in zip(boxes, labels, scores):
            class_id = int(label)
            class_name = CATEGORY_ID_TO_NAME.get(class_id)
            if class_name is None:
                continue
            if class_name not in class_boxes or score > class_boxes[class_name][1]:
                class_boxes[class_name] = (box, score)

        for class_name, (box, _) in class_boxes.items():
            x1, y1, x2, y2 = box.astype(int)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(img_np.shape[1], x2), min(img_np.shape[0], y2)
            if x2 > x1 and y2 > y1:
                result[class_name] = img_np[y1:y2, x1:x2].copy()
                logger.debug(f"Вырезана область {class_name}: [{x1},{y1},{x2},{y2}]")

        detected_classes = [c for c, v in result.items() if v is not None]
        logger.info(f"Найдены классы: {detected_classes}")
        return result

    except Exception as e:
        logger.error(f"Ошибка при детекции регионов: {type(e).__name__}: {e}")
        logger.error(traceback.format_exc())
        return {k: None for k in CATEGORY_ID_TO_NAME.values()}


# ------------------------------------------------------------------
# Основная функция OCR с использованием модели
# ------------------------------------------------------------------
@shared_task(bind=True)
def process_open_lists(self, open_lists_ids, user_id):
    return process_documents(self, open_lists_ids, user_id, 'open_lists', load_function=load_raw_open_lists,
                             process_function=open_list_ocr)


def open_list_ocr(pdf_path, progress_recorder, pages_count, total_processed,
                  open_list_id, progress_json, task_id, time_on_start):
    logger.info(f"Начало обработки open_list_id={open_list_id}, pdf_path={pdf_path}")
    open_lists = OpenLists.objects.all()
    for open_list in open_lists:
        if open_list.source and open_list.id != open_list_id and os.path.isfile(open_list.source.path):
            file_hash = calculate_file_hash(pdf_path)
            open_list_hash = calculate_file_hash('uploaded_files/' + open_list.source.name)
            if file_hash == open_list_hash:
                raise FileExistsError(
                    f"Такой файл уже загружен в систему: {progress_json['file_groups'][str(open_list_id)]['origin_filename']}")

    document = fitz.open(pdf_path)
    logger.info(f"PDF содержит {len(document)} страниц")
    for page_number in range(len(document)):
        pages_processed = total_processed[0] + page_number
        progress_json['file_groups'][str(open_list_id)]['pages']['processed'] = page_number
        expected_time = ((datetime.now() - time_on_start) / (pages_processed if pages_processed > 0 else 1)) * (sum(
            pages_count.values()) - pages_processed)
        total_seconds = int(expected_time.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        progress_json['expected_time'] = f"{hours:02}:{minutes:02}:{seconds:02}"
        redis_client.set(task_id, json.dumps(progress_json))
        progress_recorder.set_progress(pages_processed, sum(pages_count.values()),
                                       progress_json)

        logger.info(f"Обработка страницы {page_number + 1}/{len(document)}")
        page = document.load_page(page_number)

        pix = page.get_pixmap(dpi=300)
        pil_img = Image.open(io.BytesIO(pix.tobytes("png")))
        ratio = (pil_img.width / 596 + pil_img.height / 842) / 2
        if ratio > 2.1:
            new_ratio = 2.08
            pil_img = pil_img.resize(
                (int(pil_img.width / ratio * new_ratio), int(pil_img.height / ratio * new_ratio)),
                Image.LANCZOS)
        page_koef = (pil_img.width / 596 + pil_img.height / 842) / 2 * UPSCALE[0]

        # Детекция областей моделью
        logger.info("Запуск детекции областей моделью")
        regions = detect_regions(pil_img, confidence_threshold=CONFIDENCE_THRESHOLD)

        # Подготовка переменных для каждого поля
        list_data = {'Номер листа': '', 'Держатель': '', 'Объект': '', 'Работы': '', 'Начало срока': '',
                     'Конец срока': '', 'Тип работ': ''}

        # Обработка номера листа
        if regions.get('number') is not None:
            logger.info("Распознавание номера листа")
            list_number_img = regions['number']
            list_number_img = change_brightness_and_perspect(list_number_img, page_koef)
            extracted_text = preprocess_list_number(extract_text_from_image(list_number_img, '1'))
            list_number_match = re.search(r'№[ \n]*.*\d+-*\d*.*', extracted_text, re.IGNORECASE)
            if list_number_match:
                list_data['Номер листа'] = list_number_match.group(0)
            else:
                list_data['Номер листа'] = extracted_text.strip()
            logger.info(f"Номер листа: {list_data['Номер листа']}")
        else:
            logger.warning("Номер листа не найден")

        # Обработка держателя (ФИО)
        if regions.get('holder') is not None:
            logger.info("Распознавание держателя (ФИО)")
            holder_region = regions['holder']
            holder_region = change_brightness_and_perspect(holder_region, page_koef)
            extracted_text = extract_text_from_image(holder_region, '1')
            list_holder = re.search(r'[А-ЯЁ]+[а-яё]+[ \n]+[А-ЯЁ]+[а-яё]+[ \n]+[А-ЯЁ]+[а-яё]+', extracted_text)
            if list_holder:
                list_data['Держатель'] = list_holder.group(0)
            else:
                list_data['Держатель'] = extracted_text.strip()
            logger.info(f"Держатель: {list_data['Держатель']}")
        else:
            logger.warning("Держатель не найден")

        # Обработка объекта
        if regions.get('object') is not None:
            logger.info("Распознавание объекта")
            object_region = regions['object']
            # 1. Обрезаем "чужие" строки сверху/снизу по данным OCR
            object_region = crop_to_main_text(object_region, confidence_threshold=40, psm='6')
            # 2. Постобработка (перспектива + очистка + бинаризация)
            object_region = change_brightness_and_perspect(object_region, page_koef)
            extracted_text = preprocess_string(extract_text_from_image(object_region, '1'))
            list_data['Объект'] = spell_check(extracted_text)
            logger.info(f"Объект: {list_data['Объект'][:100]}...")
        else:
            logger.warning("Объект не найден")

        # Обработка работ
        if regions.get('works') is not None:
            logger.info("Распознавание работ")
            works_region = regions['works']
            # 1. Обрезаем лишние строки
            works_region = crop_to_main_text(works_region, confidence_threshold=40, psm='6')
            # 2. Постобработка
            works_region = change_brightness_and_perspect(works_region, page_koef)
            extracted_text = preprocess_string(extract_text_from_image(works_region, '1')).lower()

            best_type_similarity = best_text_similarity = 0
            best_type_similarity_text = best_text_similarity_text = ''
            for works_in_list in WORKS_TYPES:
                for work_type in WORKS_TYPES_SHORTLY:
                    if work_type in works_in_list:
                        similarity = fuzz.partial_ratio(work_type, extracted_text)
                        if best_type_similarity < similarity:
                            best_type_similarity = similarity
                            best_type_similarity_text = work_type
                        similarity = fuzz.partial_ratio(works_in_list, extracted_text)
                        if best_text_similarity < similarity:
                            best_text_similarity = similarity
                            best_text_similarity_text = works_in_list
            list_data['Тип работ'] = best_type_similarity_text
            list_data['Работы'] = extracted_text
            logger.info(f"Тип работ: {list_data['Тип работ']}")
        else:
            logger.warning("Работы не найдены")

        # Обработка дат (start_date, end_date)
        if not list_data['Начало срока'] or not list_data['Конец срока']:
            start_date_region = regions.get('start_date')
            start_date_region = change_brightness_and_perspect(start_date_region, page_koef)
            end_date_region = regions.get('end_date')
            end_date_region = change_brightness_and_perspect(end_date_region, page_koef)
            dates_list_regions = []
            if start_date_region is not None:
                dates_list_regions.append(start_date_region)
            if end_date_region is not None:
                dates_list_regions.append(end_date_region)

            if dates_list_regions:
                logger.info(f"Распознавание дат, найдено областей: {len(dates_list_regions)}")
            else:
                logger.warning("Даты не найдены")

            period_dates = []
            for idx, date_region in enumerate(dates_list_regions):
                extracted_text = preprocess_date(extract_text_from_image(date_region, '6'))
                date_form = re.search(r'«*\d+»* *.[^ ]+ \d{4}', extracted_text, re.IGNORECASE)
                if date_form:
                    date_form = date_form.group(0)
                if date_form and date_check(date_form):
                    period_dates.append(date_form)
                    logger.debug(f"Дата {idx + 1} успешно распознана: {date_form}")
                else:
                    # Пробуем улучшить изображение
                    j = 0
                    date_is_correct = False
                    current_date = date_region.copy()
                    while j < 6 and (not date_form or not date_is_correct):
                        if j == 1 or j == 5:
                            h, w = current_date.shape[:2]
                            current_date = change_img_perspect(current_date, dst_pts=np.array(
                                [[-0.02 * w, 0], [0.99 * w, 0], [0, h], [w, h]], dtype=np.float32))
                        elif 4 > j > 1 or j == 0:
                            current_date = cv2.convertScaleAbs(current_date, alpha=1.2, beta=0)
                        elif j == 4:
                            gray = cv2.cvtColor(current_date, cv2.COLOR_RGB2GRAY)
                            current_date = sauvola_binarization(gray)
                        extracted_text = preprocess_date(extract_text_from_image(current_date, '6'))
                        date_form = re.search(r'«*\d+»* *.[^ ]+ \d{4}', extracted_text, re.IGNORECASE)
                        if date_form:
                            date_form = date_form.group(0)
                            date_is_correct = date_check(date_form)
                        else:
                            index = 0
                            for month_in_list in MONTHS.keys():
                                if month_in_list in extracted_text:
                                    index = extracted_text.find(month_in_list)
                                    if index > 0:
                                        extracted_text = preprocess_number(extracted_text[:index]) + \
                                                         ' ' + extracted_text[index:]
                                        break
                            if index > 0:
                                date_form = re.search(r'«*\d+»* *.[^ ]+ \d{4}', extracted_text, re.IGNORECASE)
                                if date_form:
                                    date_form = date_form.group(0)
                                    date_is_correct = date_check(date_form)
                        j += 1
                    period_dates.append(extracted_text)
                    logger.debug(f"Дата {idx + 1} после улучшений: {extracted_text}")

            if len(period_dates) > 0:
                list_data['Начало срока'] = date_to_dots_format(period_dates[0])
                logger.info(f"Начало срока: {list_data['Начало срока']}")
            if len(period_dates) > 1:
                list_data['Конец срока'] = date_to_dots_format(period_dates[1])
                logger.info(f"Конец срока: {list_data['Конец срока']}")

        # Сохраняем результаты в базу
        open_list = OpenLists.objects.get(id=open_list_id)
        open_list.number = list_data['Номер листа']
        open_list.holder = list_data['Держатель']
        open_list.object = list_data['Объект']
        open_list.works = list_data['Работы']
        open_list.start_date = list_data['Начало срока']
        open_list.end_date = list_data['Конец срока']
        open_list.is_processing = False
        open_list.save()
        logger.info(f"Данные сохранены в БД для open_list_id={open_list_id}")

    total_processed[0] += len(document)
    logger.info(f"Обработка завершена для open_list_id={open_list_id}")


@shared_task
def error_handler_open_lists(task, exception, exception_desc):
    logger.error(f"Задача {task.id} завершилась с ошибкой: {exception} {exception_desc}")
    progress_json = redis_client.get(task.id)
    if progress_json is None:
        progress_json = redis_client.get('celery-task-meta-' + str(task.id))
    progress_json = json.loads(progress_json)
    for open_list_id, source in progress_json['file_groups'].items():
        if source['processed'] != 'True':
            open_list = OpenLists.objects.get(id=open_list_id)
            open_list.delete()
    progress_json['time_ended'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raise type(exception)({"error_text": str(exception), "progress_json": progress_json}) from exception


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    file_path = choose_image_file()
    dir = file_path
    for root, dirs, files in os.walk(dir):
        for file in files:
            if not file.lower().endswith('.pdf'):
                continue
            print(file)
            pdf_path = os.path.join(root, file)
            open_list_ocr(file_path, pdf_path)
