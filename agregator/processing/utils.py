import re


def clean_path_component(name):
    # Удаляем недопустимые символы для Windows
    # return re.sub(r'[<>:"/\\|?*]', '', name)
    return re.sub(r'[^a-zA-Zа-яА-Я0-9 \-,«»\.\(\)]', '', name).strip(' .')


def str_is_float(string):
    try:
        float(string)
    except ValueError:
        return False
    return True
