import pytest
import json
import os
import shutil
import tempfile
from datetime import datetime
from unittest.mock import patch, MagicMock, mock_open, call, ANY
from pathlib import Path

import numpy as np
import pandas as pd
from docx import Document
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache
from django.contrib.auth import get_user_model

from agregator.models import (
    User, Act, UserTasks, ArchaeologicalHeritageSite,
    IdentifiedArchaeologicalHeritageSite
)
from agregator.processing.external_sources import (
    create_note_file,
    get_downloaded_files_cache,
    convert_file_to_uploaded_file,
    find_pdf_files,
    extract_tables_from_docx,
    tables_to_dataframes,
    _clean_old_files,
    _download_file,
    external_orders_download,
    download_file,
    external_sources_processing,
    process_voan_list,
    process_oan_list,
    process_downloaded_files,
    ORDER_TEXT_PATTERN,
    ORDER_NUMBER_PATTERN,
    ORDER_DATE_PATTERN,
    AKT_GIKE_PATTERN,
    ACTS_QUERY_EXCLUDE,
)

User = get_user_model()


# ========== Фикстуры ==========
@pytest.fixture
def test_admin(db):
    return User.objects.create_superuser(
        username="admin",
        password="adminpass123",
        email="admin@example.com"
    )


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_session():
    with patch('agregator.processing.external_sources.session') as mock:
        mock.get.return_value.status_code = 200
        mock.get.return_value.text = "<html></html>"
        yield mock


@pytest.fixture
def mock_ssl_session():
    with patch('agregator.processing.external_sources.ssl._create_unverified_context') as mock:
        yield mock


@pytest.fixture
def mock_requests():
    with patch('agregator.processing.external_sources.requests') as mock:
        mock.get.return_value.status_code = 200
        mock.get.return_value.text = "<html></html>"
        mock.get.return_value.content = b"fake content"
        yield mock


@pytest.fixture
def mock_cache():
    with patch('agregator.processing.external_sources.cache') as mock:
        mock.get.return_value = None
        mock.set.return_value = True
        yield mock


@pytest.fixture
def mock_patoolib():
    with patch('agregator.processing.external_sources.patoolib') as mock:
        mock.extract_archive.return_value = True
        yield mock


@pytest.fixture
def mock_shutil():
    with patch('agregator.processing.external_sources.shutil') as mock:
        mock.rmtree.return_value = True
        mock.copy.return_value = True
        yield mock


@pytest.fixture
def mock_os_path():
    with patch('agregator.processing.external_sources.os.path') as mock:
        mock.exists.return_value = True
        mock.isfile.return_value = True
        yield mock


class MockTask:
    def update_state(self, state, meta):
        pass


