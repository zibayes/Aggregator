# middleware.py
import os
import html
from django.http import HttpResponse, FileResponse
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin
from pathlib import Path
import magic


class FilePreviewMiddleware(MiddlewareMixin):
    def process_request(self, request):
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

        # Для PDF - показываем в браузере
        if ext == '.pdf':
            return None

        # Для изображений
        elif ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']:
            return None

        # Для текстовых файлов
        elif ext in ['.txt', '.csv', '.log', '.xml', '.html', '.htm', '.css', '.js', '.py']:
            return self._serve_text(file_path, filename, request)

        # Для офисных документов
        elif ext in ['.doc', '.docx', '.odt', '.xlsx', '.xls', '.ppt', '.pptx']:
            return self._serve_office(file_path, filename, request)

        # Для KML/KMZ - показываем как XML с подсветкой
        elif ext in ['.kml', '.kmz']:
            return self._serve_kml(file_path, filename, request)

        # Для остальных форматов - показываем информацию о файле
        else:
            return self._serve_file_info(file_path, filename, request)

    def _serve_office(self, file_path, filename, request):
        """Конвертируем офисные документы в HTML для просмотра"""
        download_url = f"{request.path}?download=1"

        # Конвертируем в HTML
        html_content = self._convert_to_html(file_path)

        if html_content:
            html_content = f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>{html.escape(filename)}</title>
                <style>
                    body {{ margin: 20px; }}
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
                    }}
                </style>
            </head>
            <body>
                <a href="{download_url}" class="download-btn">⬇️ Скачать оригинал</a>
                <div style="margin-top: 60px;">
                    {html_content}
                </div>
            </body>
            </html>
            '''
        else:
            # Fallback на информацию о файле
            html_content = self._serve_file_info(file_path, filename, request)

        return HttpResponse(html_content)

    def _convert_to_html(self, file_path):
        """Конвертирует офисные документы в HTML через LibreOffice"""
        try:
            import subprocess
            import tempfile

            # Создаем временный HTML файл
            with tempfile.NamedTemporaryFile(suffix='.html', delete=False) as temp_html:
                html_path = temp_html.name

            # Конвертируем через LibreOffice
            result = subprocess.run([
                'libreoffice', '--headless', '--convert-to', 'html',
                '--outdir', os.path.dirname(html_path), file_path
            ], capture_output=True, timeout=30)

            if result.returncode == 0 and os.path.exists(html_path):
                with open(html_path, 'r', encoding='utf-8') as f:
                    return f.read()

        except Exception as e:
            print(f"Ошибка конвертации в HTML: {e}")

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
        highlighted_content = escaped_content.replace('&lt;', '<span style="color: #905">&lt;')
        highlighted_content = highlighted_content.replace('&gt;', '&gt;</span>')
        highlighted_content = highlighted_content.replace('&lt;/', '<span style="color: #905">&lt;/')

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
                    background: #2d2d2d;
                    color: #f8f8f2;
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
                    background: #1e1e1e;
                    padding: 20px;
                    border-radius: 5px;
                    border: 1px solid #444;
                    overflow-x: auto;
                    max-width: 100%;
                    line-height: 1.4;
                }}
                .xml-tag {{ color: #905; }}
                .xml-attr {{ color: #9cdcfe; }}
                .xml-value {{ color: #ce9178; }}
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
            from django.template.defaultfilters import filesizeformat
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
