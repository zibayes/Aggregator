import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock, ANY
from django.contrib.auth import get_user_model
from agregator.models import ScientificReport
from agregator.processing.scientific_reports_processing import (
    choose_file,
    process_scientific_reports,
    extract_text_and_images,
    error_handler_scientific_reports,
)
from agregator.celery_task_template import process_documents

User = get_user_model()


@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def test_report(test_user, tmpdir):
    """Создаёт тестовый научный отчёт с минимальными данными"""
    file_path = tmpdir.join("report.pdf")
    file_path.write("dummy")
    report = ScientificReport.objects.create(
        user=test_user,
        name="",
        is_processing=True,
        source=[{"path": str(file_path), "origin_filename": "report.pdf", "type": "all"}]
    )
    return report


@pytest.fixture
def mock_redis():
    with patch('agregator.processing.scientific_reports_processing.redis_client') as mock:
        mock.set.return_value = True
        yield mock


@pytest.fixture
def mock_fitz():
    with patch('agregator.processing.scientific_reports_processing.fitz') as mock:
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Текст отчёта"
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.close.return_value = None
        mock.open.return_value = mock_doc
        yield mock


@pytest.fixture
def mock_pdfplumber():
    with patch('agregator.processing.scientific_reports_processing.pdfplumber') as mock:
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_tables.return_value = []
        mock_pdf.pages = [mock_page]
        mock.open.return_value.__enter__.return_value = mock_pdf
        yield mock


# ========== Тесты для choose_file ==========
def test_choose_file():
    with patch('agregator.processing.scientific_reports_processing.filedialog.askopenfilename') as mock_dialog:
        mock_dialog.return_value = "/path/to/file.pdf"
        result = choose_file()
        assert result == "/path/to/file.pdf"
        mock_dialog.assert_called_once()


def test_choose_file_cancel():
    with patch('agregator.processing.scientific_reports_processing.filedialog.askopenfilename') as mock_dialog:
        mock_dialog.return_value = ""
        result = choose_file()
        assert result is None


# ========== Тесты для process_scientific_reports ==========
@patch('agregator.processing.scientific_reports_processing.process_documents')
def test_process_scientific_reports(mock_process_docs):
    """Задача process_scientific_reports вызывает process_documents с правильными аргументами"""
    from unittest.mock import ANY
    reports_ids = [1, 2]
    user_id = 1
    select_text = True
    select_enrich = False
    select_image = True
    select_coord = False

    result = process_scientific_reports.run(reports_ids, user_id, select_text, select_enrich, select_image,
                                            select_coord)

    mock_process_docs.assert_called_once_with(
        ANY, reports_ids, user_id, 'scientific_reports',
        model_class=ScientificReport,
        load_function=ANY,
        select_text=select_text,
        select_enrich=select_enrich,
        select_image=select_image,
        select_coord=select_coord,
        process_function=extract_text_and_images
    )
    assert result == mock_process_docs.return_value


# ========== Тесты для extract_text_and_images ==========
@pytest.mark.django_db
@patch('agregator.processing.scientific_reports_processing.extract_images_with_captions')
@patch('agregator.processing.scientific_reports_processing.extract_coordinates')
@patch('agregator.processing.scientific_reports_processing.insert_supplement_links')
def test_extract_text_and_images_success(
        mock_insert_links,
        mock_extract_coords,
        mock_extract_images,
        test_report,
        mock_redis,
        mock_fitz,
        mock_pdfplumber
):
    """Успешная обработка научного отчёта с извлечением данных"""
    # Настройка моков для извлечения текста из PDF (с учётом регулярок научных отчётов)
    mock_fitz.open.return_value.__getitem__.return_value.get_text.return_value = """
    Научный отчет
    Название отчёта
    Выполнил: Иванов И.И.
    Открытый лист от 01.01.2024 г. № 123
    ООО «Археология»
    г. Красноярск 2024
    Общая площадь 1234.56 м2
    """
    mock_fitz.open.return_value.__len__.return_value = 1

    progress_recorder = MagicMock()
    pages_count = {str(test_report.source_dict[0]['path']): 1}
    total_processed = [0]
    progress_json = {
        "file_groups": {
            str(test_report.id): [
                {
                    "origin_filename": "report.pdf",
                    "processed": "False",
                    "pages": {"processed": 0, "all": 1},
                    "type": "all"
                }
            ]
        }
    }
    task_id = "task123"
    user_id = test_report.user.id
    is_public = False
    select_text = True
    select_enrich = False
    select_image = True
    select_coord = True

    extract_text_and_images(
        current_report=test_report,
        file=str(test_report.source_dict[0]['path']),
        progress_recorder=progress_recorder,
        pages_count=pages_count,
        total_processed=total_processed,
        progress_json=progress_json,
        report_id=test_report.id,
        source_index=0,
        task_id=task_id,
        user_id=user_id,
        is_public=is_public,
        select_text=select_text,
        select_enrich=select_enrich,
        select_image=select_image,
        select_coord=select_coord
    )

    test_report.refresh_from_db()
    assert "Название отчёта" in test_report.name
    assert test_report.author == "Иванов И.И."
    assert "Открытый лист от 01.01.2024 г. № 123" in test_report.open_list
    assert test_report.organization == "ООО «Археология»"
    assert "Красноярск" in test_report.place
    assert test_report.writing_date == "2024"
    assert test_report.area_info == "1234.56 м2"
    assert test_report.is_processing is False

    mock_extract_images.assert_called()
    mock_extract_coords.assert_called()
    mock_insert_links.assert_called()


