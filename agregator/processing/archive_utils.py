# import patoolib
import zipfile
import rarfile
import py7zr
import tarfile

rarfile.UNRAR_TOOL = '/usr/bin/unrar'  # /usr/bin/7z
rarfile.PRIORITY = (rarfile.UNRAR_TOOL,)


def fix_name(name):
    for enc_from, enc_to in [('cp437', 'cp866'), ('cp437', 'cp1251')]:
        try:
            return name.encode(enc_from).decode(enc_to)
        except:
            continue
    return name


def unzip_zip(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file_info in zip_ref.infolist():
            file_info.filename = fix_name(file_info.filename)
            zip_ref.extract(file_info, extract_to)


def unzip_rar(rar_path, extract_to):
    with rarfile.RarFile(rar_path, 'r') as rar_ref:
        for file_info in rar_ref.infolist():
            file_info.filename = fix_name(file_info.filename)
            rar_ref.extract(file_info, extract_to)


def unzip_7z(seven_zip_path, extract_to):
    with py7zr.SevenZipFile(seven_zip_path, mode='r') as archive:
        archive.extractall(path=extract_to)


def untar_tgz(tar_gz_path, extract_to, mode):
    with tarfile.open(tar_gz_path, mode) as tar_ref:
        tar_ref.extractall(path=extract_to)
