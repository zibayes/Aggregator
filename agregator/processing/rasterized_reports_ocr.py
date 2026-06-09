import re
import traceback

import fitz  # PyMuPDF
import ocrmypdf
import logging

logger = logging.getLogger(__name__)


def detect_rasterization_pdf(document, text_threshold=10, rasterization_threshold=0.8, pages_to_check=10):
    """Функция распознавания растеризированных документов"""
    result = []
    len_test = min(len(document), pages_to_check)
    for page_num in range(len_test):
        page = document[page_num]

        # 1. Получаем словарь со всей информацией о содержимом страницы
        page_dict = page.get_text("dict")

        # 2. Анализируем текстовые блоки
        total_text_len = 0
        for block in page_dict.get("blocks", []):
            if block.get("type", -1) == 0:  # 0 — это текстовый блок
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        total_text_len += len(span.get("text", "").strip())

        # 3. Анализируем изображения
        image_list = page.get_images(full=True)
        has_images = len(image_list) > 0

        # Если текста мало, но изображения есть — страница, вероятно, растеризована
        if total_text_len < text_threshold and has_images:
            result.append("rasterized")
        elif total_text_len >= text_threshold:
            result.append("has_text_layer")
        else:
            result.append("unknown")
    if result.count("rasterized") / len_test > rasterization_threshold:
        return True
    return False


def add_pdf_text_layer_ocr(input_path: str, output_path: str):
    """Функция создания текстового слоя для растеризированных документов"""
    try:
        ocrmypdf.ocr(
            input_path,
            output_path,
            language='rus',  # rus+eng
            deskew=True,
            force_ocr=True,
            optimize=0
        )
        logger.info(f"OCR завершен успешно для файла: {input_path}")
    except Exception as e:
        logger.error(f"Ошибка OCR: {e}")
        logger.error(traceback.format_exc())


def is_likely_mojibake(text, threshold=0.5):
    """Функция проверки на битый или закодированный файл"""
    if not text.strip():
        return False

    # Разрешённые категории
    allowed = re.compile(
        r'[а-яёА-ЯЁ]+'
    )
    total = len(text)
    if total == 0:
        return False
    suspicious = sum(1 for ch in text if not allowed.match(ch))
    ratio = suspicious / total
    print(total)
    return ratio > threshold


def report_rasterization_check_and_process(file_path, pages_to_check=8):
    document = fitz.open(file_path)
    if file_path.endswith('.pdf') and type != 'images' and (
            detect_rasterization_pdf(document, pages_to_check) or is_likely_mojibake(
        ''.join([page.get_text() for page in document[:pages_to_check]]))):
        add_pdf_text_layer_ocr(file_path, file_path)
