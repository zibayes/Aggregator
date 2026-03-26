import pytest
from unittest.mock import patch, MagicMock
from agregator.processing.hash_utils import (
    check_file_hash_in_sources,
    add_hash_to_source,
    migrate_existing_hashes,
)


@pytest.fixture
def mock_model():
    return MagicMock()


@pytest.fixture
def mock_record():
    record = MagicMock()
    record.source_dict = []
    record.source = []
    return record


def test_check_file_hash_in_sources_found_by_hash(mock_model):
    mock_record1 = MagicMock()
    mock_record1.source_dict = [{'path': '/test/file1.pdf', 'origin_filename': 'file1.pdf', 'file_hash': 'abc123'}]
    mock_model.objects.all.return_value = [mock_record1]

    with patch('agregator.processing.hash_utils.calculate_file_hash') as mock_hash:
        mock_hash.return_value = 'abc123'
        found, file_hash = check_file_hash_in_sources('/tmp/test.pdf', mock_model)

    assert found is True
    assert file_hash == 'abc123'


def test_check_file_hash_in_sources_found_by_path(mock_model):
    mock_record1 = MagicMock()
    mock_record1.source_dict = [{'path': '/existing/file.pdf', 'origin_filename': 'file.pdf', 'file_hash': None}]
    mock_model.objects.all.return_value = [mock_record1]

    with patch('agregator.processing.hash_utils.calculate_file_hash') as mock_hash, \
            patch('agregator.processing.hash_utils.os.path.exists') as mock_exists, \
            patch('agregator.processing.hash_utils.os.path.samefile') as mock_samefile:
        mock_hash.return_value = 'newhash'
        mock_exists.return_value = True
        mock_samefile.return_value = True

        found, file_hash = check_file_hash_in_sources('/tmp/new.pdf', mock_model)

    assert found is True
    assert file_hash == 'newhash'


def test_check_file_hash_in_sources_not_found(mock_model):
    mock_record1 = MagicMock()
    mock_record1.source_dict = [{'path': '/test/file1.pdf', 'origin_filename': 'file1.pdf', 'file_hash': 'abc123'}]
    mock_model.objects.all.return_value = [mock_record1]

    with patch('agregator.processing.hash_utils.calculate_file_hash') as mock_hash:
        mock_hash.return_value = 'def456'
        found, file_hash = check_file_hash_in_sources('/tmp/test.pdf', mock_model)

    assert found is False
    assert file_hash == 'def456'


def test_check_file_hash_in_sources_no_source_dict(mock_model):
    mock_record1 = MagicMock()
    mock_record1.source_dict = None
    mock_model.objects.all.return_value = [mock_record1]

    with patch('agregator.processing.hash_utils.calculate_file_hash') as mock_hash:
        mock_hash.return_value = 'abc123'
        found, file_hash = check_file_hash_in_sources('/tmp/test.pdf', mock_model)

    assert found is False
    assert file_hash == 'abc123'


def test_check_file_hash_in_sources_exception(mock_model):
    mock_model.objects.all.return_value = []

    with patch('agregator.processing.hash_utils.calculate_file_hash') as mock_hash:
        mock_hash.side_effect = Exception("Hash error")
        found, file_hash = check_file_hash_in_sources('/tmp/test.pdf', mock_model)

    assert found is False
    assert file_hash is None


def test_add_hash_to_source(mock_record):
    mock_record.source_dict = [
        {'path': '/test/file1.pdf', 'origin_filename': 'file1.pdf'},
        {'path': '/test/file2.pdf', 'origin_filename': 'file2.pdf'}
    ]
    mock_record.source = mock_record.source_dict

    with patch('agregator.processing.hash_utils.calculate_file_hash') as mock_hash:
        mock_hash.side_effect = ['hash1', 'hash2']
        add_hash_to_source(mock_record)

    assert mock_record.source_dict[0]['file_hash'] == 'hash1'
    assert mock_record.source_dict[1]['file_hash'] == 'hash2'
    mock_record.save.assert_called_once()


def test_add_hash_to_source_no_path(mock_record):
    mock_record.source_dict = [{'origin_filename': 'file1.pdf'}]
    mock_record.source = mock_record.source_dict

    with patch('agregator.processing.hash_utils.calculate_file_hash') as mock_hash:
        add_hash_to_source(mock_record)

    assert 'file_hash' not in mock_record.source_dict[0]
    mock_hash.assert_not_called()
    mock_record.save.assert_called_once()


def test_add_hash_to_source_empty_source_dict(mock_record):
    mock_record.source_dict = []
    add_hash_to_source(mock_record)
    mock_record.save.assert_not_called()


def test_add_hash_to_source_exception(mock_record):
    mock_record.source_dict = [{'path': '/test/file1.pdf', 'origin_filename': 'file1.pdf'}]
    mock_record.source = mock_record.source_dict

    with patch('agregator.processing.hash_utils.calculate_file_hash') as mock_hash:
        mock_hash.side_effect = Exception("Hash error")
        add_hash_to_source(mock_record)

    assert mock_record.source_dict[0]['file_hash'] is None
    mock_record.save.assert_called_once()


def test_migrate_existing_hashes(mock_model):
    mock_record1 = MagicMock()
    mock_record2 = MagicMock()
    mock_model.objects.all.return_value = [mock_record1, mock_record2]

    with patch('agregator.processing.hash_utils.add_hash_to_source') as mock_add:
        migrate_existing_hashes(mock_model)

    assert mock_add.call_count == 2
    mock_add.assert_any_call(mock_record1)
    mock_add.assert_any_call(mock_record2)
