import math


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