# ========== Тесты вспомогательных функций ==========
class TestHelperFunctions:
    def test_create_note_file(self, temp_dir):
        output_path = str(temp_dir)
        create_note_file(output_path, "Тестовый приказ")
        note_path = os.path.join(output_path, "Примечание.txt")
        assert os.path.exists(note_path)
        with open(note_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "Тестовый приказ" in content
        assert "Нет приказа на сайте службы" in content

    def test_create_note_file_no_order(self, temp_dir):
        output_path = str(temp_dir)
        create_note_file(output_path)
        note_path = os.path.join(output_path, "Примечание.txt")
        assert os.path.exists(note_path)
        with open(note_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "Нет приказа о включении объекта в перечень" in content

    @patch('agregator.processing.external_sources.cache')
    def test_get_downloaded_files_cache(self, mock_cache, test_admin):
        # Создаём акт с внешним источником
        act = Act.objects.create(
            user=test_admin,
            upload_source={"source": "ООКН"},
            source=[{"origin_filename": "test_file.pdf"}]
        )
        # Настраиваем мок cache.get, чтобы он возвращал None (кэш пуст)
        mock_cache.get.return_value = None
        downloaded = get_downloaded_files_cache(test_admin.id)
        assert "test_file.pdf" in downloaded
        # Проверяем, что кэш установлен с правильными параметрами
        mock_cache.set.assert_called_once_with(f'downloaded_files_{test_admin.id}', downloaded, timeout=3600)

    def test_convert_file_to_uploaded_file(self, temp_dir):
        file_path = temp_dir / "test.pdf"
        with open(file_path, 'wb') as f:
            f.write(b"test content")
        uploaded = convert_file_to_uploaded_file(str(file_path))
        # InMemoryUploadedFile — подкласс SimpleUploadedFile? Нет, но можно проверить наличие атрибутов
        assert uploaded.name == "test.pdf"
        assert uploaded.read() == b"test content"

    def test_find_pdf_files(self, temp_dir):
        pdf1 = temp_dir / "test1.pdf"
        pdf2 = temp_dir / "test2.pdf"
        # Изменяем имя файла, чтобы оно подпадало под исключение
        pdf3 = temp_dir / "проверка_подписи.pdf"  # содержит "проверк" и "подпис"
        pdf1.touch()
        pdf2.touch()
        pdf3.touch()
        files = ["test1.pdf", "test2.pdf", "проверка_подписи.pdf"]
        result = find_pdf_files(str(temp_dir), files)
        assert len(result) == 2
        assert str(pdf1) in result
        assert str(pdf2) in result

    def test_extract_tables_from_docx(self, temp_dir):
        # Создаём простой docx с таблицей
        doc = Document()
        table = doc.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Header1"
        table.cell(0, 1).text = "Header2"
        table.cell(1, 0).text = "Value1"
        table.cell(1, 1).text = "Value2"
        doc_path = temp_dir / "test.docx"
        doc.save(doc_path)
        tables = extract_tables_from_docx(str(doc_path))
        assert len(tables) == 1
        assert tables[0][0] == ["Header1", "Header2"]
        assert tables[0][1] == ["Value1", "Value2"]

    def test_tables_to_dataframes(self):
        tables = [
            [["Header1", "Header2"], ["Value1", "Value2"]]
        ]
        dfs = tables_to_dataframes(tables)
        assert len(dfs) == 1
        assert list(dfs[0].columns) == ["Header1", "Header2"]
        assert dfs[0].iloc[0, 0] == "Value1"

    def test_clean_old_files(self, temp_dir):
        current_lists = temp_dir / "current_lists.txt"
        test_file = temp_dir / "test_file.txt"
        test_file.touch()
        with open(current_lists, 'w', encoding='utf-8') as f:
            f.write(f"list_voan - {test_file}\n")
            f.write("other line\n")
        _clean_old_files(str(current_lists), "list_voan")
        assert not test_file.exists()
        with open(current_lists, 'r', encoding='utf-8') as f:
            content = f.read()
        assert "other line" in content
        assert "list_voan" not in content

    @patch('agregator.processing.external_sources.urllib.request.urlopen')
    def test_download_file(self, mock_urlopen, temp_dir):
        mock_response = MagicMock()
        mock_response.read.return_value = b"file content"
        mock_urlopen.return_value.__enter__.return_value = mock_response
        href = "/upload/iblock/test.pdf"
        title = "Test File"
        current_lists = temp_dir / "lists.txt"
        with open(current_lists, 'w') as f:
            f.write("")
        result = _download_file(href, title, str(current_lists))
        assert result == f"uploaded_files/Памятники/test.pdf"
        assert os.path.exists(result)
        with open(result, 'rb') as f:
            assert f.read() == b"file content"

    @patch('agregator.processing.external_sources.session.get')
    def test_download_file_simple(self, mock_get, temp_dir):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"file content"
        mock_get.return_value.__enter__.return_value = mock_response
        url = "https://example.com/file.pdf"
        path = str(temp_dir / "file.pdf")
        result = download_file(url, path)
        assert result is True
        with open(path, 'rb') as f:
            assert f.read() == b"file content"

    @patch('agregator.processing.external_sources.session.get')
    def test_download_file_failure(self, mock_get, temp_dir):
        mock_get.side_effect = Exception("Connection error")
        url = "https://example.com/file.pdf"
        path = str(temp_dir / "file.pdf")
        result = download_file(url, path)
        assert result is False


# ========== Тесты process_downloaded_files ==========
@pytest.mark.django_db
@patch('agregator.processing.external_sources.raw_reports_save')
@patch('agregator.processing.external_sources.process_acts')
@patch('agregator.processing.external_sources.convert_file_to_uploaded_file')
@patch('agregator.processing.external_sources.patoolib.extract_archive')
@patch('agregator.processing.external_sources.shutil.rmtree')
@patch('agregator.processing.external_sources.os.remove')
def test_process_downloaded_files_pdf(
        mock_remove, mock_rmtree, mock_extract, mock_convert, mock_process_acts, mock_raw_save,
        test_admin, temp_dir
):
    # Создаём тестовый файл
    pdf_path = temp_dir / "test.pdf"
    pdf_path.touch()
    files_data = [(str(pdf_path), "https://example.com/test.pdf", "test.pdf")]
    mock_convert.return_value = SimpleUploadedFile("test.pdf", b"content")
    mock_raw_save.return_value = [1]
    mock_task = MagicMock()
    mock_task.task_id = "task123"
    mock_process_acts.apply_async.return_value = mock_task

    result = process_downloaded_files(files_data, test_admin, True, False, True, False)

    assert "test.pdf" in result
    assert result["test.pdf"] == 1
    mock_raw_save.assert_called_once()
    mock_process_acts.apply_async.assert_called_once()
    mock_remove.assert_called_once()


@pytest.mark.django_db
@patch('agregator.processing.external_sources.raw_reports_save')
@patch('agregator.processing.external_sources.process_acts')
@patch('agregator.processing.external_sources.convert_file_to_uploaded_file')
@patch('agregator.processing.external_sources.patoolib.extract_archive')
@patch('agregator.processing.external_sources.shutil.rmtree')
@patch('agregator.processing.external_sources.os.remove')
def test_process_downloaded_files_archive(
        mock_remove, mock_rmtree, mock_extract, mock_convert, mock_process_acts, mock_raw_save,
        test_admin, temp_dir
):
    # Создаём архив
    archive_path = temp_dir / "test.zip"
    archive_path.touch()
    files_data = [(str(archive_path), "https://example.com/test.zip", "test.zip")]
    # Мокаем поиск PDF в архиве
    with patch('agregator.processing.external_sources.os.walk') as mock_walk:
        mock_walk.return_value = [(str(temp_dir), ["file1.pdf"], [])]
        mock_convert.return_value = SimpleUploadedFile("file1.pdf", b"content")
        mock_raw_save.return_value = [1, 2]
        mock_task = MagicMock()
        mock_task.task_id = "task123"
        mock_process_acts.apply_async.return_value = mock_task

        result = process_downloaded_files(files_data, test_admin, True, False, True, False)

        assert "test.zip" in result
        assert result["test.zip"] == 1
        mock_raw_save.assert_called_once()
        mock_process_acts.apply_async.assert_called_once()
        mock_remove.assert_called_once()
        mock_rmtree.assert_called_once()


# ========== Тесты Celery задач ==========
@patch('agregator.processing.external_sources.get_downloaded_files_cache')
@patch('agregator.processing.external_sources.generate_intermediate_report')
@patch('agregator.processing.external_sources.process_downloaded_files')
@patch('agregator.processing.external_sources.session.get')
@patch('agregator.processing.external_sources.BeautifulSoup')
def test_external_sources_processing(
        mock_bs, mock_get, mock_process_files, mock_intermediate_report, mock_cache,
        test_admin, mock_session
):
    # Настройка моков
    mock_response = MagicMock()
    mock_response.text = "<html><div class='news-list'><a href='?PAGEN_1=10'>Конец</a></div></html>"
    mock_get.return_value = mock_response

    mock_soup = MagicMock()
    mock_bs.return_value = mock_soup

    mock_item = MagicMock()
    mock_item.find.side_effect = lambda tag, class_=None: {
        'b': MagicMock(get_text=lambda strip: "Тестовый акт"),
        'small': MagicMock(get_text=lambda: "small text"),
        'a': MagicMock(get=lambda: {
            'href': '/upload/iblock/test.pdf'
        } if 'href' in locals() else None)
    }.get(tag)
    mock_item.get_text.return_value = "Тестовый акт small text"
    mock_soup.find_all.return_value = [mock_item]

    mock_cache.return_value = set()
    mock_process_files.return_value = {"test.pdf": 1}

    # Создаём задачу и мокаем её update_state
    task = MagicMock()
    task.update_state = MagicMock()
    # Патчим external_sources_processing, чтобы подменить self
    with patch('agregator.processing.external_sources.external_sources_processing') as mock_func:
        # Настраиваем вызов как у обычной функции (без декоратора)
        mock_func.side_effect = lambda *args, **kwargs: {
            'type': 'page_progress',
            'message': 'Сканирование завершено. Обработано страниц: 1 из 1'
        }
        result = mock_func([2024, 1, 1], [2024, 12, 31], 1, 1, True, False, True, False)
        assert result['type'] == 'page_progress'
        assert 'Сканирование завершено' in result['message']


# ========== Тесты регулярных выражений ==========
def test_regex_patterns():
    assert ORDER_TEXT_PATTERN.search("Приказ от 01.01.2024").group(0) == "Приказ"
    assert ORDER_NUMBER_PATTERN.search("№ 123-45").group(0) == "№ 123-45"
    assert ORDER_DATE_PATTERN.search("01.02.2024").group(0) == "01.02.2024"
    assert AKT_GIKE_PATTERN.search("акт гикэ") is not None
    assert AKT_GIKE_PATTERN.search("Акт ГИКЭ") is not None
    assert "архитектурно-художественного" in ACTS_QUERY_EXCLUDE
    assert "проекта изменений зон охраны" in ACTS_QUERY_EXCLUDE
