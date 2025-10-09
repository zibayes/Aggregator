import pytest
import re
import os
import math
import fitz
import pdfplumber
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from celery.exceptions import TaskError
from celery.result import AsyncResult
from django_celery_results.models import TaskResult
from agregator.models import Act, UserTasks
from agregator.processing.acts_processing import (
    get_gike_object_size,
    extract_text_and_images,
    error_handler_acts,
    SQUARE_RESERVE
)
from agregator.redis_config import redis_client
from io import BytesIO
from copy import deepcopy


# Помощник для создания тестовых PDF
def create_test_pdf(content, pages=1):
    """Создает временный PDF файл с заданным текстом"""
    buffer = BytesIO()
    doc = fitz.open()
    for _ in range(pages):
        page = doc.new_page()
        page.insert_text(fitz.Point(100, 100), content)
    doc.save(buffer)
    buffer.seek(0)
    return SimpleUploadedFile("test.pdf", buffer.read(), content_type="application/pdf")


# Помощник для создания мок-объектов
def create_mock_document(content, page_count=1):
    """Создает мок-документ для тестирования"""
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = content

    # Настройка мока для нескольких страниц
    mock_doc.__len__.return_value = page_count
    mock_doc.__getitem__.side_effect = lambda idx: mock_page if idx < page_count else None
    mock_doc.open.return_value = mock_doc
    mock_doc.close.return_value = None

    return mock_doc


# Помощник для настройки прогресса
def setup_progress(task_id, act_id, source_index=0, pages_count=None):
    """Настраивает прогресс-данные в Redis"""
    if pages_count is None:
        pages_count = {str(act_id): 10}

    progress_json = {
        "task_id": task_id,
        "expected_time": "00:00:00",
        "file_groups": {
            str(act_id): [
                {
                    "id": 1,
                    "source_id": 1,
                    "type": "all",
                    "pages": {
                        "total": pages_count[str(act_id)],
                        "processed": 0
                    },
                    "processed": "False",
                    "origin_filename": "test.pdf",
                    "source": "Пользовательский файл"
                }
            ]
        },
        "total": 1,
        "processed": 0,
        "status": "PROGRESS",
        "time_started": timezone.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    redis_client.set(task_id, json.dumps(progress_json))
    return progress_json


# ======================
# Тесты для get_gike_object_size
# ======================

@pytest.mark.parametrize("text_to_write, initial_table_info, expected_result", [
    # Сценарий 1: Обнаружение площади в формате "Общ. площадь 123,45 га"
    (
            "Общ. площадь 123,45 га",
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 123,45 га"}
    ),

    # Сценарий 2: Обнаружение площади в формате "площадь 123,45 кв. м"
    (
            "площадь 123,45 кв. м",
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 123,45 кв. м"}
    ),

    # Сценарий 3: Обнаружение протяженности
    (
            "протяж. 567,89 км",
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "протяж. 567,89 км"}
    ),

    # Сценарий 4: Обнаружение S лин. ЗУ
    (
            "площадь лин. 100,50 км",
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 123,45 га"},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 123,45 га (S лин. ЗУ = 100,50 км)"}
    ),

    # Сценарий 5: Обнаружение площади, когда уже есть данные
    (
            "Общ. площадь 456,78 га",
            {"Площадь, протяжённость и/или др. параменты объекта": "протяж. 567,89 км"},
            {"Площадь, протяжённость и/или др. параменты объекта": "протяж. 567,89 км"}
    ),

    # Сценарий 6: Обнаружение нескольких значений площади
    (
            "Общ. площадь 123,45 га\nОбщ. площадь 456,78 га",
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 456,78 га"}
    ),

    # Сценарий 7: Обнаружение площади в формате без запятой
    (
            "Общ. площадь 123 га",
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 123 га"}
    ),

    # Сценарий 8: Обнаружение площади в формате с пробелами
    (
            "Общ.  площадь   123,45   га",
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 123,45   га"}
    ),

    # Сценарий 9: Обнаружение площади с разными единицами
    (
            "Общ. площадь 123,45 га\nОбщ. площадь 567,89 кв. м",
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 567,89 кв. м"}
    ),

    # Сценарий 10: Отсутствие данных
    (
            "Нет данных о площади",
            {},
            {}
    ),

    # Сценарий 11: Площадь с отрицательным значением
    (
            "Общ. площадь -123,45 га",
            {},
            {}
    ),

    # Сценарий 12: Площадь в виде целого числа
    (
            "Общ. площадь 123 га",
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 123 га"}
    ),

    # Сценарий 13: Несколько типов данных
    (
            "Общ. площадь 123,45 га\nпротяж. 567,89 км",
            {},
            {
                "Площадь, протяжённость и/или др. параменты объекта":
                    "Общ. S = 123,45 га\nпротяж. 567,89 км"
            }
    ),

    # Сценарий 14: Несколько типов данных с S лин. ЗУ
    (
            "Общ. площадь 123,45 га\nпротяж. 567,89 км\nплощадь лин. 100,50 км",
            {},
            {
                "Площадь, протяжённость и/или др. параменты объекта":
                    "Общ. S = 123,45 га\nпротяж. 567,89 км (S лин. ЗУ = 100,50 км)"
            }
    ),

    # Сценарий 15: Граничный случай - очень маленькое число
    (
            "Общ. площадь 0,01 га",
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 0,01 га"}
    ),

    # Сценарий 16: Граничный случай - очень большое число
    (
            "Общ. площадь 999999,99 га",
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 999999,99 га"}
    ),

    # Сценарий 17: Площадь с разными разделителями
    (
            "Общ. площадь 1 234,56 га",
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 1 234,56 га"}
    ),

    # Сценарий 18: Площадь в кавычках
    (
            'Общ. площадь "123,45" га',
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = \"123,45\" га"}
    ),

    # Сценарий 19: Площадь с единицами в разных регистрах
    (
            "Общ. площадь 123,45 ГА",
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 123,45 ГА"}
    ),

    # Сценарий 20: Площадь с нестандартными единицами
    (
            "Общ. площадь 123,45 кв. метра",
            {},
            {"Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 123,45 кв. метра"}
    )
])
def test_get_gike_object_size_parameterized(text_to_write, initial_table_info, expected_result):
    """Параметризованный тест для всех возможных сценариев обработки площади и длины"""
    table_info = deepcopy(initial_table_info)
    get_gike_object_size(text_to_write, table_info)

    # Проверяем результат
    if expected_result:
        assert table_info == expected_result
    else:
        # Если ожидаем пустой результат, проверяем, что table_info не изменился
        if initial_table_info:
            assert table_info == initial_table_info
        else:
            assert not table_info


