import pytest
import os
import xml.etree.ElementTree as ET
import zipfile
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from agregator.processing.batch_kml_utils import KMLProcessor, KMLParser


# ==================== Фикстуры ====================
@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def basic_kml_content():
    return '''<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>
            <Placemark>
                <name>Point 1</name>
                <Point>
                    <coordinates>55.123,37.456</coordinates>
                </Point>
            </Placemark>
        </Document>
    </kml>'''


@pytest.fixture
def folder_kml_content():
    return '''<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Folder>
            <name>Test Folder</name>
            <Placemark>
                <name>Point in Folder</name>
                <Point>
                    <coordinates>55.789,37.890</coordinates>
                </Point>
            </Placemark>
        </Folder>
    </kml>'''


@pytest.fixture
def polygon_kml_content():
    return '''<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Placemark>
            <name>Polygon A</name>
            <Polygon>
                <outerBoundaryIs>
                    <LinearRing>
                        <coordinates>
                            55.0,37.0
                            55.1,37.1
                            55.1,37.2
                            55.0,37.2
                            55.0,37.0
                        </coordinates>
                    </LinearRing>
                </outerBoundaryIs>
            </Polygon>
        </Placemark>
    </kml>'''


@pytest.fixture
def shurf_kml_content():
    return '''<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Folder>
            <name>Шурфы</name>
            <Placemark>
                <name>Шурф 1</name>
                <Point>
                    <coordinates>55.111,37.222</coordinates>
                </Point>
            </Placemark>
        </Folder>
    </kml>'''


@pytest.fixture
def photo_kml_content():
    return '''<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Folder>
            <name>Фотофиксация</name>
            <Placemark>
                <name>Точка 1</name>
                <Point>
                    <coordinates>55.333,37.444</coordinates>
                </Point>
            </Placemark>
        </Folder>
    </kml>'''


@pytest.fixture
def linestring_kml_content():
    return '''<?xml version="1.0" encoding="UTF-8"?>
    <kml xmlns="http://www.opengis.net/kml/2.2">
        <Placemark>
            <name>Line</name>
            <LineString>
                <coordinates>
                    55.0,37.0
                    55.1,37.1
                    55.2,37.2
                </coordinates>
            </LineString>
        </Placemark>
    </kml>'''


@pytest.fixture
def kmz_content(temp_dir, basic_kml_content):
    """Создаёт временный KMZ файл с KML внутри"""
    kmz_path = temp_dir / "test.kmz"
    with zipfile.ZipFile(kmz_path, 'w') as zf:
        zf.writestr("doc.kml", basic_kml_content)
    return str(kmz_path)


