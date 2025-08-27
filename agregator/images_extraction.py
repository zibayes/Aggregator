import io
import re
from pathlib import Path

import cv2
import fitz
import numpy as np
import pytesseract
from PIL import Image
# from tensorflow.keras.models import load_model

from agregator.models import UserTasks
from .files_saving import raw_open_lists_save
from .open_lists_ocr import process_open_lists, error_handler_open_lists, \
    borders_cut, get_image_angle, image_binarization_plain, rotate_image
from .torch_image_classifier import PyTorchImageClassifier

pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'  # 'C:/Program Files/Tesseract-OCR/tesseract.exe'
IMAGE_MIN_SIZE = 150
CURRENT_OPEN_LIST_RGB = (205, 221, 229)
RGB_ACCURACY = 20
# image_classification_model = load_model('image_classificator.keras')
PYTORCH_CLASS_NAMES = ["Карты", "Материал", "Общий вид", "Открытые листы",
                       "Спутниковые снимки", "Схемы", "Шурфы"]
pytorch_classifier = PyTorchImageClassifier('image_classifier.pth', PYTORCH_CLASS_NAMES)

SUPPLEMENT_CONTENT = {
    "maps": [],
    "schemas": [],
    "object_fotos": [],
    "pits_fotos": [],
    "excavation_fotos": [],
    "material_fotos": [],
    "heritage_info": [],
    "other": [],
    "no_captions": [],
    "title_page": [],
    "docs": [],
    "open_list": [],
}

ACCOUNT_CARD_CONTENT = {
    "maps": [],
    "schemas": [],
    "object_fotos": [],
}


def hex_to_rgb(hex_color):
    # Удаляем символ '#' если он есть
    hex_color = hex_color.lstrip('#')

    # Преобразуем строки в целые числа
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    return r, g, b


COLOR_PALETTE = [hex_to_rgb('#deecf1'), hex_to_rgb('#adc3d4'), hex_to_rgb('#bdc2d2')]
ACCURACY_PALETTE = 15
COLOR_PARTS = [38, 8, 8]
ACCURACY_PARTS = 8
COLOR_PALETTE_LEN = len(COLOR_PALETTE)
COLOR_PALETTE_ARRAY = np.array(COLOR_PALETTE)
LOWER_BOUNDS = COLOR_PALETTE_ARRAY - ACCURACY_PALETTE
UPPER_BOUNDS = COLOR_PALETTE_ARRAY + ACCURACY_PALETTE


def is_image_open_list(avg_color, pil_img):
    if not all([CURRENT_OPEN_LIST_RGB[i] - RGB_ACCURACY <= avg_color[i] <=
                CURRENT_OPEN_LIST_RGB[i] + RGB_ACCURACY for i in range(3)]):
        return False
    pixels = list(pil_img.getdata())
    pixels_len = len(pixels)
    pixels_array = np.array(pixels)

    for part in range(COLOR_PALETTE_LEN):
        near_enough = np.sum(
            np.all((pixels_array >= LOWER_BOUNDS[part]) & (pixels_array <= UPPER_BOUNDS[part]), axis=1))
        near_part = (near_enough / pixels_len) * 100
        if not (COLOR_PARTS[part] - ACCURACY_PARTS <= near_part <= COLOR_PARTS[part] + ACCURACY_PARTS):
            return False
    return True


def image_rotate(pil_img):
    image_np = np.array(pil_img)
    if image_np.shape[2] == 3:
        image_cv = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)
    else:
        image_cv = image_np

    image_bytes = None
    try:
        osd_data = pytesseract.image_to_osd(image_cv, output_type=pytesseract.Output.DICT)
        print(osd_data)
        if osd_data['rotate'] == 90:
            image_cv = cv2.rotate(image_cv, cv2.ROTATE_90_CLOCKWISE)
        elif osd_data['rotate'] == 270:
            image_cv = cv2.rotate(image_cv, cv2.ROTATE_90_COUNTERCLOCKWISE)
    except Exception as e:
        print(e)
    success, encoded_image = cv2.imencode('.png', image_cv)
    if success:
        image_bytes = encoded_image.tobytes()
        pil_img = Image.open(io.BytesIO(image_bytes))
    return pil_img, image_bytes


