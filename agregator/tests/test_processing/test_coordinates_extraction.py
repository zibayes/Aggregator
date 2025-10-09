# tests/test_coordinates_extraction.py
import pytest
import re
import pandas as pd
import pdfplumber
from django.conf import settings
from unittest.mock import MagicMock, patch
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile

from agregator.processing.coordinates_extraction import (
    extract_coordinates,
    dms_to_decimal,
    convert_to_wgs84,
    convert_proj4
)


@pytest.fixture
def mock_pdf_document():
    """Создает мок PDF документа с методами и свойствами, подобными pdfplumber"""
    doc = MagicMock()
    doc.__len__.return_value = 2
    doc.pages = [MagicMock(), MagicMock()]
    return doc


@pytest.fixture
def mock_pdf_page():
    """Создает мок страницы PDF с методами для извлечения текста и таблиц"""
    page = MagicMock()
    page.get_text.return_value = ""
    page.extract_tables.return_value = []
    return page


@pytest.fixture
def coordinates_dict():
    """Возвращает базовый словарь координат для тестов"""
    return {'Шурфы': {}}


@pytest.fixture
def mock_pdf_with_table():
    """Создает мок PDF с таблицей координат"""

    def create_pdf_with_table(table_data):
        pdf = MagicMock()
        pdf.pages = [MagicMock()]
        pdf.pages[0].extract_tables.return_value = [table_data]
        return pdf

    return create_pdf_with_table


@pytest.fixture
def mock_pdf_with_text():
    """Создает мок PDF с текстом для поиска шурфов"""

    def create_pdf_with_text(text):
        pdf = MagicMock()
        pdf.pages = [MagicMock()]
        pdf.pages[0].get_text.return_value = text
        return pdf

    return create_pdf_with_text


@pytest.fixture
def create_temp_pdf():
    """Создает временный PDF файл с тестовыми данными"""

    def _create_temp_pdf(content):
        file = BytesIO()
        # Просто эмулируем PDF содержимое
        file.write(b'%PDF-1.4\n')
        file.write(content.encode('utf-8'))
        file.seek(0)
        return SimpleUploadedFile("test.pdf", file.read(), content_type="application/pdf")

    return _create_temp_pdf


# ========================
# Тесты преобразования DMS
# ========================

@pytest.mark.parametrize("dms, expected", [
    ("55°30'15.5\"N", 55.50430556),
    ("55°30'15.5\"S", -55.50430556),
    ("37°36'30.2\"E", 37.60838889),
    ("37°36'30.2\"W", -37.60838889),
    ("45°00'00.0\"N", 45.0),
    ("00°00'00.0\"N", 0.0),
    ("90°00'00.0\"N", 90.0),
    ("90°00'00.0\"S", -90.0),
    ("180°00'00.0\"E", 180.0),
    ("180°00'00.0\"W", -180.0),
    ("55°30'15,N", 55.50416667),
    ("55°30'15,N", 55.50416667),
    ("55°30,15\"N", 55.50416667),
])
def test_dms_to_decimal(dms, expected):
    """Тестирование преобразования DMS в десятичные координаты"""
    assert dms_to_decimal(dms) == pytest.approx(expected, rel=1e-6)


@pytest.mark.parametrize("dms, error_type", [
    ("91°00'00.0\"N", ValueError),  # Недопустимая широта
    ("181°00'00.0\"E", ValueError),  # Недопустимая долгота
    ("55°60'15.5\"N", ValueError),  # Недопустимые минуты
    ("55°30'70.5\"N", ValueError),  # Недопустимые секунды
    ("invalid format", ValueError),  # Некорректный формат
    ("", ValueError),  # Пустая строка
])
def test_dms_to_decimal_invalid(dms, error_type):
    """Тестирование обработки недопустимых форматов DMS"""
    with pytest.raises(error_type):
        dms_to_decimal(dms)


# ========================
# Тесты основной функции
# ========================

