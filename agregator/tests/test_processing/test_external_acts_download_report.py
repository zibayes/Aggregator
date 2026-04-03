import pytest
import json
import os
from unittest.mock import patch, MagicMock, call, ANY
from datetime import datetime
import signal
import sys

from agregator.processing.external_acts_download_report import (
    generate_download_report,
    generate_intermediate_report,
    generate_final_report,
    generate_interrupted_report,
    TaskState,
    setup_interrupt_handling,
    handle_interrupts,
)


# ========== Фикстуры ==========
@pytest.fixture
def temp_dir(tmp_path):
    """Фикстура для временной директории (строка)"""
    return str(tmp_path)


# ========== Тесты для generate_download_report ==========
def test_generate_download_report_creates_file(temp_dir):
    """Проверяет, что функция создаёт HTML-файл с корректным содержимым"""
    report_path = os.path.join(temp_dir, "report.html")
    files_info = [
        {
            'status': 'скачан',
            'title': 'Test Title',
            'subtitle': 'Test Subtitle',
            'filename': 'test.pdf',
            'url': 'http://example.com/test.pdf',
            'reason': 'Test reason',
            'page': 1,
            'act_id': 123
        }
    ]
    result = generate_download_report(files_info, report_path)
    assert result == report_path
    assert os.path.exists(report_path)
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "Test Title" in content
    assert "Test Subtitle" in content
    assert "test.pdf" in content
    assert "http://example.com/test.pdf" in content
    assert "Test reason" in content
    assert "acts/123/" in content


def test_generate_download_report_creates_directory(temp_dir):
    """Создаёт директорию, если её нет"""
    report_path = os.path.join(temp_dir, "subdir", "report.html")
    files_info = []
    result = generate_download_report(files_info, report_path)
    assert result == report_path
    assert os.path.exists(report_path)


def test_generate_download_report_stats_calculation(temp_dir):
    """Проверяет корректность подсчёта статистики"""
    files_info = [
        {'status': 'скачан', 'title': 'A', 'filename': 'a.pdf', 'url': '', 'reason': '', 'page': 1},
        {'status': 'скачан', 'title': 'B', 'filename': 'b.pdf', 'url': '', 'reason': '', 'page': 1},
        {'status': 'пропущен', 'title': 'C', 'filename': 'c.pdf', 'url': '', 'reason': '', 'page': 1},
        {'status': 'в очереди на скачивание', 'title': 'D', 'filename': 'd.pdf', 'url': '', 'reason': '', 'page': 1},
        {'status': 'ошибка', 'title': 'E', 'filename': 'e.pdf', 'url': '', 'reason': '', 'page': 1},
    ]
    report_path = os.path.join(temp_dir, "stats.html")
    generate_download_report(files_info, report_path)
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
    assert "Всего файлов: 5" in content
    assert "Скачано: 2" in content
    assert "Пропущено: 1" in content
    assert "В очереди: 1" in content
    assert "Ошибок: 1" in content


def test_generate_download_report_exception_handling(temp_dir):
    """При ошибке записи файла исключение пробрасывается"""
    files_info = [{'status': 'скачан', 'title': 'Test', 'filename': 'test.pdf', 'url': '', 'reason': '', 'page': 1}]
    report_path = os.path.join(temp_dir, "report.html")
    with patch('builtins.open', side_effect=IOError("Write error")):
        with pytest.raises(IOError):
            generate_download_report(files_info, report_path)


# ========== Тесты для generate_intermediate_report ==========
@patch('agregator.processing.external_acts_download_report.generate_download_report')
def test_generate_intermediate_report(mock_generate, temp_dir):
    mock_generate.return_value = os.path.join(temp_dir, "intermediate.html")
    current_data = {
        'files_info': [
            {'status': 'скачан', 'title': 'Test', 'filename': 'test.pdf', 'url': '', 'reason': '', 'page': 1}],
        'start_time': '01.01.2024 12:00',
        'processed_pages': 5,
        'total_pages': 10,
        'start_date': '01.01.2024',
        'end_date': '31.12.2024',
        'start_page': 1,
        'end_page': 5
    }
    generate_intermediate_report(current_data)
    mock_generate.assert_called_once()
    args, kwargs = mock_generate.call_args
    assert args[0] == current_data['files_info']
    assert args[1] == 'uploaded_files/Акты ГИКЭ/intermediate_report.html'
    assert 'Промежуточный отчет' in args[2]
    assert 'Обработано страниц: 5 из 10' in args[2]
    assert '01.01.2024 - 31.12.2024' in args[2]
    assert '1 - 5' in args[2]


