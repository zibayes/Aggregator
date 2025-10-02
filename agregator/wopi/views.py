import os
import json
from django.http import JsonResponse, FileResponse, HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils.crypto import constant_time_compare
from django.views.decorators.http import require_http_methods
import jwt
import datetime
from urllib.parse import unquote, quote, unquote_plus, urlparse, parse_qs
import logging
from archeology.settings import BASE_URL
import time
from django.utils import timezone

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
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1),
        'ttl': 3600
    }
    return jwt.encode(payload, WOPI_ACCESS_SECRET, algorithm='HS256')


def verify_wopi_token(token, file_path):
    """Проверяет валидность WOPI токена"""
    try:
        payload = jwt.decode(token, WOPI_ACCESS_SECRET, algorithms=['HS256'])
        # Проверяем, что токен предназначен для этого файла
        token_path = unquote(payload['file_path']).strip().lstrip('/')
        request_path = unquote(file_path).strip().lstrip('/')
        if token_path != request_path:
            logger.error(f"Token path mismatch: '{token_path}' != '{request_path}'")
            return None
        return payload
    except jwt.InvalidTokenError as e:
        logger.error(f"Token validation failed: {str(e)}")
        return None


def get_safe_path(file_id):
    """
    Обрабатывает ЛЮБЫЕ названия файлов:
    - Декодирует URL (%20 → пробелы, %2B → '+')
    - Проверяет пути с пробелами и плюсами на существование
    - Защита от path traversal (../)
    """
    logger.debug(f"RAW file_id: '{file_id}'")
    # Декодируем URL стандартным способом
    decoded = unquote(file_id)
    clean_path = decoded.strip().lstrip('/')
    logger.debug(f"AFTER DECODING: '{clean_path}'")

    # Проверяем несколько вариантов имен файлов
    path_variants = [
        clean_path,  # стандартное декодирование
        clean_path.replace('+', ' ')  # заменяем плюсы на пробелы
    ]

    for path in path_variants:
        abs_path = os.path.abspath(os.path.join(WOPI_FILE_ROOT, path))
        root_path = os.path.abspath(WOPI_FILE_ROOT)

        # Защита от path traversal
        if not abs_path.startswith(root_path + os.sep):
            logger.debug(f"BLOCKED PATH TRAVERSAL: {abs_path}")
            continue

        if os.path.exists(abs_path):
            logger.debug(f"FOUND MATCHING PATH: {abs_path}")
            return abs_path

    logger.error(f"FILE NOT FOUND. TRIED VARIANTS: {', '.join(path_variants)}")
    return None


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def wopi_endpoint(request, file_id):
    """
    Обрабатывает два основных запроса WOPI:
    - GET к /wopi/files/<file_id> -> CheckFileInfo
    - GET к /wopi/files/<file_id>/contents -> GetFile
    """
    logger.debug(f"wopi_endpoint called with method {request.method} and file_id {file_id}")
    if request.method == 'POST':
        logger.error("POST request received in wopi_endpoint - should be handled by wopi_contents!")
        return HttpResponse("POST not supported here", status=400)
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

    if not access_token:
        return HttpResponse("Access token required", status=401)

    # Валидация токена с подробным логированием
    token_data = verify_wopi_token(access_token, file_id)
    if not token_data:
        logger.error(f"Invalid token for file: {file_path}")
        return HttpResponse("Invalid token", status=401)

    # Проверка времени жизни токена
    if timezone.now() > datetime.datetime.fromtimestamp(token_data['exp'], tz=datetime.timezone.utc):
        return HttpResponse("Token expired", status=401)

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
        last_modified = int(os.path.getmtime(file_path) * 1000)

        can_write = token_data.get('can_write', False)

        response_data = {
            'BaseFileName': file_name,
            'Size': file_size,
            'OwnerId': 'admin',
            'UserId': token_data.get('user_id', 'anonymous'),
            'UserFriendlyName': token_data.get('username', 'Anonymous'),
            'UserCanWrite': can_write,  # Важно! Определяет права в Collabora
            'UserCanNotWriteRelative': False,
            'SupportsUpdate': True,
            'SupportsLocks': False,
            'SupportsGetLock': False,
            'SupportsCobalt': False,
            'SupportsRename': True,
            'SupportsDeleteFile': True,
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
            'CloseButtonClosesWindow': True,
            'DownloadUrl': f'/wopi/files/{quote(file_id)}/contents?download=1',
            'HostEditUrl': f'/uploaded_files/{file_id}',
            'HostViewUrl': f'/uploaded_files/{file_id}',
            'FileUrl': f'{BASE_URL}/wopi/files/{quote(file_id)}/contents',

            'X-WOPI-ServerVersion': '1.0',
            'X-WOPI-CollectionError': 'none',
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


@csrf_exempt
@require_http_methods(["GET", "POST"])
def wopi_contents(request, file_id):
    if request.method == "GET":
        return wopi_get_file(request, file_id)
    elif request.method == "POST":
        return wopi_put_file(request, file_id)
    return HttpResponse(status=405)


def wopi_put_file(request, file_id):
    """Обрабатывает запрос WOPI PutFile - сохраняет изменения из Collabora"""
    logger.debug(f"PUT_FILE request for: {file_id}")
    logger.debug(f"Content-Length: {request.headers.get('Content-Length')}")
    logger.debug(f"Content-Type: {request.headers.get('Content-Type')}")

    file_path = get_safe_path(file_id)
    if file_path is None:
        return HttpResponse("Invalid file path", status=400)

    # Проверка токена
    access_token = request.GET.get('access_token', '')
    if not access_token:
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            access_token = auth_header[7:]

    logger.debug(f"Access token: {access_token}")

    if not access_token:
        return HttpResponse("Access token required", status=401)

    token_data = verify_wopi_token(access_token, file_id)
    if not token_data or not token_data.get('can_write', False):
        return HttpResponse("Access denied", status=403)

    try:
        # Сохраняем файл
        with open(file_path, 'wb') as f:
            f.write(request.body)
        current_time = int(time.time() * 1000)

        # Возвращаем правильный заголовок с временем модификации
        response = HttpResponse(status=200)
        response['X-WOPI-ItemVersion'] = str(current_time)
        response['X-LOOL-WOPI-Timestamp'] = str(current_time)
        response['Content-Length'] = '0'
        file_size = os.path.getsize(file_path)
        response['X-WOPI-ItemVersion'] = str(current_time)
        response['X-WOPI-ItemSize'] = str(file_size)
        return response

    except IOError as e:
        logger.error(f"Error saving file {file_path}: {e}")
        return HttpResponse(status=500)


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


@csrf_exempt
def kodexplorer_proxy(request):
    """
    Прокси для Kodexplorer → Collabora.
    Новый алгоритм:
    1. Принимает path с file_name внутри
    2. Находит реальный путь к файлу (с учётом пробелов/плюсов)
    3. Генерирует WOPI-ссылку с правильным кодированием
    """
    try:
        # Получаем полный путь из параметра
        full_path = request.GET.get('path', '')
        if not full_path:
            return HttpResponse("Missing path parameter", status=400)

        logger.info(f"Full path from Kodexplorer: {full_path}")

        # Убираем корневую часть пути Kodexplorer
        kode_root = '/var/www/html/data/uploaded_files/'
        if full_path.startswith(kode_root):
            file_path = full_path[len(kode_root):]
            logger.info(f"Relative file path: {file_path}")
        else:
            file_path = full_path
            logger.info(f"Using original path: {file_path}")

        # absolute_path = os.path.join(WOPI_FILE_ROOT, file_path)
        absolute_path = get_safe_path(file_path)

        if absolute_path is None or not os.path.exists(absolute_path):
            logger.error(f"File not found: {absolute_path}")
            return HttpResponse("File not found", status=404)

        logger.info(f"File exists: {absolute_path}")

        # Генерация токена
        access_token = generate_wopi_token(
            user_id=request.user.id if request.user.is_authenticated else 'anonymous',
            username=request.user.username if request.user.is_authenticated else 'Anonymous',
            file_path=file_path,
            can_write=True
        )

        # Формируем WOPI URL
        encoded_path = encode_file_path(file_path)
        wopi_src = quote(f"http://app:8000/wopi/files/{encoded_path}", safe='')
        wopi_url = f"http://127.0.0.1:9980/browser/dist/cool.html?WOPISrc={wopi_src}&access_token={access_token}&lang=ru"

        logger.info(f"Redirecting to Collabora: {wopi_url}")
        return HttpResponseRedirect(wopi_url)

    except Exception as e:
        logger.error(f"PROXY ERROR: {str(e)}", exc_info=True)
        return HttpResponse(f"Server Error: {str(e)}", status=500)


def encode_file_path(file_path):
    parts = file_path.strip('/').split('/')
    encoded_parts = [quote(part, safe='') for part in parts]  # safe='' чтобы все спецсимволы кодировались
    return '/'.join(encoded_parts)