def test_get_gike_object_size_squares_reserve():
    """Тест заполнения SQUARE_RESERVE при отсутствии 'га' или 'кв. м' в строке"""
    SQUARE_RESERVE.clear()

    # Строка без единиц измерения
    get_gike_object_size("Общ. площадь 123,45", {})

    assert len(SQUARE_RESERVE) == 1
    assert SQUARE_RESERVE[0] == "123,45"


def test_get_gike_object_size_with_existing_data():
    """Тест обработки когда данные уже есть в table_info"""
    table_info = {
        "Площадь, протяжённость и/или др. параменты объекта": "Общ. S = 123,45 га"
    }

    get_gike_object_size("Общ. площадь 456,78 га", table_info)

    # Данные не должны обновиться, так как уже есть "Общ. S"
    assert table_info["Площадь, протяжённость и/или др. параменты объекта"] == "Общ. S = 123,45 га"


def test_get_gike_object_size_with_empty_text():
    """Тест обработки пустого текста"""
    table_info = {}
    get_gike_object_size("", table_info)

    # Ничего не должно быть добавлено
    assert not table_info


def test_get_gike_object_size_with_invalid_data():
    """Тест обработки некорректных данных"""
    table_info = {}
    get_gike_object_size("Общ. площадь abc га", table_info)

    # Ничего не должно быть добавлено
    assert not table_info


# ======================
# Тесты для extract_text_and_images
# ======================

@pytest.fixture
def mock_pdf_document():
    """Создает мок-документ PDF для тестирования"""
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = "Test content"
    mock_page.get_pixmap.return_value = MagicMock()
    mock_page.get_pixmap().tobytes.return_value = b"fake image data"

    # Настройка мока для нескольких страниц
    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    return mock_doc


@pytest.fixture
def mock_pdfplumber():
    """Создает мок для pdfplumber"""
    with patch('agregator.processing.acts_processing.pdfplumber') as mock:
        mock.open.return_value.__enter__.return_value.pages = [
            MagicMock(extract_tables=lambda: [])
        ]
        yield mock


def create_test_act(db, test_user):
    """Создает тестовый акт"""
    return Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": "test.pdf"}]
    )


def create_test_task():
    """Создает тестовую Celery задачу"""
    task = MagicMock()
    task.id = "test_task_id"
    return task


