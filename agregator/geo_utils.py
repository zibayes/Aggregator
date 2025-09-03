import math


def wgs84_polygon_area(coords):
    """
    Вычисляет площадь полигона в WGS-84 (широта, долгота).
    Возвращает площадь в квадратных метрах.
    """
    R = 6371000  # Радиус Земли в метрах
    area = 0.0
    n = len(coords)

    for i in range(n):
        lat1, lon1 = coords[i]
        lat2, lon2 = coords[(i + 1) % n]

        # Переводим градусы в радианы
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Формула Гаусса для площади сферического многоугольника
        area += (lon2_rad - lon1_rad) * (2 + math.sin(lat1_rad) + math.sin(lat2_rad))

    area = abs(area * R ** 2 / 2)
    return area


def calculate_polygons_area(coordinates: dict):
    for key in coordinates.keys():
        if any([catalog_type in key.lower() for catalog_type in ('каталог', 'участок')]) and 'coordinate_system' in \
                coordinates[key] and coordinates[key][
            'coordinate_system'] == 'wgs84':
            if sum(1 for elem in coordinates[key] if elem not in {'coordinate_system', 'area'}) > 2:
                coordinates[key]['area'] = wgs84_polygon_area(
                    [[float(coord) for coord in value if is_float(coord)] for key, value in
                     list(coordinates[key].items()) if
                     key not in ('coordinate_system', 'area')])
            elif 'area' in coordinates[key]:
                del coordinates[key]['area']


def is_float(s):
    try:
        float(s)
        return True
    except ValueError:
        return False
