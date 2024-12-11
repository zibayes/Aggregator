from django.shortcuts import render
from .forms import UploadFileForm
from .acts_processing import extract_text_and_images, save_and_process_files, test_task
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

class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer

def index(request):
    return render(request, 'index.html')
    
def deconstructor(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            # Получаем загруженный файл
            uploaded_files = form.cleaned_data['files']
            # table = save_and_process_files(uploaded_files)
            task = test_task.delay(1)
            return render(request, 'deconstructor.html', {'form': form, 'task_id': task.task_id}) # 'table': table.to_html(classes='table table-striped'), 

    else:
        form = UploadFileForm()
    return render(request, 'deconstructor.html', {'form': form, 'task_id': None})

def constructor(request):
    return render(request, 'constructor.html')

def interactive_map(request):
    return render(request, 'interactive_map.html')

def demonstrator(request):
    table_path = "uploaded_files/РЕЕСТР актов ГИКЭ.xlsx"
    df_existing = None
    if os.path.exists(table_path):
        df_existing = pd.read_excel(table_path).to_html(classes='table table-striped')
    return render(request, 'demonstrator.html', {'table': df_existing})