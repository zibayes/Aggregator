import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from unittest.mock import patch, MagicMock
import pandas as pd
from agregator.models import Act, ScientificReport, TechReport, OpenLists, ObjectAccountCard

User = get_user_model()


@pytest.mark.django_db
class TestReportDownloadViews:

    @patch('agregator.views.create_model_dataframe')
    @patch('agregator.views.generate_excel_report')
    def test_acts_register_download(self, mock_generate, mock_create, client, test_user):
        """Тест скачивания реестра актов"""
        client.force_login(test_user)

        # Создаем тестовые акты
        Act.objects.create(
            user=test_user,
            year='2023',
            name_number='Акт 1',
            is_processing=False
        )
        Act.objects.create(
            user=test_user,
            year='2024',
            name_number='Акт 2',
            is_processing=False
        )

        # Мокируем создание DataFrame
        mock_df = MagicMock()
        mock_create.return_value = mock_df
        mock_generate.return_value = '/test/path.xlsx'

        response = client.get(reverse('acts_register_download'))

        assert response.status_code == 302
        mock_create.assert_called_once()
        mock_generate.assert_called_once()

    @patch('agregator.views.create_model_dataframe')
    @patch('agregator.views.generate_excel_report')
    def test_scientific_reports_register_download(self, mock_generate, mock_create, client, test_user):
        """Тест скачивания реестра научных отчетов"""
        client.force_login(test_user)

        ScientificReport.objects.create(
            user=test_user,
            name='Научный отчет 1',
            is_processing=False
        )

        mock_df = MagicMock()
        mock_create.return_value = mock_df
        mock_generate.return_value = '/test/path.xlsx'

        response = client.get(reverse('scientific_reports_register_download'))

        assert response.status_code == 302
        mock_create.assert_called_once()

    @patch('agregator.views.create_model_dataframe')
    @patch('agregator.views.generate_excel_report')
    def test_tech_reports_register_download(self, mock_generate, mock_create, client, test_user):
        """Тест скачивания реестра техотчетов"""
        client.force_login(test_user)

        TechReport.objects.create(
            user=test_user,
            name='Техотчет 1',
            is_processing=False
        )

        mock_df = MagicMock()
        mock_create.return_value = mock_df
        mock_generate.return_value = '/test/path.xlsx'

        response = client.get(reverse('tech_reports_register_download'))

        assert response.status_code == 302
        mock_create.assert_called_once()

    @patch('agregator.views.create_model_dataframe')
    @patch('agregator.views.generate_excel_report')
    def test_open_lists_register_download(self, mock_generate, mock_create, client, test_user):
        """Тест скачивания реестра открытых листов"""
        client.force_login(test_user)

        OpenLists.objects.create(
            user=test_user,
            number='123',
            holder='Держатель',
            is_processing=False
        )

        mock_df = MagicMock()
        mock_create.return_value = mock_df
        mock_generate.return_value = '/test/path.xlsx'

        response = client.get(reverse('open_lists_register_download'))

        assert response.status_code == 302
        mock_create.assert_called_once()

    @patch('agregator.views.create_model_dataframe')
    @patch('agregator.views.generate_excel_report')
    def test_account_cards_register_download(self, mock_generate, mock_create, client, test_user):
        """Тест скачивания реестра учетных карт"""
        client.force_login(test_user)

        ObjectAccountCard.objects.create(
            user=test_user,
            name='Объект 1',
            is_processing=False
        )

        mock_df = MagicMock()
        mock_create.return_value = mock_df
        mock_generate.return_value = '/test/path.xlsx'

        response = client.get(reverse('account_cards_register_download'))

        assert response.status_code == 302
        mock_create.assert_called_once()


@pytest.mark.django_db
class TestCommercialOfferReport:

    @patch('agregator.views.convert_to_wgs84')
    @patch('agregator.views.GeoObject.objects.filter')
    def test_download_commercial_offer_report(self, mock_convert, mock_geo_filter, client, test_user):
        """Тест генерации отчета по коммерческому предложению"""
        client.force_login(test_user)

        # Создаем коммерческое предложение
        from agregator.models import CommercialOffers
        commercial_offer = CommercialOffers.objects.create(
            user=test_user,
            origin_filename='test_offer.pdf',
            coordinates={
                'Участок': {
                    'Точка 1': [55.7558, 37.6176]
                }
            }
        )

        # Создаем тестовые учетные карты
        ObjectAccountCard.objects.create(
            user=test_user,
            name='Памятник 1',
            coordinates={
                'Объект': {
                    'Точка 1': [55.7568, 37.6186]
                }
            }
        )

        # Мокируем геообъекты и преобразование координат
        mock_geo_filter.return_value = []
        mock_convert.return_value = [55.7558, 37.6176]

        response = client.get(reverse('download_commercial_offer_report', kwargs={'pk': commercial_offer.id}))

        assert response.status_code == 302


@pytest.mark.django_db
class TestCoordinateDownloadViews:

    def test_download_coordinates_post(self, client, test_user):
        """Тест POST запроса для скачивания координат"""
        client.force_login(test_user)

        # Создаем акт с координатами
        act = Act.objects.create(
            user=test_user,
            year='2023',
            name_number='Тестовый акт',
            is_processing=False,
            coordinates={
                'Шурфы': {
                    '1': [55.7558, 37.6176],
                    '2': [55.7568, 37.6186]
                }
            }
        )

        response = client.post(reverse('download_coordinates', kwargs={
            'report_type': 'act',
            'pk': act.id
        }), {
                                   'Шурфы-1': 'on',
                                   'Шурфы-2': 'on'
                               })

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.google-earth.kml+xml'
        response_content = response.content.decode('utf-8')
        assert '<Point' in response_content
        assert '<coordinates>' in response_content

    def test_download_coordinates_no_selection(self, client, test_user):
        """Тест скачивания координатов без выбора точек"""
        client.force_login(test_user)

        act = Act.objects.create(
            user=test_user,
            year='2023',
            name_number='Тестовый акт',
            is_processing=False,
            coordinates={
                'Группа 1': {
                    'Точка 1': [55.7558, 37.6176]
                }
            }
        )

        response = client.post(reverse('download_coordinates', kwargs={
            'report_type': 'act',
            'pk': act.id
        }))

        # Должен вернуть ошибку 404
        assert response.status_code == 404

    def test_download_all_coordinates_post(self, client, test_user):
        """Тест скачивания всех координат"""
        client.force_login(test_user)

        # Создаем тестовые данные
        Act.objects.create(
            user=test_user,
            year='2023',
            name_number='Акт 1',
            is_processing=False,
            source=[{'origin_filename': 'act1.pdf'}],
            coordinates={
                'Группа 1': {
                    'Точка 1': [55.7558, 37.6176]
                }
            }
        )

        response = client.post(reverse('download_all_coordinates'), {
            'Акты-act1.pdf-Группа 1-Точка 1': 'on'
        })

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.google-earth.kml+xml'

    def test_download_all_coordinates_no_selection(self, client, test_user):
        """Тест скачивания всех координат без выбора"""
        client.force_login(test_user)

        response = client.post(reverse('download_all_coordinates'))

        assert response.status_code == 404