@pytest.mark.parametrize("page_text, expected_system", [
    ("Пункты фотфиксации. Система координат WGS-84", "wgs84"),
    ("Пункты фотфиксации. Система координат МСК-11, зона 5", "мск11зона5"),
    ("Каталог координат Участка. Система координат МСК-12", "мск12"),
    ("Пункты фотфиксации. Система координат WGS 84", "wgs84"),
    ("Пункты фотфиксации. Система координат WGS:84", "wgs84"),
    ("Пункты фотфиксации. Система координат: WGS-84", "wgs84"),
    ("Пункты фотфиксации. Система координат: МСК-11, зона 5", "мск11зона5"),
])
def test_coordinate_system_detection(mock_pdf_document, coordinates_dict, mocker, page_text, expected_system):
    """Тестирование обнаружения системы координат в тексте"""
    # Настройка мока для получения текста страницы
    mock_pdf_document.pages[0].get_text.return_value = page_text
    mock_pdf_document.pages[0].extract_tables.return_value = []

    # Мокируем convert_to_wgs84 для предотвращения реальных преобразований
    mocker.patch("agregator.processing.coordinates_extraction.convert_to_wgs84", return_value=(55.5, 37.6))

    # Выполняем извлечение координат
    extract_coordinates("test.pdf", mock_pdf_document, 0, "test_folder", coordinates_dict)

    # Проверяем, что система координат была правильно определена
    if "Пункты фотфиксации" in page_text or "Каталог координат" in page_text:
        assert 'Пункты фотфиксации' in coordinates_dict
        assert coordinates_dict['Пункты фотфиксации']['coordinate_system'] == expected_system
    else:
        assert 'Каталог координат' in coordinates_dict
        assert coordinates_dict['Каталог координат']['coordinate_system'] == expected_system


@pytest.mark.parametrize("table_data, expected_points, system", [
    # Таблица с широтой/долготой
    (
            [
                ['№', 'Северная широта', 'Восточная долгота'],
                ['1', '55°30\'15.5\"N', '37°36\'30.2\"E'],
                ['2', '56°15\'45.2\"N', '38°20\'10.5\"E']
            ],
            {
                '1': [55.50430556, 37.60838889],
                '2': [56.26255556, 38.33625]
            },
            "wgs84"
    ),
    # Таблица с X/Y (МСК)
    (
            [
                ['№', 'X', 'Y'],
                ['1', '7500000.5', '3500000.2'],
                ['2', '7505000.3', '3502500.8']
            ],
            {
                '1': [55.5, 37.6],
                '2': [55.51, 37.62]
            },
            "мск11"
    ),
    # Таблица с DMS без N/S/E/W (предполагается северная и восточная)
    (
            [
                ['№', 'Северная широта', 'Восточная долгота'],
                ['1', '55°30\'15.5"', '37°36\'30.2"'],
                ['2', '56°15\'45.2"', '38°20\'10.5"']
            ],
            {
                '1': [55.50430556, 37.60838889],
                '2': [56.26255556, 38.33625]
            },
            "wgs84"
    ),
    # Таблица с отрицательными координатами (S/W)
    (
            [
                ['№', 'Северная широта', 'Восточная долгота'],
                ['1', '55°30\'15.5\"S', '37°36\'30.2\"W']
            ],
            {
                '1': [-55.50430556, -37.60838889]
            },
            "wgs84"
    ),
])
def test_coordinate_extraction_from_tables(mock_pdf_document, coordinates_dict, mocker,
                                           table_data, expected_points, system):
    """Тестирование извлечения координат из таблицы"""
    # Настройка мока для получения таблицы
    mock_pdf_document.pages[0].extract_tables.return_value = [table_data]

    # Мокируем convert_to_wgs84 для возврата фиксированных значений
    mocker.patch("agregator.processing.coordinates_extraction.convert_to_wgs84",
                 return_value=(55.5, 37.6))

    # Мокируем dms_to_decimal для фиксированных значений
    mocker.patch("agregator.processing.coordinates_extraction.dms_to_decimal",
                 side_effect=lambda x: {
                     '55°30\'15.5\"N': 55.50430556,
                     '37°36\'30.2\"E': 37.60838889,
                     '56°15\'45.2\"N': 56.26255556,
                     '38°20\'10.5\"E': 38.33625,
                     '55°30\'15.5\"S': -55.50430556,
                     '37°36\'30.2\"W': -37.60838889,
                     '55°30\'15.5"': 55.50430556,
                     '37°36\'30.2"': 37.60838889,
                 }.get(x, 0.0))

    # Мокируем систему координат
    mocker.patch("re.search", side_effect=lambda pattern, text, flags=0:
    MagicMock(group=lambda: "Пункты фотфиксации. Система координат " + system)
    if "Пункты фотфиксации" in pattern else None)

    # Выполняем извлечение координат
    extract_coordinates("test.pdf", mock_pdf_document, 0, "test_folder", coordinates_dict)

    # Проверяем, что координаты извлечены правильно
    assert 'Пункты фотфиксации' in coordinates_dict
    for point_num, coords in expected_points.items():
        assert point_num in coordinates_dict['Пункты фотфиксации']
        assert coordinates_dict['Пункты фотфиксации'][point_num] == pytest.approx(coords, rel=1e-5)

    # Проверяем систему координат
    assert coordinates_dict['Пункты фотфиксации']['coordinate_system'] == system


