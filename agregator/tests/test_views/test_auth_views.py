import pytest
import io
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client, override_settings
from django.contrib import messages
from django.core.files.images import ImageFile

User = get_user_model()


# Тесты для регистрации
@pytest.mark.django_db
class TestUserRegister:
    """Тесты для функции user_register"""

    @pytest.mark.parametrize('method', ['get', 'post'])
    def test_register_methods(self, client, method):
        """Тест GET и POST запросов к регистрации"""
        url = reverse('register')

        if method == 'get':
            response = client.get(url)
            assert response.status_code == 200
            assert 'form' in response.context
            assert 'register.html' in [t.name for t in response.templates]
        else:
            response = client.post(url, {})
            assert response.status_code == 200  # Ожидаем ошибку валидации

    @pytest.mark.parametrize('user_data, expected_status, should_create', [
        ({
             'username': 'validuser',
             'password1': 'complexpass123!',
             'password2': 'complexpass123!',
             'email': 'valid@example.com'
         }, 302, True),
        ({
             'username': 'short',
             'password1': 'pass',
             'password2': 'pass',
             'email': 'invalid'
         }, 200, False),
        ({
             'username': 'testuser',
             'password1': 'pass1',
             'password2': 'pass2',  # Пароли не совпадают
             'email': 'test@example.com'
         }, 200, False),
        ({}, 200, False),  # Пустые данные
    ])
    def test_register_various_data(self, client, user_data, expected_status, should_create):
        """Параметризированный тест различных сценариев регистрации"""
        initial_count = User.objects.count()
        response = client.post(reverse('register'), user_data)

        assert response.status_code == expected_status
        assert User.objects.count() == initial_count + (1 if should_create else 0)

        if expected_status == 200 and not should_create:
            assert 'Неверные учетные данные' in str(response.content.decode('utf-8'))

    def test_register_success(self, client):
        """Тест успешной регистрации"""
        response = client.post(reverse('register'), {
            'username': 'new_user',
            'password1': 'ComplexPassword123!',
            'password2': 'ComplexPassword123!',
            'email': 'new@example.com'
        })

        assert response.status_code == 302
        assert User.objects.filter(username='new_user').exists()
        assert response.url == reverse('profile')

    def test_register_duplicate_username(self, client, test_user):
        """Тест регистрации с существующим username"""
        response = client.post(reverse('register'), {
            'username': 'testuser',  # Уже существует
            'password1': 'newpass123',
            'password2': 'newpass123',
            'email': 'new@example.com'
        })

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Такое имя пользователя уже занято' in content or 'Неверные учетные данные' in content


# Тесты для логина
@pytest.mark.django_db
class TestUserLogin:
    """Тесты для функции user_login"""

    def test_login_get(self, client):
        """Тест GET запроса к логину"""
        response = client.get(reverse('login'))
        assert response.status_code == 200
        assert 'login.html' in [t.name for t in response.templates]

    @pytest.mark.parametrize('credentials, expected_status', [
        ({'username': 'testuser', 'password': 'testpass123'}, 302),  # Успех
        ({'username': 'wrong', 'password': 'wrong'}, 200),  # Неверные данные
        ({}, 200),  # Пустые данные
        ({'username': 'testuser'}, 200),  # Только username
        ({'password': 'testpass123'}, 200),  # Только password
    ])
    def test_login_various_credentials(self, client, test_user, credentials, expected_status):
        """Параметризированный тест различных сценариев логина"""
        response = client.post(reverse('login'), credentials)
        assert response.status_code == expected_status

        if expected_status == 302:  # Успешный логин
            assert response.url == reverse('profile')
        else:  # Ошибка
            content = response.content.decode('utf-8')
            assert 'Неверные учетные данные' in content or 'Указаны не все учетные данные' in content

    def test_login_success_session(self, client, test_user):
        """Тест что после успешного логина создается сессия"""
        response = client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })

        assert response.status_code == 302
        assert client.session['_auth_user_id'] == str(test_user.id)


