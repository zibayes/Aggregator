import os
import json
from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils.crypto import constant_time_compare
from django.views.decorators.http import require_http_methods

# Путь к папке с файлами, который мы смонтировали
WOPI_FILE_ROOT = getattr(settings, 'WOPI_FILE_ROOT', '/app/user_data')

# Простой "секрет" для проверки подлинности запросов (в реальности нужно что-то посложнее)
WOPI_ACCESS_SECRET = 'your_very_secret_key_here_change_me'


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def wopi_endpoint(request, file_id):
    """
    Обрабатывает два основных запроса WOPI:
    - GET к /wopi/files/<file_id> -> CheckFileInfo
    - GET к /wopi/files/<file_id>/contents -> GetFile
    """
    file_path = os.path.join(WOPI_FILE_ROOT, file_id)

    # Проверяем, существует ли файл
    if not os.path.isfile(file_path):
        return HttpResponse(status=404)

    # Определяем, какой именно запрос пришёл
    if request.method == 'GET' and 'contents' not in request.path:
        # Это запрос CheckFileInfo
        return handle_check_file_info(request, file_path, file_id)
    elif request.method == 'GET' and 'contents' in request.path:
        # Это запрос GetFile
        return handle_get_file(request, file_path)
    else:
        return HttpResponse(status=400)


def handle_check_file_info(request, file_path, file_id):
    """Обрабатывает запрос WOPI CheckFileInfo"""
    file_name = os.path.basename(file_path)
    file_size = os.path.getsize(file_path)

    response_data = {
        'BaseFileName': file_name,
        'Size': file_size,
        'OwnerId': 'admin',
        'UserId': 'admin',  # Collabora передаст этого пользователя в интерфейс
        'UserFriendlyName': 'Admin',
        'UserCanWrite': True,  # Разрешаем редактирование
        'UserCanNotWriteRelative': False,
        'SupportsLocks': False,
        'SupportsUpdate': True,
        'SupportsGetLock': False,
        'ReadOnly': False,
        'RestrictedWebViewOnly': False,
        'LastModifiedTime': os.path.getmtime(file_path),
    }
    return JsonResponse(response_data)


def handle_get_file(request, file_path):
    """Обрабатывает запрос WOPI GetFile - отдаёт содержимое файла"""
    try:
        response = FileResponse(open(file_path, 'rb'))
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
        return response
    except IOError:
        return HttpResponse(status=404)


# Обработчик для сохранения файла (POST /contents)
@csrf_exempt
@require_http_methods(['POST'])
def wopi_put_file(request, file_id):
    """Обрабатывает запрос WOPI PutFile - сохраняет изменения из Collabora"""
    file_path = os.path.join(WOPI_FILE_ROOT, file_id)

    try:
        with open(file_path, 'wb') as f:
            f.write(request.body)
        return HttpResponse(status=200)
    except IOError:
        return HttpResponse(status=500)
