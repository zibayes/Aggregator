import pytest
import os
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile
from django_celery_results.models import TaskResult
from celery.exceptions import Retry
from celery import states
from celery.result import AsyncResult
from agregator.models import CommercialOffers, UserTasks
from agregator.processing.commercial_offers_processing import (
    process_commercial_offers,
    extract_coordinates,
    error_handler_commercial_offers
)
from agregator.processing.files_saving import load_raw_commercial_offers
from agregator.redis_config import redis_client
from agregator.hash import calculate_file_hash


# ======================
# ТЕСТЫ НА ИЗВЛЕЧЕНИЕ КООРДИНАТ
# ======================

@pytest.mark.parametrize("file_type,expected_result,has_tables", [
    (".pdf", {"coordinates": [{"system": "WGS84", "lat": 55.75, "lon": 37.62}]}, True),
    (".docx", {"coordinates": [{"system": "WGS84", "lat": 55.75, "lon": 37.62}]}, True),
    (".xlsx", {"coordinates": [{"system": "WGS84", "lat": 55.75, "lon": 37.62}]}, True),
    (".xls", {"coordinates": [{"system": "WGS84", "lat": 55.75, "lon": 37.62}]}, True),
    (".txt", {}, False),  # Неподдерживаемый формат
])
@patch("agregator.processing.commercial_offers_processing.extract_tables_from_pdf")
@patch("agregator.processing.commercial_offers_processing.analyze_coordinates_in_tables_from_pdf")
@patch("agregator.processing.commercial_offers_processing.Document")
@patch("agregator.processing.commercial_offers_processing.extract_coordinates_from_docx_table")
@patch("agregator.processing.commercial_offers_processing.extract_coordinates_xlsx")
@patch("agregator.processing.commercial_offers_processing.format_coordinates")
def test_extract_coordinates_success(
        mock_format_coordinates,
        mock_extract_xlsx,
        mock_extract_docx,
        mock_document,
        mock_analyze,
        mock_extract_tables,
        file_type,
        expected_result,
        has_tables,
        test_commercial_offer,
        test_user
):
    """Тест на успешное извлечение координат из разных типов файлов"""
    # Подготовка данных
    temp_file = tempfile.NamedTemporaryFile(suffix=file_type, delete=False)
    temp_file.close()

    # Настройка моков в зависимости от типа файла
    if file_type == ".pdf" and has_tables:
        mock_extract_tables.return_value = [{"table": "data"}]
        mock_analyze.return_value = ([{"lat": 55.75, "lon": 37.62}], ["WGS84"], [])
    elif file_type in (".docx", ".doc") and has_tables:
        mock_document.return_value = MagicMock(tables=[MagicMock()])
        mock_extract_docx.return_value = ([{"lat": 55.75, "lon": 37.62}], ["WGS84"])
    elif file_type in (".xlsx", ".xls") and has_tables:
        mock_extract_xlsx.return_value = ([{"lat": 55.75, "lon": 37.62}], ["WGS84"])

    mock_format_coordinates.return_value = expected_result

    # Подготовка прогресса
    task_id = "test_task_123"
    progress_json = {
        "file_groups": {str(test_commercial_offer.id): {"origin_filename": "test_file" + file_type}},
        "expected_time": "00:00:00"
    }
    redis_client.set(task_id, json.dumps(progress_json))

    # Создаем объект progress_recorder
    class MockProgressRecorder:
        def set_progress(self, current, total, progress):
            pass

    # Выполняем функцию
    extract_coordinates(
        temp_file.name,
        MockProgressRecorder(),
        {"1": 1},
        [0],
        test_commercial_offer.id,
        progress_json,
        task_id,
        datetime.now()
    )

    # Проверяем результат
    commercial_offer = CommercialOffers.objects.get(id=test_commercial_offer.id)
    assert json.loads(commercial_offer.coordinates) == expected_result
    assert commercial_offer.is_processing is False

    # Удаляем временный файл
    os.unlink(temp_file.name)


