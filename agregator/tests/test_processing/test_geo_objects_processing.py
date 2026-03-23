import pytest
import json
import zipfile
import os
import tempfile
from unittest.mock import patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile
from celery.exceptions import Retry

from agregator.models import GeoObject
from agregator.processing.geo_objects_processing import (
    extract_kml_from_kmz,
    parse_kml,
    process_geo_objects,
    extract_coordinates,
    error_handler_geo_objects,
)
from agregator.processing.files_saving import load_raw_geo_objects


# ----- Тесты для extract_kml_from_kmz -----
def test_extract_kml_from_kmz_valid():
    """Извлечение KML из корректного KMZ-архива"""
    with tempfile.TemporaryDirectory() as tmpdir:
        kmz_path = os.path.join(tmpdir, "test.kmz")
        kml_content = b'<kml><Placemark><name>Test</name><coordinates>10,20</coordinates></Placemark></kml>'
        with zipfile.ZipFile(kmz_path, 'w') as zf:
            zf.writestr("doc.kml", kml_content)

        result = extract_kml_from_kmz(kmz_path)
        assert result is not None
        assert result.endswith("doc.kml")
        assert os.path.exists(result)
        with open(result, 'rb') as f:
            assert f.read() == kml_content


def test_extract_kml_from_kmz_no_kml():
    """KMZ без KML-файла"""
    with tempfile.TemporaryDirectory() as tmpdir:
        kmz_path = os.path.join(tmpdir, "test.kmz")
        with zipfile.ZipFile(kmz_path, 'w') as zf:
            zf.writestr("other.txt", b"content")

        result = extract_kml_from_kmz(kmz_path)
        assert result is None


