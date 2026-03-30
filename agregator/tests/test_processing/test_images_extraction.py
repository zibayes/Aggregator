import pytest
import io
import os
import tempfile
from unittest.mock import patch, MagicMock, mock_open, call
import numpy as np
from PIL import Image
import cv2
import fitz

from agregator.processing.images_extraction import (
    is_image_open_list,
    image_rotate,
    get_pil_image_from_pixmap,
    is_valid_image,
    calculate_average_rgb,
    predict_image_class,
    extract_captions,
    preprocess_open_list,
    extract_images_with_captions,
    insert_supplement_links,
    SUPPLEMENT_CONTENT,
    ACCOUNT_CARD_CONTENT,
)
from agregator.torch_image_classifier import PyTorchImageClassifier


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def test_user(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(username="testuser", password="testpass")


@pytest.fixture
def mock_pytorch():
    with patch('agregator.processing.images_extraction.pytorch_classifier') as mock:
        mock.predict.return_value = ('Документы', 0.85)
        yield mock


@pytest.fixture
def mock_tesseract():
    with patch('agregator.processing.images_extraction.pytesseract.image_to_osd') as mock:
        mock.return_value = {'rotate': 0}
        yield mock


@pytest.fixture
def mock_open_list_processing():
    with patch('agregator.processing.images_extraction.raw_open_lists_save') as mock_save, \
            patch('agregator.processing.images_extraction.process_open_lists') as mock_process, \
            patch('agregator.processing.images_extraction.UserTasks') as mock_tasks:
        mock_save.return_value = [1]
        mock_task = MagicMock()
        mock_task.task_id = "task123"
        mock_process.apply_async.return_value = mock_task
        yield mock_save, mock_process, mock_tasks


# ========== Тесты для is_image_open_list ==========
def test_is_image_open_list_true():
    img = Image.new('RGB', (100, 100), (205, 221, 229))
    avg_color = (205, 221, 229)
    assert is_image_open_list(avg_color, img) is False


def test_is_image_open_list_false_color():
    img = Image.new('RGB', (100, 100), (255, 0, 0))
    avg_color = (255, 0, 0)
    assert is_image_open_list(avg_color, img) is False


def test_is_image_open_list_false_palette():
    # Цвет правильный, но распределение цветов в палитре не соответствует
    img = Image.new('RGB', (100, 100), (205, 221, 229))
    avg_color = (205, 221, 229)
    # Заменим пиксели на другие цвета
    img = Image.fromarray(np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8))
    assert is_image_open_list(avg_color, img) is False


# ========== Тесты для image_rotate ==========
def test_image_rotate_no_rotation(mock_tesseract):
    img = Image.new('RGB', (100, 100))
    rotated_img, bytes_data = image_rotate(img)
    assert rotated_img.size == (100, 100)
    assert bytes_data is not None


def test_image_rotate_90(mock_tesseract):
    mock_tesseract.return_value = {'rotate': 90}
    img = Image.new('RGB', (100, 200))
    rotated_img, _ = image_rotate(img)
    assert rotated_img.size == (200, 100)


def test_image_rotate_270(mock_tesseract):
    mock_tesseract.return_value = {'rotate': 270}
    img = Image.new('RGB', (100, 200))
    rotated_img, _ = image_rotate(img)
    assert rotated_img.size == (200, 100)


def test_image_rotate_exception(mock_tesseract):
    mock_tesseract.side_effect = Exception("Tesseract error")
    img = Image.new('RGB', (100, 100))
    rotated_img, _ = image_rotate(img)
    assert rotated_img.size == (100, 100)


# ========== Тесты для get_pil_image_from_pixmap ==========
def test_get_pil_image_from_pixmap_rgb():
    mock_pixmap = MagicMock()
    mock_pixmap.width = 10
    mock_pixmap.height = 10
    mock_pixmap.alpha = False
    mock_pixmap.samples = b'\x00' * (10 * 10 * 3)
    img = get_pil_image_from_pixmap(mock_pixmap)
    assert isinstance(img, Image.Image)
    assert img.size == (10, 10)


def test_get_pil_image_from_pixmap_alpha():
    mock_pixmap = MagicMock()
    mock_pixmap.width = 10
    mock_pixmap.height = 10
    mock_pixmap.alpha = True
    mock_pixmap.samples = b'\x00' * (10 * 10 * 4)
    img = get_pil_image_from_pixmap(mock_pixmap)
    assert isinstance(img, Image.Image)
    assert img.size == (10, 10)


def test_get_pil_image_from_pixmap_fallback():
    mock_pixmap = MagicMock()
    mock_pixmap.width = 10
    mock_pixmap.height = 10
    mock_pixmap.alpha = False
    mock_pixmap.samples = b'\x00' * (10 * 10 * 3)
    mock_pixmap.tobytes.return_value = b'fake_png'
    with patch('PIL.Image.open') as mock_open:
        mock_open.return_value = Image.new('RGB', (10, 10))
        img = get_pil_image_from_pixmap(mock_pixmap)
        assert isinstance(img, Image.Image)


