import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock
from django.conf import settings
from agregator.processing.links import (
    create_url_file,
    get_object_url,
    create_link_for_instance,
    create_links_for_all_existing,
)


# === Фикстуры ===
@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mock_instance():
    instance = MagicMock()
    instance.pk = 123
    instance.__class__.__name__ = "Act"
    return instance


# === Тесты для create_url_file ===
def test_create_url_file(temp_dir):
    file_path = os.path.join(temp_dir, "test.url")
    target_url = "http://example.com/test/"
    create_url_file(file_path, target_url)
    assert os.path.exists(file_path)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    expected = f"""[InternetShortcut]
URL={target_url}
"""
    assert content == expected


# === Тесты для get_object_url ===
@patch('agregator.processing.links.BASE_URL', 'http://testserver')
def test_get_object_url_act():
    instance = MagicMock()
    instance.__class__.__name__ = "Act"
    instance.pk = 5
    url = get_object_url(instance)
    assert url == "http://testserver/acts/5/"


@patch('agregator.processing.links.BASE_URL', 'http://testserver')
def test_get_object_url_scientific_report():
    instance = MagicMock()
    instance.__class__.__name__ = "ScientificReport"
    instance.pk = 10
    url = get_object_url(instance)
    assert url == "http://testserver/scientific_reports/10/"


@patch('agregator.processing.links.BASE_URL', 'http://testserver')
def test_get_object_url_commercial_offer():
    instance = MagicMock()
    instance.__class__.__name__ = "CommercialOffers"
    instance.pk = 7
    url = get_object_url(instance)
    assert url == "http://testserver/map/commercial_offer/7/"


@patch('agregator.processing.links.BASE_URL', 'http://testserver')
def test_get_object_url_unknown_model():
    instance = MagicMock()
    instance.__class__.__name__ = "UnknownModel"
    instance.pk = 99
    url = get_object_url(instance)
    assert url == "http://testserver/admin/agregator/unknownmodel/99/"


# === Тесты для create_link_for_instance ===
@patch('agregator.processing.links.get_object_url')
@patch('agregator.processing.links.create_url_file')
def test_create_link_for_instance_with_source_dict(mock_create_file, mock_get_url, temp_dir):
    instance = MagicMock()
    instance.__class__.__name__ = "Act"
    instance.id = 1
    instance.source_dict = [{'path': os.path.join(temp_dir, "file.pdf")}]
    mock_get_url.return_value = "http://testserver/acts/1/"

    # Создаём временный файл
    file_path = instance.source_dict[0]['path']
    with open(file_path, 'w') as f:
        f.write("dummy")

    result = create_link_for_instance(instance)

    expected_link_path = os.path.join(temp_dir, "Act_1.url")
    mock_create_file.assert_called_once_with(expected_link_path, "http://testserver/acts/1/")
    assert result == expected_link_path


@patch('agregator.processing.links.get_object_url')
@patch('agregator.processing.links.create_url_file')
def test_create_link_for_instance_with_source(mock_create_file, mock_get_url, temp_dir):
    instance = MagicMock()
    instance.__class__.__name__ = "Act"
    instance.id = 2
    instance.source = os.path.join(temp_dir, "file2.pdf")
    instance.source_dict = None
    mock_get_url.return_value = "http://testserver/acts/2/"

    with open(instance.source, 'w') as f:
        f.write("dummy")

    result = create_link_for_instance(instance)

    expected_link_path = os.path.join(temp_dir, "Act_2.url")
    mock_create_file.assert_called_once_with(expected_link_path, "http://testserver/acts/2/")
    assert result == expected_link_path


@patch('agregator.processing.links.get_object_url')
@patch('agregator.processing.links.create_url_file')
def test_create_link_for_instance_with_document_source_dict(mock_create_file, mock_get_url, temp_dir):
    instance = MagicMock()
    instance.__class__.__name__ = "ArchaeologicalHeritageSite"
    instance.id = 3
    instance.document_source_dict = [{'path': os.path.join(temp_dir, "doc.pdf")}]
    instance.source_dict = None
    instance.source = None
    mock_get_url.return_value = "http://testserver/archaeological_heritage_sites/3/"

    with open(instance.document_source_dict[0]['path'], 'w') as f:
        f.write("dummy")

    result = create_link_for_instance(instance)

    expected_link_path = os.path.join(temp_dir, "ArchaeologicalHeritageSite_3.url")
    mock_create_file.assert_called_once_with(expected_link_path, "http://testserver/archaeological_heritage_sites/3/")
    assert result == expected_link_path


@patch('agregator.processing.links.get_object_url')
@patch('agregator.processing.links.create_url_file')
def test_create_link_for_instance_open_lists(mock_create_file, mock_get_url, temp_dir):
    instance = MagicMock()
    instance.__class__.__name__ = "OpenLists"
    instance.id = 4
    instance.source = MagicMock()
    instance.source.path = os.path.join(temp_dir, "list.pdf")
    mock_get_url.return_value = "http://testserver/open_lists/4/"

    with open(instance.source.path, 'w') as f:
        f.write("dummy")

    result = create_link_for_instance(instance)

    expected_link_path = os.path.join(temp_dir, "OpenLists_4.url")
    mock_create_file.assert_called_once_with(expected_link_path, "http://testserver/open_lists/4/")
    assert result == expected_link_path


def test_create_link_for_instance_no_source_path():
    instance = MagicMock()
    instance.__class__.__name__ = "Act"
    instance.source_dict = []
    instance.source = None
    instance.document_source_dict = None

    result = create_link_for_instance(instance)
    assert result is None


def test_create_link_for_instance_source_path_not_exists():
    instance = MagicMock()
    instance.__class__.__name__ = "Act"
    instance.source_dict = [{'path': "/nonexistent/file.pdf"}]

    result = create_link_for_instance(instance)
    assert result is None


@patch('agregator.processing.links.get_object_url')
def test_create_link_for_instance_exception(mock_get_url):
    instance = MagicMock()
    instance.__class__.__name__ = "Act"
    instance.source_dict = [{'path': "/some/file.pdf"}]
    mock_get_url.side_effect = Exception("Test error")

    result = create_link_for_instance(instance)
    assert result is None


# === Тесты для create_links_for_all_existing ===
@patch('agregator.processing.links.create_link_for_instance')
def test_create_links_for_all_existing(mock_create_link):
    models = [
        'Act', 'ScientificReport', 'TechReport', 'OpenLists',
        'ObjectAccountCard', 'ArchaeologicalHeritageSite',
        'IdentifiedArchaeologicalHeritageSite', 'CommercialOffers', 'GeoObject'
    ]

    # Создаём моки для каждой модели
    model_mocks = {}
    for name in models:
        mock_model = MagicMock()
        obj1 = MagicMock()
        obj2 = MagicMock()
        mock_model.objects.all.return_value = [obj1, obj2]
        model_mocks[name] = mock_model

    # Заменяем модели в agregator.models
    with patch.multiple('agregator.models', **model_mocks):
        created_count = create_links_for_all_existing()

    assert mock_create_link.call_count == len(models) * 2
    assert created_count == len(models) * 2

    # Проверяем, что для каждого объекта был вызов
    for name in models:
        for obj in model_mocks[name].objects.all():
            mock_create_link.assert_any_call(obj)