def create_test_progress_recorder():
    """Создает тестовый прогресс-рекордер"""
    recorder = MagicMock()
    recorder.set_progress.return_value = None
    return recorder


@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
@patch('agregator.processing.acts_processing.load_raw_reports')
@patch('agregator.processing.acts_processing.calculate_file_hash')
def test_extract_text_and_images_basic_processing(
        mock_calculate_file_hash,
        mock_load_raw_reports,
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест базовой обработки текста и изображений"""
    # Настройка мока fitz
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = "Акт № 123/2023\nДата начала: 01.01.2023\nДата окончания: 02.01.2023"
    mock_page.get_pixmap.return_value = MagicMock()
    mock_page.get_pixmap().tobytes.return_value = b"fake image data"

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка мока для хэшей
    mock_calculate_file_hash.return_value = "test_hash"

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем тестовый акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 1)

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 1},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id=task_id,
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем, что акт был обновлен
    act.refresh_from_db()
    assert act.name_number == "Акт № 123/2023 б/н"
    assert act.finish_date == "02.01.2023"
    assert act.year == "2023"
    assert act.is_processing is False


@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_extract_text_and_images_duplicate_file(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест обработки дублирующегося файла"""
    # Настройка мока fitz
    mock_doc = MagicMock(spec=fitz.Document)
    mock_doc.close.return_value = None
    mock_fitz.open.return_value = mock_doc

    # Создаем тестовые PDF файлы
    folder1 = tmpdir.mkdir("folder1")
    folder2 = tmpdir.mkdir("folder2")

    file_path1 = str(folder1.join("test1.pdf"))
    file_path2 = str(folder2.join("test2.pdf"))

    with open(file_path1, "wb") as f:
        f.write(b"Test PDF content 1")

    with open(file_path2, "wb") as f:
        f.write(b"Test PDF content 1")  # То же содержимое

    # Создаем два акта с одинаковым содержимым
    act1 = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path1}]
    )

    act2 = Act.objects.create(
        id=2,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path2}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 2)

    # Пытаемся обработать второй файл
    with pytest.raises(FileExistsError) as excinfo:
        extract_text_and_images(
            file=file_path2,
            progress_recorder=create_test_progress_recorder(),
            pages_count={"2": 1},
            total_processed=[0],
            progress_json=progress_json,
            act_id=2,
            source_index=0,
            task_id=task_id,
            user_id=test_user.id,
            is_public=False,
            select_text=True,
            select_image=True,
            select_coord=True
        )

    assert "Такой файл уже загружен в систему" in str(excinfo.value)

    # Проверяем, что первый акт не был изменен
    act1.refresh_from_db()
    assert act1.is_processing is True


@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_extract_text_and_images_with_date_variations(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест обработки различных форматов дат"""
    # Создаем тестовый PDF с разными форматами дат
    test_content = """
    Акт № 456/2023
    период с «1» января 2023 г. по «15» февраля 2023 г.
    Дата окончания: 20.02.2023
    """

    # Настройка мока fitz
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = test_content
    mock_page.get_pixmap.return_value = MagicMock()
    mock_page.get_pixmap().tobytes.return_value = b"fake image data"

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем тестовый акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 1)

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 1},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id=task_id,
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем результат
    act.refresh_from_db()
    assert act.finish_date == "15.02.2023"  # Дата окончания из периода
    assert act.year == "2023"


@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_extract_text_and_images_with_object_types(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест обработки различных типов объектов"""
    # Содержимое с разными типами объектов
    test_content = """
    Акт № 789/2023
    Объект экспертизы: земли сельскохозяйственного назначения
    Дата окончания: 20.03.2023
    """

    # Настройка мока fitz
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = test_content
    mock_page.get_pixmap.return_value = MagicMock()
    mock_page.get_pixmap().tobytes.return_value = b"fake image data"

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем тестовый акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 1)

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 1},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id=task_id,
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем результат
    act.refresh_from_db()
    assert act.type == "ЗУ"  # Определен тип по ключевому слову "земли"


