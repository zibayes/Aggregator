from pathlib import Path
from typing import List
import re
from PIL import Image
import io

import fitz

IMAGE_MIN_SIZE = 150
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
}


def extract_captions(text: str) -> List:
    text = text.replace("\n", "")
    captions = []
    caption_types = ["Рис.", "Приложение"]
    for caption_type in caption_types:
        captions_count = text.count(caption_type)
        for i in range(captions_count):
            first_encounter = text.find(caption_type)
            if i != captions_count - 1:
                last_encounter = text[first_encounter + 4:].find(caption_type)
            else:
                last_encounter = len(text)
            caption = text[first_encounter:last_encounter]
            captions.append(caption)
            text = text[first_encounter + 4:]

        for i in range(len(captions)):
            for j in range(len(captions)):
                if i == j:
                    continue
                cap1 = re.search(caption_type + r' .*\d+', captions[i], re.IGNORECASE)
                if cap1:
                    cap1 = re.search(r'\d+', cap1.group(0), re.IGNORECASE).group(0)
                else:
                    continue
                cap2 = re.search(caption_type + r' .*\d+', captions[j], re.IGNORECASE)
                if cap2:
                    cap2 = re.search(r'\d+', cap2.group(0), re.IGNORECASE).group(0)
                else:
                    continue
                if int(cap1) < int(cap2):
                    captions[i], captions[j] = captions[j], captions[i]

    return captions


def extract_images_with_captions(text, page, page_number, document, folder, supplement_content, extracted_images):
    captions = extract_captions(text)
    image_list = page.get_images(full=True)
    caption_index = 0
    for img_index, img in enumerate(image_list):
        if captions and caption_index < len(captions):
            image_text = captions[caption_index]
            caption_index += 1
        img_index = img[0]
        if img_index in extracted_images:  # and not captions
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
        avg_color = sum([(x[0] + x[1] + x[2]) / 3 if isinstance(x, tuple) else x / 3 for x in pixels]) / num_pixels
        if avg_color == 255 or avg_color == 0:
            continue
        image_filename = f"page_{page_number + 1}_img_{img_index}.png"
        current_folder = folder
        if captions:
            image_text = image_text.replace('\n', '')
            lowered_image_text = image_text.lower()
            if 'общий вид участка обследования' in lowered_image_text or 'общий вид участка' in lowered_image_text or 'общие виды' in lowered_image_text:
                current_folder += '/Общий вид'
                supplement_content["object_fotos"].append({"label": image_text,
                                                           "source": current_folder + "/" + image_filename})
            elif 'карта' in lowered_image_text or 'карты' in lowered_image_text:
                current_folder += '/Карты'
                supplement_content["maps"].append({"label": image_text,
                                                   "source": current_folder + "/" + image_filename})
            elif 'схема' in lowered_image_text or 'схемы' in lowered_image_text:
                current_folder += '/Схемы'
                supplement_content["schemas"].append({"label": image_text,
                                                      "source": current_folder + "/" + image_filename})
            elif 'спутниковый снимок' in lowered_image_text:
                current_folder += '/Спутниковые снимки'
                supplement_content["maps"].append({"label": image_text,
                                                   "source": current_folder + "/" + image_filename})
            elif 'шурф' in lowered_image_text:
                current_folder += '/Шурфы'
                Path(current_folder).mkdir(exist_ok=True)
                pit = re.search(r'Шурф.* № *\d+', image_text, re.IGNORECASE)
                if pit:
                    current_folder += '/Ш' + pit.group(0)[1:]
                supplement_content["pits_fotos"].append({"label": image_text,
                                                         "source": current_folder + "/" + image_filename})
            elif 'раскоп' in lowered_image_text:
                current_folder += '/Раскопы'
                supplement_content["excavation_fotos"].append({"label": image_text,
                                                               "source": current_folder + "/" + image_filename})
            elif 'зачистка' in lowered_image_text or 'заичистка' in lowered_image_text:
                current_folder += '/Шурфы'
                Path(current_folder).mkdir(exist_ok=True)
                pit = re.search(r'Зачистка.* № *\d+', image_text, re.IGNORECASE)
                if pit:
                    current_folder += '/З' + pit.group(0)[1:]
                supplement_content["pits_fotos"].append({"label": image_text,
                                                         "source": current_folder + "/" + image_filename})
            elif 'врезка' in lowered_image_text:
                current_folder += '/Шурфы'
                Path(current_folder).mkdir(exist_ok=True)
                pit = re.search(r'Врезка.* № *\d+', image_text, re.IGNORECASE)
                if pit:
                    current_folder += '/В' + pit.group(0)[1:]
                supplement_content["pits_fotos"].append(
                    {"label": image_text, "source": current_folder + "/" + image_filename})
            else:
                current_folder += '/Иное'
                Path(current_folder).mkdir(exist_ok=True)
                supplement_content["other"].append(
                    {"label": image_text, "source": current_folder + "/" + image_filename})
        else:
            current_folder += '/Без подписей'
            Path(current_folder).mkdir(exist_ok=True)
            supplement_content["no_captions"].append(
                {"source": current_folder + "/" + image_filename})
        Path(current_folder).mkdir(exist_ok=True)
        with open(current_folder + "/" + image_filename, "wb") as img_file:
            img_file.write(image_bytes)


if __name__ == '__main__':
    pass