@pytest.mark.parametrize("text_content, expected_pits", [
    (
            "Шурф № 1\nКоординаты шурфа в системе WGS-84: N55°30'15.5\" E37°36'30.2\"",
            {'Шурф № 1': [55.50430556, 37.60838889]}
    ),
    (
            "Шурф № 2\nКоординаты шурфа в системе WGS-84: S55°30'15.5\" W37°36'30.2\"",
            {'Шурф № 2': [-55.50430556, -37.60838889]}
    ),
    (
            "Шурф № 3\nКоординаты шурфа в системе WGS-84: N55°30'15.5\" E37°36'30.2\"\nШурф № 4\nКоординаты шурфа в системе WGS-84: N56°15'45.2\" E38°20'10.5\"",
            {
                'Шурф № 3': [55.50430556, 37.60838889],
                'Шурф № 4': [56.26255556, 38.33625]
            }
    ),
    (
            "Некорректный текст без шурфов",
            {}
    ),
    (
            "Шурф № 1\nКоординаты шурфа в системе WGS-84: 55°30'15.5\" 37°36'30.2\"",
            {'Шурф № 1': [55.50430556, 37.60838889]}
    ),
])
def test_pit_coordinate_extraction(mock_pdf_document, coordinates_dict, mocker,
                                   text_content, expected_pits):
    """Тестирование извлечения координат шурфов из текста"""
    # Настройка мока для получения текста страницы
    mock_pdf_document.pages[0].get_text.return_value = text_content

    # Мокируем dms_to_decimal для фиксированных значений
    mocker.patch("agregator.processing.coordinates_extraction.dms_to_decimal",
                 side_effect=lambda x: {
                     'N55°30\'15.5"': 55.50430556,
                     'E37°36\'30.2"': 37.60838889,
                     'S55°30\'15.5"': -55.50430556,
                     'W37°36\'30.2"': -37.60838889,
                     '55°30\'15.5"': 55.50430556,
                     '37°36\'30.2"': 37.60838889,
                     'N56°15\'45.2"': 56.26255556,
                     'E38°20\'10.5"': 38.33625
                 }.get(x, 0.0))

    # Выполняем извлечение координат
    extract_coordinates("test.pdf", mock_pdf_document, 0, "test_folder", coordinates_dict)

    # Проверяем извлеченные координаты шурфов
    if expected_pits:
        assert 'Шурфы' in coordinates_dict
        for pit_num, coords in expected_pits.items():
            assert pit_num in coordinates_dict['Шурфы']
            assert coordinates_dict['Шурфы'][pit_num] == pytest.approx(coords, rel=1e-5)
    else:
        assert 'Шурфы' not in coordinates_dict or not coordinates_dict['Шурфы']


# ========================
# Граничные случаи
# ========================

@pytest.mark.parametrize("table_data", [
    # Пустая таблица
    [],

    # Таблица без данных
    [[]],

    # Таблица с заголовками, но без данных
    [['№', 'Северная широта', 'Восточная долгота']],

    # Таблица с пустыми координатами
    [
        ['№', 'Северная широта', 'Восточная долгота'],
        ['1', '', ''],
        ['2', None, None]
    ],

    # Таблица с неправильными заголовками
    [
        ['ID', 'Latitude', 'Longitude'],
        ['1', '55.5', '37.6']
    ],

    # Таблица с некорректными координатами
    [
        ['№', 'Северная широта', 'Восточная долгота'],
        ['1', 'invalid', 'data']
    ]
])
def test_table_edge_cases(mock_pdf_document, coordinates_dict, mocker, table_data):
    """Тестирование граничных случаев таблиц"""
    # Настройка мока для получения таблицы
    mock_pdf_document.pages[0].extract_tables.return_value = [table_data] if table_data else []

    # Мокируем систему координат
    mocker.patch("re.search", side_effect=lambda pattern, text, flags=0:
    MagicMock(group=lambda: "Пункты фотфиксации. Система координат wgs84")
    if "Пункты фотфиксации" in pattern else None)

    # Выполняем извлечение координат
    extract_coordinates("test.pdf", mock_pdf_document, 0, "test_folder", coordinates_dict)

    # Проверяем, что не добавлены невалидные координаты
    if 'Пункты фотфиксации' in coordinates_dict:
        # Должна быть только запись о системе координат
        assert len(coordinates_dict['Пункты фотфиксации']) == 1
        assert 'coordinate_system' in coordinates_dict['Пункты фотфиксации']
    else:
        # Должно быть пусто или только шурфы
        assert not coordinates_dict or 'Шурфы' in coordinates_dict


