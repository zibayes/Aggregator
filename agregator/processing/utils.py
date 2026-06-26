import re
from pathlib import Path
from typing import List


def clean_path_component(name):
    # Удаляем недопустимые символы для Windows
    # return re.sub(r'[<>:"/\\|?*]', '', name)
    return re.sub(r'[^a-zA-Zа-яА-ЯёЁ0-9 ,«»\.\(\)\-\–]', '', name).strip(' .')


def get_unique_filename(directory: Path, filename: str, except_list: List[str] = []) -> str:
    """
    Проверяет, существует ли файл в директории.
    Если существует – добавляет (1), (2) и т.д., пока не найдёт свободное имя.
    """
    target = directory / filename
    if not target.exists() and filename not in except_list:
        return filename  # имя свободно

    stem = target.stem  # имя без расширения
    suffix = target.suffix  # расширение (включая точку)
    counter = 1
    while True:
        new_name = f"{stem} ({counter}){suffix}"
        new_path = directory / new_name
        if not new_path.exists() and new_name not in except_list:
            return new_name
        counter += 1


def str_is_float(string):
    try:
        float(string)
    except ValueError:
        return False
    return True


def str_is_int(string):
    try:
        int(string)
    except ValueError:
        return False
    return True
