from django.shortcuts import render
from .forms import UploadFileForm
from .acts_processing import extract_text_and_images
import fitz
import os
import pandas as pd

def index(request):
    return render(request, 'index.html')
    
def deconstructor(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            # Получаем загруженный файл
            uploaded_files = form.cleaned_data['files']
            table = None
            for file in uploaded_files:
                # Сохраняем файл во временную директорию
                with open('uploaded_files/' + file.name, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)

                # Обработка файла PDF
                pdf_text = ""
                with fitz.open('uploaded_files/' + file.name) as pdf_doc:
                    for page in pdf_doc:
                        pdf_text += page.get_text()
                        
                new_table = extract_text_and_images('uploaded_files/' + file.name)
                if table is not None:
                    table = table._append(new_table, ignore_index=True)
                else:
                    table = new_table
            return render(request, 'deconstructor.html', {'form': form, 'table': table.to_html(classes='table table-striped')})

    else:
        form = UploadFileForm()
    return render(request, 'deconstructor.html', {'form': form})

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