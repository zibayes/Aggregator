import copy
import json
import math
import os
import re
import time
from datetime import datetime
from pathlib import Path
from tkinter import filedialog
import traceback
import logging
from typing import OrderedDict

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber
from celery import shared_task

from agregator.decorators import profiled
from agregator.processing.files_saving import load_raw_reports
from agregator.hash import has_duplicates_in_db
from agregator.processing.images_extraction import extract_images_with_captions, insert_supplement_links, \
    SUPPLEMENT_CONTENT
from agregator.models import Act
from agregator.redis_config import get_progress_json, create_progress_json
from agregator.celery_task_template import process_documents, progress_update, get_expected_time, CONVERTATION_PART, \
    PROCESSING_PART, ALL_PARTS
from agregator.processing.coordinates_tables import search_coords_in_text
from agregator.processing.batch_registry_utils import RegistryManager
from agregator.processing.batch_kml_utils import KMLParser
from agregator.processing.acts_regex_extractors import (extract_act_name, extract_start_date, extract_end_date,
                                                        extract_place_info, extract_customer,
                                                        extract_expert, extract_object, get_gike_object_size,
                                                        extract_exp_facts,
                                                        extract_conclusion, extract_open_list, extract_voan,
                                                        extract_executor, broken_structure_process)

logger = logging.getLogger(__name__)

SQUARE_RESERVE = []


def choose_pdf_file() -> str:
    # Открываем окно выбора файла
    # file_path = filedialog.askopenfilename(title="Выберите PDF файл", filetypes=[("PDF файлы", "*.pdf")])
    file_path = filedialog.askdirectory(title="Выберите папку")
    if file_path:
        return file_path


@shared_task(bind=True, acks_late=True, max_retries=3)
@profiled(enabled=True)
def process_acts(self, acts_ids, user_id, select_text, select_enrich, select_image, select_coord, is_reprocess=False):
    document_type = 'acts'
    progress_json = get_progress_json(self.request.id)
    if progress_json is None:
        progress_json = create_progress_json(
            user_id,
            document_type,
            task_id=self.request.id,
            task_name=self.name,
            args=[acts_ids, user_id, select_text, select_enrich, select_image, select_coord, is_reprocess],
            kwargs={}
        )
    try:
        progress_json = process_documents(self, acts_ids, user_id, document_type, model_class=Act,
                                          load_function=load_raw_reports,
                                          select_text=select_text, select_enrich=select_enrich,
                                          select_image=select_image, select_coord=select_coord,
                                          process_function=extract_text_and_images, progress_json=progress_json,
                                          is_reprocess=is_reprocess)
    except Exception as e:
        logger.error(f'Критическая ошибка при обработке актов {acts_ids}: {e}')
        logger.error(traceback.format_exc())
    return progress_json


