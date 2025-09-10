import os
import json
from django.http import JsonResponse, FileResponse, HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils.crypto import constant_time_compare
from django.views.decorators.http import require_http_methods
import jwt
import datetime
from urllib.parse import unquote, quote, urlparse, parse_qs
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
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1),  # Токен на 1 час
        'ttl': 3600
    }
    return jwt.encode(payload, WOPI_ACCESS_SECRET, algorithm='HS256')


def verify_wopi_token(token, file_path):
    """Проверяет валидность WOPI токена"""
    try:
        payload = jwt.decode(token, WOPI_ACCESS_SECRET, algorithms=['HS256'])
        # Проверяем, что токен предназначен для этого файла
        token_path = unquote(payload['file_path']).replace('+', ' ').strip().lstrip('/')
        request_path = unquote(file_path).replace('+', ' ').strip().lstrip('/')
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

    # Декодируем URL без потери плюсов (меняем %20 на пробелы, но оставляем +)
    decoded = unquote(file_id.replace('%20', ' '))
    clean_path = decoded.strip().lstrip('/')
    logger.debug(f"AFTER DECODING: '{clean_path}'")

    # Пробуем оба варианта (с пробелами и с плюсами)
    variants = [
        clean_path,
        clean_path.replace(' ', '+')  # Для файлов типа "+УК_10_12_2018..."
    ]

    # Проверяем каждый вариант пути
    for variant in variants:
        abs_path = os.path.abspath(os.path.join(WOPI_FILE_ROOT, variant))
        root_path = os.path.abspath(WOPI_FILE_ROOT)

        # Защита от path traversal
        if not abs_path.startswith(root_path + os.sep):
            logger.debug(f"BLOCKED PATH TRAVERSAL: {abs_path}")
            continue

        if os.path.exists(abs_path):
            logger.debug(f"FOUND MATCHING PATH: {abs_path}")
            return abs_path

    logger.error(f"FILE NOT FOUND. TRIED VARIANTS: {variants}")
    return None


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

    if not access_token:
        return HttpResponse("Access token required", status=401)

    # Валидация токена с подробным логированием
    token_data = verify_wopi_token(access_token, file_id)
    if not token_data:
        logger.error(f"Invalid token for file: {file_path}")
        return HttpResponse("Invalid token", status=401)

    # Проверка времени жизни токена
    if datetime.datetime.utcnow() > datetime.datetime.fromtimestamp(token_data['exp']):
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