# Тесты для logout
@pytest.mark.django_db
class TestCustomLogout:
    """Тесты для функции custom_logout"""

    def test_logout_authenticated(self, client, test_user):
        """Тест выхода для аутентифицированного пользователя"""
        client.login(username='testuser', password='testpass123')

        # Проверяем что сессия существует до выхода
        assert '_auth_user_id' in client.session

        response = client.get(reverse('logout'))

        assert response.status_code == 302
        assert response.url == reverse('index')
        assert '_auth_user_id' not in client.session  # Сессия очищена

    def test_logout_unauthenticated(self, client):
        """Тест выхода для неаутентифицированного пользователя"""
        response = client.get(reverse('logout'))

        assert response.status_code == 302
        assert response.url == reverse('login') + '?next=' + reverse('logout')


# Тесты для profile
@pytest.mark.django_db
class TestProfile:
    """Тесты для функции profile"""

    def test_profile_authenticated(self, client, test_user):
        """Тест профиля для аутентифицированного пользователя"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('profile'))

        assert response.status_code == 200
        assert 'profile.html' in [t.name for t in response.templates]
        assert response.context['user_to_show'] == test_user

    def test_profile_unauthenticated(self, client):
        """Тест редиректа для неаутентифицированного пользователя"""
        response = client.get(reverse('profile'))

        assert response.status_code == 302
        assert '/login' in response.url  # Редирект на логин

    def test_profile_different_user(self, client, test_user, test_user_2):
        """Тест просмотра чужого профиля через users view"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('users', kwargs={'pk': test_user_2.id}))

        assert response.status_code == 200
        assert response.context['user_to_show'] == test_user_2
        assert 'profile.html' in [t.name for t in response.templates]


