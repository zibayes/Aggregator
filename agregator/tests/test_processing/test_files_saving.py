import pytest
import json
import os
import tempfile
import platform
import subprocess
from unittest.mock import patch, MagicMock, mock_open, call, ANY
from pathlib import Path
import shutil
from io import BytesIO

import fitz
import pandas as pd
import PIL
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

from agregator.models import (
    Act, ScientificReport, TechReport, OpenLists,
    ObjectAccountCard, CommercialOffers, GeoObject
)
from agregator.processing.files_saving import (
    delete_files_in_directory,
    convert_document,
    _convert_with_word,
    _convert_with_libreoffice,
    get_page_count,
    _get_doc_page_count_win32,
    _get_odt_page_count_win32,
    _get_doc_page_count_linux,
    _get_odt_page_count_linux,
    _get_page_count_via_libreoffice,
    raw_open_lists_save,
    load_raw_open_lists,
    raw_reports_save,
    save_report,
    save_report_source,
    load_raw_reports,
    raw_account_cards_save,
    load_raw_account_cards,
    raw_commercial_offers_save,
    load_raw_commercial_offers,
    raw_geo_objects_save,
    load_raw_geo_objects,
)

User = get_user_model()


# ========== Фикстуры ==========
@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def sample_pdf(temp_dir):
    """Создаёт временный PDF файл"""
    pdf_path = temp_dir / "sample.pdf"
    from fitz import open as fitz_open
    doc = fitz_open()
    page = doc.new_page()
    page.insert_text((100, 100), "Test text")
    doc.save(pdf_path)
    doc.close()
    return pdf_path


@pytest.fixture
def sample_docx(temp_dir):
    """Создаёт временный DOCX файл (имитация)"""
    docx_path = temp_dir / "sample.docx"
    docx_path.touch()
    return docx_path


@pytest.fixture
def mock_win32com():
    """Мок для win32com"""
    with patch('agregator.processing.files_saving.comtypes.client') as mock_client, \
            patch('agregator.processing.files_saving.win32com.client') as mock_win32:
        mock_word = MagicMock()
        mock_doc = MagicMock()
        mock_word.Documents.Open.return_value = mock_doc
        mock_client.CreateObject.return_value = mock_word
        mock_win32.Dispatch.return_value = mock_word
        yield mock_word


@pytest.fixture
def mock_libreoffice():
    """Мок для subprocess вызовов LibreOffice"""
    with patch('agregator.processing.files_saving.subprocess.run') as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock_run


@pytest.fixture
def mock_fitz():
    """Мок для fitz"""
    with patch('agregator.processing.files_saving.fitz') as mock_fitz:
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 5
        mock_fitz.open.return_value.__enter__.return_value = mock_doc
        yield mock_fitz


# ========== Тесты delete_files_in_directory ==========
def test_delete_files_in_directory(temp_dir):
    file1 = temp_dir / "file1.txt"
    file2 = temp_dir / "file2.txt"
    file1.touch()
    file2.touch()

    # Создаём мок-файлы для закрытия
    mock_file1 = MagicMock()
    mock_file2 = MagicMock()
    mock_file1.name = "file1.txt"
    mock_file2.name = "file2.txt"

    delete_files_in_directory(str(temp_dir), [mock_file1, mock_file2])

    assert not file1.exists()
    assert not file2.exists()
    mock_file1.close.assert_called_once()
    mock_file2.close.assert_called_once()


def test_delete_files_in_directory_nonexistent(temp_dir):
    nonexistent = temp_dir / "nonexistent"
    delete_files_in_directory(str(nonexistent), [])
    # Не должно быть ошибки


# ========== Тесты convert_document ==========
@patch('agregator.processing.files_saving.platform.system')
@patch('agregator.processing.files_saving._convert_with_word')
@patch('agregator.processing.files_saving._convert_with_libreoffice')
def test_convert_document_windows_word(mock_libre, mock_word, mock_system, sample_docx, temp_dir):
    mock_system.return_value = 'Windows'
    output = temp_dir / "output.pdf"
    mock_word.return_value = str(output)

    result = convert_document(str(sample_docx), output_format='pdf')
    assert result == str(output)
    mock_word.assert_called_once()
    mock_libre.assert_not_called()


