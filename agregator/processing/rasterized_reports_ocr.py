import re
import time
import traceback

import fitz  # PyMuPDF
import ocrmypdf
import logging

import queue
import threading
from agregator.processing.ocrmypdf_progress_channel import set_queue
from agregator.celery_task_template import progress_update

logger = logging.getLogger(__name__)
PLUGIN_PATH = 'agregator/processing/ocrmypdf_progress_plugin.py'


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


def add_pdf_text_layer_ocr(input_path: str, output_path: str, progress_recorder_tuple: tuple) -> None:
    """Функция создания текстового слоя для растеризированных документов"""
    q = queue.Queue()
    set_queue(q)
    progress_recorder, task_id, progress_json, current_val, max_val = progress_recorder_tuple
    state = {
        "latest": None,
        "done": False,
        "error": None,
    }
    state_lock = threading.Lock()

    def consumer():
        try:
            progress_json["status"] = "ocr"
            while True:
                item = q.get()
                if item is None:
                    break
                with state_lock:
                    state["latest"] = item
        except Exception as e:
            with state_lock:
                state["error"] = e
                state["done"] = True

    def run_ocr():
        try:
            ocrmypdf.ocr(
                input_path,
                output_path,
                language="rus",
                deskew=True,
                force_ocr=True,
                optimize=0,
                plugins=PLUGIN_PATH,
                invalidate_digital_signatures=True
            )
        except Exception as e:
            with state_lock:
                state["error"] = e
        finally:
            with state_lock:
                state["done"] = True
            q.put(None)

    consumer_thread = threading.Thread(target=consumer, daemon=True)
    ocr_thread = threading.Thread(target=run_ocr, daemon=True)

    consumer_thread.start()
    ocr_thread.start()

    last_signature = None
    update_val = 0.
    try:
        while True:
            with state_lock:
                latest = state["latest"]
                done = state["done"]
                error = state["error"]

            if latest is not None:
                signature = (latest.get("desc"), latest.get("percent"))
                if signature != last_signature:
                    if update_val < 1.:
                        update_val += 0.01
                    progress_json["ocr"] = f"{latest.get('desc')} ({latest.get('percent')}%)"
                    progress_update(progress_recorder, task_id, progress_json, current_val + update_val, max_val)
                    last_signature = signature
                    # logger.info(f'OCRMYPDF signature: {last_signature}')

            if error is not None:
                logger.info(f'error = {error}')
                raise error

            if done:
                break

            time.sleep(0.1)

    finally:
        ocr_thread.join()
        consumer_thread.join()


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


def report_rasterization_check_and_process(file_path, progress_recorder, pages_to_check=8):
    document = fitz.open(file_path)
    if file_path.endswith('.pdf') and type != 'images' and (
            detect_rasterization_pdf(document, pages_to_check) or is_likely_mojibake(
        ''.join([page.get_text() for page in document[:pages_to_check]]))):
        add_pdf_text_layer_ocr(file_path, file_path, progress_recorder)
