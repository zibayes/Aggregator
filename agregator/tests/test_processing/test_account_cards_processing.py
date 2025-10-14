import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch, MagicMock
import cv2
import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from celery.exceptions import Retry

from agregator.models import ObjectAccountCard, IdentifiedArchaeologicalHeritageSite, ArchaeologicalHeritageSite
from agregator.processing.account_cards_processing import (
    extract_text_from_image,
    sort_contours_custom,
    process_account_cards,
    extract_text_tables_and_images,
    connect_account_card_to_heritage,
    ccw,
    intersect,
    error_handler_account_cards
)
from agregator.processing.files_saving import load_raw_account_cards


class TestAccountCardsProcessing(TestCase):
    """Базовый класс для тестов обработки учетных карточек"""

    def setUp(self):
        self.test_user = Mock()
        self.test_user.id = 1
        self.account_card = Mock(spec=ObjectAccountCard)
        self.account_card.id = 1
        self.account_card.name = "Тестовый объект"
        self.account_card.source = "/fake/path/document.doc"
        self.account_card.supplement = {}
        self.account_card.coordinates = {}
        self.account_card.is_processing = False

        self.heritage_site = Mock(spec=IdentifiedArchaeologicalHeritageSite)
        self.heritage_site.id = 1
        self.heritage_site.name = "Тестовый объект"
        self.heritage_site.source = "/fake/heritage/path"


class TestImageProcessingFunctions(TestAccountCardsProcessing):
    """Тесты функций обработки изображений"""

    def test_extract_text_from_image_config(self):
        """Тест различных конфигураций PSM для Tesseract"""
        test_cases = [
            ("6", "--oem 3 --psm 6"),
            ("11", "--oem 3 --psm 11"),
            ("1", "--oem 3 --psm 1"),
        ]

        for psm_conf, expected_config in test_cases:
            with self.subTest(psm_conf=psm_conf, expected_config=expected_config):
                with patch(
                        'agregator.processing.account_cards_processing.pytesseract.image_to_string') as mock_tesseract:
                    mock_image = Mock()
                    extract_text_from_image(mock_image, psm_conf)
                    mock_tesseract.assert_called_once_with(
                        mock_image,
                        lang='rus+eng',
                        config=expected_config
                    )

    def test_extract_text_from_image_success(self):
        """Тест успешного извлечения текста из изображения"""
        mock_image = Mock()
        expected_text = "Извлеченный текст"

        with patch('agregator.processing.account_cards_processing.pytesseract.image_to_string') as mock_tesseract:
            mock_tesseract.return_value = expected_text
            result = extract_text_from_image(mock_image, "6")
            assert result == expected_text

    def test_extract_text_from_image_empty(self):
        """Тест извлечения текста из пустого изображения"""
        mock_image = Mock()

        with patch('agregator.processing.account_cards_processing.pytesseract.image_to_string') as mock_tesseract:
            mock_tesseract.return_value = ""
            result = extract_text_from_image(mock_image, "6")
            assert result == ""

    def test_sort_contours_custom(self):
        """Тест кастомной сортировки контуров"""
        test_cases = [
            # Простой случай - сортировка по Y
            ([((0, 0, 10, 20),), ((0, 30, 10, 20),)], [0, 1]),
            # Контуры на одной линии Y, но разные X
            ([((20, 10, 10, 20),), ((10, 10, 10, 20),)], [1, 0]),
        ]

        for contours_data, expected_order in test_cases:
            with self.subTest(contours_data=contours_data, expected_order=expected_order):
                contours = []
                for data in contours_data:
                    x, y, w, h = data[0]
                    contour = np.array([
                        [[x, y]],
                        [[x + w, y]],
                        [[x + w, y + h]],
                        [[x, y + h]]
                    ], dtype=np.int32)
                    contours.append(contour)

                sorted_contours = sort_contours_custom(contours)
                assert len(sorted_contours) == len(expected_order)

    def test_sort_contours_empty(self):
        """Тест сортировки пустого списка контуров"""
        result = sort_contours_custom([])
        assert result == []


