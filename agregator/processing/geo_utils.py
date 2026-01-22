import math
import re
import traceback

from pyproj import Proj, transform

from agregator.processing.utils import str_is_float

COORDINATE_SYSTEMS = [
    r'wgs.*?\d+',
    r'мск.*?\d+',
    r'гск.*?\d+',
]
COORDINATE_MARKS = {
    ('север', 'вост'): False,
    ('широт', 'долг'): False,
    ('x', 'y'): False,
    ('n', 'e'): False,
}
COORDINATE_TYPES = [
    r'[NS]+\d+°\s*\d+\'\s*\d+[\.,]\d+"|\d+°\s*\d+\'\s*\d+[\.,]\d+"[СЮ]+',
    r'[EW]+\d+°\s*\d+\'\s*\d+[\.,]\d+"|\d+°\s*\d+\'\s*\d+[\.,]\d+"[ВЗ]+',
    r'\d+°\s*\d+\'\s*\d+[\.,]\d+"',

    r'\d+[.,]+\d+',
]

projections = {
    "wgs84": Proj(proj='latlong', datum='WGS84'),
    "мск162": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=78 +k=1 +x_0=62728.20 +y_0=-7546013.80 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск163": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=81 +k=1 +x_0=65425.70 +y_0=-7434483.20 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск164": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=84 +k=1 +x_0=86209.80 +y_0=-6542783.50 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск165": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=87 +k=1 +x_0=105295.80 +y_0=-5652185.00 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск166": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=90 +k=1 +x_0=107543.30 +y_0=-5540944.50 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск167": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=93 +k=1 +x_0=106797.80 +y_0=-5578022.50 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск168": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=96 +k=1 +x_0=108285.20 +y_0=-5503868.60 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск169": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=99 +k=1 +x_0=117308.60 +y_0=-5503868.60 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск170": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=102 +k=1 +x_0=90338.90 +y_0=-6357146.10 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск171": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=105 +k=1 +x_0=87870.50 +y_0=-6468522.70 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск24зона1": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=81.51666667 +k=1 +x_0=1500000 +y_0=-5416586.442 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск24зона2": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=87.51666667 +k=1 +x_0=2500000 +y_0=-5416586.442 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск24зона3": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=93.51666667 +k=1 +x_0=3500000 +y_0=-5416586.442 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск24зона4": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=99.51666667 +k=1 +x_0=4500000 +y_0=-5416586.442 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск24зона5": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=105.51666667 +k=1 +x_0=5500000 +y_0=-5416586.442 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "мск24зона6": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=111.51666667 +k=1 +x_0=6500000 +y_0=-5416586.442 +ellps=krass +towgs84=23.57,-140.95,-79.8,0,0.35,0.79,-0.22 +units=m +no_defs'),
    "гск2011": Proj(
        '+proj=tmerc +lat_0=0 +lon_0=81 +k=1 +x_0=14500000 +y_0=0 +ellps=GSK2011 +towgs84=0,0,0,0,0,0,0 +units=m +no_defs +type=crs'),
}


def convert_to_wgs84(x, y, system):
    y, x = transform(projections[system], projections['wgs84'], y, x)
    return x, y


def convert_proj4(x, y, init_system, final_system):
    y, x = transform(projections[init_system], projections[final_system], y, x)
    return x, y


def normalize_coordinates(coord: str) -> str:
    coord = coord.strip()
    coord = coord.replace(' 0', ' ').replace(' ', '"')
    coord = coord[1:] if coord[0] == '0' else coord
    return coord


def dms_to_decimal(dms):
    """Преобразует координаты из формата DMS в десятичный формат."""
    dms = dms.replace(',', '.')
    dms = re.sub(r'[^\d°\'".]', '', dms)
    print('!!' + str(dms))
    parts = re.split('[°\'"]+', dms)
    print('!!' + str(parts))

    if len(parts) >= 3 and str_is_float(parts[0]) and str_is_float(parts[1]) and str_is_float(parts[2]):
        degrees = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])
    else:
        return None

    decimal = degrees + minutes / 60 + seconds / 3600
    return decimal


