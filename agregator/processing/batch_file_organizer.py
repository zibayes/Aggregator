import os
import shutil
import logging
from pathlib import Path
import re
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class FileOrganizer:
    """Организатор файловой структуры для отчетов"""

    # Корневые папки для разных типов файлов (абсолютные пути)
    ROOT_FOLDERS = {
        'act': '/app/uploaded_files/Акты ГИКЭ',
        'scientific_report': '/app/uploaded_files/Научные отчёты',
        'tech_report': '/app/uploaded_files/Научно-технические отчёты'
    }

    @staticmethod
    def clean_filename(name: str, max_length: int = 100) -> str:
        """
        Очищает имя файла от недопустимых символов и ограничивает длину
        """
        # Заменяем недопустимые символы
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')

        # Удаляем множественные пробелы и подчеркивания
        name = re.sub(r'\s+', ' ', name)
        name = re.sub(r'_+', '_', name)

        # Обрезаем до максимальной длины
        if len(name) > max_length:
            name = name[:max_length].rstrip(' ._')

        return name

    @staticmethod
    def should_reorganize(file_path: str, root_folder: str) -> bool:
        """
        Проверяет, нужно ли реорганизовывать файл
        """
        file_path = Path(file_path)
        root_path = Path(root_folder)

        # Проверяем, находится ли файл внутри корневой папки
        try:
            relative_path = file_path.relative_to(root_path)
        except ValueError:
            # Файл не находится в корневой папке - не реорганизуем
            logger.debug(f"Файл {file_path} не находится в корневой папке {root_folder}")
            return False

        path_parts = relative_path.parts

        # Если файл в корне или на одном уровне вложенности - реорганизуем
        if len(path_parts) <= 2:  # [file] или [year/file]
            logger.debug(f"Файл {file_path} находится на уровне {len(path_parts)}, реорганизуем")
            return True

        # Если в той же папке есть другие PDF файлы - реорганизуем
        parent_dir = file_path.parent
        if parent_dir != root_path:
            try:
                pdf_files = list(parent_dir.glob('*.pdf'))
                if len(pdf_files) > 1:
                    logger.debug(f"В папке {parent_dir} найдено {len(pdf_files)} PDF файлов, реорганизуем")
                    return True
            except Exception as e:
                logger.warning(f"Ошибка при проверке PDF файлов в {parent_dir}: {e}")

        logger.debug(f"Файл {file_path} не требует реорганизации")
        return False

    @staticmethod
    def create_organized_structure(file_path: str, file_type: str) -> Tuple[str, bool]:
        """
        Создает организованную структуру папок и перемещает файлы
        Возвращает (новый_путь_к_файлу, был_ли_файл_перемещен)
        """
        try:
            original_path = Path(file_path)
            root_folder = FileOrganizer.ROOT_FOLDERS.get(file_type)

            if not root_folder:
                logger.warning(f"Неизвестный тип файла: {file_type}")
                return file_path, False

            if not original_path.exists():
                logger.warning(f"Файл не существует: {file_path}")
                return file_path, False

            # Проверяем, нужно ли реорганизовывать
            if not FileOrganizer.should_reorganize(file_path, root_folder):
                return file_path, False

            # Создаем имя папки на основе имени файла
            file_stem = original_path.stem
            clean_folder_name = FileOrganizer.clean_filename(file_stem)

            # Определяем целевую папку
            relative_to_root = Path(file_path).relative_to(root_folder)
            if len(relative_to_root.parts) > 1:
                # Сохраняем структуру вложенности (например, год)
                parent_folder = relative_to_root.parts[0]
                target_dir = Path(root_folder) / parent_folder / clean_folder_name
            else:
                target_dir = Path(root_folder) / clean_folder_name

            # Создаем целевую папку
            target_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Создана папка: {target_dir}")

            # Новый путь для PDF файла
            new_pdf_path = target_dir / original_path.name

            # Перемещаем PDF файл, если он еще не в целевой папке
            moved_pdf = False
            if new_pdf_path != original_path:
                if new_pdf_path.exists():
                    logger.warning(f"Файл {new_pdf_path} уже существует, пропускаем перемещение")
                else:
                    shutil.move(str(original_path), str(new_pdf_path))
                    moved_pdf = True
                    logger.info(f"Перемещен PDF: {original_path} -> {new_pdf_path}")
            else:
                new_pdf_path = original_path

            # Ищем и перемещаем KML файл
            kml_moved = FileOrganizer._move_kml_file(original_path, target_dir)

            return str(new_pdf_path), (moved_pdf or kml_moved)

        except Exception as e:
            logger.error(f"Ошибка при организации файла {file_path}: {e}")
            return file_path, False

    @staticmethod
    def _move_kml_file(original_pdf_path: Path, target_dir: Path) -> bool:
        """
        Перемещает KML файл, связанный с PDF
        """
        try:
            # Ищем KML файлы с тем же именем
            pdf_stem = original_pdf_path.stem
            original_dir = original_pdf_path.parent

            possible_kml_names = [
                f"{pdf_stem}.kml",
                f"{pdf_stem}.KML",
                f"{pdf_stem}_coordinates.kml",
                f"{pdf_stem}_координаты.kml"
            ]

            for kml_name in possible_kml_names:
                kml_path = original_dir / kml_name
                if kml_path.exists():
                    new_kml_path = target_dir / kml_name
                    if new_kml_path != kml_path:
                        if new_kml_path.exists():
                            logger.warning(f"KML файл {new_kml_path} уже существует, пропускаем перемещение")
                        else:
                            shutil.move(str(kml_path), str(new_kml_path))
                            logger.info(f"Перемещен KML: {kml_path} -> {new_kml_path}")
                            return True

            # Ищем любые KML файлы в исходной папке с похожими именами
            for kml_file in original_dir.glob("*.kml"):
                kml_stem = kml_file.stem
                # Проверяем, связано ли имя KML с именем PDF
                if (pdf_stem in kml_stem or kml_stem in pdf_stem or
                        pdf_stem.replace(' ', '_') in kml_stem or
                        kml_stem.replace(' ', '_') in pdf_stem):
                    new_kml_path = target_dir / kml_file.name
                    if new_kml_path != kml_file:
                        if new_kml_path.exists():
                            logger.warning(f"KML файл {new_kml_path} уже существует, пропускаем перемещение")
                        else:
                            shutil.move(str(kml_file), str(new_kml_path))
                            logger.info(f"Перемещен KML: {kml_file} -> {new_kml_path}")
                            return True

            return False

        except Exception as e:
            logger.error(f"Ошибка при перемещении KML файла: {e}")
            return False

    @staticmethod
    def organize_batch_files(files: list, file_type: str) -> list:
        """
        Организует файлы пакетной обработки
        """
        organized_files = []

        for file_info in files:
            try:
                original_path = file_info['path']
                logger.info(f"Организация файла: {original_path}")

                new_path, was_moved = FileOrganizer.create_organized_structure(
                    original_path, file_type
                )

                # Обновляем информацию о файле
                updated_info = file_info.copy()
                updated_info['path'] = new_path
                updated_info['was_organized'] = was_moved
                updated_info['final_location'] = new_path

                organized_files.append(updated_info)

                if was_moved:
                    logger.info(f"Файл организован: {original_path} -> {new_path}")
                else:
                    logger.info(f"Файл не требует организации: {original_path}")

            except Exception as e:
                logger.error(f"Ошибка организации файла {file_info['path']}: {e}")
                # В случае ошибки оставляем оригинальный путь
                file_info['was_organized'] = False
                file_info['final_location'] = file_info['path']
                organized_files.append(file_info)

        return organized_files