# ==================== Тесты KMLProcessor ====================
class TestKMLProcessor:

    def test_process_kml_file_basic_point(self, temp_dir, basic_kml_content):
        kml_path = temp_dir / "test.kml"
        with open(kml_path, 'w', encoding='utf-8') as f:
            f.write(basic_kml_content)

        processor = KMLProcessor()
        result = processor.process_kml_file(str(kml_path))

        # Для одиночной точки без папки ключ верхнего уровня — имя точки
        assert "Point 1" in result
        assert result["Point 1"]["Point 1"] == [37.456, 55.123]
        assert result["Point 1"]["coordinate_system"] == "wgs84"

    def test_process_kml_file_folder(self, temp_dir, folder_kml_content):
        kml_path = temp_dir / "test.kml"
        with open(kml_path, 'w', encoding='utf-8') as f:
            f.write(folder_kml_content)

        processor = KMLProcessor()
        result = processor.process_kml_file(str(kml_path))

        assert "Test Folder" in result
        # Координаты сохраняются в порядке [долгота, широта]
        assert result["Test Folder"]["Point in Folder"] == [37.890, 55.789]

    def test_process_kml_file_polygon(self, temp_dir, polygon_kml_content):
        kml_path = temp_dir / "test.kml"
        with open(kml_path, 'w', encoding='utf-8') as f:
            f.write(polygon_kml_content)

        processor = KMLProcessor()
        result = processor.process_kml_file(str(kml_path))

        assert "Каталог координат Polygon A" in result
        coords = result["Каталог координат Polygon A"]
        assert coords["coordinate_system"] == "wgs84"
        # Должно быть 5 точек
        assert len(coords) == 6  # 5 точек + coordinate_system

    def test_process_kml_file_polygon_with_existing_points(self, temp_dir):
        content = '''<?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
            <Folder>
                <name>TestFolder</name>
                <Placemark>
                    <name>Point 1</name>
                    <Point><coordinates>55.0,37.0</coordinates></Point>
                </Placemark>
                <Placemark>
                    <name>Polygon A</name>
                    <Polygon>
                        <outerBoundaryIs>
                            <LinearRing><coordinates>
                                55.0,37.0
                                55.1,37.1
                                55.1,37.2
                                55.0,37.2
                                55.0,37.0
                            </coordinates></LinearRing>
                        </outerBoundaryIs>
                    </Polygon>
                </Placemark>
            </Folder>
        </kml>'''
        kml_path = temp_dir / "test.kml"
        with open(kml_path, 'w', encoding='utf-8') as f:
            f.write(content)

        processor = KMLProcessor()
        result = processor.process_kml_file(str(kml_path))

        assert "TestFolder" not in result
        assert "Каталог координат Polygon A" in result
        catalog = result["Каталог координат Polygon A"]
        assert catalog["coordinate_system"] == "wgs84"
        # Точка 1 совпала и сохранена
        assert "1" in catalog
        assert catalog["1"] == [37.0, 55.0]  # [долгота, широта]

    def test_process_kml_file_linestring(self, temp_dir, linestring_kml_content):
        kml_path = temp_dir / "test.kml"
        with open(kml_path, 'w', encoding='utf-8') as f:
            f.write(linestring_kml_content)

        processor = KMLProcessor()
        result = processor.process_kml_file(str(kml_path))

        assert "Каталог координат Line" in result
        coords = result["Каталог координат Line"]
        assert coords["coordinate_system"] == "wgs84"
        assert len(coords) == 4  # 3 точки + coordinate_system

    def test_process_kml_file_shurf(self, temp_dir, shurf_kml_content):
        kml_path = temp_dir / "test.kml"
        with open(kml_path, 'w', encoding='utf-8') as f:
            f.write(shurf_kml_content)

        processor = KMLProcessor()
        result = processor.process_kml_file(str(kml_path))

        assert "Шурфы" in result
        assert result["Шурфы"]["Шурф 1"] == [37.222, 55.111]

    def test_process_kml_file_photo(self, temp_dir, photo_kml_content):
        kml_path = temp_dir / "test.kml"
        with open(kml_path, 'w', encoding='utf-8') as f:
            f.write(photo_kml_content)

        processor = KMLProcessor()
        result = processor.process_kml_file(str(kml_path))

        assert "Пункты фотофиксации" in result
        assert result["Пункты фотофиксации"]["Точка 1"] == [37.444, 55.333]

    def test_process_kml_file_invalid(self, temp_dir):
        kml_path = temp_dir / "invalid.kml"
        with open(kml_path, 'w', encoding='utf-8') as f:
            f.write("Not XML")

        processor = KMLProcessor()
        result = processor.process_kml_file(str(kml_path))
        assert result == {}

    def test_process_kml_file_not_exists(self, temp_dir):
        processor = KMLProcessor()
        result = processor.process_kml_file(str(temp_dir / "missing.kml"))
        assert result == {}

    def test_process_kmz_file(self, kmz_content, temp_dir):
        processor = KMLProcessor()
        result = processor.process_kmz_file(kmz_content)
        assert "Point 1" in result
        assert result["Point 1"]["Point 1"] == [37.456, 55.123]

    def test_process_kmz_file_no_kml(self, temp_dir):
        kmz_path = temp_dir / "empty.kmz"
        with zipfile.ZipFile(kmz_path, 'w') as zf:
            zf.writestr("test.txt", b"content")
        processor = KMLProcessor()
        result = processor.process_kmz_file(str(kmz_path))
        assert result == {}

    def test_process_kmz_file_exception(self, temp_dir):
        with patch('zipfile.ZipFile', side_effect=Exception("Bad zip")):
            processor = KMLProcessor()
            result = processor.process_kmz_file(str(temp_dir / "fake.kmz"))
            assert result == {}

    def test_swap_coordinates(self):
        processor = KMLProcessor()
        coords = [55.123, 37.456]
        swapped = processor._swap_coordinates(coords)
        assert swapped == [37.456, 55.123]

    def test_parse_coordinates(self):
        processor = KMLProcessor()
        coords_text = "55.123,37.456,0 55.124,37.457,0"
        parsed = processor._parse_coordinates(coords_text)
        assert parsed == [[55.123, 37.456], [55.124, 37.457]]

    def test_extract_coordinates(self):
        processor = KMLProcessor()
        elem = ET.fromstring('<Point><coordinates>55.1,37.1</coordinates></Point>')
        coords = processor._extract_coordinates(elem)
        assert coords == [[55.1, 37.1]]

    def test_find_element(self):
        processor = KMLProcessor()
        xml = '<root xmlns="http://www.opengis.net/kml/2.2"><name>Test</name></root>'
        root = ET.fromstring(xml)
        result = processor._find_element(root, 'name')
        assert result is not None
        assert result.text == "Test"