# Тесты для settings
@pytest.mark.django_db
class TestSettings:
    """Тесты для функции settings"""

    def test_settings_get(self, client, test_user):
        """Тест GET запроса настроек"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('settings'))

        assert response.status_code == 200
        assert 'settings.html' in [t.name for t in response.templates]

    def test_settings_unauthenticated(self, client):
        """Тест настроек для неаутентифицированного пользователя"""
        response = client.get(reverse('settings'))

        assert response.status_code == 302
        assert '/login' in response.url

    @pytest.mark.parametrize('post_data, expected_changes', [
        ({
             'first_name': 'НовоеИмя',
             'last_name': 'НоваяФамилия',
             'username': 'newusername',
             'email': 'new@example.com',
             'password': ''
         }, {
             'first_name': 'НовоеИмя',
             'last_name': 'НоваяФамилия',
             'username': 'newusername',
             'email': 'new@example.com'
         }),
        ({
             'first_name': 'ТолькоИмя',
             'last_name': '',
             'username': 'testuser',
             'email': 'test@example.com',
             'password': ''
         }, {
             'first_name': 'ТолькоИмя',
             'last_name': 'User',
             'username': 'testuser',
             'email': 'test@example.com',
         }),
    ])
    def test_settings_update_without_password(self, client, test_user, post_data, expected_changes):
        """Тест обновления настроек без смены пароля"""
        client.login(username='testuser', password='testpass123')

        response = client.post(reverse('settings'), post_data)

        assert response.status_code == 302
        assert response.url == reverse('profile')

        # Проверяем сообщение об успехе
        messages_list = list(messages.get_messages(response.wsgi_request))
        assert any('успешно обновлен' in str(message) for message in messages_list)

        # Проверяем изменения в БД
        test_user.refresh_from_db()
        for field, expected_value in expected_changes.items():
            assert getattr(test_user, field) == expected_value

    def test_settings_update_with_password(self, client, test_user):
        """Тест обновления настроек со сменой пароля"""
        client.login(username='testuser', password='testpass123')
        old_password_hash = test_user.password

        response = client.post(reverse('settings'), {
            'first_name': 'Test',
            'last_name': 'User',
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'newcomplexpass123!'
        })

        assert response.status_code == 302
        test_user.refresh_from_db()

        # Пароль должен измениться
        assert test_user.password != old_password_hash
        # Должен остаться залогиненным (проверяем через сессию)
        assert client.session['_auth_user_id'] == str(test_user.id)

    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_settings_update_with_avatar(self, client, test_user, avatar_file):
        """Тест обновления настроек с загрузкой аватара"""
        client.login(username='testuser', password='testpass123')

        response = client.post(reverse('settings'), {
            'first_name': 'Test',
            'last_name': 'User',
            'username': 'testuser',
            'email': 'test@example.com',
            'password': '',
            'avatar': avatar_file
        })

        assert response.status_code == 302
        test_user.refresh_from_db()

        # Аватар должен быть установлен
        assert test_user.avatar.name is not None
        assert 'avatar' in test_user.avatar.name

    def test_settings_invalid_data(self, client, test_user):
        """Тест невалидных данных в настройках"""
        client.login(username='testuser', password='testpass123')

        # Пытаемся установить существующий email другого пользователя
        User.objects.create_user(username='other', email='other@example.com', password='test')

        response = client.post(reverse('settings'), {
            'first_name': 'Test',
            'last_name': 'User',
            'username': 'testuser',
            'email': 'other@example.com',  # Email уже занят
            'password': ''
        })

        content = response.content.decode('utf-8')
        print(content)
        assert response.status_code == 200
        assert 'Такой email уже занят' in content

    def test_settings_invalid_email(self, client, test_user):
        """Тест невалидного email в настройках"""
        client.login(username='testuser', password='testpass123')

        response = client.post(reverse('settings'), {
            'first_name': 'Test',
            'last_name': 'User',
            'username': 'testuser',
            'email': 'invalid-email',  # Невалидный email
            'password': ''
        })

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Некорректный email' in content

    def test_settings_duplicate_email(self, client, test_user):
        """Тест занятого email в настройках"""
        # Создаем второго пользователя с email
        User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )

        client.login(username='testuser', password='testpass123')

        response = client.post(reverse('settings'), {
            'first_name': 'Test',
            'last_name': 'User',
            'username': 'testuser',
            'email': 'other@example.com',  # Email уже занят другим пользователем
            'password': ''
        })

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Такой email уже занят' in content

    def test_settings_duplicate_username(self, client, test_user):
        """Тест занятого username в настройках"""
        # Создаем второго пользователя
        User.objects.create_user(
            username='otheruser',
            email='other@example.com',
            password='testpass123'
        )

        client.login(username='testuser', password='testpass123')

        response = client.post(reverse('settings'), {
            'first_name': 'Test',
            'last_name': 'User',
            'username': 'otheruser',  # Username уже занят
            'email': 'test@example.com',
            'password': ''
        })

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Такое имя пользователя уже занято' in content


# Тесты для index и users
@pytest.mark.django_db
class TestOtherViews:
    """Тесты для index и users views"""

    def test_index(self, client):
        """Тест главной страницы"""
        response = client.get(reverse('index'))
        assert response.status_code == 200
        assert 'index.html' in [t.name for t in response.templates]

    def test_users_view_existing(self, client, test_user):
        """Тест просмотра существующего пользователя"""
        response = client.get(reverse('users', kwargs={'pk': test_user.id}))
        assert response.status_code == 200
        assert response.context['user_to_show'] == test_user

    def test_users_view_nonexistent(self, client):
        """Тест просмотра несуществующего пользователя (должен вернуть 404)"""
        response = client.get(reverse('users', kwargs={'pk': 9999}))
        assert response.status_code == 404


# Дополнительные интеграционные тесты
@pytest.mark.django_db
class TestAuthIntegration:
    """Интеграционные тесты аутентификации"""

    def test_full_auth_flow(self, client):
        """Полный тест потока с учетом твоего поведения"""
        # 1. Регистрация (возвращает 302)
        initial_count = User.objects.count()
        register_response = client.post(reverse('register'), {
            'username': 'integrationuser',
            'password1': 'TestPass123!',
            'password2': 'TestPass123!',
            'email': 'integration@example.com'
        })

        # Проверяем что пользователь создался, независимо от статуса
        assert User.objects.count() == initial_count + 1
        assert User.objects.filter(username='integrationuser').exists()

        assert register_response.status_code == 302

        # 2. Логин
        login_response = client.post(reverse('login'), {
            'username': 'integrationuser',
            'password': 'TestPass123!'
        })
        content = login_response.content.decode('utf-8')
        assert login_response.status_code == 302  # Редирект на профиль

        # 3. Профиль (требует логина)
        profile_response = client.get(reverse('profile'))
        assert profile_response.status_code == 200

        # 4. Настройки
        settings_response = client.get(reverse('settings'))
        assert settings_response.status_code == 200

        # 5. Выход
        logout_response = client.get(reverse('logout'))
        assert logout_response.status_code == 302

        # 6. Проверяем что действительно вышли
        profile_after_logout = client.get(reverse('profile'))
        assert profile_after_logout.status_code == 302  # Редирект на логин

    def test_concurrent_sessions(self, client, test_user):
        """Тест работы с несколькими сессиями"""
        # Первая сессия
        client1 = Client()
        client1.login(username='testuser', password='testpass123')

        # Вторая сессия
        client2 = Client()
        client2.login(username='testuser', password='testpass123')

        # Обе сессии должны работать
        assert client1.get(reverse('profile')).status_code == 200
        assert client2.get(reverse('profile')).status_code == 200

        # Выход из первой сессии не должен влиять на вторую
        client1.get(reverse('logout'))
        assert client1.get(reverse('profile')).status_code == 302  # Редирект
        assert client2.get(reverse('profile')).status_code == 200  # Все еще работает


# Тесты безопасности
@pytest.mark.django_db
class TestSecurity:
    """Тесты безопасности (CSRF/XSS/SQL-injection)"""

    def test_csrf_protection(self, client, test_user):
        """Тест что формы защищены CSRF"""
        response = client.get(reverse('register'))
        assert 'csrfmiddlewaretoken' in response.content.decode('utf-8')

        response = client.get(reverse('login'))
        assert 'csrfmiddlewaretoken' in response.content.decode('utf-8')

        client.login(username='testuser', password='testpass123')
        response = client.get(reverse('settings'))
        content = response.content.decode('utf-8')
        assert 'csrfmiddlewaretoken' in content
        assert response.status_code == 200

    def test_xss_protection(self, client, test_user):
        """Тест что HTML/JS не исполняется в полях"""
        client.login(username='testuser', password='testpass123')

        response = client.post(reverse('settings'), {
            'first_name': '<script>alert("xss")</script>',
            'last_name': 'User',
            'username': 'testuser',
            'email': 'test@example.com',
            'password': ''
        })

        assert response.status_code == 302
        test_user.refresh_from_db()
        # Проверяем что скрипт не исполнился, а сохранился как текст
        assert test_user.first_name == '<script>alert("xss")</script>'

    def test_sql_injection_protection(self, client):
        """Тест что SQL инъекции не проходят"""
        # Пытаемся зарегистрироваться с SQL инъекцией в username
        response = client.post(reverse('register'), {
            'username': "admin'; DROP TABLE users; --",
            'password1': 'password123',
            'password2': 'password123',
            'email': 'test@example.com'
        })

        # Должна быть ошибка валидации, а не выполнение SQL
        assert response.status_code == 200
        assert 'Неверные учетные данные' in response.content.decode('utf-8')

    def test_csrf_register_login(self, client):
        """Тест CSRF для register и login"""
        response = client.get(reverse('register'))
        assert 'csrfmiddlewaretoken' in response.content.decode('utf-8')

        response = client.get(reverse('login'))
        assert 'csrfmiddlewaretoken' in response.content.decode('utf-8')

    def test_csrf_settings_authenticated(self, client, test_user):
        """Тест CSRF для settings (требует авторизации)"""
        client.login(username='testuser', password='testpass123')
        response = client.get(reverse('settings'))
        assert 'csrfmiddlewaretoken' in response.content.decode('utf-8')