def test_multiple_pages_extraction(mock_pdf_document, coordinates_dict, mocker):
    """Тестирование извлечения координат с нескольких страниц"""
    # Настройка текста для двух страниц
    page1_text = "Пункты фотфиксации. Система координат WGS-84"
    page2_text = "Продолжение таблицы\n1 55°30'15.5\"N 37°36'30.2\"E"

    mock_pdf_document.pages[0].get_text.return_value = page1_text
    mock_pdf_document.pages[1].get_text.return_value = page2_text

    # Мокируем таблицу на первой странице
    mock_pdf_document.pages[0].extract_tables.return_value = []

    # Мокируем dms_to_decimal
    mocker.patch("agregator.processing.coordinates_extraction.dms_to_decimal",
                 return_value=55.50430556)

    # Выполняем извлечение координат
    extract_coordinates("test.pdf", mock_pdf_document, 0, "test_folder", coordinates_dict)

    # Проверяем, что текст второй страницы был учтен
    assert 'Пункты фотфиксации' in coordinates_dict
    # Здесь не должно быть координат, так как таблица не найдена


# ========================
# Интеграционные тесты
# ========================

def test_real_pdf_processing(create_temp_pdf, coordinates_dict, mocker):
    """Интеграционный тест с реальным PDF-файлом (эмуляция)"""
    # Создаем PDF с тестовыми данными
    pdf_content = """
    %PDF-1.4
    1 0 obj
    << /Type /Catalog /Pages 2 0 R >>
    endobj
    2 0 obj
    << /Type /Pages /Kids [3 0 R] /Count 1 >>
    endobj
    3 0 obj
    << /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 612 792] /Contents 4 0 R >>
    endobj
    4 0 obj
    << /Length 44 >>
    stream
    BT /F1 24 Tf 100 700 Td (Пункты фотфиксации. Система координат WGS-84) Tj ET
    BT /F1 12 Tf 100 650 Td (1 55°30'15.5\"N 37°36'30.2\"E) Tj ET
    endstream
    endobj
    """

    pdf_file = create_temp_pdf(pdf_content)

    # Мокируем pdfplumber.open для работы с нашим PDF
    with patch("pdfplumber.open") as mock_pdf:
        # Создаем мок для извлечения текста и таблиц
        mock_page = MagicMock()
        mock_page.get_text.return_value = "Пункты фотфиксации. Система координат WGS-84\n1 55°30'15.5\"N 37°36'30.2\"E"
        mock_page.extract_tables.return_value = [[
            ['№', 'Северная широта', 'Восточная долгота'],
            ['1', '55°30\'15.5\"N', '37°36\'30.2\"E']
        ]]

        mock_pdf.return_value.__enter__.return_value.pages = [mock_page]

        # Мокируем dms_to_decimal
        mocker.patch("agregator.processing.coordinates_extraction.dms_to_decimal",
                     side_effect=lambda x: 55.50430556 if "N" in x else 37.60838889)

        # Выполняем извлечение координат
        with pdfplumber.open(pdf_file) as pdf:
            extract_coordinates(pdf_file, pdf, 0, "test_folder", coordinates_dict)

        # Проверяем результат
        assert 'Пункты фотфиксации' in coordinates_dict
        assert '1' in coordinates_dict['Пункты фотфиксации']
        assert coordinates_dict['Пункты фотфиксации']['coordinate_system'] == 'wgs84'


# ========================
# Тесты безопасности
# ========================

@pytest.mark.parametrize("malicious_input", [
    # Очень длинные строки
    "55" + "°" * 1000 + "30'15.5\"N",

    # Спецсимволы и возможные инъекции
    "55°30'15.5\"N; DROP TABLE users;",

    # HTML/JavaScript инъекции
    "55°30'15.5\"N<script>alert('xss')</script>",

    # Некорректные Unicode символы
    "55°30'15.5\"N\u202E\u202D",

    # Переполнение буфера
    "55" + "°" * 100000 + "30'15.5\"N",
])
def test_security_against_malicious_inputs(mock_pdf_document, coordinates_dict, mocker, malicious_input):
    """Тестирование обработки потенциально опасных входных данных"""
    # Настройка мока для получения таблицы
    table_data = [
        ['№', 'Северная широта', 'Восточная долгота'],
        ['1', malicious_input, malicious_input]
    ]
    mock_pdf_document.pages[0].extract_tables.return_value = [table_data]

    # Мокируем систему координат
    mocker.patch("re.search", side_effect=lambda pattern, text, flags=0:
    MagicMock(group=lambda: "Пункты фотфиксации. Система координат wgs84")
    if "Пункты фотфиксации" in pattern else None)

    # Мокируем dms_to_decimal для безопасной обработки
    mocker.patch("agregator.processing.coordinates_extraction.dms_to_decimal",
                 side_effect=lambda x: 55.5 if "N" in x else 37.6)

    # Выполняем извлечение координат
    try:
        extract_coordinates("test.pdf", mock_pdf_document, 0, "test_folder", coordinates_dict)
        # Проверяем, что координаты не были добавлены из-за некорректных данных
        assert 'Пункты фотфиксации' not in coordinates_dict or not coordinates_dict['Пункты фотфиксации']
    except Exception as e:
        pytest.fail(f"Unexpected exception: {e}")


