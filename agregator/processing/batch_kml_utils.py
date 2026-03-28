# kml_parser.py
import json
import os
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import logging

logger = logging.getLogger(__name__)


class KMLProcessor:
    """Универсальный обработчик KML/KMZ файлов для извлечения и категоризации координат"""

    def __init__(self):
        self.namespaces = {
            'kml': 'http://www.opengis.net/kml/2.2',
            'google': 'http://earth.google.com/kml/2.2'
        }

    def process_kml_file(self, kml_path: str) -> Dict[str, Any]:
        """Основной метод для обработки KML файла"""
        if not os.path.exists(kml_path):
            logger.warning(f"Файл не найден: {kml_path}")
            return {}

        try:
            tree = ET.parse(kml_path)
            root = tree.getroot()

            # Определяем namespace из корневого элемента
            root_tag = root.tag
            if '}' in root_tag:
                namespace_uri = root_tag.split('}')[0].split('{')[1]
                self.namespaces = {'kml': namespace_uri}

            result = {}

            # Рекурсивно обрабатываем все элементы
            self._process_element(root, [], result)

            logger.info(f"Успешно обработан KML: {kml_path}, найдено категорий: {len(result)}")
            return result

        except Exception as e:
            logger.error(f"Ошибка обработки KML {kml_path}: {e}")
            return {}

    def _find_element(self, element, tag_name: str):
        """Ищет элемент с учетом различных namespace"""
        for ns_prefix, ns_uri in self.namespaces.items():
            found = element.find(f'.//{{{ns_uri}}}{tag_name}')
            if found is not None:
                return found

        found = element.find(f'.//{tag_name}')
        if found is not None:
            return found

        for child in element.iter():
            tag = self._get_tag_without_namespace(child.tag)
            if tag == tag_name:
                return child

        return None

    def _find_all_elements(self, element, tag_name: str):
        """Ищет все элементы с учетом различных namespace"""
        results = []

        for ns_prefix, ns_uri in self.namespaces.items():
            found = element.findall(f'.//{{{ns_uri}}}{tag_name}')
            results.extend(found)

        found = element.findall(f'.//{tag_name}')
        results.extend(found)

        for child in element.iter():
            tag = self._get_tag_without_namespace(child.tag)
            if tag == tag_name:
                results.append(child)

        return results

    def _process_element(self, element, folder_path: List[str], result: Dict[str, Any]):
        """Рекурсивно обрабатывает элементы KML"""
        tag = self._get_tag_without_namespace(element.tag)

        if tag == 'Folder' or tag == 'Document':
            folder_name_elem = self._find_element(element, 'name')
            folder_name = folder_name_elem.text.strip() if folder_name_elem is not None and folder_name_elem.text else "Без имени"

            new_folder_path = folder_path + [folder_name]
            for child in element:
                self._process_element(child, new_folder_path, result)

        elif tag == 'Placemark':
            self._process_placemark(element, folder_path, result)
        else:
            for child in element:
                self._process_element(child, folder_path, result)

    def _process_placemark(self, placemark, folder_path: List[str], result: Dict[str, Any]):
        """Обрабатывает Placemark и распределяет по категориям"""
        name_elem = self._find_element(placemark, 'name')
        name = name_elem.text.strip() if name_elem is not None and name_elem.text else "Без имени"

        # Определяем специальные категории на основе ВСЕХ папок в пути
        is_shurf = any('шурф' in folder.lower() for folder in folder_path if folder)
        is_photo = any('фото' in folder.lower() for folder in folder_path if folder)

        # Обрабатываем геометрии с учетом специальных категорий
        self._process_geometry(placemark, name, folder_path, is_shurf, is_photo, result)

    def _process_geometry(self, placemark, name: str, folder_path: List[str], is_shurf: bool, is_photo: bool,
                          result: Dict[str, Any]):
        """Обрабатывает различные типы геометрий с учетом категорий"""

        # Полигоны - ВЫНОСИМ ОТДЕЛЬНО В КАТАЛОГ КООРДИНАТ
        polygons = self._find_all_elements(placemark, 'Polygon')
        if polygons:
            for polygon in polygons:
                poly_coords = self._extract_coordinates(polygon)
                if poly_coords:
                    # Получаем координаты полигона в правильном порядке
                    poly_coords_swapped = [self._swap_coordinates(coord) for coord in poly_coords]

                    # Ищем точки в этой же папке для проверки совпадений
                    matching_points = {}
                    remaining_points = {}

                    # Проверяем все точки в текущей папке (если она есть)
                    current_folder = folder_path[-1] if folder_path else None
                    if current_folder and current_folder in result:
                        for point_name, point_coords in result[current_folder].items():
                            if point_name not in ["coordinate_system", "area"]:
                                # Проверяем совпадение координат с полигоном
                                if any(self._coordinates_match(point_coords, poly_coord) for poly_coord in
                                       poly_coords_swapped):
                                    matching_points[point_name] = point_coords
                                else:
                                    remaining_points[point_name] = point_coords

                    # Создаем категорию "Каталог координат" + название полигона
                    catalog_name = f"Каталог координат {name}" if name != "Без имени" else "Каталог координат"

                    if catalog_name not in result:
                        result[catalog_name] = {"coordinate_system": "wgs84"}

                    # Если все точки совпали - используем существующие точки
                    if len(matching_points) == len(poly_coords_swapped):
                        for point_name, point_coords in matching_points.items():
                            result[catalog_name][point_name] = point_coords

                        # Удаляем совпавшие точки из исходной папки
                        if current_folder and current_folder in result:
                            result[current_folder] = remaining_points
                            if not any(k not in ["coordinate_system", "area"] for k in result[current_folder].keys()):
                                del result[current_folder]

                    else:
                        # Если не все точки совпали - создаем новые пронумерованные точки из полигона
                        for i, coord in enumerate(poly_coords_swapped, 1):
                            result[catalog_name][str(i)] = coord

                        # Удаляем совпавшие точки из исходной папки
                        if current_folder and current_folder in result:
                            result[current_folder] = remaining_points
                            if not any(k not in ["coordinate_system", "area"] for k in result[current_folder].keys()):
                                del result[current_folder]

            return

        # Линии - аналогичная логика
        linestrings = self._find_all_elements(placemark, 'LineString')
        if linestrings:
            for linestring in linestrings:
                line_coords = self._extract_coordinates(linestring)
                if line_coords:
                    line_coords_swapped = [self._swap_coordinates(coord) for coord in line_coords]

                    # Аналогичная проверка совпадений для линий
                    current_folder = folder_path[-1] if folder_path else None
                    matching_points = {}
                    remaining_points = {}

                    if current_folder and current_folder in result:
                        for point_name, point_coords in result[current_folder].items():
                            if point_name not in ["coordinate_system", "area"]:
                                if any(self._coordinates_match(point_coords, line_coord) for line_coord in
                                       line_coords_swapped):
                                    matching_points[point_name] = point_coords
                                else:
                                    remaining_points[point_name] = point_coords

                    catalog_name = f"Каталог координат {name}" if name != "Без имени" else "Каталог координат"

                    if catalog_name not in result:
                        result[catalog_name] = {"coordinate_system": "wgs84"}

                    if len(matching_points) == len(line_coords_swapped):
                        for point_name, point_coords in matching_points.items():
                            result[catalog_name][point_name] = point_coords

                        if current_folder and current_folder in result:
                            result[current_folder] = remaining_points
                            if not any(k not in ["coordinate_system", "area"] for k in result[current_folder].keys()):
                                del result[current_folder]
                    else:
                        for i, coord in enumerate(line_coords_swapped, 1):
                            result[catalog_name][str(i)] = coord

                        if current_folder and current_folder in result:
                            result[current_folder] = remaining_points
                            if not any(k not in ["coordinate_system", "area"] for k in result[current_folder].keys()):
                                del result[current_folder]

            return

        # ТОЧКИ - распределяем по категориям (без изменений)
        points = self._find_all_elements(placemark, 'Point')
        if points:
            for point in points:
                coords = self._extract_coordinates(point)
                if coords:
                    coord = coords[0]
                    swapped_coord = self._swap_coordinates(coord)

                    if is_shurf:
                        if "Шурфы" not in result:
                            result["Шурфы"] = {"coordinate_system": "wgs84"}
                        result["Шурфы"][name] = swapped_coord

                    elif is_photo:
                        if "Пункты фотофиксации" not in result:
                            result["Пункты фотофиксации"] = {"coordinate_system": "wgs84"}
                        result["Пункты фотофиксации"][name] = swapped_coord

                    else:
                        category_name = folder_path[-1] if folder_path else "Другие объекты"
                        if category_name not in result:
                            result[category_name] = {"coordinate_system": "wgs84"}
                        result[category_name][name] = swapped_coord

    def _coordinates_match(self, coord1: List[float], coord2: List[float], tolerance: float = 0.000001) -> bool:
        """Проверяет совпадение координат с заданной точностью"""
        if len(coord1) >= 2 and len(coord2) >= 2:
            return abs(coord1[0] - coord2[0]) < tolerance and abs(coord1[1] - coord2[1]) < tolerance
        return False

    def _swap_coordinates(self, coord: List[float]) -> List[float]:
        """Меняет порядок координат с [долгота, широта] на [широта, долгота]"""
        if len(coord) >= 2:
            return [coord[1], coord[0]]  # Меняем местами: [широта, долгота]
        return coord

    def _extract_coordinates(self, geometry_element) -> List[List[float]]:
        """Извлекает координаты из геометрии"""
        coords_elems = self._find_all_elements(geometry_element, 'coordinates')
        for coords_elem in coords_elems:
            if coords_elem is not None and coords_elem.text:
                return self._parse_coordinates(coords_elem.text)
        return []

    def _parse_coordinates(self, coords_text: str) -> List[List[float]]:
        """Парсит строку координат из KML"""
        coordinates = []
        for coord in coords_text.strip().split():
            parts = coord.split(',')
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    coordinates.append([lon, lat])  # [долгота, широта] - стандарт KML
                except ValueError:
                    continue
        return coordinates

    def _get_tag_without_namespace(self, tag: str) -> str:
        """Удаляет namespace из тега"""
        return tag.split('}')[-1] if '}' in tag else tag

    def process_kmz_file(self, kmz_path: str) -> Dict[str, Any]:
        """Обрабатывает KMZ файл (архив с KML)"""
        try:
            with zipfile.ZipFile(kmz_path, 'r') as zip_ref:
                kml_files = [f for f in zip_ref.namelist() if f.lower().endswith('.kml')]
                if not kml_files:
                    logger.warning(f"Не найден KML файл в KMZ архиве: {kmz_path}")
                    return {}

                kml_file = kml_files[0]
                extract_path = Path(kmz_path).parent / f"temp_{Path(kml_file).name}"

                with zip_ref.open(kml_file) as source, open(extract_path, 'wb') as target:
                    target.write(source.read())

                result = self.process_kml_file(str(extract_path))

                try:
                    extract_path.unlink()
                except:
                    pass

                return result

        except Exception as e:
            logger.error(f"Ошибка обработки KMZ {kmz_path}: {e}")
            return {}


