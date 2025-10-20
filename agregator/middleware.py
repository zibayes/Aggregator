# middleware.py
import os
import html
from django.http import HttpResponse, FileResponse
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponseRedirect
from django.template.defaultfilters import filesizeformat
from pathlib import Path
import magic
import tempfile
import subprocess
import shutil
from urllib.parse import quote
from .wopi.views import generate_wopi_token


class FilePreviewMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # ИСКЛЮЧАЕМ URL-ы детальных страниц из обработки
        excluded_paths = [
            '/tech_reports/',
            '/scientific_reports/',
            '/acts/',
            '/open_lists/',
            '/account_cards/',
            '/archaeological_heritage_sites/',
            '/identified_archaeological_heritage_sites/',
        ]

        # Если путь начинается с исключенного префикса - пропускаем
        for excluded_path in excluded_paths:
            if request.path.startswith(excluded_path):
                return None

        # Проверяем, что запрос идет к медиафайлам
        if request.path.startswith(settings.MEDIA_URL):
            # Если запрошено скачивание - пропускаем
            if request.GET.get('download') == '1':
                return None

            # Получаем путь к файлу
            relative_path = request.path[len(settings.MEDIA_URL):]
            file_path = os.path.join(settings.MEDIA_ROOT, relative_path)

            # Проверяем существование файла
            if os.path.isfile(file_path):
                return self.serve_preview(request, file_path, relative_path)

        return None

    def serve_preview(self, request, file_path, filename):
        ext = Path(filename).suffix.lower()

        # Для PDF и HTML - показываем в браузере
        if ext in ['.pdf', '.html']:
            return None

        # Для изображений
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']:
            return None

        # Для текстовых файлов
        elif ext in ['.txt', '.csv', '.log', '.xml', '.htm', '.css', '.js', '.py']:
            return self._serve_office(file_path, filename, request)

        # Для офисных документов
        elif ext in ['.doc', '.docx', '.odt', '.xlsx', '.xlsm', '.xls', '.ppt', '.pptx']:
            return self._serve_office(file_path, filename, request)

        # Для KML - показываем как XML с подсветкой
        elif ext in ['.kml']:
            return self._serve_kml(file_path, filename, request)

        # Для остальных форматов - показываем информацию о файле
        else:
            return self._serve_file_info(file_path, filename, request)

    def _serve_office(self, file_path, filename, request):
        """Немедленно перенаправляем офисные документы в Collabora"""

        relative_file_path = os.path.relpath(file_path, settings.MEDIA_ROOT)

        # URL-кодируем путь для WOPI!
        encoded_file_path = quote(relative_file_path)

        # Определяем права пользователя (примерная логика)
        can_edit = self._can_user_edit_file(request.user, file_path)

        # Генерируем токен доступа
        access_token = generate_wopi_token(
            user_id=request.user.id if request.user.is_authenticated else 'anonymous',
            username=request.user.username if request.user.is_authenticated else 'anonymous',
            file_path=relative_file_path,
            can_write=can_edit
        )

        # URL для WOPI-хоста (Django) - для Collabora (внутри Docker сети)
        wopi_src_url = f"http://app:8000/wopi/files/{encoded_file_path}"

        # Формируем полный URL для открытия в Collabora
        collabora_url = f"http://127.0.0.1:9980/browser/dist/cool.html?WOPISrc={wopi_src_url}&access_token={access_token}&lang=ru"

        # Немедленный редирект на Collabora
        return HttpResponseRedirect(collabora_url)

    def _can_user_edit_file(self, user, file_path):
        """Логика проверки прав на редактирование"""
        # Здесь реализуй свою логику:
        # - Проверка авторизации
        # - Проверка прав доступа к файлу
        # - Проверка ролей пользователя и т.д.

        if not user.is_authenticated:
            return False  # Анонимы не могут редактировать

        # Пример: только суперпользователи могут редактировать
        if user.is_superuser:
            return True

        # Пример: проверка прав через модель FileAccess
        # from .models import FileAccess
        # return FileAccess.objects.filter(user=user, file_path=file_path, can_edit=True).exists()

        return False  # По умолчанию запрещаем редактирование

    def _convert_to_html(self, file_path):
        """Конвертирует офисные документы в HTML через LibreOffice"""
        import logging

        logger = logging.getLogger(__name__)

        try:
            outdir = os.path.dirname(file_path)
            filename_wo_ext = os.path.splitext(os.path.basename(file_path))[0]
            html_path = os.path.join(outdir, filename_wo_ext + '.html')

            with tempfile.TemporaryDirectory() as tmp_dir:
                base_name = os.path.basename(file_path)
                tmp_file_path = os.path.join(tmp_dir, base_name)
                shutil.copy(file_path, tmp_file_path)
                # Конвертируем через LibreOffice
                result = subprocess.run([
                    'libreoffice', '--headless', '--convert-to', 'html',
                    '--outdir', tmp_dir, tmp_file_path  # outdir, file_path
                ], capture_output=True, text=True)  # text=True для удобства логов

                logger.debug(f"LibreOffice returncode: {result.returncode}")
                logger.debug(f"LibreOffice stdout: {result.stdout}")
                logger.debug(f"LibreOffice stderr: {result.stderr}")
                logger.debug(f"Ожидаемый HTML файл: {html_path}")
                logger.debug(f"HTML файл существует: {os.path.exists(html_path)}")

                html_file = os.path.splitext(tmp_file_path)[0] + '.html'
                if result.returncode == 0 and os.path.exists(html_file):
                    with open(html_file, 'r', encoding='utf-8') as f:
                        return f.read()
                else:
                    logger.error("Конвертация в HTML не удалась или файл не найден")

        except Exception as e:
            logger.exception(f"Ошибка конвертации в HTML: {e}")

        return None

    def _serve_text(self, file_path, filename, request):
        """Показ текстовых файлов с экранированием HTML"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='cp1251') as f:
                    content = f.read()
            except:
                return self._serve_file_info(file_path, filename, request)

        # Экранируем HTML-теги для безопасного отображения
        escaped_content = html.escape(content)
        download_url = f"{request.path}?download=1"

        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>{html.escape(filename)}</title>
            <style>
                body {{ 
                    margin: 0; 
                    padding: 20px 20px 20px 0;
                    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                    background: #f5f5f5;
                    font-size: 14px;
                }}
                .download-btn {{
                    position: fixed;
                    top: 15px;
                    right: 15px;
                    z-index: 1000;
                    padding: 10px 20px;
                    background: #007bff;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    font-family: Arial;
                    font-size: 14px;
                }}
                .download-btn:hover {{ background: #0056b3; }}
                pre {{
                    background: white;
                    padding: 20px;
                    border-radius: 5px;
                    border: 1px solid #ddd;
                    overflow-x: auto;
                    max-width: 100%;
                    line-height: 1.4;
                }}
            </style>
        </head>
        <body>
            <a href="{download_url}" class="download-btn" download>
                ⬇️ Скачать
            </a>
            <pre>{escaped_content}</pre>
        </body>
        </html>
        '''
        return HttpResponse(html_content)

    def _serve_kml(self, file_path, filename, request):
        """Показ KML файлов с подсветкой XML"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            try:
                with open(file_path, 'r', encoding='cp1251') as f:
                    content = f.read()
            except:
                return self._serve_file_info(file_path, filename, request)

        # Экранируем содержимое для безопасного отображения
        escaped_content = html.escape(content)
        download_url = f"{request.path}?download=1"

        # Простая подсветка XML тегов
        highlighted_content = escaped_content.replace('&lt;', '<span class="xml-tag">&lt;')
        highlighted_content = highlighted_content.replace('&gt;', '&gt;</span>')
        highlighted_content = highlighted_content.replace('&lt;/', '<span class="xml-tag">&lt;/')

        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>{html.escape(filename)}</title>
            <style>
                body {{
                    margin: 0;
                    padding: 20px 20px 20px 0;
                    font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
                    background: #f9f9f9;
                    color: #222222;
                    font-size: 14px;
                }}
                .download-btn {{
                    position: fixed;
                    top: 15px;
                    right: 15px;
                    z-index: 1000;
                    padding: 10px 20px;
                    background: #007bff;
                    color: white;
                    text-decoration: none;
                    border-radius: 5px;
                    font-family: Arial, sans-serif;
                    font-size: 14px;
                }}
                .download-btn:hover {{ background: #0056b3; }}
                pre {{
                    background: #ffffff;
                    padding: 20px;
                    border-radius: 5px;
                    border: 1px solid #ccc;
                    overflow-x: auto;
                    max-width: 100%;
                    line-height: 1.4;
                    color: #222222;
                }}
                .xml-tag {{ color: #000000; font-weight: bold; }}
                .xml-attr {{ color: #0451a5; }}
                .xml-value {{ color: #000000; }}
            </style>
        </head>
        <body>
            <a href="{download_url}" class="download-btn" download>
                ⬇️ Скачать KML
            </a>
            <pre>{highlighted_content}</pre>
        </body>
        </html>
        '''
        return HttpResponse(html_content)

    def _serve_file_info(self, file_path, filename, request):
        """Показ информации о файле с возможностью скачивания"""
        try:
            file_size = os.path.getsize(file_path)
            size_formatted = filesizeformat(file_size)
        except:
            size_formatted = "неизвестно"

        try:
            mime = magic.Magic(mime=True)
            mime_type = mime.from_file(file_path)
        except:
            mime_type = "application/octet-stream"

        download_url = f"{request.path}?download=1"
        ext = Path(filename).suffix.upper()

        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>{html.escape(filename)}</title>
            <style>
                body {{ 
                    margin: 0; 
                    padding: 50px; 
                    font-family: Arial, sans-serif;
                    background: #f8f9fa;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 2px 20px rgba(0,0,0,0.1);
                    text-align: center;
                }}
                .file-icon {{
                    font-size: 48px;
                    margin-bottom: 20px;
                }}
                .download-btn {{
                    display: inline-block;
                    margin-top: 30px;
                    padding: 15px 30px;
                    background: #007bff;
                    color: white;
                    text-decoration: none;
                    border-radius: 8px;
                    font-size: 16px;
                    transition: background 0.3s;
                }}
                .download-btn:hover {{ 
                    background: #0056b3; 
                    text-decoration: none;
                    color: white;
                }}
                .file-info {{
                    margin: 20px 0;
                    color: #666;
                    line-height: 1.6;
                }}
                .file-info div {{
                    margin: 8px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="file-icon">📄</div>
                <h2>{html.escape(filename)}</h2>

                <div class="file-info">
                    <div><strong>Тип файла:</strong> {html.escape(ext)} файл</div>
                    <div><strong>MIME-тип:</strong> {html.escape(mime_type)}</div>
                    <div><strong>Размер:</strong> {size_formatted}</div>
                </div>

                <p>Этот формат файла не может быть отображен в браузере.</p>

                <a href="{download_url}" class="download-btn" download>
                    ⬇️ Скачать файл
                </a>
            </div>
        </body>
        </html>
        '''
        return HttpResponse(html_content)
