import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from agregator.models import Act, ScientificReport, OpenLists
from unittest.mock import patch, MagicMock

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


@pytest.mark.django_db
class TestDocumentViews:
    def test_open_lists_register_download(self, client, test_user):
        """Тест скачивания реестра открытых листов"""
        client.force_login(test_user)
        OpenLists.objects.create(
            user=test_user,
            number="123",
            holder="Test Holder"
        )

        response = client.get(reverse('open_lists_register_download'))
        assert response.status_code == 302  # Проверка редиректа на файл

    @patch('agregator.views.get_scan_task')
    def test_archaeological_heritage_sites_view(self, mock_scan, client, test_user):
        """Тест списка археологических памятников"""
        mock_scan.return_value = (False, None, None)
        client.force_login(test_user)

        response = client.get(reverse('archaeological_heritage_sites'))
        assert response.status_code == 200


@pytest.mark.django_db
class TestErrorCases:
    def test_act_detail_not_found(self, client, test_user):
        """Тест 404 для несуществующего акта"""
        client.force_login(test_user)
        response = client.get(reverse('acts', kwargs={'pk': 999}))
        assert response.status_code == 404

    def test_map_with_invalid_type(self, client, test_user):
        """Тест карты с неверным типом документа"""
        client.force_login(test_user)
        response = client.get(reverse('map', kwargs={
            'report_type': 'invalid',
            'pk': 1
        }))
        assert response.status_code == 404