@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_extract_text_and_images_with_multiple_experts(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест обработки нескольких экспертов"""
    # Содержимое с несколькими экспертами
    test_content = """
    Акт № 101/2023
    Эксперты, состоящие в трудовых отношениях с заказчиком:
    Иванов И.И. - образование
    Петров П.П. - образование
    Дата окончания: 25.04.2023
    """

    # Настройка мока fitz
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = test_content
    mock_page.get_pixmap.return_value = MagicMock()
    mock_page.get_pixmap().tobytes.return_value = b"fake image data"

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем тестовый акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 1)

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 1},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id=task_id,
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем результат
    act.refresh_from_db()
    assert act.expert == "Иванов И.И., Петров П.П."


@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_extract_text_and_images_with_open_list(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест обработки открытого листа"""
    # Содержимое с информацией об открытом листе
    test_content = """
    Акт № 102/2023
    Открытый лист № 456-789 от 01.05.2023
    Дата окончания: 30.05.2023
    """

    # Настройка мока fitz
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = test_content
    mock_page.get_pixmap.return_value = MagicMock()
    mock_page.get_pixmap().tobytes.return_value = b"fake image data"

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем тестовый акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 1)

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 1},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id=task_id,
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем результат
    act.refresh_from_db()
    assert act.open_list == " от 01.05.2023 № 456-789"


@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_extract_text_and_images_with_voan(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест обработки информации об объектах археологического наследия"""
    # Содержимое с информацией об ВОАН
    test_content = """
    Акт № 103/2023
    выявлен объект археологического наследия "Тестовый объект"
    Вывод экспертизы: отрицательное заключение
    Дата окончания: 10.06.2023
    """

    # Настройка мока fitz
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = test_content
    mock_page.get_pixmap.return_value = MagicMock()
    mock_page.get_pixmap().tobytes.return_value = b"fake image data"

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем тестовый акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 1)

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 1},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id=task_id,
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем результат
    act.refresh_from_db()
    assert act.conclusion == "отрицательное заключение ВОАН \"Тестовый объект\""


# ======================
# Тесты ошибок и безопасности
# ======================

@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_extract_text_and_images_with_invalid_date(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест обработки невалидных дат"""
    # Содержимое с невалидной датой
    test_content = """
    Акт № 104/2023
    Дата окончания: 99.99.9999
    """

    # Настройка мока fitz
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = test_content
    mock_page.get_pixmap.return_value = MagicMock()
    mock_page.get_pixmap().tobytes.return_value = b"fake image data"

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем тестовый акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 1)

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 1},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id=task_id,
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем результат - должно быть пустое значение
    act.refresh_from_db()
    assert act.finish_date is None or act.finish_date == ""


@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_extract_text_and_images_with_xss_attack(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест защиты от XSS-атак в извлеченных данных"""
    # Содержимое с потенциальной XSS-атакой
    test_content = """
    Акт № <script>alert('XSS')</script>
    Объект экспертизы: <img src="x" onerror="alert('XSS')">
    """

    # Настройка мока fitz
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = test_content
    mock_page.get_pixmap.return_value = MagicMock()
    mock_page.get_pixmap().tobytes.return_value = b"fake image data"

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем тестовый акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 1)

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 1},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id=task_id,
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем результат - скрипты должны быть удалены
    act.refresh_from_db()
    assert "<script>" not in act.name_number
    assert "<img" not in act.object


@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_extract_text_and_images_with_sql_injection(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест защиты от SQL-инъекций в извлеченных данных"""
    # Содержимое с потенциальной SQL-инъекцией
    test_content = """
    Акт № 105/2023' OR 1=1 --
    Заказчик экспертизы:'; DROP TABLE users; --
    """

    # Настройка мока fitz
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = test_content
    mock_page.get_pixmap.return_value = MagicMock()
    mock_page.get_pixmap().tobytes.return_value = b"fake image data"

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем тестовый акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 1)

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 1},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id=task_id,
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем результат - инъекции должны быть удалены
    act.refresh_from_db()
    assert "OR 1=1" not in act.name_number
    assert "DROP TABLE" not in act.customer


