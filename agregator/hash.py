import hashlib


def calculate_file_hash(file_path, hash_algorithm='sha256'):
    """Вычисляет хеш-сумму файла."""
    if hash_algorithm == 'md5':
        hash_func = hashlib.md5()
    elif hash_algorithm == 'sha1':
        hash_func = hashlib.sha1()
    elif hash_algorithm == 'sha256':
        hash_func = hashlib.sha256()
    else:
        raise ValueError("Unsupported hash algorithm. Use 'md5', 'sha1', or 'sha256'.")

    with open(file_path, 'rb') as f:
        file_content = f.read()
        hash_func.update(file_content)

    return hash_func.hexdigest()