def test_extract_coordinates_duplicate_file(
        valid_pdf_file,
        test_commercial_offer,
        test_user
):
    """Тест на обнаружение дублирующегося файла по хэшу"""
    # Создаем первый объект коммерческого предложения с валидным файлом
    CommercialOffers.objects.filter(id=test_commercial_offer.id).update(
        source=valid_pdf_file,
        origin_filename="original.pdf"
    )

    # Создаем второй объект с тем же файлом
    duplicate_offer = CommercialOffers.objects.create(
        user=test_user,
        origin_filename="duplicate.pdf",
        source=valid_pdf_file
    )

    # Подготовка прогресса
    task_id = "test_task_123"
    progress_json = {
        "file_groups": {str(duplicate_offer.id): {"origin_filename": "duplicate.pdf"}},
        "expected_time": "00:00:00"
    }
    redis_client.set(task_id, json.dumps(progress_json))

    # Создаем объект progress_recorder
    class MockProgressRecorder:
        def set_progress(self, current, total, progress):
            pass

    # Проверяем, что возникает ошибка дублирования
    with pytest.raises(FileExistsError) as exc_info:
        extract_coordinates(
            duplicate_offer.source.path,
            MockProgressRecorder(),
            {"1": 1},
            [0],
            duplicate_offer.id,
            progress_json,
            task_id,
            datetime.now()
        )

    assert "Такой файл уже загружен в систему" in str(exc_info.value)


@pytest.mark.parametrize("file_type,exception", [
    (".pdf", Exception("PDF processing error")),
    (".docx", Exception("DOCX processing error")),
    (".xlsx", Exception("XLSX processing error")),
])
@patch("agregator.processing.commercial_offers_processing.extract_tables_from_pdf")
@patch("agregator.processing.commercial_offers_processing.Document")
@patch("agregator.processing.commercial_offers_processing.extract_coordinates_xlsx")
def test_extract_coordinates_processing_errors(
        mock_extract_xlsx,
        mock_document,
        mock_extract_tables,
        file_type,
        exception,
        test_commercial_offer,
        test_user
):
    """Тест обработки ошибок при извлечении координат из разных типов файлов"""
    # Настройка моков для выбрасывания ошибок
    if file_type == ".pdf":
        mock_extract_tables.side_effect = exception
    elif file_type == ".docx":
        mock_document.side_effect = exception
    elif file_type == ".xlsx":
        mock_extract_xlsx.side_effect = exception

    # Создаем временный файл
    with tempfile.NamedTemporaryFile(suffix=file_type, delete=False) as f:
        f.write(b"test content")
        f_path = f.name

    # Подготовка прогресса
    task_id = "test_task_123"
    progress_json = {
        "file_groups": {str(test_commercial_offer.id): {"origin_filename": "test_file" + file_type}},
        "expected_time": "00:00:00"
    }
    redis_client.set(task_id, json.dumps(progress_json))

    # Создаем объект progress_recorder
    class MockProgressRecorder:
        def set_progress(self, current, total, progress):
            pass

    # Проверяем, что ошибка приводит к падению задачи
    with pytest.raises(type(exception)):
        extract_coordinates(
            f_path,
            MockProgressRecorder(),
            {"1": 1},
            [0],
            test_commercial_offer.id,
            progress_json,
            task_id,
            datetime.now()
        )

    # Удаляем временный файл
    os.unlink(f_path)


# ======================
# ТЕСТЫ НА ПРОЦЕССИРОВАНИЕ КОММЕРЧЕСКИХ ПРЕДЛОЖЕНИЙ
# ======================

def test_process_commercial_offers_success(
        test_commercial_offer,
        test_user,
        valid_pdf_file
):
    """Тест успешной обработки коммерческого предложения"""
    # Устанавливаем валидный файл
    test_commercial_offer.source = valid_pdf_file
    test_commercial_offer.save()

    # Мокаем Celery task
    with patch("agregator.processing.commercial_offers_processing.process_documents") as mock_process:
        mock_process.return_value = "SUCCESS"

        # Выполняем задачу
        result = process_commercial_offers.delay(
            [test_commercial_offer.id],
            test_user.id
        )

        # Проверяем, что задача выполнена
        assert result.get() == "SUCCESS"
        mock_process.assert_called_once()