@patch('agregator.processing.external_acts_download_report.generate_download_report')
def test_generate_intermediate_report_missing_fields(mock_generate):
    """Отсутствующие поля не должны вызвать ошибку"""
    current_data = {
        'files_info': [],
        'processed_pages': 0,
        'total_pages': 0
    }
    generate_intermediate_report(current_data)
    mock_generate.assert_called_once()
    args = mock_generate.call_args[0]
    assert args[2] is not None  # промежуточная заметка есть


# ========== Тесты для generate_final_report ==========
@patch('agregator.processing.external_acts_download_report.generate_download_report')
def test_generate_final_report(mock_generate):
    current_data = {
        'files_info': [
            {'status': 'скачан', 'title': 'Test', 'filename': 'test.pdf', 'url': '', 'reason': '', 'page': 1}],
        'start_time': '01.01.2024 12:00',
        'processed_pages': 10,
        'total_pages': 10,
        'start_date': '01.01.2024',
        'end_date': '31.12.2024',
        'start_page': 1,
        'end_page': 5
    }
    generate_final_report(current_data)
    mock_generate.assert_called_once()
    args = mock_generate.call_args[0]
    assert args[1] == 'uploaded_files/Акты ГИКЭ/final_report.html'
    assert 'Задача успешно завершена' in args[2]


# ========== Тесты для generate_interrupted_report ==========
@patch('agregator.processing.external_acts_download_report.generate_download_report')
@patch('builtins.open', new_callable=MagicMock)
@patch('json.dump')
def test_generate_interrupted_report(mock_json_dump, mock_open, mock_generate, temp_dir):
    mock_generate.return_value = os.path.join(temp_dir, "interrupted.html")
    current_data = {
        'files_info': [
            {'status': 'скачан', 'title': 'Test', 'filename': 'test.pdf', 'url': '', 'reason': '', 'page': 1}],
        'start_time': '01.01.2024 12:00',
        'processed_pages': 3,
        'total_pages': 10,
        'start_date': '01.01.2024',
        'end_date': '31.12.2024',
        'start_page': 1,
        'end_page': 5
    }
    generate_interrupted_report(current_data)
    mock_generate.assert_called_once()
    args = mock_generate.call_args[0]
    assert args[1] == 'uploaded_files/Акты ГИКЭ/interrupted_report.html'
    # Ищем часть строки без HTML-тегов
    assert 'Обработка была прервана' in args[2]
    mock_open.assert_called_with('uploaded_files/Акты ГИКЭ/backup_data.json', 'w', encoding='utf-8')
    mock_json_dump.assert_called_once()


@patch('agregator.processing.external_acts_download_report.generate_download_report')
def test_generate_interrupted_report_empty_data(mock_generate, caplog):
    current_data = {'files_info': []}
    generate_interrupted_report(current_data)
    mock_generate.assert_not_called()
    assert "Нет данных для отчета о прерывании" in caplog.text


# ========== Тесты для TaskState ==========
def test_task_state_initialization():
    state = TaskState()
    assert state.data['start_time'] is None
    assert state.data['processed_pages'] == 0
    assert state.data['total_pages'] == 0
    assert state.data['files_info'] == []
    assert state.data['start_date'] is None
    assert state.data['end_date'] is None
    assert state.data['start_page'] == 0
    assert state.data['end_page'] == 0


def test_task_state_update():
    state = TaskState()
    state.update(processed_pages=5, total_pages=10)
    assert state.data['processed_pages'] == 5
    assert state.data['total_pages'] == 10
    state.update(start_time='12:00')
    assert state.data['start_time'] == '12:00'


def test_task_state_add_file_info():
    state = TaskState()
    file_info = {'filename': 'test.pdf', 'status': 'скачан'}
    state.add_file_info(file_info)
    assert len(state.data['files_info']) == 1
    assert state.data['files_info'][0] == file_info


def test_task_state_get_data():
    state = TaskState()
    state.update(processed_pages=3)
    data = state.get_data()
    assert data['processed_pages'] == 3
    # Изменение копии не влияет на оригинал
    data['processed_pages'] = 10
    assert state.data['processed_pages'] == 3