def test_extract_kml_from_kmz_not_zip():
    """Файл не является zip-архивом – должно быть исключение BadZipFile"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.kmz', delete=False) as f:
        f.write("not a zip")
        f.flush()
        path = f.name
    try:
        with pytest.raises(zipfile.BadZipFile):
            extract_kml_from_kmz(path)
    finally:
        os.unlink(path)


# ----- Тесты для parse_kml -----
def test_parse_kml_simple_placemarks():
    """Парсинг KML с Placemark без папок"""
    kml_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Placemark>
            <name>Point A</name>
            <Point>
                <coordinates>55.123,37.456</coordinates>
            </Point>
        </Placemark>
        <Placemark>
            <name>Point B</name>
            <Point>
                <coordinates>55.234,37.567</coordinates>
            </Point>
        </Placemark>
    </kml>'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as f:
        f.write(kml_content)
        f.flush()
        path = f.name
    try:
        result = parse_kml(path)
        assert "Центр объекта" in result
        assert result["Центр объекта"]["Point A"] == [55.123, 37.456]
        assert result["Центр объекта"]["Point B"] == [55.234, 37.567]
        assert result["Центр объекта"]["coordinate_system"] == 'wgs84'
    finally:
        os.unlink(path)


def test_parse_kml_with_namespace():
    """KML с пространством имён"""
    kml_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://earth.google.com/kml/2.2">
        <Placemark>
            <name>Point X</name>
            <Point>
                <coordinates>11.111,22.222</coordinates>
            </Point>
        </Placemark>
    </kml>'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as f:
        f.write(kml_content)
        f.flush()
        path = f.name
    try:
        result = parse_kml(path)
        assert result["Центр объекта"]["Point X"] == [11.111, 22.222]
    finally:
        os.unlink(path)


def test_parse_kml_empty():
    """Пустой KML"""
    kml_content = '''<?xml version="1.0" encoding="UTF-8"?><kml></kml>'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as f:
        f.write(kml_content)
        f.flush()
        path = f.name
    try:
        result = parse_kml(path)
        assert result == {"Центр объекта": {'coordinate_system': 'wgs84'}}
    finally:
        os.unlink(path)


# ----- Тесты для process_geo_objects (Celery task) -----
@patch('agregator.processing.geo_objects_processing.process_documents')
def test_process_geo_objects(mock_process_docs):
    """Задача process_geo_objects вызывает process_documents с правильными аргументами"""
    geo_objects_ids = [1, 2]
    user_id = 123

    mock_process_docs.return_value = {"status": "ok"}

    # Вызываем .run, чтобы имитировать выполнение задачи
    result = process_geo_objects.run(geo_objects_ids, user_id)

    mock_process_docs.assert_called_once_with(
        process_geo_objects, geo_objects_ids, user_id, 'geo_objects',
        model_class=GeoObject,
        load_function=load_raw_geo_objects,
        process_function=extract_coordinates
    )
    assert result == {"status": "ok"}


# ----- Тесты для extract_coordinates -----
@pytest.mark.django_db
@patch('agregator.processing.geo_objects_processing.redis_client')
@patch('agregator.processing.geo_objects_processing.calculate_file_hash')
def test_extract_coordinates_kml_success(mock_hash, mock_redis, test_user):
    """Успешная обработка KML файла"""
    # Создаём временный KML
    kml_content = '''<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Placemark>
            <name>Test Point</name>
            <Point><coordinates>55.123,37.456</coordinates></Point>
        </Placemark>
    </kml>'''
    with tempfile.NamedTemporaryFile(mode='w', suffix='.kml', delete=False) as f:
        f.write(kml_content)
        f.flush()
        file_path = f.name

    # Создаём объект GeoObject в БД
    geo_obj = GeoObject.objects.create(
        user=test_user,
        origin_filename="test.kml",
        source=file_path,
        is_processing=True
    )

    # Моки
    mock_hash.return_value = "hash123"
    mock_redis.set.return_value = None

    progress_recorder = MagicMock()
    pages_count = {"1": 1}
    total_processed = [0]
    progress_json = {
        "file_groups": {
            str(geo_obj.id): {
                "origin_filename": "test.kml"
            }
        }
    }
    task_id = "task123"
    time_on_start = MagicMock()

    try:
        extract_coordinates(
            file=file_path,
            progress_recorder=progress_recorder,
            pages_count=pages_count,
            total_processed=total_processed,
            geo_object_id=geo_obj.id,
            progress_json=progress_json,
            task_id=task_id,
            time_on_start=time_on_start
        )

        geo_obj.refresh_from_db()
        assert geo_obj.is_processing is False
        # Проверяем, что координаты сохранены в строке JSON
        coords_str = geo_obj.coordinates
        assert isinstance(coords_str, str)
        assert '"Центр объекта"' in coords_str
        assert '"Test Point"' in coords_str
        assert '[55.123, 37.456]' in coords_str  # или "55.123, 37.456"

        # Проверяем создание папки
        folder = file_path[:file_path.rfind(".")]
        assert os.path.exists(folder)
    finally:
        os.unlink(file_path)
        # Удаляем папку, если создалась
        folder = file_path[:file_path.rfind(".")]
        if os.path.exists(folder):
            os.rmdir(folder)


@pytest.mark.django_db
@patch('agregator.processing.geo_objects_processing.redis_client')
@patch('agregator.processing.geo_objects_processing.calculate_file_hash')
def test_extract_coordinates_kmz_success(mock_hash, mock_redis, test_user):
    with tempfile.TemporaryDirectory() as tmpdir:
        kmz_path = os.path.join(tmpdir, "test.kmz")
        kml_content = b'''<?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Placemark>
                <name>Point KMZ</name>
                <Point>
                    <coordinates>11.222,33.444</coordinates>
                </Point>
            </Placemark>
        </kml>'''
        with zipfile.ZipFile(kmz_path, 'w') as zf:
            zf.writestr("doc.kml", kml_content)

        geo_obj = GeoObject.objects.create(
            user=test_user,
            origin_filename="test.kmz",
            source=kmz_path,
            is_processing=True
        )

        mock_hash.return_value = "hash123"
        mock_redis.set.return_value = None

        progress_recorder = MagicMock()
        pages_count = {"1": 1}
        total_processed = [0]
        progress_json = {"file_groups": {str(geo_obj.id): {"origin_filename": "test.kmz"}}}
        task_id = "task123"
        time_on_start = MagicMock()

        extract_coordinates(
            file=kmz_path,
            progress_recorder=progress_recorder,
            pages_count=pages_count,
            total_processed=total_processed,
            geo_object_id=geo_obj.id,
            progress_json=progress_json,
            task_id=task_id,
            time_on_start=time_on_start
        )

        geo_obj.refresh_from_db()
        coords_str = geo_obj.coordinates
        assert isinstance(coords_str, str)
        assert '"Центр объекта"' in coords_str
        # Точка может быть как "Point KMZ", так и "Point KMZ" в зависимости от имени
        assert '"Point KMZ"' in coords_str
        # Проверяем, что координаты извлечены (примерное значение)
        assert "11.222" in coords_str
        assert "33.444" in coords_str


@pytest.mark.django_db
@patch('agregator.processing.geo_objects_processing.calculate_file_hash')
def test_extract_coordinates_duplicate_file(mock_hash, test_user):
    """Обработка дубликата файла (должно вызывать FileExistsError)"""
    with tempfile.NamedTemporaryFile(suffix='.kml', delete=False) as f:
        f.write(b"test")
        f.flush()
        file_path = f.name

    # Создаём два объекта с одинаковым содержимым (хэш одинаков)
    mock_hash.return_value = "same_hash"

    geo_obj1 = GeoObject.objects.create(
        user=test_user,
        origin_filename="test1.kml",
        source=file_path,
        is_processing=True
    )
    geo_obj2 = GeoObject.objects.create(
        user=test_user,
        origin_filename="test2.kml",
        source=file_path,
        is_processing=True
    )

    progress_recorder = MagicMock()
    pages_count = {"1": 1}
    total_processed = [0]
    progress_json = {"file_groups": {str(geo_obj2.id): {"origin_filename": "test2.kml"}}}
    task_id = "task123"
    time_on_start = MagicMock()

    with pytest.raises(FileExistsError) as exc_info:
        extract_coordinates(
            file=file_path,
            progress_recorder=progress_recorder,
            pages_count=pages_count,
            total_processed=total_processed,
            geo_object_id=geo_obj2.id,
            progress_json=progress_json,
            task_id=task_id,
            time_on_start=time_on_start
        )
    assert "Такой файл уже загружен в систему" in str(exc_info.value)

    os.unlink(file_path)


@pytest.mark.django_db
def test_extract_coordinates_file_not_found(test_user):
    non_existent = "/nonexistent/file.kml"
    geo_obj = GeoObject.objects.create(
        user=test_user,
        origin_filename="missing.kml",
        source=non_existent,
        is_processing=True
    )
    progress_recorder = MagicMock()
    pages_count = {"1": 1}
    total_processed = [0]
    progress_json = {"file_groups": {str(geo_obj.id): {"origin_filename": "missing.kml"}}}
    task_id = "task123"
    time_on_start = MagicMock()

    # Ожидаем FileNotFoundError, т.к. файл не существует
    with pytest.raises(FileNotFoundError):
        extract_coordinates(
            file=non_existent,
            progress_recorder=progress_recorder,
            pages_count=pages_count,
            total_processed=total_processed,
            geo_object_id=geo_obj.id,
            progress_json=progress_json,
            task_id=task_id,
            time_on_start=time_on_start
        )

    # Объект должен остаться с is_processing=True, т.к. обработка не завершилась
    geo_obj.refresh_from_db()
    assert geo_obj.is_processing is True


# ----- Тесты для error_handler_geo_objects -----
@patch('agregator.processing.geo_objects_processing.redis_client')
def test_error_handler_geo_objects_deletes_unprocessed(mock_redis, test_user):
    """Обработчик ошибок удаляет необработанные объекты"""
    geo_obj = GeoObject.objects.create(user=test_user, is_processing=True)
    task = MagicMock()
    task.id = "task_id"
    exception = Exception("Test error")

    progress_data = {
        "file_groups": {
            str(geo_obj.id): {
                "processed": "False",
                "origin_filename": "test.kml"
            }
        }
    }
    mock_redis.get.return_value = json.dumps(progress_data)

    with pytest.raises(Exception) as exc_info:
        error_handler_geo_objects(task, exception, "desc")

    # Проверяем, что объект удалён
    with pytest.raises(GeoObject.DoesNotExist):
        geo_obj.refresh_from_db()

    assert "Test error" in str(exc_info.value)
    assert "progress_json" in str(exc_info.value)


@patch('agregator.processing.geo_objects_processing.redis_client')
def test_error_handler_geo_objects_keeps_processed(mock_redis, test_user):
    """Обработчик ошибок не удаляет уже обработанные объекты"""
    geo_obj = GeoObject.objects.create(user=test_user, is_processing=True)
    task = MagicMock()
    task.id = "task_id"
    exception = Exception("Test error")

    progress_data = {
        "file_groups": {
            str(geo_obj.id): {
                "processed": "True",
                "origin_filename": "test.kml"
            }
        }
    }
    mock_redis.get.return_value = json.dumps(progress_data)

    with pytest.raises(Exception) as exc_info:
        error_handler_geo_objects(task, exception, "desc")

    # Объект должен остаться
    geo_obj.refresh_from_db()
    assert geo_obj.id is not None

    assert "Test error" in str(exc_info.value)
