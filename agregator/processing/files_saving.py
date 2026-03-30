import copy
import io
import json
import os
import platform
import subprocess
from pathlib import Path
import shutil

import PIL
import fitz
import pandas as pd
from PIL import Image
import logging

from agregator.models import Act, ScientificReport, TechReport, OpenLists, ObjectAccountCard, CommercialOffers, \
    GeoObject

logger = logging.getLogger(__name__)

SOURCE_CONTENT = []  # [{'type': 'text/images/all', 'path': 'path/to/file.pdf'}, {}, ...]


def delete_files_in_directory(directory, files):
    filenames = []
    for file in files:
        filenames.append(file.name)
        file.close()
    if os.path.exists(directory) and os.path.isdir(directory):
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            if os.path.isfile(file_path):  # and any([x in file_path for x in filenames])
                os.remove(file_path)
    else:
        print(f'Директория {directory} не существует или не является директорией.')


def convert_document(input_file, output_file=None, output_format="pdf"):
    """
    Универсальная конвертация документов между форматами с автоматическим выбором метода по ОС
    Поддерживаемые форматы: .doc, .docx, .odt -> .pdf или .docx

    :param input_file: путь к входному файлу
    :param output_format: целевой формат ('pdf' или 'docx')
    :param output_file: опциональный путь к выходному файлу
    :return: путь к сконвертированному файлу
    """
    # Проверка входного файла
    if not os.path.isfile(input_file):
        raise FileNotFoundError(f"Входной файл не найден: {input_file}")

    # Проверка поддерживаемого формата вывода
    if output_format.lower() not in ('pdf', 'docx'):
        raise ValueError("Неподдерживаемый формат вывода. Используйте 'pdf' или 'docx'")

    # Формирование выходного пути
    input_path = Path(input_file)
    if not output_file:
        output_file = input_path.with_suffix(f'.{output_format}')
    output_path = Path(output_file)

    # Определение ОС
    os_type = platform.system().lower()

    try:
        if os_type == 'windows':
            try:
                return _convert_with_word(input_path, output_path, output_format)
            except Exception as word_error:
                print(f"Ошибка Word конвертации: {word_error}")
                return _convert_with_libreoffice(input_path, output_path, output_format)

        # Linux/MacOS
        return _convert_with_libreoffice(input_path, output_path, output_format)

    except Exception as e:
        raise RuntimeError(f"Ошибка конвертации файла {input_file}: {e}")


def _convert_with_word(input_path, output_path, output_format):
    """Конвертация через MS Word (Windows only)"""
    try:
        import comtypes.client
        word = comtypes.client.CreateObject('Word.Application')
        doc = word.Documents.Open(str(input_path))

        if output_format == 'pdf':
            # Формат для PDF в Word
            file_format = 17  # wdFormatPDF
        else:  # docx
            file_format = 16  # wdFormatDocumentDefault

        doc.SaveAs(str(output_path), FileFormat=file_format)
        doc.Close()
        word.Quit()

        return str(output_path)
    except Exception as e:
        # Передаем исключение для fallback-логики
        raise


def _convert_with_libreoffice(input_path, output_path, output_format):
    """Конвертация через LibreOffice (кроссплатформенный)"""
    if shutil.which('libreoffice') is None:
        raise RuntimeError("LibreOffice не установлен в системе")

    output_dir = str(output_path.parent)

    # Форматы LibreOffice
    format_map = {
        'pdf': 'pdf',
        'docx': 'docx'
    }

    try:
        subprocess.run([
            'libreoffice',
            '--headless',
            '--convert-to',
            format_map[output_format],
            '--outdir',
            output_dir,
            str(input_path)
        ], check=True, capture_output=True)

        # LibreOffice создает файлы с базовым именем, но возможно другим расширением
        base_filename = input_path.stem
        generated_file = Path(output_dir) / f"{base_filename}.{output_format}"

        # Если LibreOffice сохранил не туда, куда ожидалось
        if generated_file != output_path:
            generated_file.rename(output_path)

        return str(output_path)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"LibreOffice ошибка: {e.stderr.decode().strip()}")
    except Exception as e:
        raise RuntimeError(f"Ошибка LibreOffice конвертации: {e}")


