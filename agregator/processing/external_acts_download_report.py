import os
import json
import signal
import sys
import atexit
from functools import wraps
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from archeology.settings import BASE_URL


def generate_download_report(all_files_info: List[Dict], report_path: str = None, additional_header: str = ""):
    """Генерирует HTML-отчет о скачанных файлах с ГЛОБАЛЬНОЙ фильтрацией и поиском"""
    if report_path is None:
        report_path = 'uploaded_files/Акты ГИКЭ/download_report.html'

    # Создаем директорию если нужно
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    # Подсчет статистики для фильтров
    total_files = len(all_files_info)
    downloaded_count = len([f for f in all_files_info if f['status'] == 'скачан'])
    skipped_count = len([f for f in all_files_info if f['status'] == 'пропущен'])
    queued_count = len([f for f in all_files_info if f['status'] == 'в очереди на скачивание'])
    error_count = len([f for f in all_files_info if f['status'] == 'ошибка'])

    # Генерируем HTML с ГЛОБАЛЬНОЙ фильтрацией
    html_content = f"""
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Отчет о скачанных файлах - {datetime.now().strftime('%d.%m.%Y %H:%M')}</title>
        <style>
            /* Все существующие стили остаются без изменений */
            .warning-banner {{
                background: #fff3cd;
                border: 1px solid #ffeaa7;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
                color: #856404;
            }}
            .success-banner {{
                background: #d1edff;
                border: 1px solid #b3d9ff;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
                color: #004085;
            }}
            .info-banner {{
                background: #e2f4e8;
                border: 1px solid #c8e6c9;
                padding: 15px;
                margin: 10px 0;
                border-radius: 5px;
                color: #2e7d32;
            }}
            .return-btn {{
                display: inline-block;
                padding: 10px 20px;
                background: #007cba;
                color: white;
                text-decoration: none;
                border-radius: 5px;
                margin-bottom: 20px;
                font-weight: bold;
            }}
            .return-btn:hover {{
                background: #005a87;
                text-decoration: none;
                color: white;
            }}
            .act-link {{
                display: inline-block;
                padding: 6px 12px;
                background: #28a745;
                color: white;
                text-decoration: none;
                border-radius: 12px;
                margin-top: 8px;
                font-size: 12px;
                font-weight: bold;
            }}
            .act-link:hover {{
                background: #218838;
                text-decoration: none;
                color: white;
            }}
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                background-color: #f5f5f5;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h1 {{
                color: #333;
                border-bottom: 2px solid #007cba;
                padding-bottom: 10px;
            }}
            .stats {{
                background: #e8f4fc;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
            }}
            .file-item {{
                border: 1px solid #ddd;
                margin: 10px 0;
                padding: 15px;
                border-radius: 5px;
                transition: background-color 0.3s;
            }}
            .file-item.downloaded {{
                background-color: #e8f5e8;
                border-left: 4px solid #4CAF50;
            }}
            .file-item.skipped {{
                background-color: #fff3e0;
                border-left: 4px solid #FF9800;
            }}
            .file-item.queued {{
                background-color: #e3f2fd;
                border-left: 4px solid #2196F3;
            }}
            .file-item.error {{
                background-color: #ffebee;
                border-left: 4px solid #f44336;
            }}
            .file-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                margin-bottom: 10px;
            }}
            .file-title {{
                font-weight: bold;
                font-size: 16px;
                color: #333;
                flex: 1;
            }}
            .file-subtitle {{
                font-weight: normal;
                font-size: 14px;
                color: #666;
                margin-top: 5px;
                line-height: 1.4;
            }}
            .file-status {{
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: bold;
                margin-left: 10px;
                white-space: nowrap;
            }}
            .status-downloaded {{
                background: #4CAF50;
                color: white;
            }}
            .status-skipped {{
                background: #FF9800;
                color: white;
            }}
            .status-queued {{
                background: #2196F3;
                color: white;
            }}
            .status-error {{
                background: #f44336;
                color: white;
            }}
            .file-details {{
                font-size: 14px;
                color: #666;
            }}
            .file-link {{
                color: #007cba;
                text-decoration: none;
                word-break: break-all;
            }}
            .file-link:hover {{
                text-decoration: underline;
            }}
            .url-truncated {{
                display: block;
                max-width: 600px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }}
            .pagination-container {{
                display: flex;
                justify-content: center;
                margin: 20px 0;
                flex-wrap: wrap;
                position: sticky;
                top: 0;
                background: white;
                padding: 10px 0;
                z-index: 100;
                border-bottom: 1px solid #ddd;
            }}
            .pagination-container.bottom {{
                position: relative;
                top: auto;
                background: transparent;
                border-bottom: none;
                border-top: 1px solid #ddd;
            }}
            .page-btn {{
                margin: 2px;
                padding: 8px 12px;
                border: 1px solid #ddd;
                background: white;
                cursor: pointer;
                border-radius: 4px;
            }}
            .page-btn.active {{
                background: #007cba;
                color: white;
                border-color: #007cba;
            }}
            .page-btn:hover {{
                background: #f0f0f0;
            }}
            .section {{
                margin-bottom: 30px;
            }}
            .section-title {{
                font-size: 18px;
                font-weight: bold;
                margin: 20px 0 10px 0;
                padding: 10px;
                background: #f8f9fa;
                border-radius: 5px;
            }}
            .search-box {{
                margin: 20px 0;
                padding: 10px;
                width: 100%;
                border: 1px solid #ddd;
                border-radius: 4px;
                font-size: 14px;
            }}
            .filter-buttons {{
                margin: 10px 0;
            }}
            .filter-btn {{
                margin: 0 5px 5px 0;
                padding: 6px 12px;
                border: 1px solid #ddd;
                background: white;
                cursor: pointer;
                border-radius: 4px;
                font-size: 12px;
            }}
            .filter-btn.active {{
                background: #007cba;
                color: white;
                border-color: #007cba;
            }}
            .file-page {{
                display: none;
            }}
            .file-page.active {{
                display: block;
            }}
            .no-results {{
                text-align: center;
                padding: 40px;
                color: #666;
                font-style: italic;
            }}
            @media (max-width: 768px) {{
                .file-header {{
                    flex-direction: column;
                }}
                .file-status {{
                    margin-left: 0;
                    margin-top: 5px;
                }}
                .url-truncated {{
                    max-width: 300px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="{BASE_URL}/external_sources/" class="return-btn">← Вернуться к обработке внешних источников</a>

            <h1>📊 Отчет о скачанных файлах ГИКЭ</h1>
            {additional_header}

            <div class="stats">
                <strong>Общая статистика:</strong><br>
                • Всего файлов: {total_files}<br>
                • Скачано: {downloaded_count}<br>
                • Пропущено: {skipped_count}<br>
                • В очереди: {queued_count}<br>
                • Ошибок: {error_count}<br>
                • Дата отчета: {datetime.now().strftime('%d.%m.%Y %H:%M')}
            </div>

            <input type="text" id="searchInput" class="search-box" placeholder="🔍 Поиск по названию файла, подзаголовку или описанию...">

            <div class="filter-buttons">
                <button class="filter-btn active" data-filter="all">Все ({total_files})</button>
                <button class="filter-btn" data-filter="скачан">Скачаны ({downloaded_count})</button>
                <button class="filter-btn" data-filter="пропущен">Пропущены ({skipped_count})</button>
                <button class="filter-btn" data-filter="в очереди на скачивание">В очереди ({queued_count})</button>
                <button class="filter-btn" data-filter="ошибка">Ошибки ({error_count})</button>
            </div>

            <!-- Верхняя пагинация -->
            <div class="pagination-container" id="paginationTop">
                <!-- Кнопки пагинации будут сгенерированы JavaScript -->
            </div>

            <div id="filesContainer">
    """

    # Добавляем файлы в исходном порядке (без группировки по страницам)
    for index, file_info in enumerate(all_files_info):
        # Определяем класс и текст статуса
        status_class = 'skipped'
        status_text = '⏭ ПРОПУЩЕН'

        if file_info['status'] == 'скачан':
            status_class = 'downloaded'
            status_text = '✓ СКАЧАН'
        elif file_info['status'] == 'в очереди на скачивание':
            status_class = 'queued'
            status_text = '⏳ В ОЧЕРЕДИ'
        elif file_info['status'] == 'ошибка':
            status_class = 'error'
            status_text = '❌ ОШИБКА'

        # Обрезаем длинные URL
        url_display = file_info['url']
        if len(url_display) > 80:
            url_display = url_display[:80] + '...'

        # Формируем ссылку на акт в системе, если есть act_id
        act_link = ""
        if file_info.get('act_id'):
            act_link = f'<br><strong>Акт в системе:</strong> <a href="{BASE_URL}/acts/{file_info["act_id"]}/" class="act-link" target="_blank">📄 Просмотр акта</a>'

        # Формируем заголовок с подзаголовком
        title_html = f"<div class='file-title'>{file_info['title']}</div>"
        if file_info.get('subtitle'):
            title_html += f"<div class='file-subtitle'>{file_info['subtitle']}</div>"

        html_content += f"""
        <div class="file-item {status_class}" data-status="{file_info['status']}" data-page="{file_info['page']}" data-index="{index}">
            <div class="file-header">
                <div style="flex: 1;">
                    {title_html}
                </div>
                <div class="file-status status-{status_class}">{status_text}</div>
            </div>
            <div class="file-details">
                <strong>Файл:</strong> {file_info['filename'] or '—'}<br>
                <strong>Ссылка:</strong> <a href="{file_info['url']}" class="file-link" target="_blank">
                    <span class="url-truncated" title="{file_info['url']}">{url_display}</span>
                </a><br>
                <strong>Причина:</strong> {file_info.get('reason', '—')}
                {act_link}
            </div>
        </div>
        """

    html_content += """
            </div>

            <!-- Нижняя пагинация -->
            <div class="pagination-container bottom" id="paginationBottom">
                <!-- Кнопки пагинации будут сгенерированы JavaScript -->
            </div>
        </div>

        <script>
            // Конфигурация
            let currentPage = 1;
            let currentFilter = 'all';
            let currentSearch = '';
            const itemsPerPage = 30; // Количество элементов на странице

            // Инициализация
            function init() {
                setupPagination();
                showPage(1);
                setupFilters();
                setupSearch();
            }

            // Получить все видимые элементы после применения фильтров
            function getVisibleItems() {
                const allItems = Array.from(document.querySelectorAll('.file-item'));
                return allItems.filter(item => {
                    const matchesFilter = currentFilter === 'all' || item.dataset.status === currentFilter;
                    const matchesSearch = itemMatchesSearch(item);
                    return matchesFilter && matchesSearch;
                });
            }

            // Настройка пагинации
            function setupPagination() {
                const visibleItems = getVisibleItems();
                const totalPages = Math.ceil(visibleItems.length / itemsPerPage);
                const paginationTop = document.getElementById('paginationTop');
                const paginationBottom = document.getElementById('paginationBottom');

                // Очищаем пагинацию
                paginationTop.innerHTML = '';
                paginationBottom.innerHTML = '';

                // Создаем кнопки пагинации
                for (let i = 1; i <= totalPages; i++) {
                    // Верхняя пагинация
                    const btnTop = document.createElement('button');
                    btnTop.className = 'page-btn';
                    btnTop.textContent = i;
                    btnTop.onclick = () => showPage(i);
                    paginationTop.appendChild(btnTop);

                    // Нижняя пагинация
                    const btnBottom = document.createElement('button');
                    btnBottom.className = 'page-btn';
                    btnBottom.textContent = i;
                    btnBottom.onclick = () => showPage(i);
                    paginationBottom.appendChild(btnBottom);
                }

                // Обновляем активные кнопки
                updatePaginationButtons();
            }

            // Показать страницу
            function showPage(pageNum) {
                currentPage = pageNum;
                const visibleItems = getVisibleItems();
                const totalPages = Math.ceil(visibleItems.length / itemsPerPage);

                // Скрываем все элементы
                document.querySelectorAll('.file-item').forEach(item => {
                    item.style.display = 'none';
                });

                // Показываем элементы для текущей страницы
                const startIndex = (pageNum - 1) * itemsPerPage;
                const endIndex = startIndex + itemsPerPage;

                visibleItems.slice(startIndex, endIndex).forEach(item => {
                    item.style.display = 'block';
                });

                // Обновляем пагинацию
                updatePaginationButtons();

                // Показываем/скрываем сообщение "Ничего не найдено"
                showNoResultsMessage(visibleItems.length === 0);
            }

            // Обновить активные кнопки пагинации
            function updatePaginationButtons() {
                document.querySelectorAll('.page-btn').forEach((btn, index) => {
                    btn.classList.toggle('active', index + 1 === currentPage);
                });
            }

            // Настройка фильтров
            function setupFilters() {
                document.querySelectorAll('.filter-btn').forEach(btn => {
                    btn.addEventListener('click', function() {
                        // Обновляем активные кнопки
                        document.querySelectorAll('.filter-btn').forEach(b => {
                            b.classList.remove('active');
                        });
                        this.classList.add('active');

                        currentFilter = this.dataset.filter;
                        currentPage = 1;
                        applyFiltersAndPagination();
                    });
                });
            }

            // Настройка поиска
            function setupSearch() {
                const searchInput = document.getElementById('searchInput');
                searchInput.addEventListener('input', function() {
                    currentSearch = this.value.toLowerCase();
                    currentPage = 1;
                    applyFiltersAndPagination();
                });
            }

            // Применить фильтры и пагинацию
            function applyFiltersAndPagination() {
                setupPagination();
                showPage(currentPage);
            }

            // Проверить соответствие элемента поисковому запросу
            function itemMatchesSearch(item) {
                if (currentSearch === '') return true;

                const titleText = item.querySelector('.file-title').textContent.toLowerCase();
                const subtitleElem = item.querySelector('.file-subtitle');
                const subtitleText = subtitleElem ? subtitleElem.textContent.toLowerCase() : '';
                const detailsText = item.querySelector('.file-details').textContent.toLowerCase();

                return titleText.includes(currentSearch) || 
                       subtitleText.includes(currentSearch) || 
                       detailsText.includes(currentSearch);
            }

            // Показать/скрыть сообщение "Ничего не найдено"
            function showNoResultsMessage(show) {
                let noResults = document.getElementById('no-results');

                if (show && !noResults) {
                    noResults = document.createElement('div');
                    noResults.id = 'no-results';
                    noResults.className = 'no-results';
                    noResults.textContent = 'Ничего не найдено';
                    document.getElementById('filesContainer').appendChild(noResults);
                } else if (!show && noResults) {
                    noResults.remove();
                }
            }

            // Запуск при загрузке
            document.addEventListener('DOMContentLoaded', init);
        </script>
    </body>
    </html>
    """

    # Сохраняем файл
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return report_path