def get_pil_image_from_pixmap(pixmap):
    if pixmap.n == 1:  # Черно-белое изображение
        img = Image.frombytes("L", [pixmap.width, pixmap.height], pixmap.samples)
        img = img.convert("RGB")
    elif pixmap.n == 3:  # RGB
        img = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
    elif pixmap.n == 4:  # RGBA
        img = Image.frombytes("RGBA", [pixmap.width, pixmap.height], pixmap.samples)
        img = img.convert("RGB")
    else:
        raise ValueError("Неподдерживаемый формат изображения.")
    return img


def calculate_average_rgb(img):
    pixels = list(img.getdata())

    r_total = 0
    g_total = 0
    b_total = 0

    # Считаем сумму значений для каждого канала
    for r, g, b in pixels:
        r_total += r
        g_total += g
        b_total += b

    # Вычисляем средние значения
    num_pixels = len(pixels)
    average_r = r_total // num_pixels
    average_g = g_total // num_pixels
    average_b = b_total // num_pixels

    return average_r, average_g, average_b


def predict_image_class(img):
    # Используем PyTorch вместо TensorFlow
    predicted_class, confidence = pytorch_classifier.predict(img)

    # Маппинг классов на старые названия (если нужно)
    class_mapping = {
        'Карты': 'Карты',
        'Материал': 'Материал',
        'Общий вид': 'Общий вид',
        'Открытые листы': 'Открытый лист',
        'Спутниковые снимки': 'Спутниковые снимки',
        'Схемы': 'Схемы',
        'Шурфы': 'Шурфы'
    }

    return class_mapping.get(predicted_class, 'Документы'), confidence


'''
def predict_image_class(img):
    image_size = 500
    img = img.resize((image_size, image_size))
    img_array = np.array(img)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = img_array / 255.0
    # y_pred = image_classification_model.predict(img_array)
    # predicted_class = np.argmax(y_pred, axis=1)
    predicted_class = [0]  # TODO!!! return TENSORFLOW
    labels = ['Документы', 'Карты', 'Материал', 'Общий вид', 'Открытый лист', 'Спутниковые снимки', 'Шурфы']
    return labels[predicted_class[0]]
'''


def extract_captions(text: str) -> tuple:
    text = text.replace("\n", "")
    captions = []
    captions_nums = []
    caption_types = ["Рис.", "Рисунок", "Приложение"]
    for caption_type in caption_types:
        caption_len = len(caption_type)
        captions_count = text.count(caption_type)
        for i in range(captions_count):
            first_encounter = text.find(caption_type)
            if i != captions_count - 1:
                last_encounter = text[first_encounter + caption_len:].find(caption_type)
            else:
                last_encounter = len(text)
            caption = text[first_encounter:last_encounter]
            captions.append(caption)
            number = re.search(caption_type + r' .*?\d+', captions[i], re.IGNORECASE)
            if number:
                number = re.search(r'\d+', number.group(0), re.IGNORECASE).group(0)
                captions_nums.append(number)
            else:
                captions_nums.append('')
            text = text[first_encounter + caption_len:]
        captions_len = len(captions)
        for i in range(captions_len):
            for j in range(captions_len):
                if i == j:
                    continue
                cap1 = re.search(caption_type + r' .*?\d+', captions[i], re.IGNORECASE)
                if cap1:
                    cap1 = re.search(r'\d+', cap1.group(0), re.IGNORECASE).group(0)
                else:
                    continue
                cap2 = re.search(caption_type + r' .*?\d+', captions[j], re.IGNORECASE)
                if cap2:
                    cap2 = re.search(r'\d+', cap2.group(0), re.IGNORECASE).group(0)
                else:
                    continue
                if int(cap1) < int(cap2):
                    captions[i], captions[j] = captions[j], captions[i]
                    captions_nums[i], captions_nums[j] = captions_nums[j], captions_nums[i]

    return captions, captions_nums


