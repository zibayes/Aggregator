import json
import os
from pathlib import Path
import comtypes.client
import fitz
import pythoncom

from .models import Act, ScientificReport

SOURCE_CONTENT = []  # [{'type': 'text/images/all', 'path': 'path/to/file.pdf'}, {}, ...]


def save_files(uploaded_files, file_groups, report_type, user):
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
        report = report_type(user_id=user.id)
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
                    for chunk in file['file'].chunks():
                        destination.write(chunk)
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
                for chunk in file['file'].chunks():
                    destination.write(chunk)
            with fitz.open(path + '/' + file['file'].name) as pdf_doc:
                pages_count[source_content[-1]['path']] = len(pdf_doc)
            i += 1
        report.source = source_content
        report.save()
    for file in uploaded_files:
        converted_source = None
        source_content = []
        report = report_type(user_id=user.id)
        report.save()
        reports_ids.append(report.id)
        origin_name = file.name
        file.name = f'{report.id}_{report_directory}' + file.name[file.name.rfind('.'):]
        path = f'uploaded_files/{report_directory}s/{report.id}_{report_directory}'
        Path(path).mkdir(exist_ok=True)

        if file.name.lower().endswith(('.doc', '.docx')):
            wdFormatPDF = 17

            with open(path + '/' + file.name, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
            converted_source = in_file = os.path.abspath(path + '/' + file.name)
            out_file = os.path.abspath(path + '/' + file.name[:file.name.rfind('.')] + '.pdf')

            word = comtypes.client.CreateObject('Word.Application')
            doc = word.Documents.Open(in_file)
            doc.SaveAs(out_file, FileFormat=wdFormatPDF)
            doc.Close()
            word.Quit()
            file.name = file.name[:file.name.rfind('.')] + '.pdf'
            converted = True

        source_content.append({'type': 'all', 'path': path + '/' + file.name})
        origin_filenames[source_content[-1]['path']] = origin_name
        report.source = source_content
        report.save()
        if converted_source is None:
            with open(path + '/' + file.name, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)
        else:
            os.remove(converted_source)
        with fitz.open(path + '/' + file.name) as pdf_doc:
            pages_count[source_content[-1]['path']] = len(pdf_doc)
    return reports_ids, pages_count, origin_filenames


if __name__ == '__main__':
    pass