@pytest.mark.parametrize("file_count", [1, 3, 5])
def test_process_commercial_offers_multiple_files(
        file_count,
        test_user
):
    """Тест обработки нескольких коммерческих предложений за раз"""
    # Создаем несколько коммерческих предложений
    commercial_offers = []
    temp_files = []

    for i in range(file_count):
        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(f"test content {i}".encode())
            f_path = f.name
            temp_files.append(f_path)

        # Создаем коммерческое предложение
        commercial_offer = CommercialOffers.objects.create(
            user=test_user,
            origin_filename=f"test_file_{i}.pdf",
            source=SimpleUploadedFile(f"test_{i}.pdf", f"test content {i}".encode())
        )
        commercial_offers.append(commercial_offer)

    # Мокаем Celery task
    with patch("agregator.processing.commercial_offers_processing.process_documents") as mock_process:
        mock_process.return_value = "SUCCESS"

        # Выполняем задачу
        result = process_commercial_offers.delay(
            [co.id for co in commercial_offers],
            test_user.id
        )

        # Проверяем, что задача выполнена
        assert result.get() == "SUCCESS"
        mock_process.assert_called_once_with(
            result, [co.id for co in commercial_offers], test_user.id,
            'commercial_offers', CommercialOffers,
            load_raw_commercial_offers, extract_coordinates
        )

    # Удаляем временные файлы
    for f_path in temp_files:
        os.unlink(f_path)


def test_process_commercial_offers_invalid_user(
        test_commercial_offer,
        test_user_2
):
    """Тест попытки обработки чужих коммерческих предложений"""
    # Устанавливаем файл в коммерческое предложение
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"test content")
        f_path = f.name

    test_commercial_offer.source = SimpleUploadedFile("test.pdf", b"test content")
    test_commercial_offer.save()

    # Мокаем Celery task
    with patch("agregator.processing.commercial_offers_processing.process_documents") as mock_process:
        # Пытаемся обработать чужое предложение
        result = process_commercial_offers.delay(
            [test_commercial_offer.id],
            test_user_2.id
        )

        # Проверяем, что задача не выполняется
        with pytest.raises(UserTasks.DoesNotExist):
            result.get(timeout=5)

        mock_process.assert_not_called()


# ======================
# ТЕСТЫ ОБРАБОТКИ ОШИБОК
# ======================

def test_error_handler_commercial_offers_deletion(
        test_commercial_offer,
        test_user
):
    """Тест удаления незавершенных коммерческих предложений при ошибке"""
    # Создаем незавершенное коммерческое предложение
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"test content")
        f_path = f.name

    test_commercial_offer.source = SimpleUploadedFile("test.pdf", b"test content")
    test_commercial_offer.save()

    # Подготовка прогресса с незавершенным статусом
    task_id = "failed_task_123"
    progress_json = {
        "file_groups": {str(test_commercial_offer.id): {"processed": False}},
        "time_ended": None
    }
    redis_client.set(task_id, json.dumps(progress_json))

    # Создаем TaskResult для задачи
    TaskResult.objects.create(
        task_id=task_id,
        status=states.FAILURE,
        result=json.dumps({"error": "Test error"})
    )

    # Вызываем обработчик ошибок
    with pytest.raises(Exception) as exc_info:
        error_handler_commercial_offers(
            AsyncResult(task_id),
            Exception("Test error"),
            "Test error description"
        )

    # Проверяем, что коммерческое предложение удалено
    with pytest.raises(CommercialOffers.DoesNotExist):
        CommercialOffers.objects.get(id=test_commercial_offer.id)

    # Проверяем, что прогресс обновлен
    assert "time_ended" in json.loads(exc_info.value.args[0]["progress_json"])
    assert exc_info.value.args[0]["error_text"] == "Test error"


@pytest.mark.parametrize("progress_status", ["PENDING", "STARTED", "RETRY"])
def test_error_handler_commercial_offers_non_final_statuses(
        progress_status,
        test_commercial_offer,
        test_user
):
    """Тест обработки ошибок для разных статусов прогресса"""
    # Подготовка прогресса с разными статусами
    task_id = "failed_task_123"
    progress_json = {
        "file_groups": {str(test_commercial_offer.id): {"processed": False}},
        "status": progress_status
    }
    redis_client.set(task_id, json.dumps(progress_json))

    # Создаем TaskResult для задачи
    TaskResult.objects.create(
        task_id=task_id,
        status=progress_status,
        result=json.dumps({"status": progress_status})
    )

    # Вызываем обработчик ошибок
    with pytest.raises(Exception):
        error_handler_commercial_offers(
            AsyncResult(task_id),
            Exception("Test error"),
            "Test error description"
        )

    # Проверяем, что коммерческое предложение удалено
    with pytest.raises(CommercialOffers.DoesNotExist):
        CommercialOffers.objects.get(id=test_commercial_offer.id)


