import os
import json
from django.http import JsonResponse, FileResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils.crypto import constant_time_compare
from django.views.decorators.http import require_http_methods
import jwt
import datetime
from urllib.parse import unquote, quote
import logging

logger = logging.getLogger(__name__)

# Путь к папке с файлами, который мы смонтировали
WOPI_FILE_ROOT = getattr(settings, 'WOPI_FILE_ROOT', '/app/user_data')

# Простой "секрет" для проверки подлинности запросов (в реальности нужно что-то посложнее)
WOPI_ACCESS_SECRET = getattr(settings, 'WOPI_ACCESS_SECRET', 'your_very_secret_key_change_me')


def generate_wopi_token(user_id, username, file_path, can_write=True):
    """Генерирует JWT токен для WOPI доступа"""
    payload = {
        'user_id': user_id,
        'username': username,
        'file_path': file_path,
        'can_write': can_write,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)  # Токен на 1 час
    }
    return jwt.encode(payload, WOPI_ACCESS_SECRET, algorithm='HS256')


def verify_wopi_token(token, file_path):
    """Проверяет валидность WOPI токена"""
    try:
        payload = jwt.decode(token, WOPI_ACCESS_SECRET, algorithms=['HS256'])
        # Проверяем, что токен предназначен для этого файла
        if payload['file_path'] != file_path:
            return None
        return payload
    except jwt.InvalidTokenError:
        return None


def get_safe_path(file_id):
    """
    Безопасно вычисляет абсолютный путь к файлу, предотвращая path traversal атаки.
    Возвращает None если путь ведёт за пределы WOPI_FILE_ROOT.
    """
    logger.debug(f"DEBUG: Raw file_id from URL: '{file_id}'")
    # Декодируем URL-encoded путь (на случай, если есть пробелы или кириллица)
    requested_path = unquote(file_id)
    logger.debug(f"DEBUG: After unquote: '{requested_path}'")

    # Нормализуем путь (убираем дублирующиеся слэши, разрешаем '..')
    absolute_requested_path = os.path.abspath(os.path.join(WOPI_FILE_ROOT, requested_path))
    absolute_root_path = os.path.abspath(WOPI_FILE_ROOT)

    logger.debug(f"DEBUG: WOPI_FILE_ROOT: '{WOPI_FILE_ROOT}'")
    logger.debug(f"DEBUG: Absolute requested path: '{absolute_requested_path}'")
    logger.debug(f"DEBUG: Absolute root path: '{absolute_root_path}'")
    logger.debug(f"DEBUG: File exists: {os.path.exists(absolute_requested_path)}")

    # Проверяем, что итоговый путь находится внутри корневой папки
    if not absolute_requested_path.startswith(absolute_root_path + os.sep):
        logger.debug(f"DEBUG: PATH TRAVERSAL ATTEMPT! Blocked.")
        return None  # Path traversal attempt!

    logger.debug(f"DEBUG: Path is safe, returning: '{absolute_requested_path}'")
    return absolute_requested_path


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def wopi_endpoint(request, file_id):
    """
    Обрабатывает два основных запроса WOPI:
    - GET к /wopi/files/<file_id> -> CheckFileInfo
    - GET к /wopi/files/<file_id>/contents -> GetFile
    """
    logger.debug(f"WOPI CHECKFILEINFO: file_id='{file_id}'")
    logger.debug(f"WOPI Request: {request.method} {request.path}")
    logger.debug(f"GET params: {dict(request.GET)}")
    logger.debug(f"Headers: {dict(request.headers)}")
    if file_id.endswith('/contents'):
        file_id = file_id[:-9]
    file_path = get_safe_path(file_id)

    if file_path is None:
        logger.debug(f"ERROR: Invalid file path for file_id='{file_id}'")
        return HttpResponse("Invalid file path", status=400)

    # Проверяем, существует ли файл
    if not os.path.isfile(file_path):
        logger.debug(f"ERROR: File not found: '{file_path}'")
        return HttpResponse(status=404)

    logger.debug(f"SUCCESS: File found: '{file_path}'")

    # Пробуем получить токен из параметров URL
    access_token = request.GET.get('access_token', '')

    # Если нет в параметрах, пробуем получить из заголовка (для других клиентов)
    if not access_token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            access_token = auth_header[7:]  # Убираем 'Bearer '

    # Проверяем токен доступа
    token_data = verify_wopi_token(access_token, file_id) if access_token else None

    if not token_data:
        return HttpResponse("Invalid or missing access token", status=401)

    # Определяем, какой именно запрос пришёл
    if request.method == 'GET' and 'contents' not in request.path:
        # Это запрос CheckFileInfo
        return handle_check_file_info(request, file_path, file_id, token_data)
    elif request.method == 'GET' and 'contents' in request.path:
        # Это запрос GetFile
        return handle_get_file(request, file_path, token_data)
    else:
        return HttpResponse(status=400)


def handle_check_file_info(request, file_path, file_id, token_data):
    """Обрабатывает запрос WOPI CheckFileInfo"""
    try:
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        last_modified = os.path.getmtime(file_path)

        can_write = token_data.get('can_write', False)

        response_data = {
            'BaseFileName': file_name,
            'Size': file_size,
            'OwnerId': 'admin',
            'UserId': token_data.get('user_id', 'anonymous'),
            'UserFriendlyName': token_data.get('username', 'Anonymous'),
            'UserCanWrite': can_write,  # Важно! Определяет права в Collabora
            'UserCanNotWriteRelative': False,
            'SupportsLocks': False,
            'SupportsUpdate': True,
            'SupportsGetLock': False,
            'ReadOnly': not can_write,  # Противоположно UserCanWrite
            'RestrictedWebViewOnly': False,
            'LastModifiedTime': last_modified,

            'Version': str(last_modified),
            'BreadcrumbBrandName': 'Агрегатор',
            'BreadcrumbDocName': file_name,
            'BreadcrumbFolderName': os.path.dirname(file_id) or '/',

            'DisablePrint': False,
            'DisableExport': False,
            'DisableCopy': False,
            'EnableOwnerTermination': True,
            'HidePrintOption': False,
            'HideSaveOption': False,
            'HideExportOption': False,
            'HideUserList': False,
            'MobileViewer': True,
            'SupportsCobalt': False,
            'SupportsRename': True,
            'SupportsDeleteFile': True,
            'CloseButtonClosesWindow': True,
            'DownloadUrl': f'/wopi/files/{quote(file_id)}/contents?download=1',
            'HostEditUrl': f'/uploaded_files/{file_id}',
            'HostViewUrl': f'/uploaded_files/{file_id}',
        }
        logger.debug(f"CheckFileInfo response: {response_data}")
        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Error in CheckFileInfo: {e}")
        return HttpResponse(status=500)


def handle_get_file(request, file_path, token_data):
    """Обрабатывает запрос WOPI GetFile - отдаёт содержимое файла"""
    if not token_data.get('can_read', True):
        return HttpResponse("Access denied", status=403)
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


@csrf_exempt
@require_http_methods(['GET'])
def wopi_get_file(request, file_id):
    """Обрабатывает запрос WOPI GetFile - отдаёт содержимое файла"""
    print(f"WOPI GET FILE: file_id='{file_id}'")

    file_path = get_safe_path(file_id)

    if file_path is None:
        return HttpResponse("Invalid file path", status=400)

    if not os.path.isfile(file_path):
        return HttpResponse("File not found", status=404)

    print(f"GET FILE: Serving file: '{file_path}'")

    try:
        response = FileResponse(open(file_path, 'rb'))
        return response
    except IOError:
        return HttpResponse(status=500)