@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_extract_text_and_images_with_long_text(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест обработки очень длинных текстов"""
    # Генерируем очень длинный текст
    long_text = "A" * 100000

    test_content = f"""
    Акт № 106/2023
    Объект экспертизы: {long_text}
    """

    # Настройка мока fitz
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = test_content
    mock_page.get_pixmap.return_value = MagicMock()
    mock_page.get_pixmap().tobytes.return_value = b"fake image data"

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем тестовый акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 1)

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 1},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id=task_id,
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем результат
    act.refresh_from_db()
    assert len(act.object) <= 255  # Проверка на ограничение длины


@pytest.mark.django_db
def test_error_handler_acts_with_exception(
        test_user,
        test_act
):
    """Тест обработчика ошибок Celery"""
    # Создаем задачу и результат
    task = MagicMock()
    task.id = "test_task_id"
    task.name = "process_acts"

    # Создаем мок-прогресс
    progress_json = {
        "file_groups": {
            str(test_act.id): [
                {
                    "id": 1,
                    "source_id": 1,
                    "type": "all",
                    "pages": {
                        "total": 10,
                        "processed": 5
                    },
                    "processed": "False",
                    "origin_filename": "test.pdf",
                    "source": "Пользовательский файл"
                }
            ]
        }
    }

    # Сохраняем прогресс в Redis
    redis_client.set(task.id, json.dumps(progress_json))

    # Создаем исключение
    exception = Exception("Test error")
    exception_desc = "Test error description"

    # Вызываем обработчик ошибок
    with pytest.raises(Exception) as excinfo:
        error_handler_acts(task, exception, exception_desc)

    # Проверяем, что акт был удален
    with pytest.raises(Act.DoesNotExist):
        test_act.refresh_from_db()

    # Проверяем, что исключение было проброшено
    assert "Test error" in str(excinfo.value)
    assert "progress_json" in str(excinfo.value)


@pytest.mark.django_db
def test_error_handler_acts_with_no_exception(
        test_user,
        test_act
):
    """Тест обработчика ошибок Celery без исключения"""
    # Создаем задачу и результат
    task = MagicMock()
    task.id = "test_task_id"
    task.name = "process_acts"

    # Создаем мок-прогресс
    progress_json = {
        "file_groups": {
            str(test_act.id): [
                {
                    "id": 1,
                    "source_id": 1,
                    "type": "all",
                    "pages": {
                        "total": 10,
                        "processed": 10
                    },
                    "processed": "True",
                    "origin_filename": "test.pdf",
                    "source": "Пользовательский файл"
                }
            ]
        }
    }

    # Сохраняем прогресс в Redis
    redis_client.set(task.id, json.dumps(progress_json))

    # Создаем исключение
    exception = Exception("Test error")
    exception_desc = "Test error description"

    # Вызываем обработчик ошибок
    with pytest.raises(Exception) as excinfo:
        error_handler_acts(task, exception, exception_desc)

    # Проверяем, что акт НЕ был удален
    test_act.refresh_from_db()
    assert test_act.id == 1

    # Проверяем, что исключение было проброшено
    assert "Test error" in str(excinfo.value)
    assert "progress_json" in str(excinfo.value)


# ======================
# Интеграционные тесты
# ======================

@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_full_processing_workflow(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Интеграционный тест полного рабочего процесса обработки акта"""
    # Содержимое с полной информацией
    test_content = """
    Акт № 107/2023
    период с «1» января 2023 г. по «15» февраля 2023 г.
    Место проведения экспертизы: Московская область
    Заказчик экспертизы: Министерство культуры
    Эксперты, состоящие в трудовых отношениях с заказчиком:
    Иванов И.И. - образование
    Петров П.П. - образование
    Объект экспертизы: земли сельскохозяйственного назначения
    Общ. площадь 123,45 га
    выявлен объект археологического наследия "Тестовый объект"
    Вывод экспертизы: положительное заключение
    Открытый лист № 456-789 от 01.05.2023
    """

    # Настройка мока fitz
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = test_content
    mock_page.get_pixmap.return_value = MagicMock()
    mock_page.get_pixmap().tobytes.return_value = b"fake image data"

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем задачу
    task = UserTasks.objects.create(
        user=test_user,
        task_id="integration_test_task",
        files_type="act",
        upload_source={"source": "Пользовательский файл"}
    )

    # Создаем акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    progress_json = setup_progress("integration_test_task", 1)

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 1},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id="integration_test_task",
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем результат
    act.refresh_from_db()
    assert act.name_number == "Акт № 107/2023 б/н"
    assert act.finish_date == "15.02.2023"
    assert act.year == "2023"
    assert act.place == "Московская область"
    assert act.customer == "Министерство культуры"
    assert act.expert == "Иванов И.И., Петров П.П."
    assert act.type == "ЗУ"
    assert act.area == "Общ. S = 123,45 га"
    assert act.conclusion == "положительное заключение ВОАН \"Тестовый объект\""
    assert act.open_list == " от 01.05.2023 № 456-789"
    assert act.is_processing is False


@pytest.mark.django_db
def test_process_acts_task(
        test_user,
        test_act
):
    """Интеграционный тест Celery задачи обработки актов"""
    from agregator.processing.acts_processing import process_acts

    # Создаем задачу
    task = process_acts.delay([test_act.id], test_user.id, True, True, True)

    # Ждем завершения задачи
    result = task.get(timeout=10)

    # Проверяем результат
    assert result is not None
    assert task.status == "SUCCESS"

    # Проверяем, что акт был обработан
    test_act.refresh_from_db()
    assert test_act.is_processing is False


