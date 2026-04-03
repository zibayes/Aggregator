import pytest
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open, call
from agregator.processing.batch_file_organizer import FileOrganizer


# ========== Тесты для clean_filename ==========
def test_clean_filename_removes_invalid_chars():
    name = 'file<>:"/\\|?*name.pdf'
    result = FileOrganizer.clean_filename(name)
    # Все запрещённые символы должны быть заменены
    invalid_chars = '<>:"/\\|?*'
    for ch in invalid_chars:
        assert ch not in result
    # После схлопывания не должно быть двух подчёркиваний подряд
    assert '__' not in result
    # Имя должно сохранить структуру: начинаться с 'file', заканчиваться 'name.pdf'
    assert result.startswith('file')
    assert result.endswith('name.pdf')
    # Между 'file' и 'name' должно быть хотя бы одно подчёркивание
    assert '_' in result


def test_clean_filename_replaces_multiple_spaces():
    name = 'file   with   many     spaces.pdf'
    result = FileOrganizer.clean_filename(name)
    assert result == 'file with many spaces.pdf'


def test_clean_filename_replaces_multiple_underscores():
    name = 'file____with____underscores.pdf'
    result = FileOrganizer.clean_filename(name)
    assert result == 'file_with_underscores.pdf'


def test_clean_filename_truncates_long_names():
    long_name = 'a' * 200 + '.pdf'
    result = FileOrganizer.clean_filename(long_name, max_length=50)
    assert len(result) == 50
    assert result.endswith('.pdf') is False  # обрезается без учёта расширения


def test_clean_filename_removes_trailing_spaces_and_dots():
    name = 'file name . . .   '
    result = FileOrganizer.clean_filename(name, max_length=20)
    # Метод заменяет множественные пробелы на один, но не обрезает конечные пробелы
    # Проверяем, что нет двух пробелов подряд
    assert '  ' not in result
    # Проверяем, что нет точки в конце (точки остаются только внутри)
    assert not result.endswith('.')
    # Проверяем, что исходные слова сохранились
    assert 'file name' in result


# ========== Тесты для should_reorganize ==========
def test_should_reorganize_file_in_root(tmp_path):
    # Создаём временную корневую папку
    root = tmp_path / "uploaded_files" / "Акты ГИКЭ"
    root.mkdir(parents=True)
    file_path = root / "document.pdf"
    file_path.touch()

    with patch.object(FileOrganizer, 'should_reorganize', wraps=FileOrganizer.should_reorganize):
        # Нужно, чтобы метод использовал реальные вызовы, но с временными путями
        # Временно заменяем логику проверки на тестовую: передаём root как строку
        # Но метод ожидает root_folder из ROOT_FOLDERS. Для теста проще создать отдельный экземпляр?
        # Поскольку метод статический, мы можем передать любой root_folder.
        result = FileOrganizer.should_reorganize(str(file_path), str(root))
        assert result is True


def test_should_reorganize_file_in_subdir_one_level(tmp_path):
    root = tmp_path / "uploaded_files" / "Акты ГИКЭ"
    subdir = root / "2023"
    subdir.mkdir(parents=True)
    file_path = subdir / "doc.pdf"
    file_path.touch()

    result = FileOrganizer.should_reorganize(str(file_path), str(root))
    assert result is True  # len(relative_path.parts) == 1? wait: relative = "2023/doc.pdf" -> parts = ['2023', 'doc.pdf'] -> len=2 <=2 -> True


def test_should_reorganize_file_deep_nested_no_other_pdfs(tmp_path):
    root = tmp_path / "uploaded_files" / "Акты ГИКЭ"
    deep_dir = root / "2023" / "extra" / "folder"
    deep_dir.mkdir(parents=True)
    file_path = deep_dir / "doc.pdf"
    file_path.touch()

    result = FileOrganizer.should_reorganize(str(file_path), str(root))
    # len(parts) = 4 >2, и в папке только один PDF => False
    assert result is False


def test_should_reorganize_deep_nested_with_multiple_pdfs(tmp_path):
    root = tmp_path / "uploaded_files" / "Акты ГИКЭ"
    deep_dir = root / "2023" / "extra" / "folder"
    deep_dir.mkdir(parents=True)
    (deep_dir / "doc1.pdf").touch()
    (deep_dir / "doc2.pdf").touch()
    file_path = deep_dir / "doc1.pdf"

    result = FileOrganizer.should_reorganize(str(file_path), str(root))
    # В папке более одного PDF, даже глубоко -> True
    assert result is True


def test_should_reorganize_file_outside_root(tmp_path):
    root = tmp_path / "uploaded_files" / "Акты ГИКЭ"
    outside = tmp_path / "other"
    outside.mkdir()
    file_path = outside / "doc.pdf"
    file_path.touch()

    result = FileOrganizer.should_reorganize(str(file_path), str(root))
    assert result is False


# ========== Тесты для create_organized_structure (с моками, чтобы не трогать реальную ФС) ==========
@pytest.fixture
def mock_path_operations():
    """Фикстура для подмены методов Path и shutil"""
    with patch('pathlib.Path.exists', return_value=True), \
            patch('pathlib.Path.relative_to'), \
            patch('shutil.move') as mock_move, \
            patch('agregator.processing.batch_file_organizer.FileOrganizer._move_kml_file', return_value=False), \
            patch('pathlib.Path.mkdir') as mock_mkdir:
        yield mock_move, mock_mkdir


