import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from unittest.mock import patch, MagicMock
from agregator.models import Act

User = get_user_model()


@pytest.mark.django_db
class TestDecorators:
    def test_owner_or_admin_required(self, client, admin_user, test_user):
        """Тест декоратора проверки прав"""
        # Создаем акт от имени обычного пользователя
        act = Act.objects.create(
            user=test_user,
            year="2023"
        )

        # Пытаемся редактировать от имени другого пользователя
        another_user = User.objects.create_user(
            username='another',
            password='pass123'
        )
        client.force_login(another_user)

        response = client.get(reverse('acts_edit', kwargs={'pk': act.id}))
        assert response.status_code == 403  # Forbidden

        # Проверяем доступ администратора
        client.force_login(admin_user)
        response = client.get(reverse('acts_edit', kwargs={'pk': act.id}))
        assert response.status_code == 200
