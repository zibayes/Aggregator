import pytest
import math
from unittest.mock import patch, MagicMock
from agregator.processing.geo_utils import (
    convert_to_wgs84,
    convert_proj4,
    normalize_coordinates,
    dms_to_decimal,
    determine_regional_msk,
    wgs84_polygon_area,
    msk_polygon_area,
    calculate_polygons_area,
    projections,
)


# ========== convert_to_wgs84 / convert_proj4 ==========
def test_convert_to_wgs84():
    """Проверка конвертации в WGS84"""
    with patch('agregator.processing.geo_utils.transform') as mock_transform:
        # transform возвращает (y, x), а функция возвращает (x, y)
        mock_transform.return_value = (10.0, 20.0)
        x, y = convert_to_wgs84(30, 40, 'мск162')
        mock_transform.assert_called_once_with(
            projections['мск162'],
            projections['wgs84'],
            40, 30
        )
        # функция возвращает (x, y) = (20, 10)
        assert x == 20.0
        assert y == 10.0


def test_convert_proj4():
    """Проверка конвертации между системами"""
    with patch('agregator.processing.geo_utils.transform') as mock_transform:
        mock_transform.return_value = (15.0, 25.0)
        x, y = convert_proj4(35, 45, 'мск162', 'мск163')
        mock_transform.assert_called_once_with(
            projections['мск162'],
            projections['мск163'],
            45, 35
        )
        assert x == 25.0
        assert y == 15.0


# ========== normalize_coordinates ==========
def test_normalize_coordinates():
    """Нормализация строки координат"""
    # исходная строка с пробелами в конце
    assert normalize_coordinates(" 55 45 30 ") == "55\"45\"30"
    assert normalize_coordinates("55 45 30") == "55\"45\"30"


# ========== dms_to_decimal ==========
def test_dms_to_decimal_valid():
    assert dms_to_decimal("55°45'30\"") == pytest.approx(55.7583333333)
    assert dms_to_decimal("55°45'30") == pytest.approx(55.7583333333)  # без кавычек в конце


def test_dms_to_decimal_invalid():
    assert dms_to_decimal("invalid") is None
    assert dms_to_decimal("") is None
    # "55°45'" без секунд должно быть None (len(parts) = 2)
    assert dms_to_decimal("55°45'") is None


def test_dms_to_decimal_with_extra_chars():
    assert dms_to_decimal("55°45'30\"N") == pytest.approx(55.7583333333)


# ========== determine_regional_msk ==========
def test_determine_regional_msk_old_msk():
    test_cases = [
        ((55.0, 77.0), "мск162"),
        ((55.0, 78.0), "мск162"),
        ((55.0, 80.0), "мск163"),
        ((55.0, 83.0), "мск164"),
        ((55.0, 86.0), "мск165"),
        ((55.0, 89.0), "мск166"),
        ((55.0, 92.0), "мск167"),
        ((55.0, 95.0), "мск168"),
        ((55.0, 98.0), "мск169"),
        ((55.0, 101.0), "мск170"),
        ((55.0, 104.0), "мск171"),
        ((55.0, 107.0), "мск24зона5"),
        ((55.0, 76.5), "мск162"),
        ((55.0, 79.5), "мск163"),
        ((55.0, 79.6), "мск163"),
    ]
    for (lat, lon), expected in test_cases:
        assert determine_regional_msk([lat, lon]) == expected


def test_determine_regional_msk_msk24():
    """Определение МСК-24 зон (только там, где нет старых МСК)"""
    test_cases = [
        ((45.0, 80.0), "мск24зона1"),  # широта вне 50-60 → старые не применяются
        ((45.0, 82.0), "мск24зона1"),
        ((45.0, 86.0), "мск24зона2"),
        ((45.0, 88.0), "мск24зона2"),
        ((45.0, 92.0), "мск24зона3"),
        ((45.0, 94.0), "мск24зона3"),
        ((45.0, 98.0), "мск24зона4"),
        ((45.0, 100.0), "мск24зона4"),
        ((45.0, 104.0), "мск24зона5"),
        ((45.0, 106.0), "мск24зона5"),
        ((45.0, 110.0), "мск24зона6"),
        ((45.0, 112.0), "мск24зона6"),
    ]
    for (lat, lon), expected in test_cases:
        assert determine_regional_msk([lat, lon]) == expected


def test_determine_regional_msk_fallback():
    """Fallback на wgs84"""
    assert determine_regional_msk([55.0, 115.0]) == "wgs84"
    assert determine_regional_msk([55.0, 70.0]) == "wgs84"
    assert determine_regional_msk([55.0, 76.0]) == "wgs84"
    # (45,90) – широта вне 50-60, но долгота 90 попадает в МСК-24 → возвращается мск24зона3
    assert determine_regional_msk([45.0, 90.0]) == "мск24зона3"


