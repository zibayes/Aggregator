import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from unittest.mock import patch, MagicMock

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