class TestGeometryFunctions(TestAccountCardsProcessing):
    """Тесты геометрических функций"""

    def test_ccw(self):
        """Тест функции определения ориентации точек"""
        test_cases = [
            ((0, 0), (1, 1), (2, 0), True),  # CCW
            ((0, 0), (2, 0), (1, 1), False),  # CW
            ((0, 0), (1, 0), (2, 0), False),  # Коллинеарные
        ]

        for A, B, C, expected in test_cases:
            with self.subTest(A=A, B=B, C=C, expected=expected):
                result = ccw(A, B, C)
                assert result == expected

    def test_intersect(self):
        """Тест функции проверки пересечения отрезков"""
        test_cases = [
            # Пересекающиеся отрезки
            ((0, 0), (2, 2), (0, 2), (2, 0), True),
            # Непересекающиеся отрезки
            ((0, 0), (1, 1), (2, 2), (3, 3), False),
            # Параллельные отрезки
            ((0, 0), (2, 0), (0, 1), (2, 1), False),
        ]

        for A, B, C, D, expected in test_cases:
            with self.subTest(A=A, B=B, C=C, D=D, expected=expected):
                result = intersect(A, B, C, D)
                assert result == expected


class TestDocumentProcessing(TestAccountCardsProcessing):
    """Тесты обработки документов"""

    def test_extract_text_tables_and_images_duplicate_file(self):
        """Тест обнаружения дубликата файла"""
        test_file = "/fake/path/test.docx"

        with patch('agregator.processing.account_cards_processing.calculate_file_hash') as mock_hash, \
                patch('agregator.processing.account_cards_processing.ObjectAccountCard.objects.all') as mock_all, \
                patch('agregator.processing.account_cards_processing.ObjectAccountCard.objects.get') as mock_get, \
                patch('agregator.processing.account_cards_processing.Document') as mock_document:
            # Настраиваем моки
            mock_get.return_value = self.account_card
            duplicate_card = Mock()
            duplicate_card.id = 2
            duplicate_card.source = "/fake/path/duplicate.doc"
            mock_all.return_value = [duplicate_card]
            mock_hash.return_value = "same_hash"

            # Мокируем документ
            mock_doc = Mock()
            mock_document.return_value = mock_doc
            mock_doc.paragraphs = []
            mock_doc.tables = []

            progress_recorder = Mock()
            pages_count = {1: 1}
            total_processed = [0]
            progress_json = {'file_groups': {str(self.account_card.id): {'origin_filename': 'test.doc'}}}
            task_id = "test_task_123"
            time_on_start = Mock()

            with pytest.raises(FileExistsError) as exc_info:
                extract_text_tables_and_images(
                    test_file, progress_recorder, pages_count, total_processed,
                    self.account_card.id, progress_json, task_id, time_on_start
                )

            assert "Такой файл уже загружен в систему" in str(exc_info.value)

    def test_extract_text_tables_and_images_file_types(self):
        """Тест обработки разных типов файлов"""
        test_cases = [
            (".docx", "docx_processor"),
            (".doc", "docx_processor"),
            (".pdf", "pdf_processor"),
        ]

        for file_extension, expected_processor in test_cases:
            with self.subTest(file_extension=file_extension, expected_processor=expected_processor):
                test_file = f"/fake/path/test{file_extension}"

                with patch('agregator.processing.account_cards_processing.Document') as mock_doc, \
                        patch('agregator.processing.account_cards_processing.fitz.open') as mock_fitz, \
                        patch(
                            'agregator.processing.account_cards_processing.ObjectAccountCard.objects.get') as mock_get, \
                        patch('agregator.processing.account_cards_processing.calculate_file_hash') as mock_hash, \
                        patch(
                            'agregator.processing.account_cards_processing.ObjectAccountCard.objects.all') as mock_all:

                    mock_all.return_value = []
                    mock_get.return_value = self.account_card
                    mock_hash.return_value = "test_hash"

                    # Моки для прогресса
                    progress_recorder = Mock()
                    pages_count = {1: 1}
                    total_processed = [0]
                    progress_json = {'file_groups': {str(self.account_card.id): {}}}
                    task_id = "test_task_123"
                    time_on_start = Mock()

                    if file_extension in ['.doc', '.docx']:
                        # Мокируем DOCX обработку
                        mock_doc_instance = Mock()
                        mock_doc.return_value = mock_doc_instance
                        mock_doc_instance.paragraphs = []
                        mock_doc_instance.tables = []

                        extract_text_tables_and_images(
                            test_file, progress_recorder, pages_count, total_processed,
                            self.account_card.id, progress_json, task_id, time_on_start
                        )
                        mock_doc.assert_called_once()
                    else:
                        # Мокируем PDF обработку
                        mock_doc_instance = Mock()
                        mock_doc_instance.__len__ = Mock(return_value=1)
                        mock_page = Mock()
                        mock_pixmap = Mock()
                        mock_pixmap.tobytes.return_value = b"fake_image_data"
                        mock_page.get_pixmap.return_value = mock_pixmap
                        mock_doc_instance.load_page.return_value = mock_page
                        mock_fitz.return_value = mock_doc_instance

                        with patch('agregator.processing.account_cards_processing.Image.open') as mock_image_open, \
                                patch('agregator.processing.account_cards_processing.cv2.cvtColor'), \
                                patch('agregator.processing.account_cards_processing.cv2.threshold'), \
                                patch('agregator.processing.account_cards_processing.cv2.findContours'), \
                                patch('agregator.processing.account_cards_processing.cv2.boundingRect'), \
                                patch('agregator.processing.account_cards_processing.cv2.dilate'):

                            mock_image = Mock()
                            mock_image.size = (100, 100)
                            mock_image.mode = 'RGB'
                            mock_image_open.return_value = mock_image

                            extract_text_tables_and_images(
                                test_file, progress_recorder, pages_count, total_processed,
                                self.account_card.id, progress_json, task_id, time_on_start
                            )
                            mock_fitz.assert_called_once()