# ========== wgs84_polygon_area ==========
def test_wgs84_polygon_area_triangle():
    """Площадь треугольника в WGS84 (небольшой)"""
    coords = [
        [0.0, 0.0],
        [0.0, 0.01],
        [0.01, 0.0]
    ]
    area = wgs84_polygon_area(coords)
    # Площадь может быть отрицательной в зависимости от порядка точек
    # Берём модуль и проверяем порядок величины
    assert abs(area) > 600000 and abs(area) < 630000


def test_wgs84_polygon_area_small():
    """Площадь маленького треугольника"""
    coords = [
        [55.0, 83.0],
        [55.0, 83.001],
        [55.001, 83.0]
    ]
    area = wgs84_polygon_area(coords)
    # Должна быть маленькой (в метрах), неотрицательной по модулю
    assert abs(area) < 10000


def test_wgs84_polygon_area_less_than_3_points():
    coords = [[0, 0], [0, 1]]
    assert wgs84_polygon_area(coords) == 0.0


# ========== msk_polygon_area ==========
def test_msk_polygon_area_triangle():
    """Площадь треугольника в МСК (используем мок, чтобы избежать реальной конвертации)"""
    with patch('agregator.processing.geo_utils.convert_proj4') as mock_convert:
        # Мокаем, чтобы вернуть те же координаты, что переданы (в метрах)
        def fake_convert(x, y, *args):
            return x, y

        mock_convert.side_effect = fake_convert
        coords = [
            [0, 0],
            [0, 100],
            [100, 0]
        ]
        area = msk_polygon_area(coords, 'мск162')
        # Площадь может быть отрицательной – берём модуль
        assert abs(area) == 5000.0


def test_msk_polygon_area_less_than_3_points():
    coords = [[0, 0], [0, 100]]
    assert msk_polygon_area(coords, 'мск162') == 0.0


def test_msk_polygon_area_with_none():
    """Точки с None не обрабатываются корректно, возникает TypeError"""
    coords = [
        [0, 0],
        [None, 0],
        [100, 100]
    ]
    with patch('agregator.processing.geo_utils.convert_proj4') as mock_convert:
        def fake_convert(x, y, *args):
            return x, y

        mock_convert.side_effect = fake_convert
        with pytest.raises(TypeError):
            msk_polygon_area(coords, 'мск162')


# ========== calculate_polygons_area ==========
def test_calculate_polygons_area_catalog():
    coordinates = {
        'Каталог координат': {
            'coordinate_system': 'wgs84',
            '1': [55.0, 83.0],
            '2': [55.0, 83.001],
            '3': [55.001, 83.0],
            '4': [55.001, 83.001]
        }
    }
    # Вычисляем площадь, она должна добавиться
    calculate_polygons_area(coordinates)
    assert 'area' in coordinates['Каталог координат']
    assert isinstance(coordinates['Каталог координат']['area'], (int, float))


def test_calculate_polygons_area_catalog_with_coordinate_system_already():
    coordinates = {
        'Каталог координат': {
            'coordinate_system': 'wgs84',
            'area': 12345.0,
            '1': [55.0, 83.0],
            '2': [55.0, 83.001],
            '3': [55.001, 83.0]
        }
    }
    # Уже есть 'area', она должна удалиться и пересчитаться
    calculate_polygons_area(coordinates)
    assert 'area' in coordinates['Каталог координат']
    assert coordinates['Каталог координат']['area'] != 12345.0


def test_calculate_polygons_area_less_than_3_points():
    coordinates = {
        'Каталог координат': {
            'coordinate_system': 'wgs84',
            '1': [55.0, 83.0],
            '2': [55.0, 83.001]
        }
    }
    calculate_polygons_area(coordinates)
    assert 'area' not in coordinates['Каталог координат']


def test_calculate_polygons_area_wgs84_fallback():
    """Если не удалось определить систему координат, используем wgs84"""
    coordinates = {
        'Каталог координат': {
            'coordinate_system': 'wgs84',
            '1': [55.0, 83.0],
            '2': [55.0, 83.001],
            '3': [55.001, 83.0]
        }
    }
    calculate_polygons_area(coordinates)
    assert 'area' in coordinates['Каталог координат']


def test_calculate_polygons_area_other_key():
    """Другие ключи (не 'Каталог координат') не обрабатываются"""
    coordinates = {
        'Центр объекта': {
            'coordinate_system': 'wgs84',
            'point1': [55.0, 83.0]
        }
    }
    calculate_polygons_area(coordinates)
    # Ничего не должно измениться
    assert 'area' not in coordinates['Центр объекта']


def test_calculate_polygons_area_invalid_points():
    """Невалидные точки пропускаются, для расчёта остаётся 2 точки -> area не добавляется"""
    coordinates = {
        'Каталог координат': {
            'coordinate_system': 'wgs84',
            '1': [55.0, 83.0],
            '2': [None, 83.001],
            '3': [55.001, None],
            '4': [55.001, 83.001]
        }
    }
    calculate_polygons_area(coordinates)
    # Две валидные точки (1 и 4) -> недостаточно для площади, поэтому area не добавляется
    assert 'area' not in coordinates['Каталог координат']