@patch('agregator.processing.files_saving.platform.system')
@patch('agregator.processing.files_saving._convert_with_word')
@patch('agregator.processing.files_saving._convert_with_libreoffice')
def test_convert_document_windows_word_fallback(mock_libre, mock_word, mock_system, sample_docx, temp_dir):
    mock_system.return_value = 'Windows'
    mock_word.side_effect = Exception("Word error")
    output = temp_dir / "output.pdf"
    mock_libre.return_value = str(output)

    result = convert_document(str(sample_docx), output_format='pdf')
    assert result == str(output)
    mock_word.assert_called_once()
    mock_libre.assert_called_once()


@patch('agregator.processing.files_saving.platform.system')
@patch('agregator.processing.files_saving._convert_with_libreoffice')
def test_convert_document_linux(mock_libre, mock_system, sample_docx, temp_dir):
    mock_system.return_value = 'Linux'
    output = temp_dir / "output.pdf"
    mock_libre.return_value = str(output)

    result = convert_document(str(sample_docx), output_format='pdf')
    assert result == str(output)
    mock_libre.assert_called_once()


def test_convert_document_file_not_found():
    with pytest.raises(FileNotFoundError):
        convert_document("/nonexistent/file.doc")


def test_convert_document_invalid_output_format(sample_docx):
    with pytest.raises(ValueError):
        convert_document(str(sample_docx), output_format='txt')


@patch('agregator.processing.files_saving._convert_with_libreoffice')
def test_convert_document_libreoffice_error(mock_libre, sample_docx, temp_dir):
    mock_libre.side_effect = RuntimeError("LibreOffice error")
    with pytest.raises(RuntimeError):
        convert_document(str(sample_docx), output_format='pdf')


# ========== Тесты _convert_with_libreoffice ==========
@patch('agregator.processing.files_saving.shutil.which')
@patch('agregator.processing.files_saving.subprocess.run')
def test_convert_with_libreoffice_success(mock_run, mock_which, temp_dir):
    mock_which.return_value = "/usr/bin/libreoffice"
    input_path = temp_dir / "test.doc"
    input_path.touch()
    output_path = temp_dir / "test.pdf"
    mock_run.return_value = MagicMock(returncode=0)

    result = _convert_with_libreoffice(input_path, output_path, 'pdf')
    assert result == str(output_path)
    mock_run.assert_called_once_with([
        'libreoffice', '--headless', '--convert-to', 'pdf',
        '--outdir', str(temp_dir), str(input_path)
    ], check=True, capture_output=True)


@patch('agregator.processing.files_saving.shutil.which')
def test_convert_with_libreoffice_not_installed(mock_which, temp_dir):
    mock_which.return_value = None
    input_path = temp_dir / "test.doc"
    with pytest.raises(RuntimeError, match="LibreOffice не установлен"):
        _convert_with_libreoffice(input_path, temp_dir / "out.pdf", 'pdf')


# ========== Тесты get_page_count ==========
@patch('agregator.processing.files_saving.platform.system')
def test_get_page_count_pdf(mock_system, sample_pdf):
    # Реальный подсчёт страниц через fitz
    count = get_page_count(str(sample_pdf))
    assert count == 1


@patch('agregator.processing.files_saving.platform.system')
@patch('agregator.processing.files_saving._get_doc_page_count_win32')
@patch('agregator.processing.files_saving._get_doc_page_count_linux')
def test_get_page_count_doc_windows(mock_linux, mock_win32, mock_system, sample_docx):
    mock_system.return_value = 'Windows'
    mock_win32.return_value = 3
    count = get_page_count(str(sample_docx))
    assert count == 3
    mock_win32.assert_called_once()
    mock_linux.assert_not_called()


