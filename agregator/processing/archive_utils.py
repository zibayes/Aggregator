# import patoolib
import os
import zipfile
import rarfile
import py7zr
import tarfile
import shutil
import hashlib

rarfile.UNRAR_TOOL = '/usr/bin/unrar'  # /usr/bin/7z
rarfile.PRIORITY = (rarfile.UNRAR_TOOL,)


def fix_name(name):
    for enc_from, enc_to in [('cp437', 'cp866'), ('cp437', 'cp1251')]:
        try:
            name = name.encode(enc_from).decode(enc_to)
            # name = name[:name.rfind('.')][:120] + name[name.rfind('.'):] if len(name) >= 120 else name
            return name
        except:
            continue
    # name = name[:name.rfind('.')][:120] + name[name.rfind('.'):] if len(name) >= 120 else name
    return name


def get_unique_filename(dest_dir, base_name):
    """Возвращает уникальное имя файла в dest_dir, добавляя суффикс при конфликте."""
    name, ext = os.path.splitext(base_name)
    counter = 1
    new_name = base_name
    while os.path.exists(os.path.join(dest_dir, new_name)):
        new_name = f"{name}_{counter}{ext}"
        counter += 1
    return new_name


def extract_file_without_folders(archive, member, dest_dir):
    """
    Извлекает один файл из архива (RarFile или ZipFile) в dest_dir,
    игнорируя структуру папок внутри архива.
    archive — объект RarFile или ZipFile.
    member — объект RarInfo или ZipInfo.
    """
    # Исправляем кодировку
    original_name = fix_name(member.filename)
    # Берём только имя файла (без папок)
    base_name = os.path.basename(original_name)
    if not base_name:
        return  # это папка, пропускаем
    # Уникальное имя в целевой папке
    unique_name = get_unique_filename(dest_dir, base_name)
    dest_path = os.path.join(dest_dir, unique_name)
    # Читаем данные файла из архива и записываем напрямую
    data = archive.read(member)  # для RarFile и ZipFile есть метод read
    with open(dest_path, 'wb') as f:
        f.write(data)


def shorten_component(component, max_bytes=200):
    """Укорачивает один компонент пути (имя папки или файла) до max_bytes"""
    if len(component.encode('utf-8')) <= max_bytes:
        return component
    # Берем первые 20 символов + хеш от полного имени
    base, ext = os.path.splitext(component)
    short = base[:20]
    hash_suffix = hashlib.md5(component.encode('utf-8')).hexdigest()[:8]
    new_name = f"{short}_{hash_suffix}{ext}"
    # Если всё ещё длинно, укорачиваем дальше
    while len(new_name.encode('utf-8')) > max_bytes and len(short) > 5:
        short = short[:-1]
        new_name = f"{short}_{hash_suffix}{ext}"
    return new_name


def shorten_path_recursive(root_dir, max_total_bytes=4000, max_component_bytes=200):
    """
    Рекурсивно обходит все файлы и папки в root_dir, переименовывает те,
    чей полный путь превышает max_total_bytes или любой компонент > max_component_bytes.
    """
    # Собираем все элементы (файлы и папки) с их полными путями
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        # Сначала обрабатываем файлы, потом папки, чтобы не нарушить итерацию
        for name in filenames + dirnames:
            full_path = os.path.join(dirpath, name)
            # Проверяем длину полного пути (в байтах)
            if len(full_path.encode('utf-8')) <= max_total_bytes:
                # Проверяем длину самого имени
                if len(name.encode('utf-8')) <= max_component_bytes:
                    continue  # всё ок
            # Нужно переименовать
            new_name = shorten_component(name, max_component_bytes)
            # Если новое имя совпадает со старым, пропускаем
            if new_name == name:
                continue
            new_full_path = os.path.join(dirpath, new_name)
            # Проверяем, не существует ли уже файл с таким именем
            counter = 1
            while os.path.exists(new_full_path):
                base, ext = os.path.splitext(new_name)
                new_name = f"{base}_{counter}{ext}"
                new_full_path = os.path.join(dirpath, new_name)
                counter += 1
            # Переименовываем
            os.rename(full_path, new_full_path)


def unzip_rar(rar_path, extract_to):
    with rarfile.RarFile(rar_path, 'r') as rar_ref:
        for file_info in rar_ref.infolist():
            if not file_info.filename.endswith('/'):  # не папка
                extract_file_without_folders(rar_ref, file_info, extract_to)
    shorten_path_recursive(extract_to)


def unzip_zip(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file_info in zip_ref.infolist():
            if not file_info.filename.endswith('/'):
                extract_file_without_folders(zip_ref, file_info, extract_to)
    shorten_path_recursive(extract_to)


def unzip_7z(seven_zip_path, extract_to):
    with py7zr.SevenZipFile(seven_zip_path, mode='r') as archive:
        # Получаем список имён файлов (не папок)
        for name in archive.getnames():
            if name.endswith('/'):
                continue
            # Читаем содержимое файла
            data = archive.read([name])[name]  # возвращает bytes
            base_name = os.path.basename(fix_name(name))
            if not base_name:
                continue
            unique_name = get_unique_filename(extract_to, base_name)
            dest_path = os.path.join(extract_to, unique_name)
            with open(dest_path, 'wb') as f:
                f.write(data)
    shorten_path_recursive(extract_to)


def untar_tgz(tar_gz_path, extract_to, mode):
    with tarfile.open(tar_gz_path, mode) as tar_ref:
        for member in tar_ref.getmembers():
            if member.isdir():
                continue
            original_name = fix_name(member.name)
            base_name = os.path.basename(original_name)
            if not base_name:
                continue
            unique_name = get_unique_filename(extract_to, base_name)
            dest_path = os.path.join(extract_to, unique_name)
            src_file = tar_ref.extractfile(member)
            if src_file:
                with open(dest_path, 'wb') as dst_file:
                    dst_file.write(src_file.read())
    shorten_path_recursive(extract_to)