class KMLParser:
    """Парсер KML файлов для извлечения координат (совместимый со старым интерфейсом)"""

    @staticmethod
    def parse_kml_file(kml_path: str) -> Dict[str, Any]:
        """Парсит KML файл и возвращает структуру координат"""
        processor = KMLProcessor()

        if kml_path.lower().endswith('.kmz'):
            return processor.process_kmz_file(kml_path)
        else:
            return processor.process_kml_file(kml_path)

    @staticmethod
    def _parse_coordinates(coords_text: str) -> list:
        """Парсит строку координат из KML (для обратной совместимости)"""
        coordinates = []
        for coord in coords_text.strip().split():
            parts = coord.split(',')
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    coordinates.append([lat, lon])  # [широта, долгота] - твой формат
                except ValueError:
                    continue
        return coordinates

    @staticmethod
    def find_kml_for_pdf(pdf_path: str, multiple_files: bool = False) -> Union[Optional[str], Optional[List[str]]]:
        """
        Находит KML/KMZ файл(ы) для PDF файла.

        Аргументы:
            pdf_path (str): путь к PDF-файлу
            multiple_files (bool): если True, возвращает список всех подходящих файлов;
                                   если False, возвращает первый найденный (или None)

        Возвращает:
            Union[str, List[str], None]: если multiple_files=False – строка или None;
                                         если multiple_files=True – список строк или None.
        """
        pdf_dir = Path(pdf_path).parent
        pdf_name = Path(pdf_path).stem

        # Сначала ищем в той же папке (новая структура)
        possible_names = [
            f"{pdf_name}.kml",
            f"{pdf_name}.KML",
            f"{pdf_name}.kmz",
            f"{pdf_name}.KMZ",
            f"{pdf_name}_coordinates.kml",
            f"{pdf_name}_coordinates.kmz",
            f"{pdf_name}_координаты.kml"
            f"{pdf_name}_координаты.kmz"
        ]

        found_files = set()

        # Вспомогательная функция для проверки и добавления
        def add_if_exists(path: Path):
            if path.exists():
                if multiple_files:
                    found_files.add(str(path))
                else:
                    return str(path)
            return None

        # 1. Поиск в той же папке по возможным именам
        for name in possible_names:
            result = add_if_exists(pdf_dir / name)
            if not multiple_files and result is not None:
                return result

        # 2. Поиск в родительской папке по возможным именам
        parent_dir = pdf_dir.parent
        for name in possible_names:
            result = add_if_exists(parent_dir / name)
            if not multiple_files and result is not None:
                return result

        # 3. Fallback: любой KML или KMZ в папке PDF
        for ext in ['*.kml', '*.kmz']:
            for kml_file in pdf_dir.glob(ext):
                if multiple_files:
                    found_files.add(str(kml_file))
                else:
                    return str(kml_file)

        # 4. Если multiple_files=False и ничего не нашли — возвращаем None
        if not multiple_files:
            return None

        # 5. Для multiple_files: возвращаем список или None
        return list(found_files) if found_files else None