@patch('agregator.processing.files_saving.platform.system')
@patch('agregator.processing.files_saving._get_doc_page_count_win32')
@patch('agregator.processing.files_saving._get_doc_page_count_linux')
def test_get_page_count_doc_linux(mock_linux, mock_win32, mock_system, sample_docx):
    mock_system.return_value = 'Linux'
    mock_linux.return_value = 5
    count = get_page_count(str(sample_docx))
    assert count == 5
    mock_linux.assert_called_once()
    mock_win32.assert_not_called()


def test_get_page_count_unsupported_format(temp_dir):
    unknown = temp_dir / "file.xyz"
    unknown.touch()
    count = get_page_count(str(unknown))
    assert count == 1  # fallback


# ========== Тесты _get_page_count_via_libreoffice ==========
@patch('agregator.processing.files_saving.subprocess.run')
def test_get_page_count_via_libreoffice(mock_run, sample_docx):
    mock_run.return_value = MagicMock(stdout="Number of pages: 7\n", stderr="", returncode=0)
    count = _get_page_count_via_libreoffice(str(sample_docx))
    assert count == 7
    mock_run.assert_called_once_with(
        ['libreoffice', '--headless', '--cat', str(sample_docx)],
        capture_output=True, text=True, check=True
    )


@patch('agregator.processing.files_saving.subprocess.run')
def test_get_page_count_via_libreoffice_error(mock_run, sample_docx):
    mock_run.side_effect = subprocess.CalledProcessError(1, "cmd")
    count = _get_page_count_via_libreoffice(str(sample_docx))
    assert count == 1


# ========== Тесты raw_open_lists_save ==========
@pytest.mark.django_db
def test_raw_open_lists_save_with_image(test_user, temp_dir):
    img = Image.new('RGB', (100, 100), color='white')
    img_buffer = BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    uploaded = SimpleUploadedFile("test.png", img_buffer.read(), content_type="image/png")

    # Убираем параметр upload_source, т.к. для SimpleUploadedFile он не применяется
    open_list_ids = raw_open_lists_save([uploaded], test_user.id, True, "test.png")
    assert len(open_list_ids) == 1
    ol = OpenLists.objects.get(id=open_list_ids[0])
    assert ol.origin_filename == "test.png"
    # Ожидаем дефолтное значение upload_source
    assert json.loads(ol.upload_source) == {"source": "Пользовательский файл"}


@pytest.mark.django_db
def test_raw_open_lists_save_with_file(test_user, temp_dir):
    content = b"dummy file content"
    uploaded = SimpleUploadedFile("test.txt", content, content_type="text/plain")
    open_list_ids = raw_open_lists_save([uploaded], test_user.id, False)
    ol = OpenLists.objects.get(id=open_list_ids[0])
    assert ol.origin_filename == "test.txt"
    assert json.loads(ol.upload_source) == {"source": "Пользовательский файл"}


# ========== Тесты load_raw_open_lists ==========
@pytest.mark.django_db
@patch('agregator.processing.files_saving.convert_document')
@patch('agregator.processing.files_saving.get_page_count')
@patch('agregator.processing.files_saving.fitz.open')
def test_load_raw_open_lists(mock_fitz_open, mock_page_count, mock_convert, test_user, temp_dir):
    # Создаём открытый лист с изображением
    ol = OpenLists.objects.create(
        user=test_user,
        source="Открытые листы/test/test.png",
        origin_filename="test.png",
        is_public=True
    )
    # Создаём реальный файл изображения
    full_path = Path(f"uploaded_files/{ol.source}")
    full_path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new('RGB', (100, 100), color='white')
    img.save(full_path)

    # Мокаем конвертацию
    mock_convert.return_value = None
    mock_page_count.return_value = 3
    mock_pdf = MagicMock()
    mock_pdf.__len__.return_value = 3
    mock_fitz_open.return_value.__enter__.return_value = mock_pdf

    open_lists, pages_count = load_raw_open_lists([ol.id])
    assert len(open_lists) == 1
    assert pages_count[str(ol.id)] == 3
    # Проверяем, что source был обновлён на PDF
    ol.refresh_from_db()
    assert ol.source.name.endswith('.pdf')


