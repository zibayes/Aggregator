import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from unittest.mock import patch, MagicMock

User = get_user_model()


@pytest.mark.django_db
class TestAuthViews:

    def test_user_login_success(self):
        """Тест успешного логина"""
        client = Client()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

        response = client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })

        assert response.status_code == 302
        assert response.url == reverse('profile')

    def test_user_login_failure(self):
        """Тест неудачного логина"""
        client = Client()

        response = client.post(reverse('login'), {
            'username': 'wronguser',
            'password': 'wrongpass'
        })

        assert response.status_code == 200
        assert 'Неверные учетные данные' in str(response.content.decode('utf-8'))

    def test_user_register_success(self):
        """Тест успешной регистрации"""
        client = Client()

        response = client.post(reverse('register'), {
            'username': 'newuser',
            'password1': 'complexpass123',
            'password2': 'complexpass123',
            'email': 'new@example.com'
        })

        assert response.status_code == 302
        assert User.objects.filter(username='newuser').exists()

    def test_user_logout(self):
        """Тест выхода из системы"""
        client = Client()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('logout'))

        assert response.status_code == 302
        assert response.url == reverse('index')

    def test_user_register_get(self, client):
        """Тест GET запроса регистрации"""
        response = client.get(reverse('register'))
        assert response.status_code == 200
        assert 'register.html' in [t.name for t in response.templates]

    def test_user_register_post_success(self, client):
        """Тест успешной регистрации"""
        response = client.post(reverse('register'), {
            'username': 'newuser',
            'password1': 'complexpassword123',
            'password2': 'complexpassword123',
            'email': 'new@example.com'
        })

        assert response.status_code == 302
        assert User.objects.filter(username='newuser').exists()

    def test_user_register_post_failure(self, client):
        """Тест неудачной регистрации"""
        response = client.post(reverse('register'), {
            'username': 'newuser',
            'password1': 'pass1',
            'password2': 'pass2',  # Пароли не совпадают
            'email': 'new@example.com'
        })

        assert response.status_code == 200
        assert 'Неверные учетные данные' in str(response.content)

    def test_user_login_get(self, client):
        """Тест GET запроса логина"""
        response = client.get(reverse('login'))
        assert response.status_code == 200
        assert 'login.html' in [t.name for t in response.templates]

    def test_user_login_post_success(self, client, test_user):
        """Тест успешного логина"""
        response = client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })

        assert response.status_code == 302
        assert response.url == reverse('profile')

    def test_user_login_post_failure(self, client):
        """Тест неудачного логина"""
        response = client.post(reverse('login'), {
            'username': 'nonexistent',
            'password': 'wrongpassword'
        })

        assert response.status_code == 200
        assert 'Неверные учетные данные' in str(response.content)


@pytest.mark.django_db
class TestProfileViews:

    def test_profile_view_authenticated(self):
        """Тест просмотра профиля аутентифицированным пользователем"""
        client = Client()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('profile'))

        assert response.status_code == 200
        assert 'testuser' in str(response.content.decode('utf-8'))

    def test_profile_view_unauthenticated(self):
        """Тест редиректа для неаутентифицированного пользователя"""
        client = Client()

        response = client.get(reverse('profile'))

        assert response.status_code == 302
        assert '/login' in response.url

    def test_settings_get(self, client, test_user):
        """Тест страницы настроек"""
        client.force_login(test_user)
        response = client.get(reverse('settings'))
        assert response.status_code == 200
        assert 'settings.html' in [t.name for t in response.templates]

    @patch('agregator.views.update_session_auth_hash')
    def test_settings_post(self, mock_update_hash, client, test_user):
        """Тест сохранения настроек"""
        client.force_login(test_user)

        response = client.post(reverse('settings'), {
            'first_name': 'Иван',
            'last_name': 'Иванов',
            'username': 'newusername',
            'email': 'new@example.com',
            'password': ''  # Без смены пароля
        })

        assert response.status_code == 302
        test_user.refresh_from_db()
        assert test_user.first_name == 'Иван'
        assert test_user.username == 'newusername'
