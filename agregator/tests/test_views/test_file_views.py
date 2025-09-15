import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from unittest.mock import patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


@pytest.mark.django_db
class TestFileViews:
    @patch('agregator.views.create_model_dataframe')
    @patch('agregator.views.generate_excel_report')
    def test_acts_register_download(self, mock_generate, mock_create):
        """Тест скачивания реестра актов"""
        client = Client()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.login(username='testuser', password='testpass123')

        # Мокируем зависимости
        mock_df = MagicMock()
        mock_create.return_value = mock_df
        mock_generate.return_value = '/test/path.xlsx'

        response = client.get(reverse('acts_register_download'))

        assert response.status_code == 302
        mock_create.assert_called_once()
        mock_generate.assert_called_once()

    def test_archaeological_heritage_sites_download(self, client, test_user):
        """Тест скачивания списка памятников"""
        client.force_login(test_user)

        # Создаем тестовый файл
        with open('uploaded_files/Памятники/current_lists.txt', 'w') as f:
            f.write('list_oan - /test/path/oan.txt\n')
            f.write('list_voan - /test/path/voan.txt\n')

        response = client.get(reverse('archaeological_heritage_sites_download'))
        assert response.status_code == 302

    def test_identified_archaeological_heritage_sites_download(self, client, test_user):
        """Тест скачивания списка выявленных памятников"""
        client.force_login(test_user)

        response = client.get(reverse('identified_archaeological_heritage_sites_download'))
        assert response.status_code == 302


@pytest.mark.django_db
class TestFileUploadViews:
    def test_account_cards_upload_get(self, client, test_user):
        """Тест GET запроса загрузки учётных карточек"""
        client.force_login(test_user)
        response = client.get(reverse('account_cards_upload'))
        assert response.status_code == 200
        assert 'account_cards_upload.html' in [t.name for t in response.templates]

    @patch('agregator.views.raw_account_cards_save')
    @patch('agregator.views.process_account_cards.apply_async')
    def test_account_cards_upload_post(self, mock_process, mock_save, client, test_user):
        """Тест POST загрузки учётных карточек"""
        mock_save.return_value = [1]
        mock_task = MagicMock(task_id='task-123')
        mock_process.return_value = mock_task

        test_file = SimpleUploadedFile("test.pdf", b"content")  # Вместо реального файла

        client.force_login(test_user)
        response = client.post(reverse('account_cards_upload'), {
            'files': [test_file],
            'file_type': 'account_card'
        })

        assert response.status_code == 200
        mock_save.assert_called_once()
        mock_process.assert_called_once()
