import io
import json
import os
import re
import tkinter as tk
from datetime import datetime
from tkinter import filedialog
from typing import List, Optional

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

from .files_saving import load_raw_open_lists
from .hash import calculate_file_hash
from .models import OpenLists
from .redis_config import redis_client
from .celery_task_template import process_documents

FRAME_BORDERS = [204, 800, 48, 545]  # each need to '* koef' [204, 778, 63, 555]
FIO_BORDERS = [390, 512, 40, 550]  # [390, 490, 60, 560]
WORKS_BORDERS = [415, 602, 40, 550]  # [415, 580, 60, 560]
OBJECT_BORDERS = [295, 472, 40, 550]  # [295, 450, 60, 560]
DATES_BORDERS = [515, 622, 240, 530]  # [515, 600, 260, 540]
LIST_NUMBER_BORDERS = [183, 240, 180, 420]  # [196, 235, 200, 420]
FIO_SKLON_BORDERS = [235, 300, 160, 445]  # [245, 285, 182, 437]

MAX_VAL = 255
UPSCALE = [1]
MONTHS = {'января': '01', 'февраля': '02', 'марта': '03', 'апреля': '04', 'мая': '05', 'июня': '06', 'июля': '07',
          'августа': '08', 'сентября': '09', 'октября': '10', 'ноября': '11', 'декабря': '12', }
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
pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'  # 'C:/Program Files/Tesseract-OCR/tesseract.exe'


# language_tool = language_tool_python.LanguageTool('ru-RU')

def choose_image_file() -> str:
    # file_path = filedialog.askopenfilename(title="Выберите файл изображения", filetypes=[("Изображения", "*.png *.jpg")])
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
    """Алгоритм Брезенхэма для определения промежуточных пикселей между двумя заданными точками."""
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
        if not 38 * koef <= lines[0][0] <= 58 * koef:  # <= 53 * koef
            return False
        if not 59 * koef <= lines[1][0] <= 80 * koef:  # <= 75 * koef
            return False
        if not 132 * koef <= lines[2][0] <= 207 * koef:
            return False
        if not 182 * koef <= lines[3][0] <= 282 * koef:
            return False
        if not 257 * koef <= lines[4][0] <= 432 * koef:
            return False
        if len(lines) == 6 and not 407 * koef <= lines[5][0] <= 762 * koef:  # <= 525 * koef
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
    # cv2.imwrite(folder + "/gaps.png", img)
    return gaps


def change_img_perspect(img, dst_pts, src_pts=None, shift=0):
    h, w = img.shape[:2]
    if src_pts is None:
        src_pts = np.array([[0, 0], [w, 0], [0, h], [w, h]], dtype=np.float32)
    return cv2.warpPerspective(src=img,
                               # матрица преобразования src_pts -> dst_pts
                               M=cv2.getPerspectiveTransform(src_pts, dst_pts),
                               dsize=(w + shift, h))


def change_brightness_and_perspect(img, koef):
    h, w = img.shape[:2]
    shift = int(koef * 12)
    img = change_img_perspect(img, dst_pts=np.array(
        [[-0.02 * w + shift, 0], [0.99 * w + shift, 0], [0 + shift, h], [w + shift, h]],
        dtype=np.float32), shift=shift)
    img = cv2.convertScaleAbs(img, alpha=1.2, beta=0)
    return img


def preprocess_string(string: str) -> str:
    string = string.replace('=', '').replace('’', '').replace('`', '').replace('^', '').replace('‘', '') \
        .replace('!', '').replace('|', '').replace('$', '').replace('@', 'а').replace('_', '').replace('&', '').strip()
    return string


def preprocess_date(string: str) -> str:
    string = string.replace('20242.', '2024  г.').replace('20252.', '2025  г.').replace('2924', '2024') \
        .replace('/', '1').replace('З', '3').strip()  # .replace('Г', '1')
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
    """Automatically apply suggestions to the text."""
    # Get the positions of 4-byte encoded characters in the text because without
    # carrying out this step, the offsets of the matches could be incorrect.
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
        print('Spell checker error:', exception)
    finally:
        return string