# ========== Тесты raw_reports_save, save_report, save_report_source ==========
@pytest.mark.django_db
@patch('agregator.hash.calculate_file_hash')
def test_save_report_source_with_hash(mock_hash, test_user, temp_dir):
    mock_hash.return_value = "abc123"
    report = Act.objects.create(user=test_user, is_public=True)
    file_content = b"test content"
    uploaded = SimpleUploadedFile("test.pdf", file_content, content_type="application/pdf")
    path = str(temp_dir / "reports")
    source_content = []
    # Создаём директорию
    os.makedirs(path, exist_ok=True)
    save_report_source(report, uploaded, path, "Акты ГИКЭ", report.id, source_content, upload_source=None)
    assert len(source_content) == 1
    assert source_content[0]['type'] == 'all'
    assert source_content[0]['origin_filename'] == 'test.pdf'
    assert source_content[0]['file_hash'] == 'abc123'
    # Проверяем, что файл сохранён
    saved_path = source_content[0]['path']
    assert os.path.exists(saved_path)
    with open(saved_path, 'rb') as f:
        assert f.read() == file_content


@pytest.mark.django_db
@patch('agregator.hash.calculate_file_hash')
def test_save_report(mock_hash, test_user, temp_dir):
    mock_hash.return_value = "hash"
    files = [
        {'file': SimpleUploadedFile("test1.pdf", b"content1", content_type="application/pdf"), 'type': 'text'},
        {'file': SimpleUploadedFile("test2.pdf", b"content2", content_type="application/pdf"), 'type': 'images'}
    ]
    reports_ids = []
    # Подготовка директории
    path = f"uploaded_files/Акты ГИКЭ/test1"
    os.makedirs(path, exist_ok=True)
    save_report(files, reports_ids, Act, test_user.id, True, "Акты ГИКЭ", upload_source=None)
    assert len(reports_ids) == 1
    report = Act.objects.get(id=reports_ids[0])
    assert report.is_public is True
    assert len(report.source_dict) == 2
    # Первый файл имеет index=0 → условие if index: не выполнится → тип 'all'
    assert report.source_dict[0]['type'] == 'all'
    # Второй файл имеет index=1 → условие выполнится → тип 'images'
    assert report.source_dict[1]['type'] == 'images'


@pytest.mark.django_db
@patch('agregator.hash.calculate_file_hash')
def test_raw_reports_save(mock_hash, test_user, temp_dir):
    mock_hash.return_value = "hash"
    file_groups = {
        "group1": [
            {'file': SimpleUploadedFile("doc1.pdf", b"content1", content_type="application/pdf"), 'type': 'all'}
        ]
    }
    uploaded_files = [SimpleUploadedFile("doc2.pdf", b"content2", content_type="application/pdf")]
    # Подготовка директории
    os.makedirs("uploaded_files/Акты ГИКЭ/doc1", exist_ok=True)
    os.makedirs("uploaded_files/Акты ГИКЭ/doc2", exist_ok=True)
    ids = raw_reports_save(file_groups, uploaded_files, Act, test_user.id, False)
    assert len(ids) == 2  # group1 + uploaded_files
    acts = Act.objects.filter(id__in=ids)
    assert acts.count() == 2
    for act in acts:
        assert len(act.source_dict) == 1


# ========== Тесты load_raw_reports ==========
@patch('agregator.processing.files_saving.fitz.open')
def test_load_raw_reports(mock_fitz_open, test_user, sample_pdf, temp_dir):
    act = Act.objects.create(user=test_user, source=[{"path": str(sample_pdf), "type": "all"}])
    mock_pdf = MagicMock()
    mock_pdf.__len__.return_value = 2
    mock_fitz_open.return_value.__enter__.return_value = mock_pdf

    reports, pages_count = load_raw_reports([act.id], Act)
    assert len(reports) == 1
    assert pages_count[str(sample_pdf)] == 2


