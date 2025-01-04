import fitz  # PyMuPDF
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import re
import pdfplumber
import pandas as pd
from celery import shared_task
from celery_progress.backend import ProgressRecorder
from .models import ScientificReport, Supplement, User


def choose_file() -> str:
    # Открываем окно выбора файла
    file_path = filedialog.askopenfilename(title="Выберите PDF файл", filetypes=[("PDF файлы", "*.pdf")])
    if file_path:
        return file_path

def local_storage_reports_processing(uploaded_files, user):
    files = []
    pages_count = 0
    for file in uploaded_files:
        last_id = ScientificReport.objects.last()
        if not last_id:
            last_id = 0
        else:
            last_id = last_id.id
        file.name = str(last_id+ 1) + '_report.pdf'
        files.append(file.name)
        # Сохраняем файл во временную директорию
        with open('uploaded_files/reports/' + file.name, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
        with fitz.open('uploaded_files/reports/' + file.name) as pdf_doc:
            pages_count += len(pdf_doc)
    task = extract_text_and_images.delay(files, pages_count, user.id)
    return task

@shared_task(bind=True)
def extract_text_and_images(self, uploaded_files, pages_count, user) -> None:
    progress_recorder = ProgressRecorder(self)
    total_processed = [0]
    progress_recorder.set_progress(total_processed[0], 100, uploaded_files)

    for file in uploaded_files:
        file = 'uploaded_files/reports/' + file
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
            for page_number in range(len(document)):
                progress_recorder.set_progress(int((total_processed[0] + page_number) / pages_count * 100), 100,
                                               uploaded_files)
                page = document[page_number]
                # Извлечение текста
                text = page.get_text()
                while True:
                    if found_part:
                        current_index = 0
                    else:
                        current_index = re.search(report_parts[current_part], text, re.IGNORECASE)
                        if current_index:
                            current_index = current_index.end()

                    next_index = None
                    if current_part + 1 < len(report_parts):
                        if df is None or df is not None and page_number+1 == int(df[df['Раздел'] == report_parts[current_part+1]]['Страницы']):
                            next_index = re.search(report_parts[current_part+1], text, re.IGNORECASE)
                    if current_index or found_part:
                        text_to_write = text[current_index:next_index.start() if next_index else len(text)]
                        report_parts_info[report_parts[current_part]] += text_to_write
                        if start_page == page_number+1:
                            text_file.write(f"--- {report_parts[current_part]} --- (стр. {page_number + 1}):\n{text_to_write}\n")
                        else:
                            text_file.write(f"{text_to_write}\n")
                        found_part = True
                    if next_index:
                        current_part += 1
                        start_page = page_number+1
                        if report_parts[current_part] == 'ОГЛАВЛЕНИЕ':
                            with pdfplumber.open(file) as pdf:
                                page_tables = pdf.pages[page_number].extract_tables()
                                df = pd.DataFrame(page_tables[0], columns=['Раздел', 'Страницы'])
                                for index, row in df.iterrows():
                                    if '-' in row['Страницы']:
                                        row['Страницы'] = row['Страницы'][:row['Страницы'].find('-')]
                                report_parts = list(df['Раздел'])
                                report_parts_info = dict(list({i: report_parts_info[i] for i in report_parts if i in report_parts_info.keys()}.items()) +
                                                         list({i: '' for i in report_parts if i not in report_parts_info.keys()}.items()))
                        continue
                    break

                text = text.replace("\n", "")
                captions = []
                captions_count = text.count("Рис.")
                for i in range(captions_count):
                    first_encounter = text.find("Рис.")
                    if i != captions_count-1:
                        last_encounter = text[first_encounter+4:].find("Рис.")
                    else:
                        last_encounter = len(text)
                    caption = text[first_encounter:last_encounter]
                    captions.append(caption)
                    text = text[first_encounter+4:]

                '''
                # Подписи к рисункам
                # Split text into blocks separated by double line break.
                blocks = text.split("\n\n")
                # Remove all new lines within blocks to remove arbitary line breaks
                blocks = map(lambda x: x.replace("\n", ""), blocks)
                # Which blocks are figure captions?
                captions = []
                for block in blocks:
                    if re.search('^Рис.', block, re.IGNORECASE):
                        captions.append(block)
                '''

                for i in range(len(captions)):
                    for j in range(len(captions)):
                        if i == j:
                            continue
                        cap1 = re.search(r'Рис. \d+', captions[i], re.IGNORECASE)
                        if cap1:
                            cap1 = re.search(r'\d+', cap1.group(0), re.IGNORECASE).group(0)
                        else:
                            continue
                        cap2 = re.search(r'Рис. \d+', captions[j], re.IGNORECASE)
                        if cap2:
                            cap2 = re.search(r'\d+', cap2.group(0), re.IGNORECASE).group(0)
                        else:
                            continue
                        if int(cap1) < int(cap2):
                            captions[i], captions[j] = captions[j], captions[i]


                # Извлечение изображений
                image_list = page.get_images(full=True)
                caption_index = 0
                for img_index, img in enumerate(image_list):
                    if captions and caption_index < len(captions):
                        image_text = captions[caption_index]
                        caption_index += 1
                    img_index = img[0]
                    if img_index in extracted_images:
                        continue
                    extracted_images.append(img_index)
                    base_image = document.extract_image(img_index)
                    image_bytes = base_image["image"]
                    image_filename = f"page_{page_number + 1}_img_{img_index}.png"

                    current_folder = folder
                    print(f"Изображение извлечено: {image_filename}")
                    if captions:
                        print(f"Подпись к изображению: {image_text}")
                        image_text = image_text.lower().replace('\n', '')
                        if 'общий вид участка обследования' in image_text or 'общий вид участка' in image_text:
                            current_folder += '/Общий вид'
                        elif 'карта' in image_text or 'карты' in image_text:
                            current_folder += '/Карты'
                        elif 'схема' in image_text or 'схемы' in image_text:
                            current_folder += '/Схемы'
                        elif 'спутниковый снимок' in image_text:
                            current_folder += '/Спутниковые снимки'
                        elif 'шурф' in image_text:
                            current_folder += '/Шурфы'
                            Path(current_folder).mkdir(exist_ok=True)
                            pit = re.search(r'Шурф.* № *\d+', image_text, re.IGNORECASE)
                            if pit:
                                current_folder += '/Ш' + pit.group(0)[1:]
                        elif 'раскоп' in image_text:
                            current_folder += '/Раскопы'
                        elif 'зачистка' in image_text or 'заичистка' in image_text:
                            current_folder += '/Шурфы'
                            Path(current_folder).mkdir(exist_ok=True)
                            pit = re.search(r'Зачистка.* № *\d+', image_text, re.IGNORECASE)
                            if pit:
                                current_folder += '/З' + pit.group(0)[1:]
                        elif 'врезка' in image_text:
                            current_folder += '/Шурфы'
                            Path(current_folder).mkdir(exist_ok=True)
                            pit = re.search(r'Врезка.* № *\d+', image_text, re.IGNORECASE)
                            if pit:
                                current_folder += '/В' + pit.group(0)[1:]
                    Path(current_folder).mkdir(exist_ok=True)
                    with open(current_folder + "/" + image_filename, "wb") as img_file:
                        img_file.write(image_bytes)
            total_processed[0] += len(document)
        document.close()

        supplement = Supplement(
            maps='Map data',
            object_fotos='Object photos data',
            pits_fotos='Pits photos data',
            plans='Plans data',
            material_fotos='Material photos data',
            heritage_info='Heritage information'
        )
        supplement.save()

        scientific_report = ScientificReport(
            user_id=user,
            supplement=supplement,
            name='Scientific Report Title',
            organization='Organization Name',
            author='Author Name',
            open_list=report_parts_info['ОТКРЫТЫЙ ЛИСТ'],
            writing_date='2023-10-01',
            introduction=report_parts_info['ВВЕДЕНИЕ'],
            contractors=report_parts_info['СПИСОК ИСПОЛНИТЕЛЕЙ РАБОТ'],
            place='Research place',
            area_info='Area information',
            research_history='Research history text',
            results='Results text',
            conclusion='Conclusion text',
            source=file
        )
        scientific_report.save()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    # Указываем путь к PDF и текстовому файлу
    extract_text_and_images(choose_file())
