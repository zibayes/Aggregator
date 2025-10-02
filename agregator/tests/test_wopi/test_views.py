import pytest
import json
import os
from unittest.mock import patch, mock_open
from django.urls import reverse
from django.test import RequestFactory
from django.http import HttpResponse
from agregator.wopi.views import (
    wopi_endpoint,
    wopi_contents,
    kodexplorer_proxy,
    generate_wopi_token,
    verify_wopi_token,
    get_safe_path,
    handle_check_file_info,
    handle_get_file
)


@pytest.mark.django_db
class TestWopiTokenFunctions:
    """Тесты для функций работы с токенами"""

    @pytest.mark.parametrize('user_id,username,file_path,can_write', [
        (1, 'testuser', 'normal_file.txt', True),
        (2, 'otheruser', 'path/with/subdir/file.docx', False),
        (999, 'user_with_special_chars', 'file with spaces.txt', True),
    ])
    def test_generate_and_verify_token_success(self, user_id, username, file_path, can_write):
        # Генерация токена
        token = generate_wopi_token(user_id, username, file_path, can_write)

        # Проверка валидности
        token_data = verify_wopi_token(token, file_path)

        assert token_data is not None
        assert token_data['user_id'] == user_id
        assert token_data['username'] == username
        assert token_data['file_path'] == file_path
        assert token_data['can_write'] == can_write

    @pytest.mark.parametrize('token_path,request_path,should_match', [
        ('same_file.txt', 'same_file.txt', True),
        ('file.txt', 'different_file.txt', False),
        ('dir/file.txt', 'dir/file.txt', True),
        ('dir/file.txt', 'other_dir/file.txt', False),
        ('file with spaces.txt', 'file with spaces.txt', True),
        ('file%20with%20spaces.txt', 'file with spaces.txt', True),  # URL decoding
    ])
    def test_verify_token_path_validation(self, test_user, token_path, request_path, should_match):
        token = generate_wopi_token(test_user.id, test_user.username, token_path, True)
        token_data = verify_wopi_token(token, request_path)

        if should_match:
            assert token_data is not None
        else:
            assert token_data is None

    def test_verify_expired_token(self, wopi_token_expired):
        result = verify_wopi_token(wopi_token_expired, 'test_file.txt')
        assert result is None

    def test_verify_invalid_token(self, wopi_invalid_token):
        result = verify_wopi_token(wopi_invalid_token, 'test_file.txt')
        assert result is None


@pytest.mark.django_db
class TestGetSafePath:
    """Тесты для функции безопасного пути"""

    @pytest.mark.parametrize('file_id,expected_filename', [
        ('normal_file.txt', 'normal_file.txt'),
        ('file with spaces.txt', 'file with spaces.txt'),
        ('file%2Bwith%2Bplus.txt', 'file+with+plus.txt'),
        ('file%20with%20plus.txt', 'file with plus.txt'),
        ('path%2Fto%2Ffile.txt', 'path/to/file.txt'),
        ('mixed file + name.txt', 'mixed file + name.txt'),
    ])
    def test_get_safe_path_success(self, settings, file_id, expected_filename):
        # Создаем тестовую структуру файлов
        test_dir = os.path.join(settings.WOPI_FILE_ROOT, 'test_dir')
        os.makedirs(test_dir, exist_ok=True)

        # Создаем полный путь к целевому файлу
        target_file_path = os.path.join(test_dir, expected_filename)

        # Создаем родительские директории если нужно
        os.makedirs(os.path.dirname(target_file_path), exist_ok=True)

        with open(target_file_path, 'w') as f:
            f.write('test content')

        try:
            full_file_id = f'test_dir/{file_id}'
            result = get_safe_path(full_file_id)
            assert result is not None
            # Сравниваем полные пути, а не только имена файлов
            assert result == target_file_path
        finally:
            if os.path.exists(target_file_path):
                os.remove(target_file_path)

    @pytest.mark.parametrize('malicious_path', [
        '../../../etc/passwd',
        '../sensitive_file.txt',
        '..\\windows\\system32',
        'normal/../../etc/passwd',
        '%2e%2e%2fetc%2fpasswd',  # URL encoded path traversal
    ])
    def test_get_safe_path_traversal_prevention(self, malicious_path):
        result = get_safe_path(malicious_path)
        assert result is None

    def test_get_safe_path_nonexistent_file(self):
        result = get_safe_path('non_existent_file_12345.txt')
        assert result is None