# ======================
# ТЕСТЫ БЕЗОПАСНОСТИ
# ======================

def test_process_commercial_offers_no_file_access(
        test_commercial_offer,
        test_user,
        test_user_2
):
    """Тест безопасности: проверка доступа к файлам"""
    # Создаем коммерческое предложение для другого пользователя
    other_offer = CommercialOffers.objects.create(
        user=test_user_2,
        origin_filename="other_offer.pdf"
    )

    # Пытаемся обработать чужой файл
    with pytest.raises(CommercialOffers.DoesNotExist):
        with patch("agregator.processing.commercial_offers_processing.process_documents") as mock_process:
            process_commercial_offers.delay(
                [other_offer.id],
                test_user.id
            ).get(timeout=5)

            mock_process.assert_not_called()


def test_extract_coordinates_path_traversal_attempt(
        test_commercial_offer,
        test_user
):
    """Тест на попытку path traversal в пути к файлу"""
    # Подготовка прогресса
    task_id = "test_task_123"
    progress_json = {
        "file_groups": {str(test_commercial_offer.id): {"origin_filename": "test_file.pdf"}},
        "expected_time": "00:00:00"
    }
    redis_client.set(task_id, json.dumps(progress_json))

    # Создаем объект progress_recorder
    class MockProgressRecorder:
        def set_progress(self, current, total, progress):
            pass

    # Пытаемся выполнить path traversal
    malicious_path = "../../../../etc/passwd"

    # Проверяем, что возникает ошибка из-за неправильного пути
    with pytest.raises(Exception):
        extract_coordinates(
            malicious_path,
            MockProgressRecorder(),
            {"1": 1},
            [0],
            test_commercial_offer.id,
            progress_json,
            task_id,
            datetime.now()
        )

    # Проверяем, что коммерческое предложение не изменено
    commercial_offer = CommercialOffers.objects.get(id=test_commercial_offer.id)
    assert commercial_offer.coordinates == {}


# ======================
# ГРАНИЧНЫЕ СЛУЧАИ
# ======================

@pytest.mark.parametrize("file_size", [0, 1, 1024 * 1024, 10 * 1024 * 1024])
def test_extract_coordinates_edge_file_sizes(
        file_size,
        test_commercial_offer,
        test_user
):
    """Тест обработки файлов разных размеров (граничные случаи)"""
    # Создаем временный файл указанного размера
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        if file_size > 0:
            f.write(b"0" * file_size)
        f_path = f.name

    # Подготовка прогресса
    task_id = "test_task_123"
    progress_json = {
        "file_groups": {str(test_commercial_offer.id): {"origin_filename": "test_file.pdf"}},
        "expected_time": "00:00:00"
    }
    redis_client.set(task_id, json.dumps(progress_json))

    # Создаем объект progress_recorder
    class MockProgressRecorder:
        def set_progress(self, current, total, progress):
            pass

    # Мокаем функции извлечения
    with patch("agregator.processing.commercial_offers_processing.extract_tables_from_pdf") as mock_extract_tables:
        with patch(
                "agregator.processing.commercial_offers_processing.analyze_coordinates_in_tables_from_pdf") as mock_analyze:
            if file_size > 0:
                mock_extract_tables.return_value = [{"table": "data"}]
                mock_analyze.return_value = ([{"lat": 55.75, "lon": 37.62}], ["WGS84"], [])

            try:
                extract_coordinates(
                    f_path,
                    MockProgressRecorder(),
                    {"1": 1},
                    [0],
                    test_commercial_offer.id,
                    progress_json,
                    task_id,
                    datetime.now()
                )

                # Проверяем результат только для непустых файлов
                if file_size > 0:
                    commercial_offer = CommercialOffers.objects.get(id=test_commercial_offer.id)
                    assert commercial_offer.coordinates is not None
            except Exception as e:
                # Пустые файлы могут вызывать ошибки - это нормально
                if file_size > 0:
                    raise e

    # Удаляем временный файл
    os.unlink(f_path)