def get_page_count(file_path):
    """Получает количество страниц в документе (кросс-платформенно)"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    try:
        if ext == '.pdf':
            with fitz.open(file_path) as doc:
                return len(doc)

        elif ext == '.doc' or ext == '.docx':
            if platform.system() == 'Windows':
                return _get_doc_page_count_win32(file_path)
            return _get_doc_page_count_linux(file_path)

        elif ext == '.odt':
            if platform.system() == 'Windows':
                return _get_odt_page_count_win32(file_path)
            return _get_odt_page_count_linux(file_path)

    except Exception as e:
        print(f"Ошибка при обработке {file_path}: {e}")

    # Фолбэк через LibreOffice
    return _get_page_count_via_libreoffice(file_path)


def _get_doc_page_count_win32(file_path):
    """Подсчет страниц DOC через MS Word на Windows"""
    import win32com.client

    word = win32com.client.Dispatch("Word.Application")
    doc = word.Documents.Open(os.path.abspath(file_path))
    count = doc.ComputeStatistics(2)  # wdStatisticPages
    doc.Close(False)
    word.Quit()
    return count


def _get_odt_page_count_win32(file_path):
    """Подсчет страниц ODT через MS Word на Windows"""
    import win32com.client

    word = win32com.client.Dispatch("Word.Application")
    doc = word.Documents.Open(os.path.abspath(file_path))
    count = doc.ComputeStatistics(2)  # wdStatisticPages
    doc.Close(False)
    word.Quit()
    return count


def _get_doc_page_count_linux(file_path):
    """Подсчет страниц DOC на Linux через LibreOffice"""
    return _get_page_count_via_libreoffice(file_path)


def _get_odt_page_count_linux(file_path):
    """Подсчет страниц ODT на Linux через LibreOffice"""
    return _get_page_count_via_libreoffice(file_path)


def _get_page_count_via_libreoffice(file_path):
    """Универсальный подсчет через LibreOffice"""
    try:
        result = subprocess.run(
            ['libreoffice', '--headless', '--cat', os.path.abspath(file_path)],
            capture_output=True,
            text=True,
            check=True
        )

        for line in result.stdout.splitlines():
            if line.startswith('Number of pages:'):
                return int(line.split(':')[1].strip())

    except subprocess.CalledProcessError as e:
        print(f"LibreOffice error: {e.stderr}")

    print(f"Не удалось определить количество страниц в файле {file_path}")
    return 1


def raw_open_lists_save(uploaded_files, user_id, is_public, origin_filename=None, upload_source=None):
    open_lists_ids = []
    for file in uploaded_files:
        open_list = OpenLists(user_id=user_id, is_public=is_public)
        open_list.save()
        if origin_filename:
            origin_filename_no_ext = origin_filename[:origin_filename.rfind('.')]
        else:
            origin_filename_no_ext = file.name[:file.name.rfind('.')]
        path = f'Открытые листы/{origin_filename_no_ext}'
        full_path = f'uploaded_files/' + path
        Path(full_path).mkdir(parents=True, exist_ok=True)
        if isinstance(file, PIL.Image.Image):
            open_list.origin_filename = origin_filename
            open_list.upload_source = upload_source
            new_filename = origin_filename_no_ext + '.png'
            file.save(full_path + '/' + new_filename, format='PNG', optimize=True)
            '''
            image_buffer = io.BytesIO()
            image_buffer.seek(0)
            with open(full_path + '/' + new_filename, 'wb+') as destination:
                destination.write(image_buffer.read())
            '''
        else:
            open_list.origin_filename = file.name
            open_list.upload_source = {'source': 'Пользовательский файл'}
            new_filename = origin_filename_no_ext + file.name[file.name.rfind('.'):]
            with open(full_path + '/' + new_filename, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
        open_list.source = path + '/' + new_filename
        open_list.save()
        open_lists_ids.append(open_list.id)
    return open_lists_ids


def load_raw_open_lists(open_lists_ids):
    pages_count = {}
    open_lists = []
    for open_list_id in open_lists_ids:
        open_list = OpenLists.objects.get(id=open_list_id)
        folder = f'uploaded_files/'

        if open_list.source.name.lower().endswith(('.png', '.jpg', '.bmp', '.tiff')):
            new_filename = open_list.source.name[:open_list.source.name.rfind('.')] + '.pdf'
            img = Image.open(folder + '/' + open_list.source.name)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(folder + '/' + new_filename, save_all=True)
            open_list.source = new_filename
            open_list.save()

        with fitz.open(folder + '/' + open_list.source.name) as pdf_doc:
            pages_count[str(open_list.id)] = len(pdf_doc)
        open_lists.append(open_list)
    return open_lists, pages_count


def raw_reports_save(file_groups, uploaded_files, report_type, user_id, is_public, upload_source=None):
    if report_type == Act:
        report_directory = 'Акты ГИКЭ'
    elif report_type == ScientificReport:
        report_directory = 'Научные отчёты'
    elif report_type == TechReport:
        report_directory = 'Научно-технические отчёты'
    else:
        report_directory = ''
    reports_ids = []
    for value in file_groups.values():
        save_report(value, reports_ids, report_type, user_id, is_public, report_directory,
                    upload_source)
    for file in uploaded_files:
        save_report(file, reports_ids, report_type, user_id, is_public, report_directory,
                    upload_source)
    return reports_ids


def save_report(files, reports_ids, report_type, user_id, is_public, report_directory,
                upload_source):
    source_content = []
    report = report_type(user_id=user_id, is_public=is_public)
    report.save()
    report_id = report.id
    reports_ids.append(report_id)
    report_folder_name = None
    if isinstance(files, list) and len(files) > 0:
        report_folder_name = files[0]['file'].name
    else:
        report_folder_name = files.name
    report_folder_name = report_folder_name[:report_folder_name.rfind('.')]
    path = f'uploaded_files/{report_directory}/{report_folder_name}'
    Path(path).mkdir(parents=True, exist_ok=True)
    if isinstance(files, list):
        i = 0
        for file in files:
            save_report_source(report, file['file'], path, report_directory, report_id, source_content,
                               file['type'], i, upload_source)
            i += 1
    else:
        save_report_source(report, files, path, report_directory, report_id,
                           source_content, upload_source=upload_source)
    report.source = source_content
    report.save()


def save_report_source(report, file, path, report_directory, report_id, source_content,
                       type=None, index=None, upload_source=None):
    origin_name = file.name
    if upload_source:
        origin_name = origin_name.replace('%20', ' ')
        report.upload_source = upload_source
    else:
        report.upload_source = {'source': 'Пользовательский файл'}

    file_path = path + '/' + file.name

    # Вычисляем хеш файла
    try:
        from agregator.hash import calculate_file_hash
        file_hash = calculate_file_hash(file_path)
    except Exception as e:
        logger.error(f"Ошибка при вычислении хеша файла {file_path}: {e}")
        file_hash = None

    if index:
        source_content.append({
            'type': type,
            'path': file_path,
            'origin_filename': origin_name,
            'file_hash': file_hash
        })
    else:
        source_content.append({
            'type': 'all',
            'path': file_path,
            'origin_filename': origin_name,
            'file_hash': file_hash
        })

    with open(file_path, 'wb+') as destination:
        if upload_source:
            destination.write(file.read())
            file.close()
        else:
            for chunk in file.chunks():
                destination.write(chunk)


def load_raw_reports(reports_ids, report_type):
    reports = []
    pages_count = {}
    for report_id in reports_ids:
        report = report_type.objects.get(id=report_id)
        report.source = report.source_dict
        i = 0
        for source in report.source_dict:
            if source['path'].lower().endswith(('.doc', '.docx')):
                new_filename = source['path'][:source['path'].rfind('.')] + '.pdf'
                in_file = os.path.abspath(source['path'])
                out_file = os.path.abspath(new_filename)

                convert_document(in_file, out_file, 'pdf')
                source['path'] = new_filename
                report.source[i]['path'] = new_filename
                report.save()

            with fitz.open(os.path.abspath(source['path'])) as pdf_doc:
                pages_count[source['path']] = len(pdf_doc)
            i += 1
        report.save()
        reports.append(report)
    return reports, pages_count


def raw_account_cards_save(uploaded_files, user_id, is_public, upload_source=None):
    account_cards_ids = []
    for file in uploaded_files:
        account_card = ObjectAccountCard(user_id=user_id, is_public=is_public)
        account_card.save()
        account_card_id = account_card.id
        account_cards_ids.append(account_card_id)
        path = f'uploaded_files/Учётные карты/{file.name[:file.name.rfind('.')]}'
        Path(path).mkdir(parents=True, exist_ok=True)
        account_card.upload_source = {'source': 'Пользовательский файл'}

        with open(path + '/' + file.name, 'wb+') as destination:
            if upload_source:
                destination.write(file.read())
                file.close()
            else:
                for chunk in file.chunks():
                    destination.write(chunk)

        source_content = []
        file_path = path + '/' + file.name

        try:
            from agregator.hash import calculate_file_hash
            file_hash = calculate_file_hash(file_path)
        except Exception as e:
            logger.error(f"Ошибка при вычислении хеша файла {file_path}: {e}")
            file_hash = None

        source_content.append({
            'type': 'all',
            'path': file_path,
            'origin_filename': file.name,
            'file_hash': file_hash
        })
        account_card.source = source_content

        account_card.save()
    return account_cards_ids


def load_raw_account_cards(account_cards_ids):
    account_cards = []
    pages_count = {}
    for account_card_id in account_cards_ids:
        account_card = ObjectAccountCard.objects.get(id=account_card_id)
        source_str = str(account_card.source)
        account_card.source = account_card.source_dict
        i = 0
        current_dict = account_card.source_dict
        for source in current_dict:
            if source['path'].lower().endswith(('.doc', '.docx')):
                in_file = os.path.abspath(source['path'])
                if source['path'].lower().endswith('.doc') and '.docx' not in source_str:
                    new_filename = source['path'][:source['path'].rfind('.')] + '.docx'
                    account_card.source.append(copy.deepcopy(source))
                    account_card.source[-1]['path'] = new_filename
                    account_card.source[-1]['origin_filename'] = account_card.source[-1]['origin_filename'][
                                                                 :account_card.source[-1]['origin_filename'].rfind(
                                                                     '.')] + '.docx'
                    out_file = os.path.abspath(new_filename)
                    convert_document(in_file, out_file, 'docx')
                pages_count[source['path']] = get_page_count(in_file)
            elif source['path'].lower().endswith('.pdf'):
                with fitz.open(source['path']) as pdf_doc:
                    pages_count[source['path']] = len(pdf_doc)
        account_card.save()
        account_cards.append(account_card)
    return account_cards, pages_count


def raw_commercial_offers_save(uploaded_files, user_id, is_public, upload_source=None):
    commercial_offers_ids = []
    for file in uploaded_files:
        commercial_offer = CommercialOffers(user_id=user_id, is_public=is_public)
        commercial_offer.save()
        commercial_offer_id = commercial_offer.id
        commercial_offers_ids.append(commercial_offer_id)
        path = f'uploaded_files/Коммерческие предложения/{file.name[:file.name.rfind('.')]}'
        Path(path).mkdir(parents=True, exist_ok=True)
        commercial_offer.origin_filename = file.name
        commercial_offer.upload_source = {'source': 'Пользовательский файл'}

        with open(path + '/' + file.name, 'wb+') as destination:
            if upload_source:
                destination.write(file.read())
                file.close()
            else:
                for chunk in file.chunks():
                    destination.write(chunk)
        commercial_offer.source = path + '/' + file.name
        commercial_offer.save()
    return commercial_offers_ids


def load_raw_commercial_offers(commercial_offers_ids):
    commercial_offers = []
    pages_count = {}
    for commercial_offer_id in commercial_offers_ids:
        commercial_offer = CommercialOffers.objects.get(id=commercial_offer_id)
        i = 0
        if commercial_offer.source.lower().endswith(('.doc', '.docx', '.odt')):
            in_file = os.path.abspath(commercial_offer.source)
            if commercial_offer.source.lower().endswith(('.doc', '.odt')):
                new_filename = commercial_offer.source[:commercial_offer.source.rfind('.')] + '.docx'
                commercial_offer.source = new_filename
                out_file = os.path.abspath(new_filename)
                convert_document(in_file, out_file, 'docx')
            pages_count[commercial_offer.source] = get_page_count(in_file)
        elif commercial_offer.source.lower().endswith('.pdf'):
            with fitz.open(commercial_offer.source) as pdf_doc:
                pages_count[commercial_offer.source] = len(pdf_doc)
        elif commercial_offer.source.lower().endswith(('.xlsx', '.xls')):
            new_filename = commercial_offer.source[
                           :commercial_offer.source.rfind('.')] + '.xlsx' if commercial_offer.source.lower().endswith(
                '.xls') else commercial_offer.source
            if commercial_offer.source.lower().endswith('.xls'):
                df = pd.read_excel(commercial_offer.source, engine='xlrd')
                df.to_excel(new_filename, index=False, engine='openpyxl')
            elif commercial_offer.source.lower().endswith('.xlsx'):
                df = pd.read_excel(commercial_offer.source, engine='openpyxl')
            commercial_offer.source = new_filename
            pages_count[commercial_offer.source] = len(df)
        commercial_offer.save()
        commercial_offers.append(commercial_offer)
    return commercial_offers, pages_count


def raw_geo_objects_save(uploaded_files, user_id, is_public, upload_source=None):
    account_cards_ids = []
    for file in uploaded_files:
        geo_object = GeoObject(user_id=user_id, is_public=is_public)
        geo_object.save()
        geo_object_id = geo_object.id
        account_cards_ids.append(geo_object_id)
        path = f'uploaded_files/Географические объекты/{file.name[:file.name.rfind('.')]}'
        Path(path).mkdir(parents=True, exist_ok=True)
        geo_object.origin_filename = file.name
        geo_object.upload_source = {'source': 'Пользовательский файл'}

        with open(path + '/' + file.name, 'wb+') as destination:
            if upload_source:
                destination.write(file.read())
                file.close()
            else:
                for chunk in file.chunks():
                    destination.write(chunk)
        geo_object.source = path + '/' + file.name
        geo_object.save()
    return account_cards_ids


def load_raw_geo_objects(geo_objects_ids):
    geo_objects = []
    pages_count = {}
    for geo_object_id in geo_objects_ids:
        geo_object = GeoObject.objects.get(id=geo_object_id)
        geo_object.save()
        pages_count[geo_object.source] = 1
        geo_objects.append(geo_object)
    return geo_objects, pages_count