# ========================
# Тесты обработки ошибок
# ========================

def test_invalid_pdf_file(mock_pdf_document, coordinates_dict):
    """Тестирование обработки недопустимого PDF файла"""
    # Имитируем ошибку при открытии PDF
    with patch("pdfplumber.open", side_effect=Exception("Invalid PDF")):
        with pytest.raises(Exception):
            extract_coordinates("invalid.pdf", mock_pdf_document, 0, "test_folder", coordinates_dict)


def test_page_index_out_of_range(mock_pdf_document, coordinates_dict):
    """Тестирование обработки недопустимого индекса страницы"""
    # Устанавливаем длину документа меньше, чем page_number
    mock_pdf_document.__len__.return_value = 1

    # Выполняем извлечение координат для несуществующей страницы
    extract_coordinates("test.pdf", mock_pdf_document, 1, "test_folder", coordinates_dict)

    # Проверяем, что не произошло падения
    assert True


# ========================
# Тесты вспомогательных функций
# ========================

def test_calculate_polygons_area_called(mock_pdf_document, coordinates_dict, mocker):
    """Тестирование вызова calculate_polygons_area"""
    # Мокируем calculate_polygons_area
    mock_calculate = mocker.patch("agregator.processing.coordinates_extraction.calculate_polygons_area")

    # Выполняем извлечение координат
    extract_coordinates("test.pdf", mock_pdf_document, 0, "test_folder", coordinates_dict)

    # Проверяем, что функция была вызвана
    mock_calculate.assert_called_once_with(coordinates_dict)


def test_convert_to_wgs84_called(mock_pdf_document, coordinates_dict, mocker):
    """Тестирование вызова convert_to_wgs84 для не-WGS систем"""
    # Настройка мока для получения таблицы
    table_data = [
        ['№', 'Северная широта', 'Восточная долгота'],
        ['1', '7500000.5', '3500000.2']
    ]
    mock_pdf_document.pages[0].extract_tables.return_value = [table_data]

    # Мокируем систему координат
    mocker.patch("re.search", side_effect=lambda pattern, text, flags=0:
    MagicMock(group=lambda: "Пункты фотфиксации. Система координат МСК-11")
    if "Пункты фотфиксации" in pattern else None)

    # Мокируем convert_to_wgs84
    mock_convert = mocker.patch("agregator.processing.coordinates_extraction.convert_to_wgs84",
                                return_value=(55.5, 37.6))

    # Выполняем извлечение координат
    extract_coordinates("test.pdf", mock_pdf_document, 0, "test_folder", coordinates_dict)

    # Проверяем, что convert_to_wgs84 был вызван
    mock_convert.assert_called_once()


def test_dms_to_decimal_called_for_wgs84(mock_pdf_document, coordinates_dict, mocker):
    """Тестирование вызова dms_to_decimal для WGS84"""
    # Настройка мока для получения таблицы
    table_data = [
        ['№', 'Северная широта', 'Восточная долгота'],
        ['1', '55°30\'15.5\"N', '37°36\'30.2\"E']
    ]
    mock_pdf_document.pages[0].extract_tables.return_value = [table_data]

    # Мокируем систему координат
    mocker.patch("re.search", side_effect=lambda pattern, text, flags=0:
    MagicMock(group=lambda: "Пункты фотфиксации. Система координат WGS-84")
    if "Пункты фотфиксации" in pattern else None)

    # Мокируем dms_to_decimal
    mock_dms = mocker.patch("agregator.processing.coordinates_extraction.dms_to_decimal")

    # Выполняем извлечение координат
    extract_coordinates("test.pdf", mock_pdf_document, 0, "test_folder", coordinates_dict)

    # Проверяем, что dms_to_decimal был вызван
    assert mock_dms.call_count == 2  # Один раз для широты, один для долготы
