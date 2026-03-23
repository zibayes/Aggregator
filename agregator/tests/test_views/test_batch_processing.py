import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock, ANY
from django.urls import reverse
from django.contrib.auth.models import AnonymousUser
from django.core.files.uploadedfile import SimpleUploadedFile

from agregator.models import UserTasks
from agregator.views.batch_processing import batch_processing_dashboard, scan_directory, process_batch_files


@pytest.mark.django_db
class TestBatchViews:
    """Тесты для пакетной обработки"""

    # ---------------------- batch_processing_dashboard ----------------------

    def test_batch_processing_dashboard_access_denied_for_non_admin(self, client, test_user):
        """Доступ к дашборду только для админа"""
        client.login(username='testuser', password='testpass123')
        url = reverse('batch_processing')
        response = client.get(url)
        # Должен быть редирект или 403 (зависит от конфигурации)
        assert response.status_code in [302, 403]

    def test_batch_processing_dashboard_access_granted_for_admin(self, client, admin_user):
        """Админ может просматривать дашборд"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_processing')
        response = client.get(url)
        assert response.status_code == 200
        assert 'batch_processing_dashboard.html' in [t.name for t in response.templates]
        assert 'default_directories' in response.context
        expected_dirs = {
            'acts': 'uploaded_files/Акты ГИКЭ',
            'scientific_reports': 'uploaded_files/Научные отчёты',
            'tech_reports': 'uploaded_files/Научно-технические отчёты'
        }
        assert response.context['default_directories'] == expected_dirs

    # ---------------------- scan_directory ----------------------

    @patch('agregator.views.batch_processing.scan_and_prepare_batch')
    def test_scan_directory_success(self, mock_scan, client, admin_user):
        """Успешное сканирование директории"""
        # Создаем временную директорию, чтобы os.path.exists вернул True
        with tempfile.TemporaryDirectory() as temp_dir:
            client.login(username='admin', password='adminpass123')
            url = reverse('batch_scan')

            # Подготавливаем мок
            mock_scan.return_value = {
                'files': [
                    {'name': 'file1.pdf', 'path': os.path.join(temp_dir, 'file1.pdf'), 'exists': False},
                    {'name': 'file2.pdf', 'path': os.path.join(temp_dir, 'file2.pdf'), 'exists': True},
                ],
                'total_scanned': 2,
                'new_files_count': 1,
                'existing_files_count': 1
            }

            post_data = {
                'directory': temp_dir,
                'file_type': 'act',
                'page': '1',
                'limit': '1000'
            }

            response = client.post(url, post_data)
            assert response.status_code == 200
            data = response.json()

            assert data['total_count'] == 2
            assert data['new_files'] == 1
            assert data['existing_files'] == 1
            assert len(data['files']) == 2
            assert data['has_next'] is False
            assert data['has_previous'] is False
            assert data['current_page'] == 1
            assert data['total_pages'] == 1

            # Проверяем вызов scan_and_prepare_batch
            mock_scan.assert_called_once_with(temp_dir, 'act', admin_user, limit=1000)

    def test_scan_directory_method_not_allowed(self, client, admin_user):
        """GET запрос запрещен"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_scan')
        response = client.get(url)
        assert response.status_code == 405
        assert response.json()['error'] == 'Метод не разрешен'

    def test_scan_directory_missing_directory(self, client, admin_user):
        """Отсутствует параметр directory"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_scan')
        response = client.post(url, {})
        assert response.status_code == 400
        assert response.json()['error'] == 'Не указана директория'

    def test_scan_directory_nonexistent_directory(self, client, admin_user):
        """Директория не существует"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_scan')
        response = client.post(url, {'directory': '/nonexistent/path'})
        assert response.status_code == 400
        assert response.json()['error'] == 'Директория не существует'

    @patch('agregator.views.batch_processing.scan_and_prepare_batch')
    def test_scan_directory_with_pagination(self, mock_scan, client, admin_user):
        """Проверка пагинации при большом количестве файлов"""
        with tempfile.TemporaryDirectory() as temp_dir:
            client.login(username='admin', password='adminpass123')
            url = reverse('batch_scan')

            # Создаем 250 файлов
            files = [{'name': f'file{i}.pdf', 'path': os.path.join(temp_dir, f'file{i}.pdf'), 'exists': False} for i in
                     range(250)]
            mock_scan.return_value = {
                'files': files,
                'total_scanned': 250,
                'new_files_count': 250,
                'existing_files_count': 0
            }

            # Первая страница
            response = client.post(url, {'directory': temp_dir, 'page': '1'})
            data = response.json()
            assert len(data['files']) == 100  # page_size = 100
            assert data['has_next'] is True
            assert data['has_previous'] is False
            assert data['current_page'] == 1
            assert data['total_pages'] == 3

            # Вторая страница
            response = client.post(url, {'directory': temp_dir, 'page': '2'})
            data = response.json()
            assert len(data['files']) == 100
            assert data['has_next'] is True
            assert data['has_previous'] is True
            assert data['current_page'] == 2

            # Последняя страница
            response = client.post(url, {'directory': temp_dir, 'page': '3'})
            data = response.json()
            assert len(data['files']) == 50
            assert data['has_next'] is False
            assert data['has_previous'] is True
            assert data['current_page'] == 3

    @patch('agregator.views.batch_processing.scan_and_prepare_batch')
    @patch('agregator.views.batch_processing.os.path.exists')
    def test_scan_directory_exception(self, mock_exists, mock_scan, client, admin_user):
        """Обработка исключения при сканировании"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_scan')

        # Делаем так, чтобы директория существовала
        mock_exists.return_value = True
        mock_scan.side_effect = Exception("Scan error")

        response = client.post(url, {'directory': '/fake/dir'})
        assert response.status_code == 500
        assert 'Ошибка при сканировании' in response.json()['error']

    def test_scan_directory_access_denied_for_non_admin(self, client, test_user):
        """Доступ только для админа"""
        client.login(username='testuser', password='testpass123')
        url = reverse('batch_scan')
        response = client.post(url, {'directory': '/tmp/test'})
        assert response.status_code in [302, 403]

    # ---------------------- process_batch_files ----------------------

    @patch('agregator.views.batch_processing.create_act_from_existing_file')
    @patch('agregator.views.batch_processing.process_acts')
    def test_process_batch_files_success(self, mock_process_acts, mock_create, client, admin_user):
        """Успешный запуск пакетной обработки"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_process')

        # Настройка моков
        mock_create.return_value = 1
        mock_task = MagicMock()
        mock_task.task_id = 'test-task-id'
        mock_process_acts.apply_async.return_value = mock_task

        post_data = {
            'file_paths': ['/tmp/file1.pdf', '/tmp/file2.pdf'],
            'file_type': 'act',
            'select_text': True,
            'select_enrich': True,
            'select_image': True,
            'select_coord': True,
            'is_public': True
        }

        response = client.post(url, json.dumps(post_data), content_type='application/json')
        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['task_id'] == 'test-task-id'
        assert data['processed_count'] == 2
        assert 'Запущена обработка 2 файлов' in data['message']

        # Проверяем, что create_act_from_existing_file вызван для каждого файла
        assert mock_create.call_count == 2
        # Проверяем аргументы
        mock_create.assert_any_call(
            {'path': '/tmp/file1.pdf', 'name': 'file1.pdf'},
            admin_user,
            True
        )
        mock_create.assert_any_call(
            {'path': '/tmp/file2.pdf', 'name': 'file2.pdf'},
            admin_user,
            True
        )

        # Проверяем запуск задачи (игнорируем link_error, т.к. сложно замокать)
        mock_process_acts.apply_async.assert_called_once()
        args, kwargs = mock_process_acts.apply_async.call_args
        assert args == ()
        assert kwargs['args'] == [[1, 1], admin_user.id, True, True, True, True]
        # link_error может быть любым объектом, не проверяем его

        # Проверяем создание UserTasks
        user_task = UserTasks.objects.filter(task_id='test-task-id').first()
        assert user_task is not None
        assert user_task.user == admin_user
        assert user_task.files_type == 'act'
        assert json.loads(user_task.upload_source) == {'source': 'Пользовательский файл'}

    def test_process_batch_files_method_not_allowed(self, client, admin_user):
        """GET запрос запрещен"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_process')
        response = client.get(url)
        assert response.status_code == 405
        assert response.json()['error'] == 'Метод не разрешен'

    def test_process_batch_files_no_files(self, client, admin_user):
        """Не выбраны файлы для обработки"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_process')
        post_data = {'file_paths': [], 'file_type': 'act'}
        response = client.post(url, json.dumps(post_data), content_type='application/json')
        assert response.status_code == 400
        assert response.json()['error'] == 'Не выбраны файлы для обработки'

    @patch('agregator.views.batch_processing.create_act_from_existing_file')
    def test_process_batch_files_creation_failure(self, mock_create, client, admin_user):
        """Ни один файл не удалось создать"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_process')

        # Оба файла не создаются
        mock_create.side_effect = [None, None]

        post_data = {
            'file_paths': ['/tmp/file1.pdf', '/tmp/file2.pdf'],
            'file_type': 'act'
        }
        response = client.post(url, json.dumps(post_data), content_type='application/json')
        assert response.status_code == 400
        assert 'Не удалось создать ни одной записи' in response.json()['error']

    @patch('agregator.views.batch_processing.create_act_from_existing_file')
    @patch('agregator.views.batch_processing.process_acts')
    def test_process_batch_files_partial_success(self, mock_process_acts, mock_create, client, admin_user):
        """Часть файлов создана успешно, остальные с ошибками"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_process')

        # Первый файл успешно, второй с ошибкой
        mock_create.side_effect = [1, Exception("Creation error")]
        mock_task = MagicMock()
        mock_task.task_id = 'test-task-id'
        mock_process_acts.apply_async.return_value = mock_task

        post_data = {
            'file_paths': ['/tmp/file1.pdf', '/tmp/file2.pdf'],
            'file_type': 'act'
        }
        response = client.post(url, json.dumps(post_data), content_type='application/json')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert data['processed_count'] == 1
        assert 'warnings' in data
        assert 'Creation error' in data['warnings'][0]

        # Проверяем, что задача запущена только для успешно созданных файлов
        mock_process_acts.apply_async.assert_called_once()
        args, kwargs = mock_process_acts.apply_async.call_args
        assert kwargs['args'] == [[1], admin_user.id, True, True, True, True]

    @patch('agregator.views.batch_processing.create_act_from_existing_file')
    def test_process_batch_files_unsupported_type(self, mock_create, client, admin_user):
        """Неподдерживаемый тип файла"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_process')

        post_data = {
            'file_paths': ['/tmp/file1.pdf'],
            'file_type': 'unsupported'
        }
        response = client.post(url, json.dumps(post_data), content_type='application/json')
        assert response.status_code == 400
        assert 'Обработка типа unsupported не реализована' in response.json()['error']

    @patch('agregator.views.batch_processing.create_act_from_existing_file')
    @patch('agregator.views.batch_processing.process_acts')
    def test_process_batch_files_without_options(self, mock_process_acts, mock_create, client, admin_user):
        """Запуск с опциями по умолчанию (без дополнительных параметров)"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_process')

        mock_create.return_value = 1
        mock_task = MagicMock()
        mock_task.task_id = 'test-task-id'
        mock_process_acts.apply_async.return_value = mock_task

        post_data = {
            'file_paths': ['/tmp/file1.pdf'],
            'file_type': 'act'
        }
        response = client.post(url, json.dumps(post_data), content_type='application/json')

        assert response.status_code == 200
        mock_create.assert_called_with({'path': '/tmp/file1.pdf', 'name': 'file1.pdf'}, admin_user, True)
        mock_process_acts.apply_async.assert_called_once()
        args, kwargs = mock_process_acts.apply_async.call_args
        assert kwargs['args'] == [[1], admin_user.id, True, True, True, True]

    @patch('agregator.views.batch_processing.create_act_from_existing_file')
    @patch('agregator.views.batch_processing.process_acts')
    def test_process_batch_files_with_options(self, mock_process_acts, mock_create, client, admin_user):
        """Запуск с пользовательскими опциями"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_process')

        mock_create.return_value = 1
        mock_task = MagicMock()
        mock_task.task_id = 'test-task-id'
        mock_process_acts.apply_async.return_value = mock_task

        post_data = {
            'file_paths': ['/tmp/file1.pdf'],
            'file_type': 'act',
            'select_text': False,
            'select_enrich': False,
            'select_image': True,
            'select_coord': False,
            'is_public': False
        }
        response = client.post(url, json.dumps(post_data), content_type='application/json')

        assert response.status_code == 200
        mock_create.assert_called_with({'path': '/tmp/file1.pdf', 'name': 'file1.pdf'}, admin_user, False)
        mock_process_acts.apply_async.assert_called_once()
        args, kwargs = mock_process_acts.apply_async.call_args
        assert kwargs['args'] == [[1], admin_user.id, False, False, True, False]

    @patch('agregator.views.batch_processing.create_act_from_existing_file')
    @patch('agregator.views.batch_processing.process_acts')
    def test_process_batch_files_exception_in_processing(self, mock_process_acts, mock_create, client, admin_user):
        """Ошибка при запуске задачи"""
        client.login(username='admin', password='adminpass123')
        url = reverse('batch_process')

        mock_create.return_value = 1
        mock_process_acts.apply_async.side_effect = Exception("Task error")

        post_data = {
            'file_paths': ['/tmp/file1.pdf'],
            'file_type': 'act'
        }
        response = client.post(url, json.dumps(post_data), content_type='application/json')
        assert response.status_code == 500
        assert 'Ошибка при обработке' in response.json()['error']

    def test_process_batch_files_access_denied_for_non_admin(self, client, test_user):
        """Доступ только для админа"""
        client.login(username='testuser', password='testpass123')
        url = reverse('batch_process')
        response = client.post(url, json.dumps({'file_paths': []}), content_type='application/json')
        assert response.status_code in [302, 403]