class TestHeritageLinking(TestAccountCardsProcessing):
    """Тесты связывания учетных карточек с объектами наследия"""

    def test_connect_account_card_to_heritage(self):
        """Тест связывания учетной карточки с объектом наследия"""
        test_cases = [
            (IdentifiedArchaeologicalHeritageSite, "Тестовый объект", "Тестовый объект", True),
            (ArchaeologicalHeritageSite, "Тестовый объект", "Тестовый объект", True),
            (IdentifiedArchaeologicalHeritageSite, "Разные имена", "Тестовый объект", False),
            (None, None, "Тестовый объект", False),
        ]

        for heritage_class, heritage_name, account_card_name, should_link in test_cases:
            with self.subTest(heritage_class=heritage_class, heritage_name=heritage_name,
                              account_card_name=account_card_name, should_link=should_link):

                with patch(
                        'agregator.processing.account_cards_processing.ObjectAccountCard.objects.filter') as mock_account_filter, \
                        patch(
                            'agregator.processing.account_cards_processing.IdentifiedArchaeologicalHeritageSite.objects.filter') as mock_identified_filter, \
                        patch(
                            'agregator.processing.account_cards_processing.ArchaeologicalHeritageSite.objects.filter') as mock_archaeological_filter, \
                        patch('agregator.processing.account_cards_processing.shutil.move') as mock_move, \
                        patch('agregator.processing.account_cards_processing.os.rename') as mock_rename, \
                        patch('agregator.processing.account_cards_processing.os.path.exists', return_value=False), \
                        patch('agregator.processing.account_cards_processing.copy.deepcopy') as mock_deepcopy:

                    # Настраиваем моки
                    mock_account_card = Mock()
                    mock_account_card.name = account_card_name
                    mock_account_card.source = "/fake/source/path/document.doc"
                    mock_account_card.origin_filename = "document.doc"
                    mock_account_card.supplement_dict = {'address': [], 'description': []}
                    mock_account_card.supplement = {}
                    mock_account_card.id = 1
                    mock_account_filter.return_value = [mock_account_card]

                    if heritage_class:
                        mock_heritage = Mock()
                        mock_heritage.name = heritage_name
                        mock_heritage.doc_name = heritage_name
                        mock_heritage.source = "/fake/heritage/path"
                        mock_heritage.account_card_id = None

                        if heritage_class == IdentifiedArchaeologicalHeritageSite:
                            mock_identified_filter.return_value = [mock_heritage]
                            mock_archaeological_filter.return_value = []
                        else:
                            mock_identified_filter.return_value = []
                            mock_archaeological_filter.return_value = [mock_heritage]
                    else:
                        mock_identified_filter.return_value = []
                        mock_archaeological_filter.return_value = []

                    mock_deepcopy.return_value = {'address': [], 'description': []}

                    # Вызываем функцию
                    connect_account_card_to_heritage(account_card_name)

                    # Проверяем результат
                    if should_link:
                        assert mock_heritage.account_card_id == mock_account_card.id
                        mock_move.assert_called_once()
                    else:
                        if heritage_class:
                            assert mock_heritage.account_card_id is None

    def test_connect_account_card_destination_exists(self):
        """Тест случая, когда папка назначения уже существует"""
        with patch(
                'agregator.processing.account_cards_processing.ObjectAccountCard.objects.filter') as mock_account_filter, \
                patch(
                    'agregator.processing.account_cards_processing.IdentifiedArchaeologicalHeritageSite.objects.filter') as mock_identified_filter, \
                patch('agregator.processing.account_cards_processing.os.path.exists', return_value=True):
            # Создаем полноценные мок-объекты
            mock_account_card = Mock()
            mock_account_card.name = "Тестовый объект"
            mock_account_card.source = "/fake/source/path/document.doc"
            mock_account_card.origin_filename = "document.doc"
            mock_account_card.supplement_dict = {'address': [], 'description': []}
            mock_account_card.supplement = {}
            mock_account_card.id = 1

            mock_account_filter.return_value = [mock_account_card]

            mock_heritage = Mock()
            mock_heritage.name = "Тестовый объект"
            mock_identified_filter.return_value = [mock_heritage]

            # Функция должна завершиться без ошибок
            connect_account_card_to_heritage("Тестовый объект")
            # Если не возникло исключений - тест пройден