# Остальные функции остаются без изменений
def generate_interrupted_report(current_report_data):
    """Генерация отчета при прерывании"""
    if not current_report_data['files_info']:
        print("Нет данных для отчета")
        return

    try:
        report_path = 'uploaded_files/Акты ГИКЭ/interrupted_report.html'

        # Добавляем пометку о прерывании
        interrupted_note = f"""
        <div class="warning-banner">
            ⚠️ <strong>ВНИМАНИЕ:</strong> Обработка была прервана!<br>
            Обработано страниц: {current_report_data['processed_pages']} из {current_report_data['total_pages']}<br>
            Время начала: {current_report_data['start_time']}<br>
            Время прерывания: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
        </div>
        """

        # Генерируем отчет
        report_path = generate_download_report(
            current_report_data['files_info'],
            report_path,
            interrupted_note
        )

        print(f"Отчет о прерванной задаче сохранен: {report_path}")

        # Также сохраняем данные в JSON для возможного продолжения
        json_path = 'uploaded_files/Акты ГИКЭ/backup_data.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(current_report_data, f, ensure_ascii=False, indent=2, default=str)

    except Exception as e:
        print(f"Ошибка при генерации отчета о прерывании: {e}")


def generate_final_report(current_report_data):
    """Генерация финального отчета при успешном завершении"""
    try:
        report_path = 'uploaded_files/Акты ГИКЭ/final_report.html'

        success_note = f"""
        <div class="success-banner">
            ✅ <strong>Задача успешно завершена!</strong><br>
            Обработано страниц: {current_report_data['processed_pages']} из {current_report_data['total_pages']}<br>
            Время начала: {current_report_data['start_time']}<br>
            Время завершения: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
        </div>
        """

        report_path = generate_download_report(
            current_report_data['files_info'],
            report_path,
            success_note
        )

        print(f"Финальный отчет сохранен: {report_path}")

    except Exception as e:
        print(f"Ошибка при генерации финального отчета: {e}")