def extract_text_and_images(file, progress_recorder, pages_count, total_processed,
                            progress_json, act_id, source_index, task_id, user_id, is_public, select_text,
                            select_enrich, select_image,
                            select_coord, is_reprocess):
    logger.info(f"ОБРАБАТЫВАЕТСЯ АКТ: {file}")
    start_time = time.time()

    if is_reprocess is False:
        has_duplicates, duplicate_id = has_duplicates_in_db(Act, file, act_id)
        if has_duplicates:
            raise FileExistsError(
                f"Такой файл уже загружен в систему (act.id = {duplicate_id}): {progress_json['file_groups'][str(act_id)][source_index]['origin_filename']}")
        logger.info(f"После проверки хеша: {round((time.time() - start_time), 2)} секунд")

    use_kml = False
    supplement_content = copy.deepcopy(SUPPLEMENT_CONTENT)
    # coordinates = copy.deepcopy(COORDINATES_SAMPLE)
    coordinates = {}
    pdf_file = file  # pdf_file = 'uploaded_files/' + file

    current_act = Act.objects.get(id=act_id)
    source_info = current_act.source_dict[source_index]

    # Логируем информацию об организации
    if source_info.get('was_organized'):
        logger.info(f"Файл был организован: {source_info.get('original_path')} -> {file}")
    else:
        logger.info(f"Файл не требовал организации: {file}")

    # Открываем PDF-файл
    if not os.path.exists(pdf_file):
        logger.error(f'Файл для акта id = {current_act.id} не найден! Обработка остановлена!')
        return

    try:
        document = fitz.open(pdf_file)
    except Exception as e:
        logger.error(f'Ошибка при открытии файла акта id = {current_act.id}! Обработка остановлена!')
        return

    folder = pdf_file[:pdf_file.rfind(".")]
    Path(folder).mkdir(exist_ok=True)

    if select_coord:
        logger.info(f"До извлечения координат из KML: {round((time.time() - start_time), 2)} секунд")
        kml_path = None
        try:
            kml_path = KMLParser.find_kml_for_pdf(pdf_file)
        except Exception as e:
            logger.error(f'Ошибка при обработке kml! {e}')

        if kml_path:
            logger.info(f"📌 Найден KML файл: {kml_path}")

            kml_coordinates = None
            try:
                kml_coordinates = KMLParser.parse_kml_file(kml_path)
            except Exception as e:
                logger.error(f"❌ Не удалось извлечь координаты из KML: {e}")

            if kml_coordinates:
                coordinates = kml_coordinates
                logger.info("✅ Координаты успешно заменены на достоверные из KML")
                use_kml = True

                total_objects = sum(len(category_objects) for category_objects in kml_coordinates.values())
                logger.info(f"📊 Извлечено {total_objects} объектов в {len(kml_coordinates)} категориях")

            else:
                logger.warning("❌ Не удалось извлечь координаты из KML")
        else:
            logger.info("ℹ️ KML файл не найден, используем координаты из PDF")
        logger.info(f"После извлечения координат из KML: {round((time.time() - start_time), 2)} секунд")

    # Разделы
    SECTIONS = OrderedDict([
        ('act', r'Акт'),
        ('start_date', r'(?<!\d)(\d\.\s*)?Дата\s*начала\s*(?!.*\s*окончания)(проведения)?\s*(экспертизы)?[\s:\-–-]*'),
        ('end_date', r'(?<!\d)(\d\.\s*)?(?<!начала и )Дата\s*окончания\s*(проведения)?\s*(экспертизы)?[\s:\-–-]*'),
        ('place', r'(?<!\d)(\d\.\s*)?Место\s*проведения\s*(экспертизы)?[\s:\-–-]*'),
        ('customer', r'(\d\.\s*)?(Заказчик\s*экспертизы|Сведения\s*о\s*заказчике\s*экспертизы)[\s:\-–-]*'),
        ('expert', r'(\d\.\s*)?(Сведения\s*об)?\s*эксперт[еах]+[\s:\-–-]*'),
        ('relation', r'(\d\.\s*)?Отношени[яе]+\s*.*\s*к?\s*заказчик[у]?'),
        ('purpose', r'(\d\.\s*)?Цель\s*экспертизы[\s:\-–-]*'),
        ('object', r'(\d\.\s*)?Объект\s*.*?экспертизы[\s:\-–-]*'),
        ('doc_list', r'Перечень\s*документов,\s*представленных\s*(на)?\s*(экспертизу)?[\s:\-–-]*'),
        ('research_info', r'Сведения\s*о\s*проведенных\s*исследованиях'),
        ('facts', r'Факты\s*и\s*сведения,\s*выявленные\s*.*\n*.*исследований'),
        ('literature', r'Перечень[а-яА-ЯёЁ \n,]*литературы'),
        ('conclusion', r'Вывод[ы]?\s*экспертизы'),
        ('appendix', r'Перечень\s*приложений')
    ])
    first_five_pages = '\n'.join([x.get_text() for x in document[:5]])
    print(f'SECTIONS = {SECTIONS}')
    SECTIONS = {**dict(sorted(list(SECTIONS.items())[:7],
                              key=lambda x: re.search(x[1], first_five_pages, re.IGNORECASE).start() if re.search(x[1],
                                                                                                                  first_five_pages,
                                                                                                                  re.IGNORECASE) else float(
                                  'inf'))), **dict(list(SECTIONS.items())[7:])}
    print(f'after SECTIONS = {SECTIONS}')

    # Список имен секций в порядке следования (сохраняем порядок)
    SECTION_NAMES = list(SECTIONS.keys())
    SECTION_PATTERNS = [re.compile(pattern, re.IGNORECASE) for name, pattern in SECTIONS.items()]  # скомпилированные
    # Для обратного поиска по шаблону (если нужно) можно оставить словарь
    SECTION_PATTERN_MAP = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in SECTIONS.items()}

    act_parts_info = {i: '' for i in SECTION_NAMES}
    object_info = ''
    place_info = ''

    table_info = {}
    table_columns = ['ГОД', 'Дата окончания проведения ГИКЭ', 'Вид ГИКЭ',
                     'Номер (если имеется) и наименование Акта ГИКЭ',
                     'Место проведения экспертизы',  # 'Муниципальный район или муниципальный округ'
                     'Заказчик работ (*если не указан, то заказчик экспертизы)',
                     'Площадь, протяжённость и/или др. параменты объекта', 'Эксперт (физ. или юр.лицо)',
                     'Исполнитель полевых работ (юр. лицо)', 'ОЛ', 'Заключение. Выявленые объекты.',
                     'Объекты расположенные в непосредственной близости. Для границ']
    table_path = "uploaded_files/Акты ГИКЭ/РЕЕСТР актов ГИКЭ.xlsx"
    broken_structure = False
    exploration_object = False
    sectors_square = []
    text_reserve = None
    voan_reserve = None
    several_experts = False
    full_name = False
    full_text = None
    full_time_interval = None
    interval_type = None
    tables = []
    logger.info(f"После подготовки разделов: {round((time.time() - start_time), 2)} секунд")

    # Создаем или очищаем текстовый файл
    with open(folder + "/" + "text.txt", "w", encoding="utf-8") as text_file:
        extracted_images = []
        current_section_idx = 0
        current_section_name = SECTION_NAMES[current_section_idx]
        time_on_start = datetime.now()
        for page_number in range(len(document)):
            try:
                logger.info(
                    F"--- Старт страницы {page_number}/{len(document)} / Время выполнения: {round((time.time() - start_time), 2)} секунд ---")
                pages_processed = total_processed[0] + page_number
                progress_json['file_groups'][str(act_id)][source_index]['pages']['processed'] = page_number
                progress_json['expected_time'] = get_expected_time(time_on_start, pages_processed, pages_count)
                progress_update(progress_recorder, task_id, progress_json,
                                CONVERTATION_PART + PROCESSING_PART * (pages_processed / sum(pages_count.values())),
                                ALL_PARTS)
                page = document[page_number]
                # Извлечение текста
                text = page.get_text()

                if current_section_name == 'act':
                    current_section_idx, exploration_object = extract_act_name(text, current_section_idx, text_file,
                                                                               page_number,
                                                                               table_info, exploration_object)
                    current_section_name = SECTION_NAMES[current_section_idx]

                if select_text:
                    while True:
                        pattern = SECTION_PATTERNS[current_section_idx]
                        match = pattern.search(text)
                        current_index = match.end() if match else 0

                        next_index = None
                        if current_section_idx + 1 < len(SECTION_NAMES):
                            next_index = SECTION_PATTERNS[current_section_idx + 1].search(text)

                        text_to_write = text[current_index:next_index.start() if next_index else len(text)]
                        text_to_write = '' if text_to_write is None else text_to_write

                        if current_section_name == 'start_date':
                            full_time_interval, interval_type, text_to_write = extract_start_date(text_to_write,
                                                                                                  table_info)

                        text_file.write(
                            f"--- {current_section_name} --- (стр. {page_number + 1}):\n{text_to_write}\n")
                        act_parts_info[current_section_name] += text_to_write

                        if current_section_name == 'end_date' or full_time_interval:
                            current_section_idx, is_continue = extract_end_date(text, SECTION_PATTERN_MAP['start_date'],
                                                                                text_to_write, full_time_interval,
                                                                                interval_type, current_section_idx,
                                                                                table_info)
                            current_section_name = SECTION_NAMES[current_section_idx]
                            if is_continue:
                                continue

                        elif current_section_name == 'place':
                            broken_structure, place_info = extract_place_info(place_info, text, text_to_write,
                                                                              table_info, broken_structure)

                        elif current_section_name == 'customer':
                            extract_customer(broken_structure, SECTION_PATTERN_MAP['expert'], table_info, text,
                                             text_to_write)
                        elif current_section_name == 'expert':
                            several_experts, full_name, broken_structure = extract_expert(text_to_write,
                                                                                          several_experts, full_name,
                                                                                          table_info, document,
                                                                                          page_number, broken_structure)
                        elif current_section_name == 'object':
                            object_info, exploration_object = extract_object(object_info, exploration_object, text,
                                                                             text_to_write, table_info, SQUARE_RESERVE)
                        elif current_section_name == 'conclusion' and \
                                'Площадь, протяжённость и/или др. параменты объекта' not in table_info.keys():
                            get_gike_object_size(text_to_write, table_info, SQUARE_RESERVE)
                        if current_section_name == 'research_info':
                            get_gike_object_size(text_to_write, table_info, SQUARE_RESERVE)
                        if current_section_name == 'facts':
                            text_reserve = extract_exp_facts(exploration_object, text_to_write, text, table_info,
                                                             SQUARE_RESERVE,
                                                             sectors_square, text_reserve)

                        if broken_structure is True:
                            broken_structure_process(text, table_info)

                        if current_section_idx > 10:
                            extract_conclusion(text_to_write, table_info, voan_reserve)

                        if not 'ОЛ' in table_info.keys() or 'от' not in table_info['ОЛ'] or '№' not in table_info[
                            'ОЛ'] or not re.search(r'[А-ЯЁ]+[а-яё]+', table_info['ОЛ']):
                            #  Открытого\s*листа\s*[а-яА-Я \n0-9.]*№[\d -]+[а-яА-Я \n\d\.,(]*
                            #  Открытого листа[а-яА-Я \n]*№[\d -]+ от [\d. г]+[а-яА-Я \n,(]*на имя.+\..+\. [а-яА-Я]+
                            #  открытого\s*листа\s*[а-яА-Я \n]*№[\d -]+[а-яА-Я \n\d\.,(]*[а-яА-Я]+.+\..+\.
                            extract_open_list(text_to_write, table_info)

                        res = extract_voan(text, table_info)
                        if res is not None:
                            voan_reserve = res

                        annotation = re.search(r'аннотация', text, re.IGNORECASE)
                        if annotation:
                            get_gike_object_size(text_to_write, table_info, SQUARE_RESERVE)

                        extract_executor(text, table_info)

                        if next_index:
                            current_section_idx += 1
                            current_section_name = SECTION_NAMES[current_section_idx]
                            continue
                        elif current_section_idx + 2 < len(SECTION_NAMES) and SECTION_PATTERNS[
                            current_section_idx + 2].search(text):
                            current_section_idx += 2
                            current_section_name = SECTION_NAMES[current_section_idx]
                            continue
                        elif current_section_idx + 3 < len(SECTION_NAMES) and SECTION_PATTERNS[
                            current_section_idx + 3].search(text):
                            current_section_idx += 3
                            current_section_name = SECTION_NAMES[current_section_idx]
                            continue
                        break
                if select_image:
                    extract_images_with_captions(text_to_write, page, page_number, document, folder,
                                                 supplement_content, extracted_images, user_id,
                                                 progress_json['file_groups'][str(act_id)][source_index][
                                                     'origin_filename'],
                                                 is_public, current_act.upload_source)
                if select_coord and not use_kml:
                    if re.search(r'Выписка\s+из\s+Единого\s+государственного\s+реестра', text, re.IGNORECASE):
                        continue
                    search_coords_in_text(page_number, document, tables, text, coordinates)
            except Exception as e:
                logger.error(f'Ошибка при обработке страницы №{page_number} акта id = {current_act.id}: {e}')
                logger.error(traceback.format_exc())
                continue

        total_processed[0] += len(document)

    '''
    if select_coord:
        results, coordinate_systems, full_text = analyze_coordinates_in_tables_from_pdf(tables, file)
        if results is not None:
            print(results)
            coordinates = coordinates | format_coordinates(results, coordinate_systems)
            print('COORDS!!!!: ' + str(coordinates))
    '''

    logger.info("--- Конец обработки / Время выполнения: %s секунд ---" % round((time.time() - start_time), 2))

    if ('Площадь, протяжённость и/или др. параменты объекта' not in table_info.keys() or \
        'Общ. S' not in table_info['Площадь, протяжённость и/или др. параменты объекта']) and len(SQUARE_RESERVE) > 0:
        table_info['Площадь, протяжённость и/или др. параменты объекта'] = 'Общ. S = ' + SQUARE_RESERVE[0]
    document.close()

    logger.info("--- ПДФка закрыта / Время выполнения: %s секунд ---" % round((time.time() - start_time), 2))

    if select_text and select_enrich:
        logger.info("=== ОБОГАЩЕНИЕ ДАННЫХ ИЗ РЕЕСТРА ===")
        try:
            registry_matcher = RegistryManager(
                "uploaded_files/Акты ГИКЭ/!! Текущий РЕЕСТР актов ГИКЭ КК 2015-2026 (на осн. 01.09.2023).xlsx")
            table_info = registry_matcher.enrich_from_registry(table_info, pdf_file)
        except Exception as e:
            logger.error(f"Ошибка при обогащении данных из реестра для акта id = {current_act.id}: {e}")
            logger.error(traceback.format_exc())

    # pd.DataFrame(table_info,columns=table_columns,index=[0]).to_excel(folder + "/" + "table.xlsx", index=False, engine='openpyxl')
    df_new = pd.DataFrame(table_info, columns=table_columns, index=[0]).fillna('')

    if select_text and select_image:
        try:
            insert_supplement_links(act_parts_info)
        except Exception as e:
            logger.error(f"Ошибка при вставке ссылок на иллюстрации для акта id = {current_act.id}: {e}")

    try:
        logger.info("--- Заполнение БД / Время выполнения: %s секунд ---" % round((time.time() - start_time), 2))
        if progress_json['file_groups'][str(act_id)][source_index]['type'] in ('text', 'all'):
            current_act.year = df_new['ГОД'][0]
            current_act.finish_date = df_new['Дата окончания проведения ГИКЭ'][0]
            current_act.type = df_new['Вид ГИКЭ'][0]
            current_act.name_number = df_new['Номер (если имеется) и наименование Акта ГИКЭ'][0]
            current_act.place = df_new['Место проведения экспертизы'][0]
            current_act.customer = df_new['Заказчик работ (*если не указан, то заказчик экспертизы)'][0]
            current_act.area = df_new['Площадь, протяжённость и/или др. параменты объекта'][0]
            current_act.expert = df_new['Эксперт (физ. или юр.лицо)'][0]
            current_act.executioner = df_new['Исполнитель полевых работ (юр. лицо)'][0]
            current_act.open_list = df_new['ОЛ'][0]
            current_act.conclusion = df_new['Заключение. Выявленые объекты.'][0]
            current_act.border_objects = df_new['Объекты расположенные в непосредственной близости. Для границ'][0]

            current_act.act = act_parts_info['act']
            current_act.start_date = act_parts_info['start_date']
            current_act.exp_place = act_parts_info[r'place']
            current_act.exp_customer = act_parts_info[r'customer']
            current_act.exp_expert = act_parts_info[r'expert']
            current_act.relationship = act_parts_info['relation']
            current_act.goal = act_parts_info['purpose']
            current_act.object = act_parts_info['object']
            current_act.docs = act_parts_info['doc_list']
            current_act.exp_info = act_parts_info['research_info']
            current_act.exp_facts = act_parts_info['facts']
            current_act.literature = act_parts_info['literature']
            current_act.exp_conclusion = act_parts_info['conclusion']
        if progress_json['file_groups'][str(act_id)][source_index]['type'] in ('images', 'all'):
            current_act.supplement = supplement_content
        print(coordinates)
        if 'Шурфы' in coordinates.keys():
            print(len(coordinates.keys()) == 1, 'Шурфы' in coordinates.keys(), len(coordinates['Шурфы'].keys()) == 0)
        if len(coordinates.keys()) == 1 and 'Шурфы' in coordinates.keys() and len(coordinates['Шурфы'].keys()) == 0:
            coordinates = {}
        current_act.coordinates = coordinates
        current_act.is_processing = False
        current_act.save()
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных акта id = {current_act.id}: {e}")
        logger.error(traceback.format_exc())