# ========== Тесты raw_account_cards_save ==========
@pytest.mark.django_db
def test_raw_account_cards_save(test_user, temp_dir):
    content = b"test account card"
    uploaded = SimpleUploadedFile("card.pdf", content, content_type="application/pdf")
    ids = raw_account_cards_save([uploaded], test_user.id, True)
    assert len(ids) == 1
    card = ObjectAccountCard.objects.get(id=ids[0])
    assert card.user == test_user
    assert card.origin_filename == "card.pdf"
    assert json.loads(card.upload_source) == {"source": "Пользовательский файл"}
    # Проверяем, что файл сохранён
    assert os.path.exists(card.source)


# ========== Тесты load_raw_account_cards ==========
@pytest.mark.django_db
@patch('agregator.processing.files_saving.get_page_count')
@patch('agregator.processing.files_saving.fitz.open')
def test_load_raw_account_cards(mock_fitz_open, mock_page_count, test_user, sample_pdf, temp_dir):
    mock_page_count.return_value = 3
    mock_pdf = MagicMock()
    mock_pdf.__len__.return_value = 3
    mock_fitz_open.return_value.__enter__.return_value = mock_pdf
    card = ObjectAccountCard.objects.create(
        user=test_user,
        source=str(sample_pdf),
        origin_filename="card.pdf"
    )
    cards, pages_count = load_raw_account_cards([card.id])
    assert len(cards) == 1
    assert pages_count[str(sample_pdf)] == 3


# ========== Тесты raw_commercial_offers_save ==========
@pytest.mark.django_db
def test_raw_commercial_offers_save(test_user, temp_dir):
    content = b"test commercial offer"
    uploaded = SimpleUploadedFile("offer.xlsx", content,
                                  content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    ids = raw_commercial_offers_save([uploaded], test_user.id, True)
    assert len(ids) == 1
    offer = CommercialOffers.objects.get(id=ids[0])
    assert offer.user == test_user
    assert offer.origin_filename == "offer.xlsx"
    assert json.loads(offer.upload_source) == {"source": "Пользовательский файл"}
    assert os.path.exists(offer.source)


# ========== Тесты load_raw_commercial_offers ==========
@pytest.mark.django_db
@patch('agregator.processing.files_saving.convert_document')
@patch('agregator.processing.files_saving.get_page_count')
@patch('agregator.processing.files_saving.fitz.open')
def test_load_raw_commercial_offers(mock_fitz_open, mock_page_count, mock_convert, test_user, sample_pdf, temp_dir):
    mock_page_count.return_value = 2
    mock_pdf = MagicMock()
    mock_pdf.__len__.return_value = 2
    mock_fitz_open.return_value.__enter__.return_value = mock_pdf
    offer = CommercialOffers.objects.create(
        user=test_user,
        source=str(sample_pdf),
        origin_filename="offer.pdf"
    )
    offers, pages_count = load_raw_commercial_offers([offer.id])
    assert len(offers) == 1
    assert pages_count[str(sample_pdf)] == 2


# ========== Тесты raw_geo_objects_save ==========
@pytest.mark.django_db
def test_raw_geo_objects_save(test_user, temp_dir):
    content = b"test geo object"
    uploaded = SimpleUploadedFile("geo.kml", content, content_type="application/vnd.google-earth.kml+xml")
    ids = raw_geo_objects_save([uploaded], test_user.id, True)
    assert len(ids) == 1
    geo = GeoObject.objects.get(id=ids[0])
    assert geo.user == test_user
    assert geo.origin_filename == "geo.kml"
    assert json.loads(geo.upload_source) == {"source": "Пользовательский файл"}
    assert os.path.exists(geo.source)


# ========== Тесты load_raw_geo_objects ==========
@pytest.mark.django_db
def test_load_raw_geo_objects(test_user, temp_dir):
    geo = GeoObject.objects.create(user=test_user, source="some/path.kml", origin_filename="geo.kml")
    geos, pages_count = load_raw_geo_objects([geo.id])
    assert len(geos) == 1
    assert pages_count[geo.source] == 1
