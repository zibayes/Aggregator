import copy
import json
from datetime import datetime

import comtypes.client
import fitz  # PyMuPDF
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import re
import pdfplumber
import pandas as pd
from celery import shared_task
from celery_progress.backend import ProgressRecorder
from django_celery_results.models import TaskResult
import redis

from .models import ScientificReport, User
from .hash import calculate_file_hash
import os
from .images_extraction import extract_images_with_captions, SUPPLEMENT_CONTENT
from .files_saving import delete_files_in_directory, load_raw_reports

redis_client = redis.StrictRedis(host='localhost', port=6379, db=0)


def choose_file() -> str:
    # Открываем окно выбора файла
    file_path = filedialog.askopenfilename(title="Выберите PDF файл", filetypes=[("PDF файлы", "*.pdf")])
    if file_path:
        return file_path


@shared_task(bind=True)
def process_reports(self, reports_ids, origin_filenames, user_id):
    progress_recorder = ProgressRecorder(self)
    progress_recorder.set_progress(0, 100, '')
    reports, pages_count = load_raw_reports(reports_ids, ScientificReport)
    # delete_files_in_directory('uploaded_files/users/' + str(user_id), uploaded_files)
    total_processed = [0]
    file_groups = {}
    for report in reports:
        report.source = json.loads(report.source)
        for source in report.source:
            file = source.copy()
            file['origin_name'] = origin_filenames[source['path']]
            file['processed'] = 'False'
            file['pages'] = {'processed': '0', 'all': pages_count[source['path']]}
            if str(report.id) in file_groups.keys():
                file_groups[str(report.id)].append(file)
            else:
                file_groups[str(report.id)] = [file]
    progress_json = {'user_id': user_id, 'file_groups': file_groups, 'file_types': 'scientific_reports',
                     'time_started': datetime.now().strftime(
                         "%Y-%m-%d %H:%M:%S")}
    redis_client.set(self.request.id, json.dumps(progress_json))
    progress_recorder.set_progress(total_processed[0], sum(pages_count.values()), progress_json)
    for current_report in reports:
        i = 0
        for source in current_report.source:
            if not source['path'].lower().endswith(('.pdf', '.doc', '.docx')):
                continue
            progress_json['file_groups'][str(current_report.id)][i]['processed'] = 'Processing'
            extract_text_and_images(current_report, source['path'], progress_recorder, pages_count,
                                    total_processed, progress_json, current_report.id, i, self.request.id, user_id)
            progress_json['file_groups'][str(current_report.id)][i]['pages']['processed'] = \
                progress_json['file_groups'][str(current_report.id)][i]['pages']['all']
            progress_json['file_groups'][str(current_report.id)][i]['processed'] = 'True'
            redis_client.set(self.request.id, json.dumps(progress_json))
            progress_recorder.set_progress(total_processed[0], sum(pages_count.values()), progress_json)
            i += 1
        current_report.is_processing = False
        current_report.save()
    progress_json['time_ended'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return progress_json


def extract_text_and_images(current_report, file, progress_recorder, pages_count, total_processed, progress_json,
                            report_id,
                            source_index, task_id, user_id):
    supplement_content = copy.deepcopy(SUPPLEMENT_CONTENT)
    reports = ScientificReport.objects.all()
    for report in reports:
        for source in report.source:
            source_path = source['path']
            if report_id != report.id and os.path.isfile(source_path):
                file_hash = calculate_file_hash(file)
                report_hash = calculate_file_hash(source_path)
                if file_hash == report_hash:
                    raise FileExistsError(
                        f"Такой файл уже загружен в систему: {progress_json['file_groups'][str(report_id)][source_index]['origin_name']}")

    document = fitz.open(file)

    folder = file[:file.rfind(".")]
    Path(folder).mkdir(exist_ok=True)

    # Разделы
    report_parts = ['АННОТАЦИЯ', 'ОГЛАВЛЕНИЕ']  # , 'ведение', 'список исполнителей работ'
    report_parts_info = {i: '' for i in report_parts}
    df = None

    # Создаем или очищаем текстовый файл
    with open(folder + "/" + "text.txt", "w", encoding="utf-8") as text_file:
        extracted_images = []
        current_part = 0
        found_part = False
        start_page = 2
        time_on_start = datetime.now()
        for page_number in range(len(document)):
            pages_processed = total_processed[0] + page_number
            progress_json['file_groups'][str(report_id)][source_index]['pages']['processed'] = page_number
            expected_time = (datetime.now() - time_on_start) / (pages_processed if pages_processed > 0 else 1) * (sum(
                pages_count.values()) - pages_processed)
            total_seconds = int(expected_time.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            progress_json['expected_time'] = f"{hours:02}:{minutes:02}:{seconds:02}"
            redis_client.set(task_id, json.dumps(progress_json))
            progress_recorder.set_progress(pages_processed, sum(pages_count.values()),
                                           progress_json)
            page = document[page_number]
            # Извлечение текста
            text = page.get_text()
            while True:
                if found_part:
                    current_index = 0
                else:
                    if current_part >= len(report_parts):
                        current_index = None
                    else:
                        current_index = re.search(report_parts[current_part], text, re.IGNORECASE)
                    if current_index:
                        current_index = current_index.end()

                next_index = None
                if current_part + 1 < len(report_parts):
                    if df is None or df is not None and page_number + 1 == int(
                            df[df['Раздел'] == report_parts[current_part + 1]]['Страницы']):
                        next_index = re.search(report_parts[current_part + 1], text, re.IGNORECASE)
                if current_index or found_part:
                    text_to_write = text[current_index:next_index.start() if next_index else len(text)]
                    report_parts_info[report_parts[current_part]] += text_to_write
                    if start_page == page_number + 1:
                        text_file.write(
                            f"--- {report_parts[current_part]} --- (стр. {page_number + 1}):\n{text_to_write}\n")
                    else:
                        text_file.write(f"{text_to_write}\n")
                    found_part = True
                if next_index:
                    current_part += 1
                    start_page = page_number + 1
                    if report_parts[current_part] == 'ОГЛАВЛЕНИЕ':
                        with pdfplumber.open(file) as pdf:
                            page_tables = pdf.pages[page_number].extract_tables()
                            df = pd.DataFrame(page_tables[0], columns=['Раздел', 'Страницы'])
                            for index, row in df.iterrows():
                                if '-' in row['Страницы']:
                                    row['Страницы'] = row['Страницы'][:row['Страницы'].find('-')]
                            report_parts = list(df['Раздел'])
                            report_parts_info = dict(list({i: report_parts_info[i] for i in report_parts if
                                                           i in report_parts_info.keys()}.items()) +
                                                     list({i: '' for i in report_parts if
                                                           i not in report_parts_info.keys()}.items()))
                    continue
                break

            extract_images_with_captions(text, page, page_number, document, folder,
                                         supplement_content, extracted_images, user_id,
                                         progress_json['file_groups'][str(report_id)][source_index]['origin_name'],
                                         current_report.upload_source)
        total_processed[0] += len(document)
    document.close()

    current_report = ScientificReport.objects.get(id=report_id)
    current_report.name = 'Scientific Report Title'
    current_report.organization = 'Organization Name'
    current_report.author = 'Author Name'
    current_report.open_list = report_parts_info[
        'ОТКРЫТЫЙ ЛИСТ'] if 'ОТКРЫТЫЙ ЛИСТ' in report_parts_info.keys() else 'Open list info'
    current_report.writing_date = '2023-10-01'
    current_report.introduction = report_parts_info[
        'ВВЕДЕНИЕ'] if 'ВВЕДЕНИЕ' in report_parts_info.keys() else 'Introduction info'
    current_report.contractors = report_parts_info[
        'СПИСОК ИСПОЛНИТЕЛЕЙ РАБОТ'] if 'СПИСОК ИСПОЛНИТЕЛЕЙ РАБОТ' in report_parts_info.keys() else 'Contractors info'
    current_report.place = 'Research place'
    current_report.area_info = 'Area information'
    current_report.research_history = 'Research history text'
    current_report.results = 'Results text'
    current_report.conclusion = 'Conclusion text'
    current_report.supplement = supplement_content
    current_report.content = report_parts_info
    current_report.save()


@shared_task
def error_handler_reports(task, exception, exception_desc):
    print(f"Задача {task.id} завершилась с ошибкой: {exception} {exception_desc}")
    progress_json = json.loads(redis_client.get(task.id))
    for report_id, sources in progress_json['file_groups'].items():
        deleted_report = False
        for source in sources:
            if source['processed'] != 'True':
                report = ScientificReport.objects.get(id=report_id)
                report.delete()
                deleted_report = True
                break
        if deleted_report:
            continue
    progress_json['time_ended'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raise type(exception)({"error_text": str(exception), "progress_json": progress_json}) from exception


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    # extract_text_and_images(choose_file())
