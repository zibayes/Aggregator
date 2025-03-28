from docx import Document
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import os
import zipfile
import win32com.client


def choose_file() -> str:
    # Открываем окно выбора файла
    file_path = filedialog.askopenfilename(title="Выберите DOC или DOCX файл")
    if file_path:
        return file_path


def convert_doc_to_docx(doc_file):
    # Создаем объект Word
    word = win32com.client.Dispatch("Word.Application")
    word.visible = False  # Скрываем окно Word

    # Открываем документ
    try:
        doc = word.Documents.Open(doc_file)
    except Exception as e:
        word.Quit()  # Закрываем Word в случае ошибки
        raise RuntimeError(f"Ошибка при открытии файла: {e}")

    # Конвертируем в .docx
    docx_file = os.path.splitext(doc_file)[0] + ".docx"
    doc.SaveAs(docx_file, FileFormat=16)  # 16 — это код формата .docx

    # Закрываем документ и выходим из Word
    doc.Close()
    word.Quit()

    return docx_file


def extract_text_tables_and_images(docx_file, output_folder):
    # Открываем документ
    doc = Document(docx_file)

    # Извлекаем весь текст
    text = []
    for paragraph in doc.paragraphs:
        text.append(paragraph.text)

    # Извлекаем таблицы
    tables = []
    for table in doc.tables:
        table_data = []
        for row in table.rows:
            row_data = []
            for cell in row.cells:
                row_data.append(cell.text)
            table_data.append(row_data)
        tables.append(table_data)

    # Извлекаем изображения
    images = []
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)  # Создаем папку для сохранения изображений

    # Открываем .docx файл как ZIP-архив
    with zipfile.ZipFile(docx_file, 'r') as zip_file:
        # Ищем файлы изображений в папке word/media
        for file in zip_file.namelist():
            if file.startswith('word/media/'):
                # Извлекаем изображение
                image_name = os.path.basename(file)
                image_path = os.path.join(output_folder, image_name)
                with open(image_path, 'wb') as img_file:
                    img_file.write(zip_file.read(file))
                images.append(image_path)

    # Возвращаем текст, таблицы и изображения
    return "\n".join(text), tables, images


# Создаем папку для сохранения изображений
output_folder = os.path.normpath('C:/Users/Admin.DESKTOP-TA0PCP4/Desktop/Archeology/Account cards/Images')
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# Выбираем файл
file_path = os.path.normpath(choose_file())
print(file_path)

# Проверяем формат файла
if file_path.lower().endswith('.doc'):
    # Конвертируем .doc в .docx
    print("Конвертация .doc в .docx...")
    file_path = convert_doc_to_docx(file_path)
    print(f"Файл конвертирован: {file_path}")

# Извлекаем текст, таблицы и изображения
text, tables, images = extract_text_tables_and_images(file_path, output_folder)

# Выводим текст
print("Текст из документа:")
print(text)

# Выводим таблицы
print("\nТаблицы из документа:")
for i, table in enumerate(tables, start=1):
    print(f"Таблица {i}:")
    for row in table:
        print(row)

# Выводим изображения
print("\nИзвлеченные изображения:")
for image in images:
    print(f"Изображение сохранено: {image}")