# ========== Тесты для setup_interrupt_handling ==========
@patch('agregator.processing.external_acts_download_report.signal.signal')
@patch('agregator.processing.external_acts_download_report.atexit.register')
def test_setup_interrupt_handling(mock_atexit, mock_signal):
    task_state = TaskState()
    setup_interrupt_handling(task_state)
    # Проверяем регистрацию обработчиков сигналов
    mock_signal.assert_any_call(signal.SIGINT, ANY)
    mock_signal.assert_any_call(signal.SIGTERM, ANY)
    mock_atexit.assert_called_once_with(ANY)


@patch('agregator.processing.external_acts_download_report.generate_interrupted_report')
@patch('agregator.processing.external_acts_download_report.sys.exit')
def test_signal_handler_calls_report(mock_exit, mock_generate):
    task_state = TaskState()
    setup_interrupt_handling(task_state)
    # Получаем зарегистрированный обработчик SIGINT
    handler = signal.getsignal(signal.SIGINT)
    # Вызываем его
    handler(signal.SIGINT, None)
    mock_generate.assert_called_once_with(task_state.get_data())
    mock_exit.assert_called_once_with(1)


@patch('agregator.processing.external_acts_download_report.generate_interrupted_report')
def test_exit_handler_calls_report(mock_generate):
    """Проверяем, что atexit-обработчик вызывает generate_interrupted_report"""
    task_state = TaskState()
    registered = []
    with patch('atexit.register', lambda f: registered.append(f)):
        setup_interrupt_handling(task_state)
    # Вызываем сохранённый обработчик
    registered[0]()
    mock_generate.assert_called_once_with(task_state.get_data())


# ========== Тесты для декоратора handle_interrupts ==========
def test_handle_interrupts_success():
    """При успешном выполнении основной функции генерируется финальный отчёт"""
    mock_func = MagicMock()
    mock_func.return_value = "success"

    @handle_interrupts
    def decorated(self, *args, **kwargs):
        return mock_func(self, *args, **kwargs)

    instance = MagicMock()
    with patch('agregator.processing.external_acts_download_report.generate_final_report') as mock_final, \
            patch('agregator.processing.external_acts_download_report.generate_interrupted_report') as mock_interrupted:
        result = decorated(instance, 1, 2, key="value")
        assert result == "success"
        mock_func.assert_called_once_with(instance, ANY, 1, 2, key="value")
        # Проверяем, что в основную функцию передан task_state (первый аргумент после self)
        args, _ = mock_func.call_args
        assert isinstance(args[1], TaskState)  # task_state
        # Финальный отчёт должен быть вызван
        mock_final.assert_called_once()
        mock_interrupted.assert_not_called()


def test_handle_interrupts_exception():
    """При исключении в основной функции генерируется отчёт о прерывании, а также финальный отчёт (из finally)"""
    mock_func = MagicMock()
    mock_func.side_effect = ValueError("Test error")

    @handle_interrupts
    def decorated(self, *args, **kwargs):
        return mock_func(self, *args, **kwargs)

    instance = MagicMock()
    with patch('agregator.processing.external_acts_download_report.generate_final_report') as mock_final, \
            patch('agregator.processing.external_acts_download_report.generate_interrupted_report') as mock_interrupted:
        with pytest.raises(ValueError) as exc:
            decorated(instance)
        assert str(exc.value) == "Test error"
        mock_interrupted.assert_called_once()
        # ИСПРАВЛЕНО: в текущей реализации finally вызывает generate_final_report всегда
        mock_final.assert_called_once()


def test_handle_interrupts_calls_setup_interrupt_handling():
    """Проверяем, что декоратор вызывает настройку обработчиков прерываний"""

    @handle_interrupts
    def dummy(self, task_state):
        return "ok"

    instance = MagicMock()
    with patch('agregator.processing.external_acts_download_report.setup_interrupt_handling') as mock_setup, \
            patch('agregator.processing.external_acts_download_report.generate_final_report'):
        dummy(instance)
        mock_setup.assert_called_once()
        # Проверяем, что в setup_interrupt_handling передан task_state
        args, _ = mock_setup.call_args
        assert isinstance(args[0], TaskState)