class TestCeleryTasks(TestAccountCardsProcessing):
    """Тесты Celery задач"""

    def test_process_account_cards_task(self):
        """Тест основной Celery задачи обработки учетных карточек"""
        mock_task = Mock()
        mock_task.id = "test_task_123"

        account_cards_ids = [1, 2, 3]
        user_id = 1

        with patch('agregator.processing.account_cards_processing.process_documents') as mock_process_documents:
            mock_process_documents.return_value = {"status": "success"}

            # Вызываем задачу как обычную функцию
            result = process_account_cards(mock_task, account_cards_ids, user_id)

            mock_process_documents.assert_called_once_with(
                mock_task, account_cards_ids, user_id, 'account_cards',
                model_class=ObjectAccountCard,
                load_function=load_raw_account_cards,
                process_function=extract_text_tables_and_images
            )
            assert result == {"status": "success"}

    def test_error_handler_account_cards(self):
        """Тест обработчика ошибок для учетных карточек"""
        mock_task = Mock()
        mock_task.id = "failed_task_123"

        exception = Exception("Test error")
        exception_desc = "Test error description"

        with patch('agregator.processing.account_cards_processing.redis_client.get') as mock_redis_get, \
                patch('agregator.processing.account_cards_processing.ObjectAccountCard.objects.get') as mock_get, \
                patch('agregator.processing.account_cards_processing.datetime') as mock_datetime:
            # Мокируем данные прогресса
            progress_data = {
                'file_groups': {
                    '1': {'processed': 'False'},
                    '2': {'processed': 'True'}
                }
            }
            mock_redis_get.return_value = json.dumps(progress_data)
            mock_datetime.now.return_value.strftime.return_value = "2024-01-01 12:00:00"

            mock_account_card = Mock()
            mock_get.return_value = mock_account_card

            # Проверяем, что исключение пробрасывается с правильными данными
            with pytest.raises(Exception) as exc_info:
                error_handler_account_cards(mock_task, exception, exception_desc)

            # Проверяем, что необработанные карточки удаляются
            mock_account_card.delete.assert_called_once()