@pytest.mark.django_db
@patch('agregator.processing.scientific_reports_processing.extract_images_with_captions')
def test_extract_text_and_images_duplicate_file(
        mock_extract_images,
        test_report,
        test_user,
        mock_redis,
        mock_fitz,
        mock_pdfplumber,
        tmpdir
):
    """Проверка, что при дубликате файла выбрасывается FileExistsError"""
    file_path = test_report.source_dict[0]['path']
    with patch('agregator.processing.scientific_reports_processing.calculate_file_hash') as mock_hash:
        mock_hash.return_value = "samehash"
        duplicate_report = ScientificReport.objects.create(
            user=test_user,
            source=[{"path": str(file_path), "origin_filename": "dup.pdf", "type": "all"}],
            is_processing=True
        )

        progress_recorder = MagicMock()
        pages_count = {str(file_path): 1}
        total_processed = [0]
        progress_json = {
            "file_groups": {
                str(duplicate_report.id): [
                    {
                        "origin_filename": "dup.pdf",
                        "processed": "False",
                        "pages": {"processed": 0, "all": 1},
                        "type": "all"
                    }
                ]
            }
        }
        with pytest.raises(FileExistsError) as exc_info:
            extract_text_and_images(
                current_report=duplicate_report,
                file=str(file_path),
                progress_recorder=progress_recorder,
                pages_count=pages_count,
                total_processed=total_processed,
                progress_json=progress_json,
                report_id=duplicate_report.id,
                source_index=0,
                task_id="task",
                user_id=test_user.id,
                is_public=False,
                select_text=True,
                select_enrich=False,
                select_image=True,
                select_coord=True
            )
        assert "Такой файл уже загружен в систему" in str(exc_info.value)


@pytest.mark.django_db
def test_extract_text_and_images_extraction_error(
        test_report,
        mock_redis,
        mock_fitz,
        mock_pdfplumber
):
    """Тест, что при ошибке извлечения текста выбрасывается исключение"""
    mock_fitz.open.return_value.__getitem__.return_value.get_text.side_effect = Exception("Ошибка извлечения текста")

    progress_recorder = MagicMock()
    pages_count = {str(test_report.source_dict[0]['path']): 1}
    total_processed = [0]
    progress_json = {
        "file_groups": {
            str(test_report.id): [
                {
                    "origin_filename": "report.pdf",
                    "processed": "False",
                    "pages": {"processed": 0, "all": 1},
                    "type": "all"
                }
            ]
        }
    }
    with pytest.raises(Exception) as exc_info:
        extract_text_and_images(
            current_report=test_report,
            file=str(test_report.source_dict[0]['path']),
            progress_recorder=progress_recorder,
            pages_count=pages_count,
            total_processed=total_processed,
            progress_json=progress_json,
            report_id=test_report.id,
            source_index=0,
            task_id="task",
            user_id=test_report.user.id,
            is_public=False,
            select_text=True,
            select_enrich=False,
            select_image=False,
            select_coord=False
        )
    assert "Ошибка извлечения текста" in str(exc_info.value)
    test_report.refresh_from_db()
    assert test_report.is_processing is True


# ========== Тесты для error_handler_scientific_reports ==========
@pytest.mark.django_db
def test_error_handler_scientific_reports_deletes_unprocessed(test_report, test_user):
    """Обработчик удаляет необработанные отчёты"""
    task = MagicMock()
    task.id = "task_id"
    exception = Exception("Test error")

    progress_json = {
        "file_groups": {
            str(test_report.id): [
                {
                    "processed": "False",
                    "origin_filename": "test.pdf"
                }
            ]
        }
    }
    with patch('agregator.processing.scientific_reports_processing.redis_client.get') as mock_get:
        mock_get.return_value = json.dumps(progress_json)

        with pytest.raises(Exception) as exc_info:
            error_handler_scientific_reports(task, exception, "desc")

        with pytest.raises(ScientificReport.DoesNotExist):
            test_report.refresh_from_db()

        assert "Test error" in str(exc_info.value)


@pytest.mark.django_db
def test_error_handler_scientific_reports_keeps_processed(test_report, test_user):
    """Обработчик не удаляет уже обработанные отчёты"""
    task = MagicMock()
    task.id = "task_id"
    exception = Exception("Test error")

    progress_json = {
        "file_groups": {
            str(test_report.id): [
                {
                    "processed": "True",
                    "origin_filename": "test.pdf"
                }
            ]
        }
    }
    with patch('agregator.processing.scientific_reports_processing.redis_client.get') as mock_get:
        mock_get.return_value = json.dumps(progress_json)

        with pytest.raises(Exception) as exc_info:
            error_handler_scientific_reports(task, exception, "desc")

        test_report.refresh_from_db()
        assert test_report.id is not None
        assert "Test error" in str(exc_info.value)