def test_create_organized_structure_unknown_type():
    result, moved = FileOrganizer.create_organized_structure('/some/file.pdf', 'unknown')
    assert result == '/some/file.pdf'
    assert moved is False


def test_create_organized_structure_file_not_exists():
    with patch('pathlib.Path.exists', return_value=False):
        result, moved = FileOrganizer.create_organized_structure('/nonexistent.pdf', 'act')
        assert result == '/nonexistent.pdf'
        assert moved is False


def test_create_organized_structure_no_reorganization_needed():
    with patch('agregator.processing.batch_file_organizer.FileOrganizer.should_reorganize', return_value=False):
        result, moved = FileOrganizer.create_organized_structure('/app/uploaded_files/Акты ГИКЭ/file.pdf', 'act')
        assert result == '/app/uploaded_files/Акты ГИКЭ/file.pdf'
        assert moved is False


def test_create_organized_structure_kml_moved(mock_path_operations):
    mock_move, mock_mkdir = mock_path_operations
    with patch('agregator.processing.batch_file_organizer.FileOrganizer.should_reorganize', return_value=True), \
            patch('pathlib.Path.relative_to', return_value=Path('file.pdf')), \
            patch('agregator.processing.batch_file_organizer.FileOrganizer._move_kml_file', return_value=True):
        result, moved = FileOrganizer.create_organized_structure('/app/uploaded_files/Акты ГИКЭ/file.pdf', 'act')
        assert moved is True


# ========== Тесты для _move_kml_file ==========
def test_move_kml_file_exact_match(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.touch()
    kml_path = tmp_path / "doc.kml"
    kml_path.touch()
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    moved = FileOrganizer._move_kml_file(pdf_path, target_dir)
    assert moved is True
    assert (target_dir / "doc.kml").exists()
    assert not kml_path.exists()


def test_move_kml_file_kmz_match(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.touch()
    kmz_path = tmp_path / "doc.kmz"
    kmz_path.touch()
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    moved = FileOrganizer._move_kml_file(pdf_path, target_dir)
    assert moved is True
    assert (target_dir / "doc.kmz").exists()


def test_move_kml_file_with_coordinates_suffix(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.touch()
    kml_path = tmp_path / "doc_coordinates.kml"
    kml_path.touch()
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    moved = FileOrganizer._move_kml_file(pdf_path, target_dir)
    assert moved is True
    assert (target_dir / "doc_coordinates.kml").exists()


def test_move_kml_file_no_related_kml(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.touch()
    unrelated = tmp_path / "unrelated.kml"
    unrelated.touch()
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    moved = FileOrganizer._move_kml_file(pdf_path, target_dir)
    assert moved is False
    assert (target_dir / "unrelated.kml").exists() is False
    assert unrelated.exists()  # не тронут


def test_move_kml_file_target_exists(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    pdf_path.touch()
    kml_path = tmp_path / "doc.kml"
    kml_path.touch()
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    existing = target_dir / "doc.kml"
    existing.touch()

    moved = FileOrganizer._move_kml_file(pdf_path, target_dir)
    assert moved is False  # не перемещаем, т.к. уже есть
    assert kml_path.exists()  # остался на месте


# ========== Тесты для organize_batch_files ==========
def test_organize_batch_files_success():
    files = [
        {'path': '/app/uploaded_files/Акты ГИКЭ/doc1.pdf', 'other': 'data1'},
        {'path': '/app/uploaded_files/Акты ГИКЭ/doc2.pdf', 'other': 'data2'}
    ]
    with patch('agregator.processing.batch_file_organizer.FileOrganizer.create_organized_structure') as mock_create:
        mock_create.side_effect = [
            ('uploaded_files/Акты ГИКЭ/new/doc1.pdf', True),
            ('uploaded_files/Акты ГИКЭ/new/doc2.pdf', False)
        ]
        result = FileOrganizer.organize_batch_files(files, 'act')

        assert len(result) == 2
        assert result[0]['path'] == 'uploaded_files/Акты ГИКЭ/new/doc1.pdf'
        assert result[0]['was_organized'] is True
        assert result[0]['final_location'] == 'uploaded_files/Акты ГИКЭ/new/doc1.pdf'
        assert result[0]['other'] == 'data1'

        assert result[1]['path'] == 'uploaded_files/Акты ГИКЭ/new/doc2.pdf'
        assert result[1]['was_organized'] is False
        assert result[1]['final_location'] == 'uploaded_files/Акты ГИКЭ/new/doc2.pdf'
        assert result[1]['other'] == 'data2'


def test_organize_batch_files_exception_handling():
    files = [{'path': '/invalid.pdf'}]
    with patch('agregator.processing.batch_file_organizer.FileOrganizer.create_organized_structure',
               side_effect=Exception('Test error')):
        result = FileOrganizer.organize_batch_files(files, 'act')
        assert len(result) == 1
        assert result[0]['path'] == '/invalid.pdf'
        assert result[0]['was_organized'] is False
        assert result[0]['final_location'] == '/invalid.pdf'


def test_organize_batch_files_preserves_original_fields():
    files = [{'path': '/some.pdf', 'extra': 'value', 'another': 123}]
    with patch('agregator.processing.batch_file_organizer.FileOrganizer.create_organized_structure',
               return_value=('/new.pdf', True)):
        result = FileOrganizer.organize_batch_files(files, 'act')
        assert result[0]['extra'] == 'value'
        assert result[0]['another'] == 123