# ==================== Тесты KMLParser ====================
class TestKMLParser:

    def test_parse_kml_file(self, temp_dir, basic_kml_content):
        kml_path = temp_dir / "test.kml"
        with open(kml_path, 'w', encoding='utf-8') as f:
            f.write(basic_kml_content)

        result = KMLParser.parse_kml_file(str(kml_path))
        assert "Point 1" in result
        assert result["Point 1"]["Point 1"] == [37.456, 55.123]

    def test_parse_kmz_file(self, kmz_content):
        result = KMLParser.parse_kml_file(kmz_content)
        assert "Point 1" in result
        assert result["Point 1"]["Point 1"] == [37.456, 55.123]

    def test_parse_coordinates_static(self):
        coords_text = "55.123,37.456 55.124,37.457"
        parsed = KMLParser._parse_coordinates(coords_text)
        # Ожидаем [долгота, широта]
        assert parsed == [[37.456, 55.123], [37.457, 55.124]]

    def test_find_kml_for_pdf_exact_match(self, temp_dir):
        pdf_path = temp_dir / "document.pdf"
        pdf_path.touch()
        kml_path = temp_dir / "document.kml"
        kml_path.touch()

        result = KMLParser.find_kml_for_pdf(str(pdf_path))
        assert result == str(kml_path)

    def test_find_kml_for_pdf_kmz(self, temp_dir):
        pdf_path = temp_dir / "document.pdf"
        pdf_path.touch()
        kmz_path = temp_dir / "document.kmz"
        kmz_path.touch()

        result = KMLParser.find_kml_for_pdf(str(pdf_path))
        assert result == str(kmz_path)

    def test_find_kml_for_pdf_with_suffix(self, temp_dir):
        pdf_path = temp_dir / "document.pdf"
        pdf_path.touch()
        kml_path = temp_dir / "document_coordinates.kml"
        kml_path.touch()

        result = KMLParser.find_kml_for_pdf(str(pdf_path))
        assert result == str(kml_path)

    def test_find_kml_for_pdf_parent_folder(self, temp_dir):
        parent = temp_dir / "parent"
        parent.mkdir()
        pdf_path = parent / "document.pdf"
        pdf_path.touch()
        kml_path = temp_dir / "document.kml"
        kml_path.touch()

        result = KMLParser.find_kml_for_pdf(str(pdf_path))
        assert result == str(kml_path)

    def test_find_kml_for_pdf_any_kml_in_folder(self, temp_dir):
        pdf_path = temp_dir / "document.pdf"
        pdf_path.touch()
        kml_path = temp_dir / "random.kml"
        kml_path.touch()

        result = KMLParser.find_kml_for_pdf(str(pdf_path))
        assert result == str(kml_path)

    def test_find_kml_for_pdf_not_found(self, temp_dir):
        pdf_path = temp_dir / "document.pdf"
        pdf_path.touch()
        result = KMLParser.find_kml_for_pdf(str(pdf_path))
        assert result is None