def generate_intermediate_report(current_report_data):
    """Генерация промежуточного отчета"""
    try:
        report_path = 'uploaded_files/Акты ГИКЭ/intermediate_report.html'

        intermediate_note = f"""
        <div class="info-banner">
            🔄 <strong>Промежуточный отчет</strong><br>
            Обработано страниц: {current_report_data['processed_pages']} из {current_report_data['total_pages']}<br>
            Время начала: {current_report_data['start_time']}<br>
            Последнее обновление: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
        </div>
        """

        report_path = generate_download_report(
            current_report_data['files_info'],
            report_path,
            intermediate_note
        )

        print(f"Промежуточный отчет сохранен: {report_path}")

    except Exception as e:
        print(f"Ошибка при генерации промежуточного отчета: {e}")


class TaskState:
    """Класс для управления состоянием задачи"""

    def __init__(self):
        self.data = {
            'start_time': None,
            'processed_pages': 0,
            'total_pages': 0,
            'files_info': []
        }

    def update(self, **kwargs):
        self.data.update(kwargs)

    def add_file_info(self, file_info):
        self.data['files_info'].append(file_info)

    def get_data(self):
        return self.data.copy()


def setup_interrupt_handling(task_state):
    """Настройка обработчиков прерывания"""

    def signal_handler(signum, frame):
        print(f"Получен сигнал {signum}, генерируем отчет...")
        generate_interrupted_report(task_state.get_data())
        sys.exit(1)

    def exit_handler():
        print("Задача завершается, генерируем отчет...")
        generate_interrupted_report(task_state.get_data())

    # Обработчики сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Обработчик при обычном выходе
    atexit.register(exit_handler)


def handle_interrupts(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # Создаем состояние задачи
        task_state = TaskState()
        task_state.update(start_time=datetime.now().strftime('%d.%m.%Y %H:%M:%S'))

        # Настраиваем обработчики прерываний
        setup_interrupt_handling(task_state)

        try:
            # Передаем состояние задачи в основную функцию
            return func(self, task_state, *args, **kwargs)
        except Exception as e:
            # Генерируем отчет при любой ошибке
            print(f"Произошла ошибка: {e}")
            generate_interrupted_report(task_state.get_data())
            raise
        finally:
            # Генерируем финальный отчет при нормальном завершении
            generate_final_report(task_state.get_data())

    return wrapper
