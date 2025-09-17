import pytest
import json
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from django_celery_results.models import TaskResult
from unittest.mock import patch, MagicMock

User = get_user_model()


# Тесты для API views
@pytest.mark.django_db
class TestUserTasksAPI:
    """Тесты для функций получения задач пользователя"""

    def test_get_user_tasks_reports_authenticated(self, client, test_user, test_tasks):
        """Тест получения задач отчетов для авторизованного пользователя"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('get_user_tasks_reports'))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'tasks_id' in data
        # Должны вернуться только задачи с типами act, scientific_report, tech_report
        assert len(data['tasks_id']) == 3
        assert all(task_id.startswith('test_task_') for task_id in data['tasks_id'])

    def test_get_user_tasks_reports_unauthenticated(self, client):
        """Тест получения задач отчетов для неавторизованного пользователя"""
        response = client.get(reverse('get_user_tasks_reports'))

        assert response.status_code == 302  # Редирект на логин

    def test_get_user_tasks_open_lists(self, client, test_user, test_tasks):
        """Тест получения задач открытых листов"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('get_user_tasks_open_lists'))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'tasks_id' in data
        assert len(data['tasks_id']) == 1
        assert data['tasks_id'][0] == 'test_task_3'

    @pytest.mark.parametrize('admin_exists', [True, False])
    def test_get_user_tasks_external(self, client, test_user, admin_user, test_tasks, admin_tasks, admin_exists):
        """Тест получения внешних задач (с админом и без)"""
        client.login(username='testuser', password='testpass123')

        if not admin_exists:
            # Удаляем админа чтобы проверить fallback на текущего пользователя
            User.objects.filter(is_superuser=True).delete()

        response = client.get(reverse('get_user_tasks_external'))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'tasks_id' in data

        if admin_exists:
            # Должны вернуться задачи админа с external source
            assert len(data['tasks_id']) == 4
            assert all(task_id.startswith('admin_task_') for task_id in data['tasks_id'])
        else:
            # Должны вернуться задачи текущего пользователя с external source
            # Но у test_user все задачи с 'Пользовательский файл', поэтому пустой список
            assert len(data['tasks_id']) == 0

    def test_get_user_tasks_object_account_cards(self, client, test_user, test_tasks):
        """Тест получения задач учетных карточек"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('get_user_tasks_object_account_cards'))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'tasks_id' in data
        assert len(data['tasks_id']) == 1
        assert data['tasks_id'][0] == 'test_task_4'

    def test_get_user_tasks_commercial_offers(self, client, test_user, test_tasks):
        """Тест получения задач коммерческих предложений"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('get_user_tasks_commercial_offers'))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'tasks_id' in data
        assert len(data['tasks_id']) == 1
        assert data['tasks_id'][0] == 'test_task_5'

    def test_get_user_tasks_geo_objects(self, client, test_user, test_tasks):
        """Тест получения задач геообъектов"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('get_user_tasks_geo_objects'))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'tasks_id' in data
        assert len(data['tasks_id']) == 1
        assert data['tasks_id'][0] == 'test_task_6'

    def test_get_user_tasks_empty(self, client, test_user):
        """Тест получения задач когда их нет"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('get_user_tasks_reports'))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['tasks_id'] == []

    def test_get_user_tasks_different_users(self, client, test_user, admin_user, test_tasks):
        """Тест что пользователи видят только свои задачи"""
        # Создаем задачи для админа
        from agregator.models import UserTasks
        admin_task = UserTasks.objects.create(
            user=admin_user,
            task_id='admin_task',
            files_type='act',
            upload_source={'source': 'test'}
        )
        TaskResult.objects.create(
            task_id='admin_task',
            status='SUCCESS',
            result='{"message": "success"}'
        )

        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('get_user_tasks_reports'))

        assert response.status_code == 200
        data = json.loads(response.content)
        # Должны вернуться только задачи test_user, не админа
        assert 'admin_task' not in data['tasks_id']
        assert len(data['tasks_id']) == 3

    @pytest.mark.parametrize('task_status', ['SUCCESS', 'FAILURE', 'PENDING', 'PROGRESS'])
    def test_get_user_tasks_different_statuses(self, client, test_user, task_status):
        """Тест получения задач с разными статусами"""
        from agregator.models import UserTasks

        task = UserTasks.objects.create(
            user=test_user,
            task_id=f'test_task_{task_status}',
            files_type='act',
            upload_source={'source': 'Пользовательский файл'}
        )
        TaskResult.objects.create(
            task_id=f'test_task_{task_status}',
            status=task_status,
            result='{"message": "test"}'
        )

        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('get_user_tasks_reports'))

        assert response.status_code == 200
        data = json.loads(response.content)
        # Все задачи должны возвращаться независимо от статуса
        assert f'test_task_{task_status}' in data['tasks_id']

    def test_get_user_tasks_filter_upload_source(self, client, test_user):
        """Тест фильтрации по источнику загрузки"""
        from agregator.models import UserTasks

        # Задача с источником 'Пользовательский файл'
        task1 = UserTasks.objects.create(
            user=test_user,
            task_id='user_file_task',
            files_type='act',
            upload_source={'source': 'Пользовательский файл'}
        )

        # Задача с другим источником
        task2 = UserTasks.objects.create(
            user=test_user,
            task_id='external_task',
            files_type='act',
            upload_source={'source': 'external'}
        )

        for task in [task1, task2]:
            TaskResult.objects.create(
                task_id=task.task_id,
                status='SUCCESS',
                result='{"message": "test"}'
            )

        client.login(username='testuser', password='testpass123')

        # get_user_tasks_reports использует upload_source=False по умолчанию
        # (только 'Пользовательский файл')
        response = client.get(reverse('get_user_tasks_reports'))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['tasks_id'] == ['user_file_task']  # Только пользовательские файлы

    @patch('agregator.views.get_user_tasks')
    def test_get_user_tasks_exception_handling(self, mock_get_user_tasks, client, test_user):
        """Тест обработки исключений в get_user_tasks"""
        mock_get_user_tasks.side_effect = Exception("Test error")

        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('get_user_tasks_reports'))

        # Должен вернуться пустой список при ошибке
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['tasks_id'] == []