# ======================
# Тесты на граничные случаи
# ======================

@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_extract_text_and_images_empty_document(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест обработки пустого документа"""
    # Настройка мока fitz для пустого документа
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = ""

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем тестовый акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 1)

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 1},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id=task_id,
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем результат
    act.refresh_from_db()
    assert act.name_number == ""
    assert act.finish_date == ""
    assert act.year == ""
    assert act.is_processing is False


@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_extract_text_and_images_multi_page_document(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест обработки многостраничного документа"""
    # Содержимое для первой страницы
    content1 = "Акт № 108/2023\nДата начала: 01.01.2023"

    # Содержимое для второй страницы
    content2 = "Дата окончания: 02.01.2023\nМесто проведения: Москва"

    # Настройка мока fitz для двух страниц
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page1 = MagicMock(spec=fitz.Page)
    mock_page1.get_text.return_value = content1

    mock_page2 = MagicMock(spec=fitz.Page)
    mock_page2.get_text.return_value = content2

    mock_doc.__len__.return_value = 2
    mock_doc.__getitem__.side_effect = lambda idx: mock_page1 if idx == 0 else mock_page2
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: []),
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем тестовый акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 1, pages_count={"1": 2})

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 2},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id=task_id,
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем результат
    act.refresh_from_db()
    assert act.name_number == "Акт № 108/2023 б/н"
    assert act.finish_date == "02.01.2023"
    assert act.year == "2023"
    assert act.place == "Москва"
    assert act.is_processing is False


@pytest.mark.django_db
@patch('agregator.processing.acts_processing.fitz')
@patch('agregator.processing.acts_processing.pdfplumber')
def test_extract_text_and_images_with_broken_structure(
        mock_pdfplumber,
        mock_fitz,
        test_user,
        tmpdir
):
    """Тест обработки документа с нарушенной структурой"""
    # Содержимое с нарушенной структурой
    test_content = """
    Акт № 109/2023
    период с «1» января 2023 г. по «15» февраля 2023 г.
    Место проведения экспертизы:
    Московская область
    Заказчик экспертизы: Министерство культуры
    Сведения об эксперте: Иванов И.И.
    Отношение к заказчику: Независимый
    """

    # Настройка мока fitz
    mock_doc = MagicMock(spec=fitz.Document)
    mock_page = MagicMock(spec=fitz.Page)
    mock_page.get_text.return_value = test_content
    mock_page.get_pixmap.return_value = MagicMock()
    mock_page.get_pixmap().tobytes.return_value = b"fake image data"

    mock_doc.__len__.return_value = 1
    mock_doc.__getitem__.side_effect = lambda idx: mock_page
    mock_doc.close.return_value = None

    mock_fitz.open.return_value = mock_doc

    # Настройка мока pdfplumber
    mock_pdfplumber.open.return_value.__enter__.return_value.pages = [
        MagicMock(extract_tables=lambda: [])
    ]

    # Настройка временной директории
    folder_path = tmpdir.mkdir("test_folder")
    file_path = str(folder_path.join("test.pdf"))

    # Создаем тестовый PDF файл
    with open(file_path, "wb") as f:
        f.write(b"Test PDF content")

    # Создаем тестовый акт
    act = Act.objects.create(
        id=1,
        user=test_user,
        is_processing=True,
        source=[{"path": file_path}]
    )

    # Настройка прогресса
    task_id = "test_task_id"
    progress_json = setup_progress(task_id, 1)

    # Выполняем извлечение
    extract_text_and_images(
        file=file_path,
        progress_recorder=create_test_progress_recorder(),
        pages_count={"1": 1},
        total_processed=[0],
        progress_json=progress_json,
        act_id=1,
        source_index=0,
        task_id=task_id,
        user_id=test_user.id,
        is_public=False,
        select_text=True,
        select_image=True,
        select_coord=True
    )

    # Проверяем результат
    act.refresh_from_db()
    assert act.name_number == "Акт № 109/2023 б/н"
    assert act.finish_date == "15.02.2023"
    assert act.year == "2023"
    assert act.place == "Московская область"
    assert act.customer == "Министерство культуры"
    assert act.expert == "Иванов И.И."
    assert act.relationship == "Независимый"
    assert act.is_processing is False