@pytest.mark.django_db
class TestWopiEndpoint:
    """Тесты основного WOPI endpoint"""

    def test_wopi_endpoint_checkfileinfo_success(self, client, test_user, wopi_test_file):
        # Генерируем токен с правильным file_id
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        token = generate_wopi_token(
            test_user.id, test_user.username, file_id, True
        )

        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            response = client.get(
                f'/wopi/files/{file_id}',
                {'access_token': token}
            )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['BaseFileName'] == file_id

    @pytest.mark.parametrize('token_fixture,expected_status', [
        ('wopi_invalid_token', 401),
        ('wopi_token_expired', 401),
        (None, 401),  # No token
    ])
    def test_wopi_endpoint_authentication_failures(self, client, wopi_test_file, request,
                                                   token_fixture, expected_status):
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        token = request.getfixturevalue(token_fixture) if token_fixture else None

        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            url = f'/wopi/files/{file_id}'
            if token:
                response = client.get(url, {'access_token': token})
            else:
                response = client.get(url)

        assert response.status_code == expected_status

    def test_wopi_endpoint_getfile_success(self, client, wopi_test_file, wopi_token):
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            response = client.get(
                f'/wopi/files/{file_id}/contents',
                {'access_token': wopi_token}
            )

        assert response.status_code == 200
        assert response['Content-Disposition'] == f'inline; filename="{file_id}"'
        content = b''.join(response.streaming_content)
        assert b'Test file content for WOPI' in content

    def test_wopi_endpoint_nonexistent_file(self, client, wopi_token):
        response = client.get(
            '/wopi/files/nonexistent_file_12345.txt',
            {'access_token': wopi_token}
        )
        assert response.status_code in [400, 404]


@pytest.mark.django_db
class TestWopiContents:
    """Тесты для endpoint содержимого файлов"""

    def test_wopi_put_file_success(self, client, test_user, wopi_test_file):
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        # Генерируем токен с правильным file_id и правами на запись
        token = generate_wopi_token(
            test_user.id, test_user.username, file_id, True
        )

        new_content = b'Updated file content via WOPI'

        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            response = client.post(
                f'/wopi/files/{file_id}/contents',
                data=new_content,
                content_type='application/octet-stream',
                QUERY_STRING=f'access_token={token}'
            )

        assert response.status_code == 200

        # Проверяем, что файл действительно обновлен
        with open(wopi_test_file, 'rb') as f:
            assert f.read() == new_content

    def test_wopi_put_file_readonly_token(self, client, wopi_test_file, wopi_token_readonly):
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            response = client.post(
                f'/wopi/files/{file_id}/contents',
                data=b'Attempted content',
                content_type='application/octet-stream',
                QUERY_STRING=f'access_token={wopi_token_readonly}'
            )

        assert response.status_code == 403

    def test_wopi_put_file_io_error(self, client, test_user, wopi_test_file):
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        token = generate_wopi_token(
            test_user.id, test_user.username, file_id, True
        )

        # Мокаем открытие файла чтобы вызвать IOError
        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            with patch('builtins.open', side_effect=IOError("Disk error")):
                response = client.post(
                    f'/wopi/files/{file_id}/contents',
                    data=b'content',
                    content_type='application/octet-stream',
                    QUERY_STRING=f'access_token={token}'
                )

        assert response.status_code == 500


