import math
import re
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

    degrees = float(parts[0])
    minutes = float(parts[1])
    seconds = float(parts[2])

    decimal = degrees + minutes / 60 + seconds / 3600
    return decimal


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
        elif None in coords[i]:
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


def calculate_polygons_area(coordinates: dict):
    for key in coordinates.keys():
        if any([catalog_type in key.lower() for catalog_type in ('каталог', 'участок')]) and 'coordinate_system' in \
                coordinates[key] and coordinates[key][
            'coordinate_system'] == 'wgs84':
            if sum(1 for elem in coordinates[key] if elem not in {'coordinate_system', 'area'}) > 2:
                coordinates[key]['area'] = wgs84_polygon_area(
                    [[float(coord) for coord in value if str_is_float(coord)] for key, value in
                     list(coordinates[key].items()) if
                     key not in ('coordinate_system', 'area')])
            elif 'area' in coordinates[key]:
                del coordinates[key]['area']