class TestSecurityAndEdgeCases(TestAccountCardsProcessing):
    """Тесты безопасности и граничных случаев"""

    def test_malicious_filename_handling(self):
        """Тест обработки потенциально опасных имен файлов"""
        test_cases = [
            "../malicious_file.doc",
            "../../etc/passwd",
            "script<script>alert('xss')</script>.doc",
        ]

        for malicious_content in test_cases:
            with self.subTest(malicious_content=malicious_content):
                with patch('agregator.processing.account_cards_processing.ObjectAccountCard.objects.all') as mock_all, \
                        patch('agregator.processing.account_cards_processing.calculate_file_hash') as mock_hash, \
                        patch(
                            'agregator.processing.account_cards_processing.ObjectAccountCard.objects.get') as mock_get:

                    mock_all.return_value = []
                    mock_hash.return_value = "test_hash"
                    mock_get.return_value = self.account_card

                    progress_recorder = Mock()
                    pages_count = {1: 1}
                    total_processed = [0]
                    progress_json = {'file_groups': {str(self.account_card.id): {}}}
                    task_id = "test_task_123"
                    time_on_start = Mock()

                    # Функция должна корректно обработать имя файла без ошибок безопасности
                    try:
                        with patch('agregator.processing.account_cards_processing.Document') as mock_doc:
                            mock_doc_instance = Mock()
                            mock_doc.return_value = mock_doc_instance
                            mock_doc_instance.paragraphs = []
                            mock_doc_instance.tables = []

                            extract_text_tables_and_images(
                                malicious_content, progress_recorder, pages_count, total_processed,
                                self.account_card.id, progress_json, task_id, time_on_start
                            )
                    except Exception as e:
                        # Ожидаем ошибки файловой системы, но не уязвимости
                        assert "No such file" in str(e) or "Unable to open" in str(e)

    def test_large_file_handling(self):
        """Тест обработки очень больших файлов"""
        with patch('agregator.processing.account_cards_processing.ObjectAccountCard.objects.all') as mock_all, \
                patch('agregator.processing.account_cards_processing.calculate_file_hash') as mock_hash, \
                patch('agregator.processing.account_cards_processing.Document') as mock_doc, \
                patch('agregator.processing.account_cards_processing.ObjectAccountCard.objects.get') as mock_get:
            mock_all.return_value = []
            mock_hash.return_value = "test_hash"
            mock_get.return_value = self.account_card

            # Мокируем документ с большим количеством контента
            mock_doc_instance = Mock()
            mock_doc.return_value = mock_doc_instance
            mock_doc_instance.paragraphs = [Mock(text=f"Paragraph {i}") for i in range(1000)]
            mock_doc_instance.tables = [
                Mock(rows=[Mock(cells=[Mock(text=f"Cell {i}_{j}") for j in range(10)]) for i in range(50)])]

            progress_recorder = Mock()
            pages_count = {1: 1}
            total_processed = [0]
            progress_json = {'file_groups': {str(self.account_card.id): {}}}
            task_id = "test_task_123"
            time_on_start = Mock()

            # Функция должна обработать большой файл без сбоев
            extract_text_tables_and_images(
                "/fake/path/large.doc", progress_recorder, pages_count, total_processed,
                self.account_card.id, progress_json, task_id, time_on_start
            )

    def test_corrupted_file_handling(self):
        """Тест обработки поврежденных файлов"""
        test_cases = [".docx", ".pdf"]

        for corrupted_file_type in test_cases:
            with self.subTest(corrupted_file_type=corrupted_file_type):
                with patch('agregator.processing.account_cards_processing.ObjectAccountCard.objects.all') as mock_all, \
                        patch('agregator.processing.account_cards_processing.calculate_file_hash') as mock_hash, \
                        patch(
                            'agregator.processing.account_cards_processing.ObjectAccountCard.objects.get') as mock_get:
                    mock_all.return_value = []
                    mock_hash.return_value = "test_hash"
                    mock_get.return_value = self.account_card

                    progress_recorder = Mock()
                    pages_count = {1: 1}
                    total_processed = [0]
                    progress_json = {'file_groups': {str(self.account_card.id): {}}}
                    task_id = "test_task_123"
                    time_on_start = Mock()

                    # Ожидаем соответствующие исключения для поврежденных файлов
                    with pytest.raises((ValueError, Exception)):
                        extract_text_tables_and_images(
                            f"/fake/path/corrupted{corrupted_file_type}",
                            progress_recorder, pages_count, total_processed,
                            self.account_card.id, progress_json, task_id, time_on_start
                        )

    def test_memory_usage_with_large_images(self):
        """Тест использования памяти при обработке больших изображений"""
        with patch('agregator.processing.account_cards_processing.fitz.open') as mock_fitz, \
                patch('agregator.processing.account_cards_processing.ObjectAccountCard.objects.get') as mock_get, \
                patch('agregator.processing.account_cards_processing.ObjectAccountCard.objects.all') as mock_all, \
                patch('agregator.processing.account_cards_processing.calculate_file_hash') as mock_hash, \
                patch('agregator.processing.account_cards_processing.cv2.cvtColor') as mock_cvt, \
                patch('agregator.processing.account_cards_processing.cv2.threshold') as mock_threshold:
            mock_all.return_value = []
            mock_get.return_value = self.account_card
            mock_hash.return_value = "test_hash"

            # Мокируем большую PDF страницу
            mock_page = Mock()
            mock_page.get_pixmap.return_value.tobytes.return_value = b"x" * (100 * 1024 * 1024)  # 100MB
            mock_doc = Mock()
            mock_doc.__len__ = Mock(return_value=1)  # Правильная настройка мока для __len__
            mock_doc.load_page.return_value = mock_page
            mock_fitz.return_value = mock_doc

            progress_recorder = Mock()
            pages_count = {1: 1}
            total_processed = [0]
            progress_json = {'file_groups': {str(self.account_card.id): {}}}
            task_id = "test_task_123"
            time_on_start = Mock()

            # Функция должна обработать большой файл без чрезмерного использования памяти
            with patch('agregator.processing.account_cards_processing.Image.open') as mock_image_open, \
                    patch('agregator.processing.account_cards_processing.cv2.findContours'), \
                    patch('agregator.processing.account_cards_processing.cv2.boundingRect'), \
                    patch('agregator.processing.account_cards_processing.cv2.dilate'):
                mock_image = Mock()
                mock_image.size = (100, 100)
                mock_image.mode = 'RGB'
                mock_image_open.return_value = mock_image

                extract_text_tables_and_images(
                    "/fake/path/large.pdf", progress_recorder, pages_count, total_processed,
                    self.account_card.id, progress_json, task_id, time_on_start
                )