@pytest.mark.django_db
class TestKodexplorerProxy:
    """Тесты для прокси Kodexplorer"""

    def test_kodexplorer_proxy_success(self, client, test_user, wopi_test_file):
        file_id = os.path.basename(wopi_test_file)

        with patch('agregator.wopi.views.get_safe_path') as mock_safe_path:
            mock_safe_path.return_value = wopi_test_file

            response = client.get(
                reverse('kodexplorer_proxy'),
                {'path': f'/var/www/html/data/uploaded_files/{file_id}'}
            )

        assert response.status_code == 302  # Redirect
        assert 'cool.html?WOPISrc=' in response.url
        assert 'access_token=' in response.url
        assert 'lang=ru' in response.url

    def test_kodexplorer_proxy_missing_path(self, client):
        response = client.get(reverse('kodexplorer_proxy'))
        assert response.status_code == 400

    def test_kodexplorer_proxy_file_not_found(self, client):
        with patch('agregator.wopi.views.get_safe_path') as mock_safe_path:
            mock_safe_path.return_value = None

            response = client.get(
                reverse('kodexplorer_proxy'),
                {'path': '/var/www/html/data/uploaded_files/nonexistent.txt'}
            )

        assert response.status_code == 404

    def test_kodexplorer_proxy_exception_handling(self, client, wopi_test_file):
        """Тест обработки исключений в kodexplorer_proxy"""
        file_id = os.path.basename(wopi_test_file)

        with patch('agregator.wopi.views.get_safe_path') as mock_safe_path:
            # Файл существует, чтобы дойти до генерации токена
            mock_safe_path.return_value = wopi_test_file

            # Исключение произойдет при вызове generate_wopi_token
            with patch('agregator.wopi.views.generate_wopi_token', side_effect=Exception("Test error")):
                response = client.get(
                    reverse('kodexplorer_proxy'),
                    {'path': f'/var/www/html/data/uploaded_files/{file_id}'}
                )

        assert response.status_code == 500
        assert "Server Error" in str(response.content)


@pytest.mark.django_db
class TestWopiSecurity:
    """Тесты безопасности WOPI implementation"""

    @pytest.mark.parametrize('malicious_input', [
        '../../../etc/passwd',
        '../config/settings.py',
        '..\\..\\windows\\system32\\drivers\\etc\\hosts',
        '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd',
    ])
    def test_path_traversal_prevention(self, client, malicious_input, wopi_token):
        response = client.get(
            f'/wopi/files/{malicious_input}',
            {'access_token': wopi_token}
        )
        # Должен возвращать 400 или 404, но не 200 и не раскрывать информацию
        assert response.status_code in [400, 404, 401]
        assert response.status_code != 200

    def test_token_isolation_between_users(self, test_user, test_user_2):
        # Токен для user1 не должен работать для файлов user2
        token_user1 = generate_wopi_token(
            test_user.id, test_user.username, 'user1_file.txt', True
        )

        # Попытка доступа к файлу user2 с токеном user1
        result = verify_wopi_token(token_user1, 'user2_file.txt')
        assert result is None

    def test_authorization_header_support(self, client, wopi_test_file, wopi_token):
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            response = client.get(
                f'/wopi/files/{file_id}',
                HTTP_AUTHORIZATION=f'Bearer {wopi_token}'
            )

        assert response.status_code == 200