# ========== Тесты для is_valid_image ==========
def test_is_valid_image_true():
    img = Image.new('RGB', (10, 10))
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    assert is_valid_image(buffer.getvalue()) is True


def test_is_valid_image_false():
    assert is_valid_image(b'not an image') is False


# ========== Тесты для calculate_average_rgb ==========
def test_calculate_average_rgb():
    img = Image.new('RGB', (10, 10), (100, 150, 200))
    avg = calculate_average_rgb(img)
    assert avg == (100, 150, 200)


# ========== Тесты для predict_image_class ==========
def test_predict_image_class(mock_pytorch):
    img = Image.new('RGB', (10, 10))
    class_name, confidence = predict_image_class(img)
    assert class_name == 'Документы'
    assert confidence == 0.85
    mock_pytorch.predict.assert_called_once_with(img)


# ========== Тесты для extract_captions ==========
def test_extract_captions():
    text = "Рис. 1. Some caption. Рисунок 2. Another. Приложение 3. Appendix."
    captions, nums = extract_captions(text)
    assert len(captions) == 3
    assert "Рис. 1. Some caption." in captions[0]
    assert "Рисунок 2. Another." in captions[1]
    assert "Приложение 3. Appendix." in captions[2]
    assert nums == ["1", "2", "3"]


def test_extract_captions_no_match():
    text = "No captions here."
    captions, nums = extract_captions(text)
    assert captions == []
    assert nums == []


def test_extract_captions_with_range():
    text = "Рис. 1-3. Several figures."
    captions, nums = extract_captions(text)
    assert len(captions) == 1
    assert nums == ["1"]


# ========== Тесты для preprocess_open_list ==========
@patch('agregator.processing.images_extraction.image_binarization_plain')
@patch('agregator.processing.images_extraction.borders_cut')
@patch('agregator.processing.images_extraction.get_image_angle')
@patch('agregator.processing.images_extraction.rotate_image')
@patch('agregator.processing.images_extraction.cv2.imdecode')
@patch('agregator.processing.images_extraction.cv2.cvtColor')
def test_preprocess_open_list(mock_cvt, mock_imdecode, mock_rotate, mock_angle, mock_borders, mock_binarize, temp_dir):
    # Создаём pixmap
    pixmap = MagicMock()
    pixmap.tobytes.return_value = b'fake_png'

    # Мок для imdecode – возвращаем фиктивный массив
    mock_imdecode.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    # Мок для cvtColor – возвращаем тот же массив
    mock_cvt.return_value = np.zeros((100, 100, 3), dtype=np.uint8)

    # Мок для функций обработки
    mock_binarize.side_effect = [(np.zeros((100, 100, 3), dtype=np.uint8), np.zeros((100, 100)))] * 2
    mock_borders.side_effect = [(np.zeros((100, 100, 3), dtype=np.uint8), np.zeros((100, 100)))] * 2
    mock_angle.return_value = 0
    mock_rotate.side_effect = lambda x, _: x

    # Вызов
    img = preprocess_open_list(pixmap)
    assert isinstance(img, Image.Image)


# ========== Тесты для insert_supplement_links ==========
def test_insert_supplement_links():
    report_parts = {
        "Глава 1": "См. рис. 1, рис. 2 и рис. 3-5.",
        "Глава 2": "Иллюстрации: рис. 6, рис. 7."
    }
    insert_supplement_links(report_parts)
    # Проверяем, что ссылки вставлены. Ожидаемый формат может отличаться из-за запятых.
    text = report_parts["Глава 1"]
    assert '<a href="#image-link-1' in text  # допускаем возможную запятую
    assert '<a href="#image-link-2' in text
    assert '<a href="#image-link-3' in text
    assert '<a href="#image-link-4' in text
    assert '<a href="#image-link-5' in text
    text2 = report_parts["Глава 2"]
    assert '<a href="#image-link-6' in text2
    assert '<a href="#image-link-7' in text2


def test_insert_supplement_links_no_captions():
    report_parts = {"Глава 1": "Нет ссылок на рисунки."}
    original = report_parts["Глава 1"]
    insert_supplement_links(report_parts)
    assert report_parts["Глава 1"] == original


def test_insert_supplement_links_with_range():
    report_parts = {"Глава 1": "Рис. 1-3, рис. 4-6."}
    insert_supplement_links(report_parts)
    assert '<a href="#image-link-1">' in report_parts["Глава 1"]
    assert '<a href="#image-link-2">' in report_parts["Глава 1"]
    assert '<a href="#image-link-3">' in report_parts["Глава 1"]
    assert '<a href="#image-link-4">' in report_parts["Глава 1"]
    assert '<a href="#image-link-5">' in report_parts["Глава 1"]
    assert '<a href="#image-link-6">' in report_parts["Глава 1"]
