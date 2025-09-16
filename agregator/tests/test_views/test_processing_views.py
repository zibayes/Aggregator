import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from agregator.models import Act, User
from django_celery_results.models import TaskResult
from unittest.mock import patch, MagicMock
import pandas as pd
from agregator.processing.coordinates_extraction import process_coords_from_edit_page
from agregator.views.utils import generate_excel_report
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestCoordinatesProcessing:
    def test_process_coords_from_edit_page(self, rf, test_user):
        """Тест обработки координат из формы редактирования"""
        request = rf.post('/fake-url', {
            'group[0]': 'group',
            'coordinate_system[group]': 'wgs84',
            'point[group]': 'point1; 55.7558; 37.6176',
        })

        request.user = test_user

        act = Act.objects.create(
            user=test_user,
            year="2023"
        )

        result = process_coords_from_edit_page(request, act)
        assert 'group' in result
        assert 'point1' in result['group']
        assert result['group']['point1'] == ['55.7558', '37.6176']

    def test_process_coords_different_systems(self, rf, test_user):
        """Тест обработки координат в разных системах"""
        request = rf.post('/fake-url', {
            'group[0]': 'group',
            'coordinate_system[group]': 'custom',
            'point[group]': 'point1; 100; 200',
        })

        request.user = test_user

        act = Act.objects.create(user=test_user)
        result = process_coords_from_edit_page(request, act)

        assert 'group' in result
        assert result['group']['coordinate_system'] == 'custom'


@pytest.mark.django_db
class TestFileProcessing:
    def test_generate_excel_report(self, tmp_path):
        """Тест генерации Excel отчета"""
        df = pd.DataFrame({'col1': [1, 2], 'col2': [3, 4]})
        output_path = tmp_path / "report.xlsx"

        generate_excel_report(df, str(output_path), {'A': 20})

        assert output_path.exists()
        # Можно добавить проверку содержимого файла

    @patch('agregator.views.create_model_dataframe')
    def test_create_model_dataframe_empty(self, mock_create):
        """Тест создания DataFrame из пустой модели"""
        client = APIClient()
        mock_create.return_value = None
        response = client.get(reverse('acts_register_download'))
        assert response.status_code == 302  # Редирект при пустых данных


@pytest.mark.django_db
class TestExternalProcessing:
    @patch('agregator.views.external_sources_processing.delay')
    def test_external_sources_scan(self, mock_delay, client, test_user):
        """Тест запуска сканирования внешних источников"""
        client.force_login(test_user)

        # Создаем суперпользователя
        User.objects.create_superuser('admin', 'admin@example.com', 'adminpass')

        mock_task = MagicMock()
        mock_task.id = 'scan-task-123'
        mock_delay.return_value = mock_task

        response = client.post(reverse('external_sources'), {
            'select_text': 'on',
            'select_image': 'on',
            'select_coord': 'on'
        })

        assert response.status_code == 200
        mock_delay.assert_called_once()


@pytest.mark.django_db
class TestErrorHandling:
    def test_check_external_scan_progress_invalid_task(self, client, test_user):
        """Тест проверки прогресса несуществующей задачи"""
        client.force_login(test_user)
        response = client.get(reverse('check_external_scan_progress', kwargs={'task_id': 'invalid'}))
        assert response.status_code == 200
        assert response.json()['state'] in ['PENDING', 'UNKNOWN']

    def test_cancel_external_scan_task_invalid(self, client, test_user):
        """Тест отмены несуществующей задачи"""
        client.force_login(test_user)
        response = client.get(reverse('cancel_external_scan_task', kwargs={'task_id': 'invalid'}))
        assert response.status_code == 200
        json_data = response.json()
        assert json_data.get('status') == 'success'
        assert 'message' in json_data
