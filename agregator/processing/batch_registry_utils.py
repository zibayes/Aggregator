import pandas as pd
import os
import logging
from typing import Dict, Optional, Any
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)


class RegistryManager:
    """Менеджер для работы с реестром XLSX"""

    def __init__(self, registry_path: str):
        self.registry_path = registry_path
        self.df = None
        self._load_registry()

    def _load_registry(self):
        """Загружает реестр из XLSX файла"""
        try:
            if os.path.exists(self.registry_path):
                self.df = pd.read_excel(self.registry_path, engine='openpyxl')
                logger.info(f"Реестр загружен: {len(self.df)} записей")
            else:
                logger.warning(f"Файл реестра не найден: {self.registry_path}")
                self.df = pd.DataFrame()
        except Exception as e:
            logger.error(f"Ошибка загрузки реестра: {e}")
            self.df = pd.DataFrame()

    def find_by_filename(self, filename: str) -> Optional[Dict[str, Any]]:
        """Находит запись в реестре по имени файла"""
        if self.df is None or self.df.empty:
            return None

        # Пробуем разные варианты сопоставления
        basename = os.path.splitext(filename)[0]

        # По полному имени файла
        match = self.df[self.df['Имя файла'] == filename]
        if not match.empty:
            return match.iloc[0].to_dict()

        # По имени без расширения
        match = self.df[self.df['Имя файла'].str.startswith(basename, na=False)]
        if not match.empty:
            return match.iloc[0].to_dict()

        # По номеру акта в имени файла
        import re
        act_number = re.search(r'№?\s*(\d+[/-]?\d*)', filename)
        if act_number:
            act_num = act_number.group(1)
            # Ищем в колонке с номером акта
            for col in ['Номер акта', 'Номер', 'Акт №']:
                if col in self.df.columns:
                    match = self.df[self.df[col].astype(str).str.contains(act_num, na=False)]
                    if not match.empty:
                        return match.iloc[0].to_dict()

        logger.info(f"Запись для файла {filename} не найдена в реестре")
        return None


class KMLParser:
    """Парсер KML файлов для извлечения координат"""

    @staticmethod
    def parse_kml_file(kml_path: str) -> Dict[str, Any]:
        """Парсит KML файл и возвращает структуру координат"""
        try:
            if not os.path.exists(kml_path):
                return {}

            tree = ET.parse(kml_path)
            root = tree.getroot()

            # Namespace для KML
            ns = {'kml': 'http://www.opengis.net/kml/2.2'}

            coordinates = {}

            # Ищем Placemarks
            for placemark in root.findall('.//kml:Placemark', ns):
                name_elem = placemark.find('kml:name', ns)
                if name_elem is None:
                    continue

                name = name_elem.text.strip() if name_elem.text else "Без имени"

                # Полигоны
                polygon = placemark.find('.//kml:Polygon', ns)
                if polygon is not None:
                    coords_elem = polygon.find('.//kml:coordinates', ns)
                    if coords_elem is not None and coords_elem.text:
                        coords = KMLParser._parse_coordinates(coords_elem.text)
                        if 'Полигоны' not in coordinates:
                            coordinates['Полигоны'] = {}
                        coordinates['Полигоны'][name] = coords

                # Линии
                linestring = placemark.find('.//kml:LineString', ns)
                if linestring is not None:
                    coords_elem = linestring.find('.//kml:coordinates', ns)
                    if coords_elem is not None and coords_elem.text:
                        coords = KMLParser._parse_coordinates(coords_elem.text)
                        if 'Линии' not in coordinates:
                            coordinates['Линии'] = {}
                        coordinates['Линии'][name] = coords

                # Точки
                point = placemark.find('.//kml:Point', ns)
                if point is not None:
                    coords_elem = point.find('.//kml:coordinates', ns)
                    if coords_elem is not None and coords_elem.text:
                        coords = KMLParser._parse_coordinates(coords_elem.text)
                        if 'Точки' not in coordinates:
                            coordinates['Точки'] = {}
                        coordinates['Точки'][name] = coords[0] if coords else None

            logger.info(f"Из KML {kml_path} извлечено: {len(coordinates)} типов объектов")
            return coordinates

        except Exception as e:
            logger.error(f"Ошибка парсинга KML {kml_path}: {e}")
            return {}

    @staticmethod
    def _parse_coordinates(coords_text: str) -> list:
        """Парсит строку координат из KML"""
        coordinates = []
        for coord in coords_text.strip().split():
            parts = coord.split(',')
            if len(parts) >= 2:
                try:
                    lon = float(parts[0])
                    lat = float(parts[1])
                    coordinates.append([lon, lat])
                except ValueError:
                    continue
        return coordinates

    @staticmethod
    def find_kml_for_pdf(pdf_path: str) -> Optional[str]:
        """Находит KML файл для PDF файла в новой структуре"""
        pdf_dir = Path(pdf_path).parent
        pdf_name = Path(pdf_path).stem

        # Сначала ищем в той же папке (новая структура)
        possible_names = [
            f"{pdf_name}.kml",
            f"{pdf_name}.KML",
            f"{pdf_name}_coordinates.kml",
            f"{pdf_name}_координаты.kml"
        ]

        for name in possible_names:
            kml_path = pdf_dir / name
            if kml_path.exists():
                return str(kml_path)

        # Если не нашли, ищем в родительской папке (старая структура)
        parent_dir = pdf_dir.parent
        for name in possible_names:
            kml_path = parent_dir / name
            if kml_path.exists():
                return str(kml_path)

        # Ищем любой KML в папке PDF
        for kml_file in pdf_dir.glob("*.kml"):
            return str(kml_file)

        return None