# Дополнительные интеграционные тесты
@pytest.mark.django_db
class TestUserTasksIntegration:
    """Интеграционные тесты для полного потока задач"""

    def test_multiple_task_types_integration(self, client, test_user, test_tasks):
        """Интеграционный тест всех типов задач"""
        client.login(username='testuser', password='testpass123')

        # Тестируем все endpoints
        endpoints = [
            ('get_user_tasks_reports', 3),
            ('get_user_tasks_open_lists', 1),
            ('get_user_tasks_object_account_cards', 1),
            ('get_user_tasks_commercial_offers', 1),
            ('get_user_tasks_geo_objects', 1)
        ]

        for endpoint, expected_count in endpoints:
            response = client.get(reverse(endpoint))
            assert response.status_code == 200
            data = json.loads(response.content)
            assert len(data['tasks_id']) == expected_count

    def test_tasks_ordering(self, client, test_user):
        """Тест что задачи возвращаются в правильном порядке (последние first)"""
        from agregator.models import UserTasks
        from django.utils import timezone
        from datetime import timedelta

        # Создаем задачи с разным временем создания
        for i in range(3):
            task = UserTasks.objects.create(
                user=test_user,
                task_id=f'task_{i}',
                files_type='act',
                upload_source={'source': 'Пользовательский файл'}
            )
            # Меняем дату создания для теста порядка
            TaskResult.objects.create(
                task_id=f'task_{i}',
                status='SUCCESS',
                result='{"message": "test"}',
                date_done=timezone.now() - timedelta(hours=i)  # task_0 - самая старая
            )

        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('get_user_tasks_reports'))

        assert response.status_code == 200
        data = json.loads(response.content)
        # Задачи должны быть отсортированы от новых к старым
        assert data['tasks_id'] == ['task_2', 'task_1', 'task_0']
