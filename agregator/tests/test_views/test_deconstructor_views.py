import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from unittest.mock import patch, MagicMock

User = get_user_model()


@pytest.mark.django_db
class TestDeconstructorViews:

    def test_deconstructor_get(self, client, test_user):
        """Тест GET запроса deconstructor"""
        client.force_login(test_user)

        response = client.get(reverse('deconstructor'))

        assert response.status_code == 200
        assert 'deconstructor.html' in [t.name for t in response.templates]

    @patch('agregator.views.raw_reports_save')
    @patch('agregator.views.process_acts.apply_async')
    def test_deconstructor_post_act(self, mock_apply, mock_save, client, test_user):
        """Тест POST deconstructor для актов"""
        client.force_login(test_user)

        mock_save.return_value = [1]
        mock_task = MagicMock()
        mock_task.task_id = 'test-task-123'
        mock_apply.return_value = mock_task

        with patch('agregator.views.UserTasks.objects.create') as mock_create:
            response = client.post(reverse('deconstructor'), {
                'file_type': 'act',
                'upload_type': 'fully',
                'storage_type': 'private',
                'select_text': 'on',
                'select_image': 'on',
                'select_coord': 'on'
            })

        assert response.status_code == 200
        mock_save.assert_called_once()
        mock_apply.assert_called_once()


@pytest.mark.django_db
class TestExternalSourcesViews:

    def test_external_sources_get(self, client, test_user):
        """Тест GET запроса external_sources"""
        # Создаем суперпользователя чтобы избежать ошибки
        User.objects.create_superuser(
            username='admin',
            password='adminpass',
            email='admin@example.com'
        )
        client.force_login(test_user)

        response = client.get(reverse('external_sources'))

        assert response.status_code == 200

    @patch('agregator.views.external_sources_processing.delay')
    def test_external_sources_post(self, mock_delay, client, test_user):
        """Тест POST external_sources"""
        # Создаем суперпользователя
        User.objects.create_superuser(
            username='admin',
            password='adminpass',
            email='admin@example.com'
        )
        client.force_login(test_user)

        mock_task = MagicMock()
        mock_task.id = 'test-task-456'
        mock_delay.return_value = mock_task

        response = client.post(reverse('external_sources'), {
            'select_text': 'on',
            'select_image': 'on',
            'select_coord': 'on'
        })

        assert response.status_code == 200


@pytest.mark.django_db
class TestMapViews:

    def test_interactive_map(self, client, test_user):
        """Тест interactive_map"""
        client.force_login(test_user)

        # Создаем тестовые данные с координатами И source
        from agregator.models import Act
        act = Act.objects.create(
            user=test_user,
            year='2023',
            name_number='test-map',
            is_processing=False,
            source=[{'origin_filename': 'test.pdf', 'path': '/test/path'}],  # ← ДОБАВЬ source!
            coordinates={'test_point': [55.7558, 37.6176]}
        )

        response = client.get(reverse('interactive_map'))

        assert response.status_code == 200

    def test_map_detail(self, client, test_user):
        """Тест детальной карты"""
        client.force_login(test_user)

        from agregator.models import Act
        act = Act.objects.create(
            user=test_user,
            year='2023',
            name_number='test-map',
            is_processing=False,
            source=[{'origin_filename': 'test.pdf', 'path': '/test/path'}],  # ← ДОБАВЬ source!
            coordinates={'test_point': [55.7558, 37.6176]}
        )

        response = client.get(reverse('map', kwargs={
            'report_type': 'act',
            'pk': act.id
        }))

        assert response.status_code == 200