def determine_regional_msk(coords):
    """
    Определяет региональную МСК по координатам WGS84
    Возвращает ключ проекции из словаря

    Логика определения:
    1. Сначала проверяем старые МСК (162-171)
    2. Затем проверяем МСК-24 (более крупные зоны)
    3. Если не попали - расчёт проводится в WGS-84
    """
    if len(coords) != 2:
        return "wgs84"

    latitude, longitude = coords

    # 1. ПРОВЕРКА СТАРЫХ МСК (162-171) - 3-градусные зоны
    # МСК-162: 78° в.д. (Западная Сибирь)
    if 76.5 <= longitude < 79.5 and 50 <= latitude <= 60:
        return "мск162"

    # МСК-163: 81° в.д. (Западная Сибирь/Урал)
    elif 79.5 <= longitude < 82.5 and 50 <= latitude <= 60:
        return "мск163"

    # МСК-164: 84° в.д. (Центральная Сибирь)
    elif 82.5 <= longitude < 85.5 and 50 <= latitude <= 60:
        return "мск164"

    # МСК-165: 87° в.д. (Центральная Сибирь)
    elif 85.5 <= longitude < 88.5 and 50 <= latitude <= 60:
        return "мск165"

    # МСК-166: 90° в.д. (Восточная Сибирь)
    elif 88.5 <= longitude < 91.5 and 50 <= latitude <= 60:
        return "мск166"

    # МСК-167: 93° в.д. (Восточная Сибирь)
    elif 91.5 <= longitude < 94.5 and 50 <= latitude <= 60:
        return "мск167"

    # МСК-168: 96° в.д. (Восточная Сибирь/Дальний Восток)
    elif 94.5 <= longitude < 97.5 and 50 <= latitude <= 60:
        return "мск168"

    # МСК-169: 99° в.д. (Дальний Восток)
    elif 97.5 <= longitude < 100.5 and 50 <= latitude <= 60:
        return "мск169"

    # МСК-170: 102° в.д. (Дальний Восток)
    elif 100.5 <= longitude < 103.5 and 50 <= latitude <= 60:
        return "мск170"

    # МСК-171: 105° в.д. (Дальний Восток)
    elif 103.5 <= longitude < 106.5 and 50 <= latitude <= 60:
        return "мск171"

    # 2. ПРОВЕРКА МСК-24 ЗОН (6-градусные зоны)
    if 78 <= longitude < 84:
        return "мск24зона1"  # 78° - 84° в.д.
    elif 84 <= longitude < 90:
        return "мск24зона2"  # 84° - 90° в.д.
    elif 90 <= longitude < 96:
        return "мск24зона3"  # 90° - 96° в.д.
    elif 96 <= longitude < 102:
        return "мск24зона4"  # 96° - 102° в.д.
    elif 102 <= longitude < 108:
        return "мск24зона5"  # 102° - 108° в.д.
    elif 108 <= longitude < 114:
        return "мск24зона6"  # 108° - 114° в.д.

    return "wgs84"


def wgs84_polygon_area(coords):
    """
    Вычисляет площадь полигона в WGS-84 (широта, долгота).
    Возвращает площадь в квадратных метрах.
    """
    R = 6378137  # Радиус Земли в метрах
    circle = R * 2 * math.pi  # Окружность
    coords_x_y = []
    area = []
    n = len(coords)

    first_lat = first_lon = None

    if n < 3:
        return 0.0

    for i in range(n):
        if len(coords[i]) != 2:
            continue
        elif None in coords[i] or None in coords[(i + 1) % n] or len(coords[i]) == 0 or len(coords[(i + 1) % n]) == 0:
            continue

        lat1, lon1 = coords[i]
        lat2, lon2 = coords[(i + 1) % n]

        if i == 0:
            first_lat = lat1
            first_lon = lon1

        # Переводим градусы в радианы
        # lat1_rad = math.radians(lat1)
        # lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        # lon2_rad = math.radians(lon2)

        y = (lat2 - first_lat) / 360 * circle
        x = (lon2 - first_lon) / 360 * circle * math.cos(lat2_rad)

        coords_x_y.append([x, y])
        if i != 0:
            # local_area = ((y[i-1] * x[i]) - (x[i-1] * y[i])) / 2
            local_area = ((coords_x_y[i - 1][1] * coords_x_y[i][0]) - (coords_x_y[i - 1][0] * coords_x_y[i][1])) / 2
            area.append(local_area)

    return sum(area)


def msk_polygon_area(coords, coordinates_system):
    """
    Вычисляет площадь полигона в МСК (широта, долгота).
    Возвращает площадь в квадратных метрах.
    """
    area = []
    n = len(coords)

    if n < 3:
        return 0.0

    for i in range(n):
        if len(coords[i]) != 2:
            continue
        elif None in coords[i]:
            continue

        lat1, lon1 = convert_proj4(coords[i][0], coords[i][1], 'wgs84', coordinates_system)
        lat2, lon2 = convert_proj4(coords[(i + 1) % n][0], coords[(i + 1) % n][1], 'wgs84', coordinates_system)

        local_area = (lat2 + lat1) * (lon2 - lon1) / 2
        area.append(local_area)

    return sum(area)


def calculate_polygons_area(coordinates: dict):
    for key in coordinates.keys():
        try:
            if any([catalog_type in key.lower() for catalog_type in ('каталог', 'участок')]) and 'coordinate_system' in \
                    coordinates[key] and coordinates[key][
                'coordinate_system'] == 'wgs84':
                if sum(1 for elem in coordinates[key] if elem not in {'coordinate_system', 'area'}) > 2:
                    coordinates_extracted = [[float(coord) for coord in value if str_is_float(coord)] for key, value in
                                             list(coordinates[key].items()) if key not in ('coordinate_system', 'area')]
                    coordinates_system = [determine_regional_msk(elem) for elem in coordinates_extracted]
                    print('all area coordinates_system: ' + str(coordinates_system))
                    coordinates_system = coordinates_system[0] if all(
                        [coordinates_system[i] == coordinates_system[i + 1] for i in
                         range(len(coordinates_system) - 1)]) and coordinates_system[0] else 'wgs84'
                    print('area coordinates_system: ' + coordinates_system)
                    if coordinates_system == 'wgs84':
                        coordinates[key]['area'] = wgs84_polygon_area(coordinates_extracted)
                    else:
                        coordinates[key]['area'] = msk_polygon_area(coordinates_extracted, coordinates_system)
                elif 'area' in coordinates[key]:
                    del coordinates[key]['area']
        except Exception as e:
            print(f'Ошибка при обработке координат: {e}')
            traceback.print_exc()
            continue