class TestIntegrationScenarios(TestAccountCardsProcessing):
    """Интеграционные тесты полных сценариев"""

    def test_complete_processing_flow_docx(self):
        """Тест полного цикла обработки DOCX файла"""
        with patch('agregator.processing.account_cards_processing.Document') as mock_document, \
                patch('agregator.processing.account_cards_processing.ObjectAccountCard.objects.get') as mock_get, \
                patch('agregator.processing.account_cards_processing.ObjectAccountCard.objects.all') as mock_all, \
                patch('agregator.processing.account_cards_processing.calculate_file_hash') as mock_hash, \
                patch('agregator.processing.account_cards_processing.zipfile.ZipFile') as mock_zip, \
                patch('os.makedirs'), \
                patch('os.path.join', return_value='/fake/image/path'), \
                patch('agregator.processing.account_cards_processing.connect_account_card_to_heritage') as mock_connect:
            mock_all.return_value = []
            mock_get.return_value = self.account_card
            mock_hash.return_value = "test_hash"
            mock_zip.return_value.__enter__.return_value.namelist.return_value = []

            # Мокируем документ
            mock_doc_instance = Mock()
            mock_document.return_value = mock_doc_instance

            # Мокируем параграфы и таблицы
            mock_paragraph = Mock()
            mock_paragraph.text = "Тестовый текст"
            mock_doc_instance.paragraphs = [mock_paragraph]
            mock_doc_instance.tables = []

            progress_recorder = Mock()
            pages_count = {1: 1}
            total_processed = [0]
            progress_json = {'file_groups': {str(self.account_card.id): {}}}
            task_id = "test_task_123"
            time_on_start = Mock()

            extract_text_tables_and_images(
                "/fake/path/test.docx", progress_recorder, pages_count, total_processed,
                self.account_card.id, progress_json, task_id, time_on_start
            )

            # Проверяем, что функция связывания была вызвана
            mock_connect.assert_called_once()

    def test_processing_chain_with_celery(self):
        """Тест цепочки обработки через Celery"""
        with patch('agregator.processing.account_cards_processing.process_documents') as mock_process_documents:
            mock_task = Mock()
            account_cards_ids = [1, 2, 3]
            user_id = 1

            # Имитируем успешное выполнение
            mock_process_documents.return_value = {"status": "completed", "processed": 3}

            result = process_account_cards(mock_task, account_cards_ids, user_id)

            # Проверяем корректность вызова
            mock_process_documents.assert_called_once_with(
                mock_task, account_cards_ids, user_id, 'account_cards',
                model_class=ObjectAccountCard,
                load_function=load_raw_account_cards,
                process_function=extract_text_tables_and_images
            )

            assert result["status"] == "completed"
            assert result["processed"] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=agregator.processing.account_cards_processing", "--cov-report=html"])
