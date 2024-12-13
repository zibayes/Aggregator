from django.shortcuts import render
from .forms import UploadFileForm
from .acts_processing import save_and_process_files
import fitz
import os
import pandas as pd
from rest_framework import viewsets
from .models import Item
from .serializers import ItemSerializer

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
                    acts = acts[acts.lower().find(',акт')+1:]
                    acts_list.append(act)
                for act in acts_list:
                    i = 0
                    for num in df_existing['Номер (если имеется) и наименование Акта ГИКЭ'].tolist():
                        if act[:act.find('\n')].replace('\r', '') == num[:num.find('\n')].replace('\r', ''):
                            df = df._append(pd.DataFrame([df_existing.iloc[i].to_list()], columns=df_existing.columns, index=[0]), ignore_index=True)
                        i += 1
            return render(request, 'deconstructor.html', {'form': form, 'task_id': None, 'table': df.to_html(classes='table table-striped')})
        else:
            form = UploadFileForm(request.POST, request.FILES)
            if form.is_valid():
                # Получаем загруженный файл
                uploaded_files = form.cleaned_data['files']
                files = []
                pages_count = 0
                for file in uploaded_files:
                    files.append(file.name)
                    # Сохраняем файл во временную директорию
                    with open('uploaded_files/' + file.name, 'wb+') as destination:
                        for chunk in file.chunks():
                            destination.write(chunk)
                    with fitz.open('uploaded_files/' + file.name) as pdf_doc:
                        pages_count += len(pdf_doc)
                # table = save_and_process_files.delay(files)
                task = save_and_process_files.delay(files, pages_count)
                # task = test_task.delay(1)
                return render(request, 'deconstructor.html', {'form': form, 'task_id': task.task_id}) # 'table': table.to_html(classes='table table-striped'),

    else:
        form = UploadFileForm()
    return render(request, 'deconstructor.html', {'form': form, 'task_id': None})

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