@pytest.mark.django_db
class TestWopiIntegration:
    """Интеграционные тесты полного цикла WOPI"""

    def test_complete_wopi_flow(self, client, test_user, wopi_test_file):
        # 1. Генерация токена
        file_id = os.path.basename(wopi_test_file)
        token = generate_wopi_token(
            test_user.id, test_user.username, file_id, True
        )

        test_dir = os.path.dirname(wopi_test_file)

        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            # 2. CheckFileInfo
            check_info_response = client.get(
                f'/wopi/files/{file_id}',
                {'access_token': token}
            )
            assert check_info_response.status_code == 200

            # 3. GetFile
            get_file_response = client.get(
                f'/wopi/files/{file_id}/contents',
                {'access_token': token}
            )
            assert get_file_response.status_code == 200

            # 4. PutFile (обновление содержимого)
            new_content = b'Integration test updated content'
            put_file_response = client.post(
                f'/wopi/files/{file_id}/contents',
                data=new_content,
                content_type='application/octet-stream',
                QUERY_STRING=f'access_token={token}'
            )
            assert put_file_response.status_code == 200

            # 5. Проверяем, что содержимое обновилось
            with open(wopi_test_file, 'rb') as f:
                assert f.read() == new_content

    def test_concurrent_access_simulation(self, client, wopi_test_file, wopi_token):
        """Тест имитации конкурентного доступа"""
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            # Множественные одновременные запросы CheckFileInfo
            responses = []
            for i in range(5):
                response = client.get(
                    f'/wopi/files/{file_id}',
                    {'access_token': wopi_token}
                )
                responses.append(response)

            # Все запросы должны быть успешными
            assert all(r.status_code == 200 for r in responses)


# Дополнительные утилиты для тестирования
def test_handle_check_file_info_integration(wopi_test_file, test_user):
    """Интеграционный тест для handle_check_file_info"""
    from agregator.wopi.views import handle_check_file_info
    from django.test import RequestFactory

    factory = RequestFactory()
    request = factory.get('/')

    file_id = os.path.basename(wopi_test_file)
    token_data = {
        'user_id': test_user.id,
        'username': test_user.username,
        'can_write': True
    }

    response = handle_check_file_info(request, wopi_test_file, file_id, token_data)

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data['BaseFileName'] == file_id
    assert data['UserCanWrite'] == True


def test_error_handling_and_logging(client, wopi_token, caplog):
    """Тест обработки ошибок и логирования"""
    with patch('agregator.wopi.views.get_safe_path', side_effect=Exception("Test error")):
        with caplog.at_level('ERROR', logger='django.request'):
            try:
                response = client.get(
                    '/wopi/files/test.txt',
                    {'access_token': wopi_token}
                )
                # Если мы дошли сюда, значит Django не поднял исключение
                assert response.status_code == 500
            except Exception as e:
                # Для старых версий Django - исключение поднимается напрямую
                assert str(e) == "Test error"
                # Проверяем, что ошибка залогирована
                assert any(
                    "Test error" in record.message or
                    "Test error" in (record.exc_text or '')
                    for record in caplog.records
                )