@csrf_exempt
def kodexplorer_proxy(request):
    """
    Прокси для Kodexplorer → Collabora.
    Новый алгоритм:
    1. Принимает path с file_name внутри
    2. Находит реальный путь к файлу (с учётом пробелов/плюсов)
    3. Генерирует WOPI-ссылку с правильным кодированием
    """
    logger.info(f"REQUEST: {request.GET}")

    logger.info("=" * 80)
    logger.info("FULL REQUEST DUMP:")
    logger.info(f"Method: {request.method}")
    logger.info(f"Path: {request.path}")
    logger.info(f"Full path: {request.get_full_path()}")
    logger.info(f"GET params: {dict(request.GET)}")
    logger.info(f"POST params: {dict(request.POST)}")
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"META data:")
    for key, value in request.META.items():
        if any(kw in key for kw in ['HTTP', 'QUERY', 'PATH', 'CONTENT']):
            logger.info(f"  {key}: {value}")

    # Логируем сырой QUERY_STRING
    query_string = request.META.get('QUERY_STRING', '')
    logger.info(f"RAW QUERY_STRING: {query_string}")

    # Парсим QUERY_STRING вручную
    from urllib.parse import parse_qs
    params = parse_qs(query_string, keep_blank_values=True)
    logger.info(f"PARSED QUERY_STRING: {params}")

    # Пробуем все возможные параметры
    path_value = request.GET.get('path', '')
    logger.info(f"Raw path value: {path_value}")

    # Декодируем и анализируем
    try:
        decoded_path = unquote(path_value)
        prefix = '/var/www/html/data'
        if decoded_path.startswith(prefix):
            decoded_path = decoded_path[len(prefix):]
        logger.info(f"Decoded path: {decoded_path}")

        # Парсим как URL
        parsed_url = urlparse(decoded_path)
        logger.info(f"Parsed URL: {parsed_url}")

        # Парсим query параметры из URL
        url_params = parse_qs(parsed_url.query, keep_blank_values=True)
        logger.info(f"URL query params: {url_params}")

        # Ищем ВСЕ возможные параметры с путями
        all_path_params = {}
        for key, values in url_params.items():
            if any(x in key.lower() for x in ['path', 'file', 'name', 'fid']):
                all_path_params[key] = values

        logger.info(f"All path-related params: {all_path_params}")

    except Exception as e:
        logger.error(f"Error parsing: {e}")

    logger.info("=" * 80)

    # Извлекаем file_name из вложенного URL
    try:
        path = request.GET.get('path')
        if not path:
            return HttpResponse("Missing 'path' parameter", status=400)

        # Достаём file_name из параметров вложенного URL
        parsed = urlparse(unquote(path))
        params = parse_qs(parsed.query)
        fid = params.get('fid', [''])[0]
        file_name = params.get('file_name', [''])[0].strip()

        logger.info(f"FID: {fid}")
        logger.info(f"File name: {file_name}")

        if not file_name:
            return HttpResponse("Missing 'file_name'", status=400)

        # Удаляем первый слэш, если есть, но сохраняем плюсы!
        file_path = unquote(file_name).lstrip('/')
        logger.info(f"EXTRACTED FILE PATH: '{file_path}'")

        import glob
        search_pattern = os.path.join(WOPI_FILE_ROOT, '**', file_name)
        found_files = glob.glob(search_pattern, recursive=True)

        if found_files:
            # Берём первый найденный файл
            full_file_path = os.path.relpath(found_files[0], WOPI_FILE_ROOT)
            logger.info(f"Found file: '{full_file_path}'")
        else:
            # Если не нашли - пробуем альтернативные варианты имени
            logger.warning(f"File '{file_name}' not found, trying alternatives...")

            # Вариант 1: Заменяем пробелы на плюсы
            alt_name_1 = file_name.replace(' ', '+')
            search_pattern_1 = os.path.join(WOPI_FILE_ROOT, '**', alt_name_1)
            found_files_1 = glob.glob(search_pattern_1, recursive=True)

            # Вариант 2: Ищем без первого слэша
            alt_name_2 = file_name.lstrip('/')
            search_pattern_2 = os.path.join(WOPI_FILE_ROOT, '**', alt_name_2)
            found_files_2 = glob.glob(search_pattern_2, recursive=True)

            if found_files_1:
                full_file_path = os.path.relpath(found_files_1[0], WOPI_FILE_ROOT)
                logger.info(f"Found with spaces replaced: '{full_file_path}'")
            elif found_files_2:
                full_file_path = os.path.relpath(found_files_2[0], WOPI_FILE_ROOT)
                logger.info(f"Found without leading slash: '{full_file_path}'")
            else:
                # Последний вариант - используем как есть
                full_file_path = file_name
                logger.warning(f"Using original filename: '{full_file_path}'")

        file_path = full_file_path

        # Генерация токена
        access_token = generate_wopi_token(
            user_id=1,  # Заглушка (реализуй свою логику)
            username='user',
            file_path=file_path,
            can_write=True
        )

        # URL для Collabora с двойным кодированием спецсимволов
        wopi_src = quote(f"http://app:8000/wopi/files/{quote(file_path)}", safe='')
        wopi_url = f"http://127.0.0.1:9980/browser/dist/cool.html?WOPISrc={wopi_src}&access_token={access_token}&lang=ru"

        return HttpResponseRedirect(wopi_url)

    except Exception as e:
        logger.error(f"PROXY ERROR: {str(e)}", exc_info=True)
        return HttpResponse(f"Server Error: {str(e)}", status=500)


def encode_file_path(file_path):
    parts = file_path.strip('/').split('/')
    encoded_parts = [quote(part, safe='') for part in parts]  # safe='' чтобы все спецсимволы кодировались
    return '/'.join(encoded_parts)