def compare_two_texts(extracted_text, extracted_text_twin):
    extracted_len = len(extracted_text) >= 45
    twin_len = len(extracted_text_twin) >= 45
    if extracted_len and not twin_len:
        return spell_check(extracted_text)  # language_tool.correct(extracted_text)
    elif not extracted_len and twin_len:
        return spell_check(extracted_text_twin)  # language_tool.correct(extracted_text_twin)
    else:
        extracted_len = []
        twin_len = []
        for word in WORDS_TO_CHECK:
            extracted_len.append(fuzz.partial_ratio(word, extracted_text))
            twin_len.append(fuzz.partial_ratio(word, spell_check(extracted_text_twin)))
        if sum(extracted_len) > sum(twin_len):
            return spell_check(extracted_text)  # language_tool.correct(extracted_text)
        else:
            return spell_check(extracted_text_twin)  # language_tool.correct(extracted_text_twin)


@shared_task(bind=True)
def process_open_lists(self, open_lists_ids, user_id):
    return process_documents(self, open_lists_ids, user_id, 'open_lists', load_function=load_raw_open_lists,
                             process_function=open_list_ocr)


def open_list_ocr(pdf_path, progress_recorder, pages_count, total_processed,
                  open_list_id, progress_json, task_id, time_on_start):
    open_lists = OpenLists.objects.all()
    for open_list in open_lists:
        if open_list.source and open_list.id != open_list_id and os.path.isfile(open_list.source.path):
            file_hash = calculate_file_hash(pdf_path)
            open_list_hash = calculate_file_hash('uploaded_files/' + open_list.source.name)
            if file_hash == open_list_hash:
                raise FileExistsError(
                    f"Такой файл уже загружен в систему: {progress_json['file_groups'][str(open_list_id)]['origin_filename']}")

    dates_borders = None
    document = fitz.open(pdf_path)
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
        page = document.load_page(page_number)

        image_filename = translit(pdf_path[:pdf_path.rfind(".")], 'ru', reversed=True)
        image_filename = image_filename + ".png"
        if not os.path.isfile(image_filename):
            pix = page.get_pixmap(dpi=300)
            pil_img = Image.open(io.BytesIO(pix.tobytes("png")))
            ratio = (pil_img.width / 596 + pil_img.height / 842) / 2
            print(pil_img.width, pil_img.height)
            print(ratio)
            if ratio > 2.1:
                new_ratio = 2.08
                pil_img = pil_img.resize(
                    (int(pil_img.width / ratio * new_ratio), int(pil_img.height / ratio * new_ratio)),
                    Image.LANCZOS)
            pil_img.save(image_filename, format='PNG', optimize=True)

        list_data = {'Номер листа': '', 'Держатель': '', 'Объект': '', 'Работы': '', 'Начало срока': '',
                     'Конец срока': '', 'Тип работ': ''}
        binarization_threshold = 120
        img_colored = cv2.imread(image_filename)
        img_colored, image = image_binarization_plain(img_colored, binarization_threshold)
        '''
        image, img_colored = borders_cut(image, img_colored)
        angle = get_image_angle(img_colored)
        if angle is not None:
            img_colored = rotate_image(img_colored, angle)
        img_colored, image = image_binarization_plain(img_colored, binarization_threshold)
        image, img_colored = borders_cut(image, img_colored)
        '''
        try:
            sauvola_bin = sauvola_binarization(img_colored)
        except np.core._exceptions._ArrayMemoryError as error:
            print('sauvola error: ' + str(error))
            sauvola_bin = None
        object_sauvola = dates_sauvola = dates_rgb = None

        height, width = image.shape[:2]
        ratio = (width / 596 + height / 842) / 2  # image ratio for different resolutions
        koef = UPSCALE[0] * ratio  # int(UPSCALE[0] * ratio)

        frame_borders = [int(x * koef) for x in FRAME_BORDERS]
        frame = sauvola_bin[frame_borders[0]:frame_borders[1],
                frame_borders[2]:frame_borders[3]] if sauvola_bin is not None else image[
                                                                                   frame_borders[0]:frame_borders[1],
                                                                                   frame_borders[2]:frame_borders[3]]
        frame_rgb = img_colored[frame_borders[0]:frame_borders[1], frame_borders[2]:frame_borders[3]]
        frame_sauvola = sauvola_bin[frame_borders[0]:frame_borders[1],
                        frame_borders[2]:frame_borders[3]] if sauvola_bin is not None else None
        # cv2.imwrite(folder + "/frame.png", frame_rgb)
        list_number = fio = fio_sklon = object = works = dates = None

        no_lines = []
        line_length = 485
        line_color_thresh = 80
        lines = extract_data_by_lines(frame, koef, line_length, line_color_thresh, find_sloped_lines=False)
        print('lines 1', lines)
        len_lines = len(lines)
        lines = check_lines(lines, koef)
        while not lines and len_lines <= 10 and binarization_threshold <= 200:
            if binarization_threshold <= 200:
                if len_lines == 0:
                    binarization_threshold += 10
                else:
                    binarization_threshold += 5
                img_colored, image = image_binarization_plain(img_colored, binarization_threshold)
                frame = image[frame_borders[0]:frame_borders[1], frame_borders[2]:frame_borders[3]]
                frame_rgb = img_colored[frame_borders[0]:frame_borders[1], frame_borders[2]:frame_borders[3]]
            else:
                line_color_thresh += 5
            lines = extract_data_by_lines(frame, koef, line_length, line_color_thresh)
            print('lines while', binarization_threshold, lines)
            len_lines = len(lines)
            lines = check_lines(lines, koef)
        if not lines:
            lines = []
        if 5 <= len(lines) <= 6:
            print(lines)
            margin = int(30 * koef)
            object = frame_rgb[lines[1][0] + margin:lines[2][0], :]
            object = change_brightness_and_perspect(object, koef)
            object_sauvola = frame_sauvola[lines[1][0] + margin:lines[2][0], :] if frame_sauvola is not None else None
            # cv2.imwrite(folder + "/object_frame.png", object)
            fio = frame_rgb[lines[2][0] + margin:lines[3][0]]
            fio = change_brightness_and_perspect(fio, koef)
            # cv2.imwrite(folder + "/fio_frame.png", fio)
            margin = int(32 * koef)
            works = frame_rgb[lines[3][0] + margin:lines[4][0], :]
            works = change_brightness_and_perspect(works, koef)
            works_sauvola = frame_sauvola[lines[3][0] + margin:lines[4][0], :] if frame_sauvola is not None else None
            # cv2.imwrite(folder + "/works_frame.png", works)
            margin = [int(35 * koef), int(90 * koef), int(200 * koef)]
            dates_sauvola = frame_sauvola[lines[4][0] + margin[0]:lines[4][0] + margin[1],
                            margin[2]:] if frame_sauvola is not None else None
            dates_rgb = frame_rgb[lines[4][0] + margin[0]:lines[4][0] + margin[1], margin[2]:]
            dates_sauvola = frame_sauvola[lines[4][0] + margin[0]:lines[4][0] + margin[1], margin[2]:]
            # cv2.imwrite(folder + "/dates_frame.png", dates)
        else:
            no_lines.append(image_filename)
            gaps = get_gaps(frame, koef, 250)
            index = 0

            koef_values = [
                int(12 * koef),  # 0
                int(40 * koef),  # 1
                int(10 * koef),  # 2
                int(22 * koef),  # 3
                int(14 * koef),  # 4
                int(23 * koef),  # 5
                int(30 * koef),  # 6
                int(8 * koef),  # 7
                int(4 * koef),  # 8
                int(5 * koef)  # 9
            ]

            for i in range(len(gaps) - 1):
                if (gaps[i + 1] - gaps[i] < koef_values[0]) or (i == 0 and gaps[i] < koef_values[0]):
                    continue
                if index == 0 and gaps[i] > koef_values[1]:
                    list_number = frame[:gaps[i] + koef_values[9]]
                    if list_number.size == 0:
                        list_number = None
                if index == 1 and gaps[i + 1] - gaps[i] > koef_values[2]:
                    fio_sklon = frame[gaps[i]:gaps[i + 1]]
                    if fio_sklon.size == 0:
                        fio_sklon = None
                elif index == 3 and gaps[i + 1] - gaps[i] > koef_values[3]:
                    object = frame[gaps[i] + koef_values[3]:gaps[i + 1] - koef_values[8]]
                    if object.size == 0:
                        object = None
                elif index == 5 and gaps[i + 1] - gaps[i] > koef_values[4]:
                    fio = frame[gaps[i]:gaps[i + 1] - koef_values[9]]
                    if fio.size == 0:
                        fio = None
                elif index == 6 and gaps[i + 1] - gaps[i] > koef_values[3]:
                    works = frame[gaps[i] + koef_values[5]:gaps[i + 1]]
                    if works.size == 0:
                        works = None
                elif index == 8 and koef_values[6] > gaps[i + 1] - gaps[i] > koef_values[0]:
                    dates = frame[gaps[i] + koef_values[7]:gaps[i + 1] + koef_values[8]]
                    dates_rgb = frame_rgb[gaps[i] + koef_values[7]:gaps[i + 1] + koef_values[8]]
                    if dates.size == 0:
                        dates = None
                index += 1

        if not (fio is not None and object is not None
                and works is not None and dates is not None):
            fio_borders = [int(x * koef) for x in FIO_BORDERS]
            fio = image[fio_borders[0]:fio_borders[1], fio_borders[2]:fio_borders[3]]
            # cv2.imwrite(folder + "/fio.png", fio)

            works_borders = [int(x * koef) for x in WORKS_BORDERS]
            works = image[works_borders[0]:works_borders[1], works_borders[2]:works_borders[3]]
            gaps = get_gaps(works, koef, 240)
            gap_num = 0
            gap_interval = int(36 * koef)
            for i in range(len(gaps) - 1):
                if (gaps[i + 1] - gaps[i] < gap_interval) or (i == 0 and gaps[i] < gap_interval):
                    continue
                gap_num = i
                break
            works = img_colored[works_borders[0]:works_borders[1], works_borders[2]:works_borders[3]]
            if len(gaps) > 1:
                works = works[gaps[gap_num] + int(24 * koef):gaps[gap_num + 1] if len(gaps) > 1 else len(works)]
            if works.size > 0:
                pass
                # cv2.imwrite(folder + "/works.png", works)
            else:
                works = img_colored[works_borders[0]:works_borders[1], works_borders[2]:works_borders[3]]

            object_borders = [int(x * koef) for x in OBJECT_BORDERS]
            object = image[object_borders[0]:object_borders[1], object_borders[2]:object_borders[3]]
            gaps = get_gaps(object, koef, 250)
            gap_num = 0
            gap_interval = int(21 * koef)
            for i in range(len(gaps) - 1):
                if (gaps[i + 1] - gaps[i] < gap_interval) or (i == 0 and gaps[i] < gap_interval):
                    continue
                gap_num = i
                break
            object = img_colored[object_borders[0]:object_borders[1], object_borders[2]:object_borders[3]]
            if len(gaps) > 1:
                object = object[
                         gaps[gap_num] + int(24 * koef):(gaps[gap_num + 1] if len(gaps) > 1 else len(object)) - int(
                             5 * koef)]
            if object.size > 0:
                pass
                # cv2.imwrite(folder + "/object.png", object)
            else:
                object = img_colored[object_borders[0]:object_borders[1], object_borders[2]:object_borders[3]]

            dates_borders = [int(x * koef) for x in DATES_BORDERS]
            dates = image[dates_borders[0]:dates_borders[1], dates_borders[2]:dates_borders[3]]
            dates_rgb = img_colored[dates_borders[0]:dates_borders[1], dates_borders[2]:dates_borders[3]]
        if not list_data['Номер листа']:
            list_number_borders = [int(x * koef) for x in LIST_NUMBER_BORDERS]
            list_number = img_colored[list_number_borders[0]:list_number_borders[1],
                          list_number_borders[2]:list_number_borders[3]]
            list_number = cv2.convertScaleAbs(list_number, alpha=1.2, beta=0)
            # cv2.imwrite(folder + "/list_number.png", list_number)
            extracted_text = preprocess_list_number(extract_text_from_image(list_number, '1'))
            list_number = re.search(r'№[ \n]*.*\d+-*\d*.*', extracted_text, re.IGNORECASE)
            if list_number:
                list_data['Номер листа'] = list_number.group(0)
            else:
                list_data['Номер листа'] = extracted_text.strip()
        if not list_data['Держатель']:
            extracted_text = extract_text_from_image(fio, '1')
            list_holder = re.search(r'[А-ЯЁ]+[а-яё]+[ \n]+[А-ЯЁ]+[а-яё]+[ \n]+[А-ЯЁ]+[а-яё]+', extracted_text)
            if not list_holder or len(list_holder.group(0)) <= 12:
                fio_sklon_borders = [int(x * koef) for x in FIO_SKLON_BORDERS]
                fio_sklon = img_colored[fio_sklon_borders[0]:fio_sklon_borders[1],
                            fio_sklon_borders[2]:fio_sklon_borders[3]]
                # cv2.imwrite(folder + "/fio_sklon.png", fio_sklon)
                extracted_text = extract_text_from_image(fio_sklon, '1')
                list_holder = re.search(r'[А-ЯЁ]+[а-яё]+[ \n]+[А-ЯЁ]+[а-яё]+[ \n]+[А-ЯЁ]+[а-яё]+',
                                        extracted_text)
            if list_holder:
                list_data['Держатель'] = list_holder.group(0)
            else:
                list_data['Держатель'] = extracted_text.strip()
        if not list_data['Объект']:
            extracted_text = preprocess_string(extract_text_from_image(object, '1'))
            if object_sauvola is not None:
                extracted_text_twin = preprocess_string(extract_text_from_image(object_sauvola, '1'))
                list_data['Объект'] = compare_two_texts(extracted_text, extracted_text_twin)

        if not list_data['Работы']:
            extracted_text = preprocess_string(extract_text_from_image(works, '1')).lower()
            extracted_text = spell_check(extracted_text)
            # extracted_text = language_tool.correct(extracted_text)

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
            # extracted_text = best_text_similarity_text

            '''
            extracted_text = ''.join([char for char in extracted_text if char.isalpha() or char.isspace()])

            min_dist = 99
            min_dist_works = ''
            for works_in_list in works_types:
                dist = Levenshtein.distance(extracted_text, works_in_list)
                if dist < min_dist:
                    min_dist = dist
                    min_dist_works = works_in_list
            if min_dist_works:
                extracted_text = min_dist_works
            '''

            list_data['Работы'] = extracted_text
        if not list_data['Начало срока'] or not list_data['Конец срока']:
            dates_list = extract_dates_from_image(dates, koef)
            if len(dates_list) < 3:
                if dates_borders is None and dates_rgb is None:
                    dates_borders = [int(x * koef) for x in DATES_BORDERS]
                    dates_rgb = image[dates_borders[0]:dates_borders[1], dates_borders[2]:dates_borders[3]]
                binarization_threshold = 120
                while len(dates_list) < 3 and binarization_threshold <= 200:
                    binarization_threshold += 10
                    dates_rgb, dates = image_binarization_plain(dates_rgb, binarization_threshold)
                    dates_list = extract_dates_from_image(dates, koef)

            # imgz_dates = dates # img_colored[515*koef:600*koef, 260*koef:540*koef]
            if len(dates_list) >= 2 and dates_list[0][1] > dates_list[1][1]:
                dates_list[0] = list(dates_list[0])
                dates_list[1] = list(dates_list[1])
                dates_list[0][1], dates_list[1][1] = dates_list[1][1], dates_list[0][1]
            if dates_sauvola is not None:
                dates_bin_list = cut_dates_from_image(dates_sauvola, dates_list, koef)
            else:
                dates_bin_list = cut_dates_from_image(dates, dates_list, koef)
            dates_list = cut_dates_from_image(dates_rgb, dates_list, koef)
            period_dates = []
            date_index = 0
            extracted_text = None
            all_sucess = [False for _ in dates_list]
            if len(dates_list) > 2:  # if dates_list == 3
                i = 0
                for date in dates_list:
                    if i > 1 and all(all_sucess[:2]):
                        break
                    # date = change_brightness_and_perspect(date, koef)
                    extracted_text = preprocess_date(extract_text_from_image(date, '6'))
                    date_form = re.search(r'«*\d+»* *.[^ ]+ \d{4}', extracted_text, re.IGNORECASE)
                    if date_form:
                        date_form = date_form.group(0)
                    if date_form and date_check(date_form):
                        period_dates.append(date_form)
                        # cv2.imwrite(folder + f"/date{i}.png", date)
                        all_sucess[i] = True
                    else:
                        j = 0
                        date_is_correct = False
                        while j < 6 and (not date_form or not date_is_correct):
                            if j == 1 or j == 5:
                                h, w = date.shape[:2]
                                date = change_img_perspect(date, dst_pts=np.array(
                                    [[-0.02 * w, 0], [0.99 * w, 0], [0, h], [w, h]], dtype=np.float32))
                            elif 4 > j > 1 or j == 0:
                                date = cv2.convertScaleAbs(date, alpha=1.2, beta=0)
                            elif j == 4:
                                date = dates_bin_list[i]
                            extracted_text = preprocess_date(extract_text_from_image(date, '6'))
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
                        # cv2.imwrite(folder + f"/date{i}.png", date)
                        if date_is_correct:
                            all_sucess[i] = True
                    i += 1
            else:
                extracted_text = preprocess_date(extract_text_from_image(dates, '6'))
                '''
                substr_place = extracted_text.find('Срок')
                if substr_place > 0:
                    initial_str = 'Срок действия открытого листа'
                    distance = Levenshtein.distance(extracted_text[substr_place:substr_place+len(initial_str)], initial_str)
                    # [А-Яа-яёЁA-Za-z \n,0-9:.;"()«»\\–-]+?(?=Дата)
                    if distance < 12:
                extracted_text = extracted_text.replace('20242.', '2024  г.').replace('/', '1').replace('З',
                                                                                                        '3').replace('[', '').strip()
                '''
                period_dates = re.findall(r'«*\d+»* *.[^ ]+ \d{4}', extracted_text, re.IGNORECASE)
            if len(period_dates) > 0:
                date = period_dates[0]
                if not re.search(r'«*\d+»* *.[^ ]+ \d{4}', date, re.IGNORECASE) and len(period_dates) > 2:
                    date = period_dates[2]
                if date:
                    list_data['Начало срока'] = date_to_dots_format(date)
            if len(period_dates) > 1:
                date = period_dates[1]
                if date:
                    list_data['Конец срока'] = date_to_dots_format(date)
            '''
            if all(list_data.values()):
                break
            '''
        total_processed[0] += len(document)
        os.remove(image_filename)
        open_list = OpenLists.objects.get(id=open_list_id)
        open_list.number = list_data['Номер листа']
        open_list.holder = list_data['Держатель']
        open_list.object = list_data['Объект']
        open_list.works = list_data['Работы']
        open_list.start_date = list_data['Начало срока']
        open_list.end_date = list_data['Конец срока']
        open_list.is_processing = False
        open_list.save()


@shared_task
def error_handler_open_lists(task, exception, exception_desc):
    print(f"Задача {task.id} завершилась с ошибкой: {exception} {exception_desc}")
    progress_json = redis_client.get(task.id)
    if progress_json is None:
        progress_json = redis_client.get('celery-task-meta-' + str(task.id))
    progress_json = json.loads(progress_json)
    for open_list_id, source in progress_json['file_groups'].items():
        print(open_list_id, source)
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
