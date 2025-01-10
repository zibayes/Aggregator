import json
import os
from pathlib import Path
import comtypes.client
import fitz
import pythoncom
from PIL import Image

from .models import Act, ScientificReport, OpenLists

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


def raw_files_save(uploaded_files, user_id):
    path = 'uploaded_files/users/' + str(user_id)
    Path(path).mkdir(exist_ok=True)
    file_names = [x.name for x in uploaded_files]
    for file in uploaded_files:
        with open(path + '/' + file.name, 'wb+') as destination:
            for chunk in file.chunks():
                destination.write(chunk)
    return file_names


def load_raw_files(uploaded_files, user_id):
    path = 'uploaded_files/users/' + str(user_id)
    files = []
    for file in uploaded_files:
        if not isinstance(file, str):
            filename = file.name
        else:
            filename = path + '/' + file
        f = open(filename, 'rb+')
        files.append(f)
    return files


def save_report_files(uploaded_files, file_groups, report_type, user_id):
    uploaded_files = load_raw_files(uploaded_files, user_id)
    pythoncom.CoInitialize()
    if report_type == Act:
        report_directory = 'act'
    elif report_type == ScientificReport:
        report_directory = 'report'
    else:
        report_directory = ''
    reports_ids = []
    pages_count = {}
    origin_filenames = {}
    path = ''
    for value in file_groups.values():
        i = 0
        source_content = []
        report = report_type(user_id=user_id)
        report.save()
        report_id = report.id
        reports_ids.append(report_id)
        for file in value:
            if i == 0:
                path = f'uploaded_files/{report_directory}s/{report_id}_{report_directory}'
                Path(path).mkdir(exist_ok=True)
            origin_name = file['file'].name
            file['file'].name = f'{report_id}_{report_directory}_{i}' + file['file'].name[file['file'].name.rfind('.'):]

            if file['file'].name.lower().endswith(('.doc', '.docx')):
                wdFormatPDF = 17

                with open(path + '/' + file['file'].name, 'wb+') as destination:
                    destination.write(file.read())
                in_file = os.path.abspath(path + '/' + file['file'].name)
                out_file = os.path.abspath(path + '/' + file['file'].name[:file['file'].name.rfind('.')] + '.pdf')

                word = comtypes.client.CreateObject('Word.Application')
                doc = word.Documents.Open(in_file)
                doc.SaveAs(out_file, FileFormat=wdFormatPDF)
                doc.Close()
                word.Quit()
                file['file'].name = file['file'].name[:file['file'].name.rfind('.')] + '.pdf'

            source_content.append({'type': file['type'], 'path': path + '/' + file['file'].name})
            origin_filenames[source_content[-1]['path']] = origin_name
            with open(path + '/' + file['file'].name, 'wb+') as destination:
                destination.write(file.read())
            with fitz.open(path + '/' + file['file'].name) as pdf_doc:
                pages_count[source_content[-1]['path']] = len(pdf_doc)
            i += 1
        report.source = source_content
        report.save()
    for file in uploaded_files:
        converted_source = None
        source_content = []
        report = report_type(user_id=user_id)
        report.save()
        reports_ids.append(report.id)
        origin_name = file.name
        file.name = f'{report.id}_{report_directory}' + file.name[file.name.rfind('.'):]
        path = f'uploaded_files/{report_directory}s/{report.id}_{report_directory}'
        Path(path).mkdir(exist_ok=True)

        if file.name.lower().endswith(('.doc', '.docx')):
            wdFormatPDF = 17

            with open(path + '/' + file.name, 'wb+') as destination:
                destination.write(file.read())
                # for chunk in file.chunks():
                #    destination.write(chunk)
            converted_source = in_file = os.path.abspath(path + '/' + file.name)
            out_file = os.path.abspath(path + '/' + file.name[:file.name.rfind('.')] + '.pdf')

            word = comtypes.client.CreateObject('Word.Application')
            doc = word.Documents.Open(in_file)
            doc.SaveAs(out_file, FileFormat=wdFormatPDF)
            doc.Close()
            word.Quit()
            file.name = file.name[:file.name.rfind('.')] + '.pdf'

        source_content.append({'type': 'all', 'path': path + '/' + file.name})
        origin_filenames[source_content[-1]['path']] = origin_name
        report.source = source_content
        report.save()
        if converted_source is None:
            with open(path + '/' + file.name, 'wb+') as destination:
                destination.write(file.read())
        else:
            os.remove(converted_source)
        with fitz.open(path + '/' + file.name) as pdf_doc:
            pages_count[source_content[-1]['path']] = len(pdf_doc)
    return reports_ids, pages_count, origin_filenames


def save_open_list_files(uploaded_files, user_id):
    uploaded_files = load_raw_files(uploaded_files, user_id)
    origin_filenames = {}
    pages_count = {}
    open_lists_ids = []
    for file in uploaded_files:
        open_list = OpenLists(user_id=user_id)
        open_list.save()
        path = f'open_lists/{open_list.id}_open_list'
        full_path = f'uploaded_files/' + path
        Path(full_path).mkdir(exist_ok=True)
        origin_filenames[str(open_list.id)] = file.name
        new_filename = str(open_list.id) + '_open_list.pdf'

        if file.name.lower().endswith(('.png', '.jpg', '.bmp', '.tiff')):
            with open(full_path + '/' + file.name, 'wb+') as destination:
                destination.write(file.read())
            img = Image.open(full_path + '/' + file.name)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            img.save(full_path + '/' + new_filename, save_all=True)
        elif file.name.lower().endswith('.pdf'):
            with open(full_path + '/' + new_filename, 'wb+') as destination:
                destination.write(file.read())

        with fitz.open(full_path + '/' + new_filename) as pdf_doc:
            pages_count[str(open_list.id)] = len(pdf_doc)
        open_list.source = path + '/' + new_filename
        open_list.save()
        open_lists_ids.append(open_list.id)
    return open_lists_ids, pages_count, origin_filenames


if __name__ == '__main__':
    pass
