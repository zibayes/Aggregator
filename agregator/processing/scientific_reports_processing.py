import copy
import json
import os
import re
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber
from celery import shared_task

from agregator.processing.coordinates_extraction import extract_coordinates, COORDINATES_SAMPLE
from agregator.processing.files_saving import load_raw_reports
from agregator.hash import calculate_file_hash
from agregator.processing.images_extraction import extract_images_with_captions, insert_supplement_links, \
    SUPPLEMENT_CONTENT
from agregator.models import ScientificReport
from agregator.redis_config import redis_client
from agregator.celery_task_template import process_documents


def choose_file() -> str:
    # Открываем окно выбора файла
    file_path = filedialog.askopenfilename(title="Выберите PDF файл", filetypes=[("PDF файлы", "*.pdf")])
    if file_path:
        return file_path


@shared_task(bind=True)
def process_scientific_reports(self, reports_ids, user_id, select_text, select_enrich, select_image, select_coord):
    return process_documents(self, reports_ids, user_id, 'scientific_reports', model_class=ScientificReport,
                             load_function=load_raw_reports,
                             select_text=select_text, select_enrich=select_enrich, select_image=select_image,
                             select_coord=select_coord,
                             process_function=extract_text_and_images)


def extract_text_and_images(current_report, file, progress_recorder, pages_count, total_processed, progress_json,
                            report_id,
                            source_index, task_id, user_id, is_public, select_text, select_enrich, select_image,
                            select_coord):
    if current_report.supplement:
        supplement_content = current_report.supplement_dict  # json.loads(current_report.supplement)
    else:
        supplement_content = copy.deepcopy(SUPPLEMENT_CONTENT)
    if current_report.coordinates:
        coordinates = current_report.coordinates_dict  # json.loads(current_report.coordinates)
    else:
        coordinates = copy.deepcopy(COORDINATES_SAMPLE)
    reports = ScientificReport.objects.all()
    for report in reports:
        if report.source_dict is not None:
            for source in report.source_dict:
                source_path = source['path']
                if report_id != report.id and os.path.isfile(source_path):
                    file_hash = calculate_file_hash(file)
                    report_hash = calculate_file_hash(source_path)
                    if file_hash == report_hash:
                        raise FileExistsError(
                            f"Такой файл уже загружен в систему: {progress_json['file_groups'][str(report_id)][source_index]['origin_filename']}")

    document = fitz.open(file)

    folder = file[:file.rfind(".")]
    Path(folder).mkdir(exist_ok=True)

    # Разделы
    report_parts = ['аннотация', 'оглавление']  # , 'ведение', 'список исполнителей работ'
    report_parts_info = {i: '' for i in report_parts}
    table_columns = ['Название отчёта', 'Организация', 'Автор',
                     'Открытый лист', 'Населённый пункт', 'Год написания отчёта',
                     'Вид работ', 'Площадь', 'Исполнители',
                     'Заключение']
    table_columns_info = {i: '' for i in table_columns}
    df = None

    # Создаем или очищаем текстовый файл
    with open(folder + "/" + "text.txt", "w", encoding="utf-8") as text_file:
        extracted_images = []
        current_part = 0
        reading_contents = False
        start_page = 2
        is_introduction = False
        introduction_part = None
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
            text = page.get_text()
            if select_text:
                while True:
                    current_index = re.search(
                        report_parts[current_part].lower().replace('оглавление', r'оглавление|содержание').replace(' ',
                                                                                                                   r'[ \n]*'),
                        text, re.IGNORECASE)
                    if current_index:
                        current_index = current_index.end()
                    else:
                        current_index = 0

                    next_index = None
                    if current_part + 1 < len(report_parts):
                        next_index = re.search(
                            report_parts[current_part + 1].replace('оглавление', r'оглавление|содержание').replace(' ',
                                                                                                                   r'[ \n]*')
                            .replace('(', r'\(').replace(')', r'\)'), text, re.IGNORECASE)
                        if next_index:
                            reading_contents = False

                    if introduction_part != current_part:
                        is_introduction = False
                    if 'введение' in text.lower() and introduction_part is None:
                        is_introduction = True
                        introduction_part = current_part

                    text_to_write = text[current_index:next_index.start() if next_index else len(text)]
                    report_parts_info[report_parts[current_part]] += text_to_write
                    text_file.write(
                        f"--- {report_parts[current_part]} --- (стр. {page_number + 1}):\n{text_to_write}\n")
                    if next_index or reading_contents:
                        if 'оглавление' in report_parts[current_part + 1].lower() or 'содержание' in report_parts[
                            current_part + 1].lower() or reading_contents:
                            with pdfplumber.open(file) as pdf:
                                page_tables = pdf.pages[page_number].extract_tables()
                            if page_tables:
                                df_new = pd.DataFrame(page_tables[0], columns=['Раздел', 'Страницы'])
                                if reading_contents:
                                    df = df._append(df_new, ignore_index=True)
                                else:
                                    df = df_new
                                for index, row in df.iterrows():
                                    if '-' in row['Страницы']:
                                        row['Страницы'] = row['Страницы'][:row['Страницы'].find('-')]
                                report_parts = list(df['Раздел'])
                                report_parts_info = {i: '' for i in report_parts}
                                '''
                                report_parts_info = dict(list({i: report_parts_info[i] for i in report_parts if
                                                               i in report_parts_info.keys()}.items()) +
                                                         list({i: '' for i in report_parts if
                                                               i not in report_parts_info.keys()}.items()))
                                '''
                                continue
                            else:
                                titles = re.findall(r'^(?!\d+\s*$)\.*\d*\.*\d*.*?[\s\S]*?\s*\d+\.*\s*\d*\s*$',
                                                    text, re.MULTILINE)
                                structure = []
                                for title_line in titles:
                                    title = re.search(
                                        r'(^(?!\d+\s*$)\d*\.*.*?(?=…))|(^(?!\d+\s*$)\d+\..*\s.+?(?=…))|^(?!\d+\s*$)\d*\.*.*[^…]*?(?=\n\d+)|^(?!\d+\s*$)\d*\.*[\s\S]*?(?=\.\.\.)',
                                        title_line, re.MULTILINE)

                                    if title:
                                        title = title.group(0).replace('\n', '').replace('  ', ' ').strip()
                                        title = title[:-1] if title[-1] == '.' else title
                                        title_page = re.findall(r'\d+', title_line, re.IGNORECASE)
                                        if title_page:
                                            title_page = title_page[-1].replace('\n', '')
                                            title = title[:-len(title_page) if title_page in title else len(title)]
                                        structure.append({'Раздел': title, 'Страницы': title_page})
                                df_new = pd.DataFrame(structure, columns=['Раздел', 'Страницы'])
                                if reading_contents:
                                    df = df._append(df_new, ignore_index=True)
                                else:
                                    df = df_new
                                report_parts = list(df['Раздел'])
                                report_parts_info = {i: '' for i in report_parts}
                                current_part = 0
                                report_parts_lower = [s.lower() for s in report_parts]
                                index = -1
                                if any('оглавление' in s.lower() for s in report_parts_lower):
                                    for i, s in enumerate(report_parts_lower):
                                        if 'оглавление' in s:
                                            index = i
                                    current_part = report_parts_lower.index('оглавление')
                                elif any('содержание' in s.lower() for s in report_parts_lower):
                                    for i, s in enumerate(report_parts_lower):
                                        if 'содержание' in s.lower():
                                            index = i
                                if index > 0:
                                    current_part = index
                                # print(df)
                            reading_contents = True
                            break

                    if page_number + 1 == 1:
                        report_name = re.search(
                            r'н*\s*а*\s*у*\s*ч*\s*н*\s*ы*\s*й*\s*о\s*т\s*ч\s*[её]\s*т[\s\S]*?\d{4}\s*.*г\.*[оду]*',
                            text,
                            re.IGNORECASE)
                        if report_name:
                            report_name = report_name.group(0)
                            table_columns_info['Название отчёта'] = report_name

                            place = re.search(r'г\.[\s\S]+?\d{4}', report_name, re.IGNORECASE)
                            if place:
                                table_columns_info['Населённый пункт'] = place.group(0)

                        author = re.search(r'выполнил:\s+.*|автор:\s+.*', text, re.IGNORECASE)
                        if author:
                            author = re.search(
                                r'[А-ЯЁ]+[а-яё]+[ \n]+[А-Яа-яёЁ]{1}\.[ \n]*[А-Яа-яёЁ]{1}\.|[А-Яа-яёЁ]{1}\.[ \n]*[А-Яа-яёЁ]{1}\.[ \n]+[А-ЯЁ]+[а-яё]+',
                                author.group(0), re.MULTILINE)
                            if author:
                                table_columns_info['Автор'] = author.group(0)

                        open_list = re.search(
                            r'[А-ЯЁ]+[а-яё]+[ \n]+[А-Яа-яёЁ]{1}\.[ \n]*[А-Яа-яёЁ]{1}\.[Держатель]*\s*Открыт[ыйого]*\sлист[а]*[\s\S]*?№\s\d+-*\d*[\s\S]*?\d{2}\.\s*\d{2}\.\s*\d+|[А-Яа-яёЁ]{1}\.[ \n]*[А-Яа-яёЁ]{1}\.[ \n]+[А-ЯЁ]+[а-яё]+[Держатель]*\s*Открыт[ыйого]*\sлист[а]*[\s\S]*?№\s\d+-*\d*[\s\S]*?\d{2}\.\s*\d{2}\.\s*\d+',
                            text)
                        if not open_list:
                            open_list = re.search(
                                r'[А-ЯЁ]+[а-яё]+[ \n]+[А-Яа-яёЁ]{1}\.[ \n]*[А-Яа-яёЁ]{1}\.[Держатель]*\s*Открыт[ыйого]*\sлист[а]*[\s\S]*?№\s\d+-*\d*[\s\S]*?|[А-Яа-яёЁ]{1}\.[ \n]*[А-Яа-яёЁ]{1}\.[ \n]+[А-ЯЁ]+[а-яё]+[Держатель]*\s*Открыт[ыйого]*\sлист[а]*[\s\S]*?№\s\d+-*\d*[\s\S]*?',
                                text)
                            if not open_list:
                                open_list = re.findall(
                                    r'[Держатель]*\s*Открыт[ыйого]*\sлист[а]*[\s\S]*?№\s\d+-*\d*[\s\S]*?[А-Яа-яёЁ]{1}\.[ \n]*[А-Яа-яёЁ]{1}\.[ \n]+[А-ЯЁ]{1}[а-яё]+|[Держатель]*\s*Открыт[ыйого]*\sлист[а]*[\s\S]*?№\s\d+-*\d*[\s\S]*?[А-ЯЁ]{1}[а-яё]+[ \n]+[А-Яа-яёЁ]{1}\.[ \n]*[А-Яа-яёЁ]{1}\.',
                                    text)
                                if open_list:
                                    open_list = ';\n'.join(open_list)
                        if open_list and not isinstance(open_list, (list, str)):
                            open_list = open_list.group(0)
                        if open_list:
                            table_columns_info['Открытый лист'] = open_list

                        organization = re.search(r'Общество\s+с\s+ограниченной\s+ответственностью\s*[\n]*«[^»]+»', text,
                                                 re.IGNORECASE)
                        if not organization:
                            organization = re.search(r'ООО\s+[^\n]+?(?:«[^»]+»|“[^”]+”|\"[^\"]+\")?\s*[\n]*\"?[^\n]*\"',
                                                     text, re.IGNORECASE)
                        if not organization:
                            organization = re.search(r'ООО\s+«[^»]+»', text, re.IGNORECASE)
                        if organization:
                            table_columns_info['Организация'] = organization.group(0)

                        year_of_writing = re.search(
                            r'[А-ЯЁ]{1}[а-яё,]+-*[А-ЯЁ]*[а-яё,]*\s*\d{4}', text)
                        if year_of_writing:
                            year_of_writing = year_of_writing.group(0)
                            if not table_columns_info['Населённый пункт']:
                                place = re.search(r'[\s\S]*?(?=\d{4})', year_of_writing, re.IGNORECASE)
                                if place:
                                    table_columns_info['Населённый пункт'] = place.group(
                                        0).strip() + ' (место написания отчёта)'
                            year_of_writing = re.search(r'\d{4}', year_of_writing, re.IGNORECASE)
                            if year_of_writing:
                                table_columns_info['Год написания отчёта'] = year_of_writing.group(0)

                    if 'заключение' in report_parts[current_part].lower() or 'аннотация' in report_parts[
                        current_part].lower():
                        if 'аннотация' in report_parts[current_part].lower():
                            works_type = re.search(
                                r'работы\sпо[\s\S]+?наблюд[^\s]+|работы\sпо[\s\S]+?шур[^\s]+|результ[\s\S]+?раб[^\s]+|обслед[\s\S]+?наслед[^\s]+|археолог[\s\S]+?развед[^\s]+',
                                text, re.IGNORECASE)
                            if works_type:
                                table_columns_info['Вид работ'] = works_type
                        if not table_columns_info['Площадь']:
                            square = re.search(
                                r'Общ[аяей]*\sплощад[\s\S]*?[\d,.]+\s*.*?м2', text, re.IGNORECASE)
                            if not square:
                                square = re.search(
                                    r'[Общаяей]*\sплощад[\s\S]*?[\d,.]+\s*.*?м2', text, re.IGNORECASE)
                            if not square:
                                square = re.search(
                                    r'[Общаяей]*\sплощад[\s\S]*?[\d,.]+\s*.*?м', text, re.IGNORECASE)
                            if square:
                                square = re.search(r'\d+[,.]*\d*\s*.*?м2*', square.group(0), re.IGNORECASE)
                                if square:
                                    table_columns_info['Площадь'] = square.group(0)

                    if is_introduction or 'список исполнителей' in report_parts[current_part].lower():
                        with pdfplumber.open(file) as pdf:
                            page_tables = pdf.pages[page_number].extract_tables()
                        if page_tables and len(page_tables[0]) > 0 and len(page_tables[0][0]) == 2:
                            executors = []
                            if 'ФИО' in page_tables[0][0] and 'Степень участия' in page_tables[0][0]:
                                df_new = pd.DataFrame(page_tables[0], columns=['ФИО', 'Степень участия'])
                                for cell in df_new['ФИО']:
                                    fio = re.search(r'[А-ЯЁ]{1}[а-яё]+\s+[А-ЯЁ]{1}[а-яё]+\s+[А-ЯЁ]{1}[а-яё]+', cell)
                                    if fio:
                                        executors.append(
                                            fio.group(0) + ': ' + df_new[df_new['ФИО'] == cell]['Степень участия'])
                                if executors:
                                    table_columns_info['Исполнители'] = ';\n'.join(executors)
                            else:
                                df_new = pd.DataFrame(page_tables[0], columns=['Параметр', 'Значение'])
                                fio = None
                                works = None
                                for index, cell in df_new.iterrows():
                                    if fio is None:
                                        fio = re.search(r'[А-ЯЁ]{1}[а-яё]+\s+[А-ЯЁ]{1}[а-яё]+\s+[А-ЯЁ]{1}[а-яё]+',
                                                        cell['Параметр'])
                                        if fio:
                                            fio = fio.group(0)
                                        elif 'Степень участия' in cell['Параметр']:
                                            works = cell['Значение']
                                    elif 'Степень участия' in cell['Параметр']:
                                        works = cell['Значение']
                                if fio and works:
                                    table_columns_info['Исполнители'] = fio + ': ' + works

                    if next_index:
                        current_part += 1
                        start_page = page_number + 1
                        continue
                    elif current_part + 2 < len(report_parts) and re.search(
                            report_parts[current_part + 2].replace(' ', r'[ \n]*')
                                    .replace('(', r'\(').replace(')', r'\)'), text):
                        current_part += 2
                        continue
                    break

            if select_image:
                extract_images_with_captions(text, page, page_number, document, folder,
                                             supplement_content, extracted_images, user_id,
                                             progress_json['file_groups'][str(report_id)][source_index][
                                                 'origin_filename'],
                                             is_public, current_report.upload_source)
            if select_coord:
                extract_coordinates(file, document, page_number, folder, coordinates)
        total_processed[0] += len(document)
    document.close()

    if select_text and select_image:
        insert_supplement_links(report_parts_info)

    if progress_json['file_groups'][str(report_id)][source_index]['type'] in ('text', 'all'):
        current_report.name = table_columns_info['Название отчёта']
        current_report.organization = table_columns_info['Организация']
        current_report.author = table_columns_info['Автор']
        current_report.open_list = table_columns_info[
            'Открытый лист']
        current_report.writing_date = table_columns_info['Год написания отчёта']
        current_report.introduction = report_parts_info[
            'ВВЕДЕНИЕ'] if 'ВВЕДЕНИЕ' in report_parts_info.keys() else ''
        current_report.contractors = table_columns_info['Исполнители']
        current_report.place = table_columns_info['Населённый пункт']
        current_report.area_info = table_columns_info['Площадь']
        current_report.research_history = ''
        current_report.results = ''
        current_report.conclusion = ''
        current_report.content = report_parts_info
    if progress_json['file_groups'][str(report_id)][source_index]['type'] in ('images', 'all'):
        current_report.supplement = supplement_content
    if len(coordinates.keys()) == 1 and 'Шурфы' in coordinates.keys() and len(coordinates['Шурфы'].keys()) == 0:
        coordinates = {}
    current_report.coordinates = coordinates
    current_report.is_processing = False
    current_report.save()


@shared_task
def error_handler_scientific_reports(task, exception, exception_desc):
    print(f"Задача {task.id} завершилась с ошибкой: {exception} {exception_desc}")
    progress_json = redis_client.get(task.id)
    if progress_json is None:
        progress_json = redis_client.get('celery-task-meta-' + str(task.id))
    if not isinstance(progress_json, dict):
        progress_json = json.loads(progress_json)
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