@pytest.mark.django_db
class TestAdditionalCoverage:
    """Тесты для покрытия оставшихся строк кода"""

    def test_token_expiration(self, client, wopi_token_expired, wopi_test_file):
        """Покрывает строки 100-101 (проверка истечения срока действия токена)"""
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            response = client.get(
                f'/wopi/files/{file_id}',
                {'access_token': wopi_token_expired}
            )

        assert response.status_code == 401
        assert "Invalid token" in str(response.content)

    def test_wopi_endpoint_invalid_method(self, client, wopi_token, wopi_test_file):
        """Покрывает строку 107 (ошибка при неподдерживаемом методе)"""
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            response = client.post(
                f'/wopi/files/{file_id}',
                {'access_token': wopi_token}
            )

        assert response.status_code == 400
        assert "POST not supported here" in str(response.content)

    def test_handle_get_file_no_read_permission(self, wopi_test_file):
        """Покрывает строки 116-117 (проверка прав на чтение)"""
        file_id = os.path.basename(wopi_test_file)
        file_path = wopi_test_file

        # Создаем фейковый request
        factory = RequestFactory()
        request = factory.get(f'/wopi/files/{file_id}')

        # Данные токена с can_read = False
        token_data = {
            'can_read': False,
            'user_id': 1,
            'username': 'testuser',
            'file_path': file_id,
            'can_write': True
        }

        # Вызываем handle_get_file напрямую
        response = handle_get_file(request, file_path, token_data)

        assert response.status_code == 403
        assert "Access denied" in str(response.content)

    def test_wopi_put_file_logging(self, client, test_user, wopi_test_file, caplog):
        """Покрывает строку 141 (логирование ошибки при сохранении файла)"""
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        token = generate_wopi_token(
            test_user.id, test_user.username, file_id, True
        )

        # Мокаем открытие файла чтобы вызвать IOError
        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            with patch('builtins.open', side_effect=IOError("Disk error")):
                with caplog.at_level('ERROR'):
                    client.post(
                        f'/wopi/files/{file_id}/contents',
                        data=b'content',
                        content_type='application/octet-stream',
                        QUERY_STRING=f'access_token={token}'
                    )

        assert "Error saving file" in caplog.text

    def test_kodexplorer_proxy_file_not_found(self, client):
        """Покрывает строки 207-209 (проверка существования файла)"""
        with patch('agregator.wopi.views.get_safe_path', return_value=None):
            response = client.get(
                reverse('kodexplorer_proxy'),
                {'path': '/var/www/html/data/uploaded_files/nonexistent.txt'}
            )

        assert response.status_code == 404
        assert "File not found" in str(response.content)

    def test_kodexplorer_proxy_server_error(self, client, wopi_test_file):
        """Покрывает строку 231 (ошибка сервера в прокси)"""
        file_id = os.path.basename(wopi_test_file)

        with patch('agregator.wopi.views.get_safe_path') as mock_safe_path:
            mock_safe_path.return_value = wopi_test_file

            # Исключение произойдет при вызове generate_wopi_token
            with patch('agregator.wopi.views.generate_wopi_token', side_effect=Exception("Test error")):
                response = client.get(
                    reverse('kodexplorer_proxy'),
                    {'path': f'/var/www/html/data/uploaded_files/{file_id}'}
                )

        assert response.status_code == 500
        assert "Server Error" in str(response.content)

    def test_wopi_contents_no_token(self, client, wopi_test_file):
        """Покрывает строку 242 (отсутствие токена в wopi_contents)"""
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            response = client.post(
                f'/wopi/files/{file_id}/contents',
                data=b'content',
                content_type='application/octet-stream'
            )

        assert response.status_code == 401
        assert "Access token required" in str(response.content)

    def test_wopi_put_file_no_write_permission(self, client, wopi_test_file):
        """Покрывает строки 247-249 (проверка прав на запись)"""
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        # Мокаем token_data без права на запись
        with patch('agregator.wopi.views.verify_wopi_token', return_value={
            'can_write': False,
            'user_id': 1,
            'username': 'testuser'
        }):
            with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
                response = client.post(
                    f'/wopi/files/{file_id}/contents',
                    data=b'content',
                    content_type='application/octet-stream',
                    QUERY_STRING='access_token=valid_token'
                )

        assert response.status_code == 403
        assert "Access denied" in str(response.content)

    def test_wopi_endpoint_no_token(self, client, wopi_test_file):
        """Покрывает строки 288, 291 (отсутствие токена в wopi_endpoint)"""
        file_id = os.path.basename(wopi_test_file)
        test_dir = os.path.dirname(wopi_test_file)

        with patch('agregator.wopi.views.WOPI_FILE_ROOT', test_dir):
            response = client.get(
                f'/wopi/files/{file_id}'
            )

        assert response.status_code == 401
        assert "Access token required" in str(response.content)

    def test_kodexplorer_proxy_exception_logging(self, client, wopi_test_file, caplog):
        """Покрывает строки 325-326 (логирование исключений в прокси)"""
        file_id = os.path.basename(wopi_test_file)

        with patch('agregator.wopi.views.get_safe_path') as mock_safe_path:
            mock_safe_path.return_value = wopi_test_file

            # Исключение произойдет при вызове generate_wopi_token
            with patch('agregator.wopi.views.generate_wopi_token', side_effect=Exception("Test error")):
                with caplog.at_level('ERROR'):
                    client.get(
                        reverse('kodexplorer_proxy'),
                        {'path': f'/var/www/html/data/uploaded_files/{file_id}'}
                    )

        assert "PROXY ERROR" in caplog.text