def test_extract_coordinates_empty_tables(
        test_commercial_offer,
        test_user
):
    """Тест обработки файлов без данных (пустые таблицы)"""
    # Создаем временный PDF-файл
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"PDF content with no tables")
        f_path = f.name

    # Подготовка прогресса
    task_id = "test_task_123"
    progress_json = {
        "file_groups": {str(test_commercial_offer.id): {"origin_filename": "test_file.pdf"}},
        "expected_time": "00:00:00"
    }
    redis_client.set(task_id, json.dumps(progress_json))

    # Создаем объект progress_recorder
    class MockProgressRecorder:
        def set_progress(self, current, total, progress):
            pass

    # Мокаем функции извлечения
    with patch("agregator.processing.commercial_offers_processing.extract_tables_from_pdf") as mock_extract_tables:
        mock_extract_tables.return_value = []

        extract_coordinates(
            f_path,
            MockProgressRecorder(),
            {"1": 1},
            [0],
            test_commercial_offer.id,
            progress_json,
            task_id,
            datetime.now()
        )

    # Проверяем, что координаты пустые
    commercial_offer = CommercialOffers.objects.get(id=test_commercial_offer.id)
    assert commercial_offer.coordinates == {}

    # Удаляем временный файл
    os.unlink(f_path)


# ======================
# ИНТЕГРАЦИОННЫЕ ТЕСТЫ
# ======================

@pytest.mark.django_db(transaction=True)
def test_commercial_offers_processing_integration(
        test_commercial_offer,
        test_user
):
    """Интеграционный тест обработки коммерческого предложения"""
    # Создаем временный файл с координатами
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"PDF with coordinates")
        f_path = f.name

    # Устанавливаем файл в коммерческое предложение
    test_commercial_offer.source = SimpleUploadedFile("test.pdf", b"PDF with coordinates")
    test_commercial_offer.save()

    # Мокаем функцию извлечения координат
    with patch("agregator.processing.commercial_offers_processing.extract_coordinates") as mock_extract:
        mock_extract.return_value = None  # Имитируем успешную обработку

        # Запускаем задачу
        task = process_commercial_offers.delay(
            [test_commercial_offer.id],
            test_user.id
        )

        # Ждем завершения задачи
        result = task.get(timeout=10)

        # Проверяем результат
        assert result == "SUCCESS"
        mock_extract.assert_called_once()

        # Проверяем обновление статуса
        commercial_offer = CommercialOffers.objects.get(id=test_commercial_offer.id)
        assert commercial_offer.is_processing is False


@pytest.mark.django_db(transaction=True)
def test_commercial_offers_processing_with_real_file(
        test_commercial_offer,
        test_user
):
    """Интеграционный тест с использованием реального файла"""
    # Создаем тестовый PDF файл с координатами
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n"
        b"<< /Type /Catalog /Pages 2 0 R >>\n"
        b"endobj\n"
        b"2 0 obj\n"
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
        b"endobj\n"
        b"3 0 obj\n"
        b"<< /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 612 792] >>\n"
        b"endobj\n"
        b"xref\n"
        b"0 4\n"
        b"0000000000 65535 f \n"
        b"0000000010 00000 n \n"
        b"0000000053 00000 n \n"
        b"0000000142 00000 n \n"
        b"trailer\n"
        b"<< /Size 4 /Root 1 0 R >>\n"
        b"startxref\n"
        b"201\n"
        b"%%EOF"
    )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_content)
        f_path = f.name

    # Устанавливаем файл в коммерческое предложение
    test_commercial_offer.source = SimpleUploadedFile("test.pdf", pdf_content)
    test_commercial_offer.save()

    # Мокаем функции извлечения таблиц
    with patch("agregator.processing.commercial_offers_processing.extract_tables_from_pdf") as mock_extract_tables:
        mock_extract_tables.return_value = [
            [
                ["Координата", "Широта", "Долгота"],
                ["WGS84", "55.75", "37.62"]
            ]
        ]

        # Запускаем задачу
        task = process_commercial_offers.delay(
            [test_commercial_offer.id],
            test_user.id
        )

        # Ждем завершения задачи
        result = task.get(timeout=10)

        # Проверяем результат
        assert result == "SUCCESS"

        # Проверяем обновление координат
        commercial_offer = CommercialOffers.objects.get(id=test_commercial_offer.id)
        assert commercial_offer.coordinates == {
            "coordinates": [
                {"system": "WGS84", "lat": 55.75, "lon": 37.62}
            ]
        }

    # Удаляем временный файл
    os.unlink(f_path)
