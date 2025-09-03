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
        lon1, lat1 = coords[i]
        lon2, lat2 = coords[(i + 1) % n]

        # Переводим градусы в радианы
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)

        # Формула Гаусса для площади сферического многоугольника
        area += (lon2_rad - lon1_rad) * (2 + math.sin(lat1_rad) + math.sin(lat2_rad))

    area = abs(area * R ** 2 / 2)
    return area
