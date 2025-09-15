import pytest
import json
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from unittest.mock import patch, MagicMock, mock_open
from django.core.files.uploadedfile import SimpleUploadedFile
from agregator.models import (
    Act, ScientificReport, TechReport, OpenLists, UserTasks, TaskResult,
    ArchaeologicalHeritageSite, IdentifiedArchaeologicalHeritageSite,
    ObjectAccountCard, CommercialOffers, GeoObject, GeojsonData, Chat, Message
)

User = get_user_model()


@pytest.mark.django_db
class TestEdgeCases:
    """ТЕСТЫ ГРАНИЧНЫХ СЛУЧАЕВ"""

    def test_deconstructor_no_files(self, client, test_user):
        """Тест deconstructor без файлов"""
        client.force_login(test_user)

        response = client.post(reverse('deconstructor'), {
            'file_type': 'act',
            'upload_type': 'fully'
        })

        assert response.status_code == 200  # Должен вернуть форму с ошибками

    def test_deconstructor_invalid_form(self, client, test_user):
        """Тест deconstructor с невалидной формой"""
        client.force_login(test_user)

        response = client.post(reverse('deconstructor'), {})
        assert response.status_code == 200

    def test_external_sources_no_superuser(self, client, test_user):
        """Тест external_sources без суперпользователя"""
        client.force_login(test_user)

        # Убедимся что нет суперпользователя
        User.objects.filter(is_superuser=True).delete()

        response = client.get(reverse('external_sources'))
        assert response.status_code == 200  # Должен работать с текущим пользователем

    def test_get_user_tasks_external_no_superuser(self, client, test_user):
        """Тест получения внешних задач без суперпользователя"""
        client.force_login(test_user)

        # Убедимся что нет суперпользователя
        User.objects.filter(is_superuser=True).delete()

        response = client.get(reverse('get_user_tasks_external'))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'tasks_id' in data

    def test_doc_reprocess_invalid_referer(self, client, test_user):
        """Тест переобработки с неверным referer"""
        client.force_login(test_user)

        response = client.post(reverse('doc_reprocess', kwargs={'pk': 999}), {
            'select_text': 'on'
        }, HTTP_REFERER='http://invalid.com/')

        assert response.status_code == 404

    def test_doc_reprocess_no_referer(self, client, test_user):
        """Тест переобработки без referer"""
        client.force_login(test_user)

        response = client.post(reverse('doc_reprocess', kwargs={'pk': 999}), {
            'select_text': 'on'
        })

        assert response.status_code == 404

    def test_check_external_scan_progress_invalid_task(self, client, test_user):
        """Тест проверки прогресса несуществующей задачи"""
        client.force_login(test_user)

        response = client.get(reverse('check_external_scan_progress', kwargs={'task_id': 'nonexistent-task'}))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['state'] in ['PENDING', 'UNKNOWN']

    def test_cancel_external_scan_task_invalid(self, client, test_user):
        """Тест отмены несуществующей задачи"""
        client.force_login(test_user)

        response = client.get(reverse('cancel_external_scan_task', kwargs={'task_id': 'nonexistent-task'}))
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['status'] == 'error'

    def test_geojson_polygons_invalid_data(self, client, test_user):
        """Тест получения полигонов с невалидными данными"""
        client.force_login(test_user)

        response = client.post(reverse('get_geojson_polygons'),
                               'invalid json',
                               content_type='application/json')

        assert response.status_code == 400

    def test_ask_gpt_invalid_json(self, client, test_user):
        """Тест запроса к GPT с невалидным JSON"""
        client.force_login(test_user)

        response = client.post(reverse('ask_gpt'),
                               'invalid json',
                               content_type='application/json')

        assert response.status_code == 400

    def test_create_gpt_chat_invalid_data(self, client, test_user):
        """Тест создания чата с невалидными данными"""
        client.force_login(test_user)

        response = client.post(reverse('create_gpt_chat'),
                               'invalid json',
                               content_type='application/json')

        assert response.status_code == 400

    def test_edit_gpt_chat_invalid_data(self, client, test_user):
        """Тест редактирования чата с невалидными данными"""
        client.force_login(test_user)

        response = client.post(reverse('edit_gpt_chat'),
                               'invalid json',
                               content_type='application/json')

        assert response.status_code == 400

    def test_delete_gpt_chat_invalid_data(self, client, test_user):
        """Тест удаления чата с невалидными данными"""
        client.force_login(test_user)

        response = client.post(reverse('delete_gpt_chat'),
                               'invalid json',
                               content_type='application/json')

        assert response.status_code == 400

    def test_edit_chat_message_invalid_data(self, client, test_user):
        """Тест редактирования сообщения с невалидными данными"""
        client.force_login(test_user)

        response = client.post(reverse('edit_chat_message'),
                               'invalid json',
                               content_type='application/json')

        assert response.status_code == 400

    def test_delete_chat_message_invalid_data(self, client, test_user):
        """Тест удаления сообщения с невалидными данными"""
        client.force_login(test_user)

        response = client.post(reverse('delete_chat_message'),
                               'invalid json',
                               content_type='application/json')

        assert response.status_code == 400