def preprocess_open_list(pix):
    image_bytes = pix.tobytes("png")
    nparr = np.frombuffer(image_bytes, np.uint8)
    img_colored = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
    img_colored = cv2.cvtColor(img_colored, cv2.COLOR_BGR2RGB)
    binarization_threshold = 120
    img_colored, image = image_binarization_plain(img_colored, binarization_threshold)
    image, img_colored = borders_cut(image, img_colored)
    angle = get_image_angle(img_colored)
    if angle is not None:
        img_colored = rotate_image(img_colored, angle)
    img_colored, image = image_binarization_plain(img_colored, binarization_threshold)
    image, img_colored = borders_cut(image, img_colored)
    pil_img = Image.fromarray(img_colored)
    ratio = (pil_img.width / 596 + pil_img.height / 842) / 2
    print(pil_img.width, pil_img.height)
    print(ratio)
    if ratio > 2.1:
        new_ratio = 2.08
        pil_img = pil_img.resize(
            (int(pil_img.width / ratio * new_ratio), int(pil_img.height / ratio * new_ratio)),
            Image.LANCZOS)
    print(pil_img.width, pil_img.height)
    return pil_img


def extract_images_with_captions(text, page, page_number, document, folder,
                                 supplement_content, extracted_images, user_id, origin_name, is_public,
                                 upload_source=None):
    captions, captions_nums = extract_captions(text)
    image_list = page.get_images(full=True)
    caption_index = 0
    for img_index, img in enumerate(image_list):
        if captions and caption_index < len(captions):
            image_text = captions[caption_index]
            image_num = captions_nums[caption_index]
            caption_index += 1
        img_index = img[0]
        if img_index in extracted_images:
            continue
        extracted_images.append(img_index)
        base_image = document.extract_image(img_index)
        image_bytes = base_image["image"]
        pixmap = fitz.Pixmap(image_bytes)
        if pixmap.width <= IMAGE_MIN_SIZE or pixmap.height <= IMAGE_MIN_SIZE:
            continue
        image = Image.open(io.BytesIO(image_bytes))
        pixels = list(image.getdata())
        num_pixels = len(pixels)
        avg_color = sum([(x[0] + x[1] + x[2]) // 3 if isinstance(x, tuple) else x // 1 for x in pixels]) // num_pixels
        if avg_color == 255 or avg_color == 0:
            continue
        image_filename = f"page_{page_number + 1}_img_{img_index}.png"
        current_folder = folder
        pil_img = get_pil_image_from_pixmap(pixmap)
        avg_color = calculate_average_rgb(pil_img)
        if captions:
            image_text = image_text.replace('\n', '')
            lowered_image_text = image_text.lower()
            if 'общий вид участка обследования' in lowered_image_text or 'общий вид участка' in lowered_image_text or 'общие виды' in lowered_image_text:
                current_folder += '/Общий вид'
                supplement_content["object_fotos"].append({"label": image_text, "image_num": image_num,
                                                           "source": current_folder + "/" + image_filename})
            elif 'карта' in lowered_image_text or 'карты' in lowered_image_text:
                current_folder += '/Карты'
                supplement_content["maps"].append({"label": image_text, "image_num": image_num,
                                                   "source": current_folder + "/" + image_filename})
            elif 'схема' in lowered_image_text or 'схемы' in lowered_image_text:
                current_folder += '/Схемы'
                supplement_content["schemas"].append({"label": image_text, "image_num": image_num,
                                                      "source": current_folder + "/" + image_filename})
            elif 'спутниковый снимок' in lowered_image_text:
                current_folder += '/Спутниковые снимки'
                supplement_content["maps"].append({"label": image_text, "image_num": image_num,
                                                   "source": current_folder + "/" + image_filename})
            elif 'шурф' in lowered_image_text:
                current_folder += '/Шурфы'
                Path(current_folder).mkdir(exist_ok=True)
                pit = re.search(r'Шурф.*? № *\d+', image_text, re.IGNORECASE)
                image_folder = None
                if pit:
                    image_folder = 'Ш' + pit.group(0)[1:]
                    current_folder += '/' + image_folder
                supplement_content["pits_fotos"].append({"label": image_text, "image_num": image_num,
                                                         "source": current_folder + "/" + image_filename,
                                                         'folder': image_folder})
            elif 'раскоп' in lowered_image_text:
                current_folder += '/Раскопы'
                supplement_content["excavation_fotos"].append({"label": image_text, "image_num": image_num,
                                                               "source": current_folder + "/" + image_filename})
            elif 'зачистка' in lowered_image_text or 'заичистка' in lowered_image_text:
                current_folder += '/Шурфы'
                Path(current_folder).mkdir(exist_ok=True)
                pit = re.search(r'Зачистка.*? № *\d+', image_text, re.IGNORECASE)
                image_folder = None
                if pit:
                    image_folder = 'З' + pit.group(0)[1:]
                    current_folder += '/' + image_folder
                supplement_content["pits_fotos"].append({"label": image_text, "image_num": image_num,
                                                         "source": current_folder + "/" + image_filename,
                                                         'folder': image_folder})
            elif 'врезка' in lowered_image_text:
                current_folder += '/Шурфы'
                Path(current_folder).mkdir(exist_ok=True)
                pit = re.search(r'Врезка.*? № *\d+', image_text, re.IGNORECASE)
                image_folder = None
                if pit:
                    image_folder = 'В' + pit.group(0)[1:]
                    current_folder += '/' + image_folder
                supplement_content["pits_fotos"].append(
                    {"label": image_text, "image_num": image_num, "source": current_folder + "/" + image_filename,
                     'folder': image_folder})
            elif 'открытый лист' in lowered_image_text or is_image_open_list(avg_color, pil_img) or (
                    ((result := predict_image_class(pil_img))[0] == 'Открытый лист' and result[1] >= 0.75)):
                pix = page.get_pixmap(dpi=300)
                try:
                    pil_img = preprocess_open_list(pix)
                except Exception as e:
                    print('OpenList preprocess failed: ' + str(e))
                image_bytes = pil_img.tobytes()
                print(image_filename)
                # pil_img, image_bytes = image_rotate(pil_img)
                current_folder += '/Открытый лист'
                Path(current_folder).mkdir(exist_ok=True)
                supplement_content["open_list"].append(
                    {"label": image_text, "image_num": image_num, "source": current_folder + "/" + image_filename})

                open_lists_ids = raw_open_lists_save([pil_img], user_id, is_public, origin_name, upload_source)
                task = process_open_lists.apply_async((open_lists_ids, user_id),
                                                      link_error=error_handler_open_lists.s())
                user_task = UserTasks(user_id=user_id, task_id=task.task_id, files_type='open_list',
                                      upload_source=upload_source)
                user_task.save()
            else:
                print(image_filename)
                pil_img, image_bytes = image_rotate(pil_img)
                image_class, confidence = predict_image_class(pil_img)
                print(image_class)
                if image_class == 'Документы' and confidence >= 0.75:
                    current_folder += '/Документы'
                    Path(current_folder).mkdir(exist_ok=True)
                    supplement_content["docs"].append(
                        {"label": image_text, "image_num": image_num, "source": current_folder + "/" + image_filename})
                elif image_class == 'Карты' and confidence >= 0.75:
                    current_folder += '/Карты'
                    Path(current_folder).mkdir(exist_ok=True)
                    supplement_content["maps"].append(
                        {"label": image_text, "image_num": image_num, "source": current_folder + "/" + image_filename})
                elif image_class == 'Материал' and confidence >= 0.75:
                    current_folder += '/Материал'
                    Path(current_folder).mkdir(exist_ok=True)
                    supplement_content["material_fotos"].append(
                        {"label": image_text, "image_num": image_num, "source": current_folder + "/" + image_filename})
                else:
                    current_folder += '/Иное'
                    Path(current_folder).mkdir(exist_ok=True)
                    supplement_content["other"].append(
                        {"label": image_text, "image_num": image_num, "source": current_folder + "/" + image_filename})
        else:
            print(image_filename)
            pil_img, image_bytes = image_rotate(pil_img)
            image_class, confidence = predict_image_class(pil_img)
            print(image_class)
            if page_number == 0:
                current_folder += '/Титульник'
                Path(current_folder).mkdir(exist_ok=True)
                supplement_content["title_page"].append(
                    {"source": current_folder + "/" + image_filename})
            elif is_image_open_list(avg_color, pil_img) or (image_class == 'Открытый лист' and confidence >= 0.75):
                pix = page.get_pixmap(dpi=300)
                try:
                    pil_img = preprocess_open_list(pix)
                except Exception as e:
                    print('OpenList preprocess failed: ' + str(e))
                image_bytes = pil_img.tobytes()
                current_folder += '/Открытый лист'
                Path(current_folder).mkdir(exist_ok=True)
                supplement_content["open_list"].append(
                    {"source": current_folder + "/" + image_filename})
                open_lists_ids = raw_open_lists_save([pil_img], user_id, is_public, origin_name, upload_source)

                task = process_open_lists.apply_async((open_lists_ids, user_id),
                                                      link_error=error_handler_open_lists.s())
                user_task = UserTasks(user_id=user_id, task_id=task.task_id, files_type='open_list',
                                      upload_source=upload_source)
                user_task.save()
            elif image_class == 'Документы':
                current_folder += '/Документы'
                Path(current_folder).mkdir(exist_ok=True)
                supplement_content["docs"].append(
                    {"source": current_folder + "/" + image_filename})
            elif image_class == 'Карты':
                current_folder += '/Карты'
                Path(current_folder).mkdir(exist_ok=True)
                supplement_content["maps"].append(
                    {"source": current_folder + "/" + image_filename})
            elif image_class == 'Материал':
                current_folder += '/Материал'
                Path(current_folder).mkdir(exist_ok=True)
                supplement_content["material_fotos"].append(
                    {"source": current_folder + "/" + image_filename})
            else:
                current_folder += '/Без подписей'
                Path(current_folder).mkdir(exist_ok=True)
                supplement_content["no_captions"].append(
                    {"source": current_folder + "/" + image_filename})
        Path(current_folder).mkdir(exist_ok=True)
        with open(current_folder + "/" + image_filename, "wb") as img_file:
            img_file.write(image_bytes)


def insert_supplement_links(report_parts: dict) -> None:
    caption_types = ["Рис.", "Рисунок", "Приложение"]

    for part, text in report_parts.items():
        offset = 0
        links = []
        for caption_type in caption_types:
            links += re.finditer(caption_type + r'[\s\d\-;,]+', text, re.IGNORECASE)  # \s*\d+\s*-*\s*\d*

        links_len = len(links)
        for i in range(links_len):
            for caption_type in caption_types:
                numbers = []

                link_number = re.search(caption_type + r'[\s\d\-;,]+', links[i].group(0), re.IGNORECASE)
                if link_number:
                    link_number = re.search(r'[\s\d\-;,]+', link_number.group(0), re.IGNORECASE).group(0).strip()
                    if '-' not in link_number:
                        numbers.append(link_number)
                    else:
                        delimiters = r'[;,]'
                        number_groups = re.split(delimiters, link_number)
                        number_groups = [item for item in number_groups if item]
                        for group in number_groups:
                            group = group.split('-')
                            if len(group) == 2 and group[0] and group[1]:
                                numbers += [str(x) for x in list(range(int(group[0]), int(group[1]) + 1))]
                            elif len(numbers) == 2 and group[0]:
                                numbers += group
                                numbers.pop(-1)
                            else:
                                continue
                    final_string = ''
                    j = 0
                    numbers_len = len(numbers)
                    for number in numbers:
                        if j != numbers_len - 1:
                            # final_string += f'<a href="javascript:;" onclick="openGalleryFromLink(\'image-link-{number}\')">' + number + '</a>, '
                            final_string += f'<a href="#image-link-{number}">' + number + '</a>, '
                        else:
                            # final_string += f'<a href="javascript:;" onclick="openGalleryFromLink(\'image-link-{number}\')">' + number + '</a>'
                            final_string += f'<a href="#image-link-{number}">' + number + '</a>'
                        j += 1
                    final_string = ' [' + final_string + ']'
                    text = text[:links[i].end() + offset] + final_string + text[links[i].end() + offset:]
                    offset += len(final_string)
        report_parts[part] = text


if __name__ == '__main__':
    pass
