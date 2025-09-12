import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client

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
