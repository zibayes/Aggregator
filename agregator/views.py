from django.shortcuts import render
from .forms import UploadFileForm
from .acts_processing import local_storage_acts_processing
from .reports_processing import local_storage_reports_processing
from .external_sources import external_sources_processing
from .open_lists_ocr import process_open_lists
from .ask import ask_question_with_context
import fitz
import os
import pandas as pd
from rest_framework import viewsets
from .models import Item
from .serializers import ItemSerializer
import json

import asyncio
from django.http import JsonResponse
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from celery import shared_task
from celery.result import AsyncResult
from celery_progress.backend import ProgressRecorder
from django_celery_results.models import TaskResult


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer


def index(request):
    return render(request, 'index.html')


def deconstructor(request):
    if request.method == 'POST':
        if 'acts' in request.POST:
            form = UploadFileForm()
            table_path = "uploaded_files/РЕЕСТР актов ГИКЭ.xlsx"
            df = pd.DataFrame()
            if os.path.exists(table_path):
                df_existing = pd.read_excel(table_path, engine='openpyxl')
                acts = request.POST['acts']
                acts_list = []
                while len(acts) > 0:
                    if acts.lower().find(',акт') < 0:
                        acts_list.append(acts)
                        break
                    act = acts[:acts.lower().find(',акт')]
                    acts = acts[acts.lower().find(',акт') + 1:]
                    acts_list.append(act)
                for act in acts_list:
                    i = 0
                    for num in df_existing['Номер (если имеется) и наименование Акта ГИКЭ'].tolist():
                        if act[:act.find('\n')].replace('\r', '') == num[:num.find('\n')].replace('\r', ''):
                            df = df._append(
                                pd.DataFrame([df_existing.iloc[i].to_list()], columns=df_existing.columns, index=[0]),
                                ignore_index=True)
                        i += 1
            return render(request, 'deconstructor.html',
                          {'form': form, 'task_id': None, 'table': df.to_html(classes='table table-striped')})
        else:
            form = UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                # Получаем загруженный файл
                uploaded_files = form.cleaned_data['files']
                if 'file_type' in request.POST:
                    file_type = request.POST['file_type']
                else:
                    return render(request, 'deconstructor.html', {'form': form, 'task_id': None})
                if file_type == 'act':
                    task = local_storage_acts_processing(uploaded_files)
                elif file_type == 'report':
                    task = local_storage_reports_processing(uploaded_files)
                else:
                    task = None
                return render(request, 'deconstructor.html', {'form': form,
                                                              'task_id': task.task_id})  # 'table': table.to_html(classes='table table-striped'),

    else:
        form = UploadFileForm()
    return render(request, 'deconstructor.html', {'form': form, 'task_id': None})


def external_sources(request):
    is_processing = False
    if request.method == 'POST':
        external_sources_processing.delay()
        is_processing = True
    return render(request, 'external_sources.html', {'is_processing': is_processing})


def processing_status(request):
    tasks_id = list(TaskResult.objects.values_list('task_id', flat=True))
    return render(request, 'processing_status.html', {'tasks_id': tasks_id})


def constructor(request):
    return render(request, 'constructor.html')


def interactive_map(request):
    return render(request, 'interactive_map.html')


def demonstrator(request):
    table_path = "uploaded_files/РЕЕСТР актов ГИКЭ.xlsx"
    df_existing = None
    if os.path.exists(table_path):
        df_existing = pd.read_excel(table_path, engine='openpyxl').to_html(classes='table table-striped')
    return render(request, 'demonstrator.html', {'table': df_existing})


def open_list_ocr(request):
    if request.method == 'POST':
        form = UploadFileForm()
        if 'open_lists' in request.POST:
            table_path = "uploaded_files/Открытые листы.xlsx"
            df = pd.DataFrame()
            if os.path.exists(table_path):
                df_existing = pd.read_excel(table_path, engine='openpyxl')
                open_lists = request.POST['open_lists']
                ol_list = []
                while len(open_lists) > 0:
                    if open_lists.lower().find(',') < 0:
                        ol_list.append(open_lists)
                        break
                    open_list = open_lists[:open_lists.lower().find(',')]
                    open_lists = open_lists[open_lists.lower().find(',') + 1:]
                    ol_list.append(open_list)
                for ol in ol_list:
                    i = 0
                    for num in df_existing['Номер листа'].tolist():
                        if ol[:ol.find('\n')].replace('\r', '') == num[:num.find('\n')].replace('\r', ''):
                            df = df._append(
                                pd.DataFrame([df_existing.iloc[i].to_list()], columns=df_existing.columns, index=[0]),
                                ignore_index=True)
                        i += 1
            return render(request, 'open_list_ocr.html',
                          {'form': form, 'task_id': None, 'table': df.to_html(classes='table table-striped')})
        else:
            form = UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                uploaded_files = form.cleaned_data['files']
                files = []
                for file in uploaded_files:
                    files.append(file.name)
                    with open('uploaded_files/' + file.name, 'wb+') as destination:
                        for chunk in file.chunks():
                            destination.write(chunk)
                task = process_open_lists.delay(files)
                return render(request, 'open_list_ocr.html', {'form': form, 'task_id': task.task_id})
    else:
        form = UploadFileForm()
    return render(request, 'open_list_ocr.html', {'form': form, 'task_id': None})


def gpt_chat(request):
    return render(request, 'gpt_chat.html')


def ask_gpt(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        body_data = json.loads(body_unicode)
        answer = ask_question_with_context(body_data['messages'][1]['content'])
        return JsonResponse({'choices': [{'message': {'content': answer}}]})
