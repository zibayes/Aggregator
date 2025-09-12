import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from agregator.models import Act

User = get_user_model()


@pytest.mark.django_db
class TestActViews:

    def test_acts_list_view(self):
        """Тест списка актов"""
        client = Client()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.login(username='testuser', password='testpass123')

        # Создаем тестовый акт
        act = Act.objects.create(
            user=user,
            year='2023',
            name_number='test-123',
            is_processing=False,
            is_public=True,
        )

        response = client.get(reverse('acts_register'))

        assert response.status_code == 200
        assert 'test-123' in str(response.content.decode('utf-8'))

    def test_act_detail_view(self):
        """Тест детальной страницы акта"""
        client = Client()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.login(username='testuser', password='testpass123')

        act = Act.objects.create(
            user=user,
            year='2023',
            name_number='test-123'
        )

        response = client.get(reverse('acts', kwargs={'pk': act.id}))

        assert response.status_code == 200
        assert 'test-123' in str(response.content.decode('utf-8'))

    def test_act_edit_view_get(self):
        """Тест GET запроса редактирования акта"""
        client = Client()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.login(username='testuser', password='testpass123')

        act = Act.objects.create(
            user=user,
            year='2023',
            name_number='test-123'
        )

        response = client.get(reverse('acts_edit', kwargs={'pk': act.id}))

        assert response.status_code == 200
        assert 'Редактирование' in str(response.content.decode('utf-8'))

    def test_act_delete_view(self):
        """Тест удаления акта"""
        client = Client()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.login(username='testuser', password='testpass123')

        act = Act.objects.create(
            user=user,
            year='2023',
            name_number='test-123'
        )

        response = client.get(reverse('acts_delete', kwargs={'pk': act.id}))

        assert response.status_code == 302
        assert not Act.objects.filter(id=act.id).exists()
