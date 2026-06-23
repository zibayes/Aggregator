import hashlib
import os


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

    if os.path.isfile(file_path):
        with open(file_path, 'rb') as f:
            file_content = f.read()
            hash_func.update(file_content)
    else:
        return None

    return hash_func.hexdigest()


def has_duplicates_in_db(model, file, obj_id):
    file_hash = calculate_file_hash(file)
    instances = model.objects.all()
    if len(instances) == 0:
        return False, None
    for instance in instances:
        if instance.source_dict is not None:
            for source in instance.source_dict:
                if instance.id != obj_id:
                    act_hash = source['file_hash']
                    source_path = source['path']
                    if not act_hash and os.path.isfile(source_path):
                        act_hash = calculate_file_hash(source_path)
                    if file_hash == act_hash:
                        return True, instance.id
    return False, None
