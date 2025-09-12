import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from agregator.models import Act

User = get_user_model()


@pytest.mark.django_db
class TestAPIViews:

    def test_user_list_api(self):
        """Тест API списка пользователей"""
        client = APIClient()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.force_authenticate(user=user)

        response = client.get(reverse('user-list'))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_act_detail_api(self):
        """Тест API детальной информации акта"""
        client = APIClient()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.force_authenticate(user=user)

        act = Act.objects.create(
            user=user,
            year='2023',
            name_number='test-123'
        )

        response = client.get(reverse('act-detail', kwargs={'pk': act.id}))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['name_number'] == 'test-123'
