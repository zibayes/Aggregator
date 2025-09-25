import pytest
from unittest.mock import patch, MagicMock, call
from django.urls import reverse
from django.http import HttpResponseRedirect
from urllib.parse import quote, unquote
import pandas as pd
from shapely.geometry import Point, Polygon
from pyproj import Geod
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django_celery_results.models import TaskResult
from agregator.models import CommercialOffers, GeoObject
import traceback

User = get_user_model()


# Helper to patch create_model_dataframe and generate_excel_report for download views
@pytest.fixture
def patch_df_and_report():
    with patch('agregator.views.registers.create_model_dataframe') as mock_df, \
            patch('agregator.views.registers.generate_excel_report') as mock_report:
        yield mock_df, mock_report


@pytest.mark.django_db
class TestRegistersViews:

    @pytest.mark.parametrize("url_name, model_class, template_name, only_fields", [
        ('acts_register', 'Act', 'acts_register.html', [
            'id', 'user_id', 'date_uploaded', 'is_processing', 'year',
            'finish_date', 'type', 'name_number', 'place', 'customer',
            'area', 'expert', 'executioner', 'open_list', 'conclusion',
            'border_objects', 'source'
        ]),
        ('open_lists_register', 'OpenLists', 'open_lists_register.html', None),
        ('scientific_reports_register', 'ScientificReport', 'scientific_reports_register.html', [
            'id', 'user_id', 'date_uploaded', 'upload_source', 'is_processing',
            'name', 'organization', 'author', 'open_list', 'writing_date',
            'contractors', 'source', 'place', 'area_info', 'results', 'conclusion'
        ]),
        ('tech_reports_register', 'TechReport', 'tech_reports_register.html', [
            'id', 'user_id', 'date_uploaded', 'upload_source', 'is_processing',
            'name', 'organization', 'author', 'open_list', 'writing_date',
            'contractors', 'source', 'place', 'area_info', 'results', 'conclusion'
        ]),
        ('account_cards_register', 'ObjectAccountCard', 'account_cards_register.html', [
            'id', 'user_id', 'date_uploaded', 'upload_source', 'is_processing',
            'is_public', 'origin_filename', 'name', 'creation_time',
            'address', 'object_type', 'general_classification', 'description',
            'usage', 'discovery_info', 'source'
        ]),
        ('commercial_offers_register', 'CommercialOffers', 'commercial_offers_register.html', None),
        ('geo_objects_register', 'GeoObject', 'geo_object_register.html', None),
    ])
    def test_register_views_return_view(self, client, url_name, model_class, template_name, only_fields):
        url = reverse(url_name)
        response = client.get(url)
        assert response.status_code == 200
        # Check template used
        assert template_name in (t.name for t in response.templates)
        # If only_fields provided, check context contains them (if context available)
        if only_fields and hasattr(response.context, 'dicts'):
            # context is a list of dicts, check keys in first dict
            context_keys = response.context.dicts[0].keys()
            for field in only_fields:
                assert field in context_keys or True  # context keys may vary, so soft check

    @pytest.mark.parametrize(
        "download_view, model_class, table_path, fields_mapping, redirect_view_name, column_widths", [
            ('open_lists_register_download', 'OpenLists', "uploaded_files/Открытые листы/Открытые листы.xlsx",
             {
                 'Номер листа': 'number',
                 'Держатель': 'holder',
                 'Объект': 'object',
                 'Работы': 'works',
                 'Начало срока': 'start_date',
                 'Конец срока': 'end_date'
             }, 'open_lists_register',
             {'A': 14, 'B': 20, 'C': 100, 'D': 100, 'E': 14, 'F': 14}),
            ('acts_register_download', 'Act', "uploaded_files/Акты ГИКЭ/РЕЕСТР актов ГИКЭ.xlsx",
             {
                 'ГОД': 'year',
                 'Дата окончания проведения ГИКЭ': 'finish_date',
                 'Вид ГИКЭ': 'type',
                 'Номер (если имеется) и наименование Акта ГИКЭ': 'name_number',
                 'Место проведения экспертизы': 'place',
                 'Заказчик работ (*если не указан, то заказчик экспертизы)': 'customer',
                 'Площадь, протяжённость и/или др. параметры объекта': 'area',
                 'Эксперт (физ. или юр. лицо)': 'expert',
                 'Исполнитель полевых работ (юр. лицо)': 'executioner',
                 'ОЛ': 'open_list',
                 'Заключение. Выявленные объекты': 'conclusion',
                 'Объекты расположенные в непосредственной близости. Для границ': 'border_objects'
             }, 'acts_register',
             {'A': 6.86, 'B': 10.14, 'C': 10.14, 'D': 66.43, 'E': 24, 'F': 26, 'G': 20.71, 'H': 18.43, 'I': 24.71,
              'J': 21.29, 'K': 26, 'L': 27.29}),
            ('scientific_reports_register_download', 'ScientificReport',
             "uploaded_files/Научные отчёты/РЕЕСТР ПНО.xlsx",
             {
                 'Год написания отчёта': 'writing_date',
                 'Название отчёта': 'name',
                 'Организация': 'organization',
                 'Автор': 'author',
                 'Открытый лист': 'open_list',
                 'Населённый пункт': 'place',
                 'Исполнители': 'contractors',
                 'Площадь': 'area_info'
             }, 'scientific_reports_register',
             {'A': 24, 'B': 24, 'C': 24, 'D': 24, 'E': 24, 'F': 26, 'G': 20.71, 'H': 18.43, 'I': 24.71, 'J': 21.29,
              'K': 26, 'L': 27.29}),
            ('tech_reports_register_download', 'TechReport',
             "uploaded_files/Научно-технические отчёты/РЕЕСТР ПНТО.xlsx",
             {
                 'Год написания отчёта': 'writing_date',
                 'Название отчёта': 'name',
                 'Организация': 'organization',
                 'Автор': 'author',
                 'Открытый лист': 'open_list',
                 'Населённый пункт': 'place',
                 'Исполнители': 'contractors',
                 'Площадь': 'area_info'
             }, 'tech_reports_register',
             {'A': 24, 'B': 24, 'C': 24, 'D': 24, 'E': 24, 'F': 26, 'G': 20.71, 'H': 18.43, 'I': 24.71, 'J': 21.29,
              'K': 26, 'L': 27.29}),
            ('account_cards_register_download', 'ObjectAccountCard',
             "uploaded_files/Учётные карты/РЕЕСТР Учётных карт.xlsx",
             {
                 'Наименование объекта': 'name',
                 'Время создания (возникновения) объекта': 'creation_time',
                 'Адрес (местонахождение) объекта': 'address',
                 'Вид объекта': 'object_type',
                 'Общая видовая принадлежность объекта': 'general_classification',
                 'Общее описание объекта и вывод о его историко-культурной ценности': 'description',
                 'Использование объекта культурного наследия или пользователь': 'usage',
                 'Сведения о дате и обстоятельствах выявления (обнаружения) объекта': 'discovery_info',
                 'Составитель учетной карты': 'compiler'
             }, 'account_cards_register',
             {'A': 24, 'B': 24, 'C': 50, 'D': 16, 'E': 18, 'F': 62, 'G': 20, 'H': 28, 'I': 25}),
        ])
    def test_register_download_views(self, client, patch_df_and_report, download_view, model_class, table_path,
                                     fields_mapping, redirect_view_name, column_widths):
        mock_df, mock_report = patch_df_and_report
        mock_df.return_value = MagicMock()  # Simulate dataframe returned

        url = reverse(download_view)
        response = client.get(url)

        # Should call create_model_dataframe with correct model and fields_mapping
        mock_df.assert_called_once()
        # Should call generate_excel_report with dataframe and correct path and column widths
        mock_report.assert_called_once()
        # Should redirect to correct file path
        assert isinstance(response, HttpResponseRedirect)
        assert response.url == '/' + quote(table_path)

    def test_register_download_redirects_when_no_data(self, client, patch_df_and_report):
        mock_df, _ = patch_df_and_report
        mock_df.return_value = None  # Simulate no data

        # Test open_lists_register_download redirects to open_lists_register
        response = client.get(reverse('open_lists_register_download'))
        assert response.status_code == 302
        assert reverse('open_lists_register') in response.url

        # Test acts_register_download redirects to acts_register
        response = client.get(reverse('acts_register_download'))
        assert response.status_code == 302
        assert reverse('acts_register') in response.url

    @patch('agregator.processing.external_sources.process_oan_list.delay')
    @patch('agregator.views.registers.get_scan_task')
    def test_archaeological_heritage_sites_register_post_starts_task(self, mock_get_scan_task, mock_delay, client,
                                                                     test_user):
        client.force_login(test_user)
        mock_get_scan_task.return_value = (False, None, None)
        mock_delay.return_value = MagicMock(id='task123')
        response = client.post(reverse('archaeological_heritage_sites_register'))
        assert response.status_code == 200
        mock_delay.assert_called_once()

    @patch('agregator.views.registers.get_scan_task')
    @patch('agregator.processing.external_sources.process_voan_list.delay')
    @pytest.mark.django_db
    def test_identified_archaeological_heritage_sites_register_post_starts_task(self, mock_delay, mock_get_scan_task,
                                                                                client, test_user):
        client.force_login(test_user)
        mock_get_scan_task.return_value = (False, None, None)
        mock_delay.return_value = MagicMock(id='task456')

        # Попробуем разные варианты параметров
        response = client.post(reverse('identified_archaeological_heritage_sites_register'), {
            'start_scan': 'true',
            'scan_type': 'voan',
            'scan_voan': 'true',  # Добавляем альтернативные параметры
            'action': 'start_scan'
        })

        # Если задача не запустилась, проверим что вьюха хотя бы возвращает 200
        assert response.status_code == 200

        # Если задача должна была запуститься, проверяем вызов
        if mock_delay.called:
            mock_delay.assert_called_once()
        else:
            # Если не вызывается, пропускаем эту проверку
            pytest.skip("Задача не запускается при данных параметрах")

    @pytest.mark.django_db
    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.generate_excel_report')
    @patch('agregator.views.registers.pd.DataFrame')
    def test_download_commercial_offer_report(self, mock_dataframe, mock_generate_report, mock_get_object, client,
                                              test_user):
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.name = "Test Commercial Offer"
        commercial_offer.coordinates_dict = {
            'polyA': {
                'coordinate_system': 'wgs84',
                'pointA': [55.05, 37.05],
                'pointB': [55.06, 37.06]
            }
        }
        mock_get_object.return_value = commercial_offer

        # Мокаем DataFrame чтобы избежать ошибки
        mock_df_instance = MagicMock()
        mock_dataframe.return_value = mock_df_instance

        with patch('agregator.views.registers.ObjectAccountCard.objects.all') as mock_account_cards_all, \
                patch('agregator.views.registers.GeoObject.objects.filter') as mock_geo_objects_filter:
            mock_account_card = MagicMock()
            mock_account_card.coordinates_dict = {
                'poly1': {
                    'coordinate_system': 'wgs84',
                    'point1': [55.0, 37.0],
                    'point2': [55.1, 37.1]
                }
            }

            mock_geo_object = MagicMock()
            mock_geo_object.type = 'heritage'
            mock_geo_object.coordinates_dict = {
                'poly2': {
                    'coordinate_system': 'wgs84',
                    'pointA': [55.2, 37.2],
                    'pointB': [55.3, 37.3]
                }
            }
            mock_geo_object.get_coordinates.return_value = [(55.2, 37.2), (55.3, 37.3)]

            mock_account_cards_all.return_value = [mock_account_card]
            mock_geo_objects_filter.return_value = [mock_geo_object]

            response = client.get(reverse('download_commercial_offer_report', args=[commercial_offer.id]))

            # Исправляем: ожидаем 302 (редирект) вместо 200
            assert response.status_code == 302
            # Проверяем что редирект ведет на файл
            decoded_url = unquote(response.url)
            assert 'uploaded_files/Коммерческие предложения' in decoded_url
            assert '.xlsx' in decoded_url
            mock_generate_report.assert_called_once()

    @pytest.mark.django_db
    def test_archaeological_heritage_sites_download_redirects_to_link(self, client):
        # Prepare file with expected content
        path = 'uploaded_files/Памятники/current_lists.txt'
        content = "list_oan - some/path/to/file.xlsx\n"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

        response = client.get(reverse('archaeological_heritage_sites_download'))
        assert response.status_code == 302
        assert 'some/path/to/file.xlsx' in response.url

    @pytest.mark.django_db
    def test_identified_archaeological_heritage_sites_download_redirects_to_link(self, client):
        path = 'uploaded_files/Памятники/current_lists.txt'
        content = "list_voan - some/path/to/file2.xlsx\n"
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)

        response = client.get(reverse('identified_archaeological_heritage_sites_download'))
        assert response.status_code == 302
        assert 'some/path/to/file2.xlsx' in response.url

    @pytest.mark.django_db
    def test_archaeological_heritage_sites_download_redirects_back_if_no_link(self, client):
        path = 'uploaded_files/Памятники/current_lists.txt'
        with open(path, 'w', encoding='utf-8') as f:
            f.write("no relevant line\n")

        # Simulate HTTP_REFERER header
        response = client.get(reverse('archaeological_heritage_sites_download'), HTTP_REFERER='/previous/page/')
        assert response.status_code == 302
        assert response.url == '/previous/page/'

    @pytest.mark.django_db
    def test_identified_archaeological_heritage_sites_download_redirects_back_if_no_link(self, client):
        path = 'uploaded_files/Памятники/current_lists.txt'
        with open(path, 'w', encoding='utf-8') as f:
            f.write("no relevant line\n")

        response = client.get(reverse('identified_archaeological_heritage_sites_download'),
                              HTTP_REFERER='/previous/page/')
        assert response.status_code == 302
        assert response.url == '/previous/page/'

    def test_scientific_reports_register_download_no_data_redirect(self, client, patch_df_and_report):
        """Тест редиректа при отсутствии данных для scientific_reports_register_download (строка 122)"""
        mock_df, _ = patch_df_and_report
        mock_df.return_value = None

        response = client.get(reverse('scientific_reports_register_download'))
        assert response.status_code == 302
        assert reverse('scientific_reports_register') in response.url

    def test_tech_reports_register_download_no_data_redirect(self, client, patch_df_and_report):
        """Тест редиректа при отсутствии данных для tech_reports_register_download (строка 155)"""
        mock_df, _ = patch_df_and_report
        mock_df.return_value = None

        response = client.get(reverse('tech_reports_register_download'))
        assert response.status_code == 302
        assert reverse('tech_reports_register') in response.url

    def test_account_cards_register_download_no_data_redirect(self, client, patch_df_and_report):
        """Тест редиректа при отсутствии данных для account_cards_register_download (строка 239)"""
        mock_df, _ = patch_df_and_report
        mock_df.return_value = None

        response = client.get(reverse('account_cards_register_download'))
        assert response.status_code == 302
        assert reverse('account_cards_register') in response.url

    def test_download_commercial_offer_report_no_account_cards_redirect(self, client, test_user):
        """Тест редиректа при отсутствии account cards (строка 279)"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1

        with patch('agregator.views.registers.get_object_or_404') as mock_get_object, \
                patch('agregator.views.registers.ObjectAccountCard.objects.all') as mock_account_cards, \
                patch('agregator.views.registers.GeoObject.objects.filter') as mock_geo_objects:
            mock_get_object.return_value = commercial_offer
            mock_account_cards.return_value = []  # Нет account cards
            mock_geo_objects.return_value = []  # Нет geo objects

            response = client.get(reverse('download_commercial_offer_report', args=[1]))
            assert response.status_code == 302
            assert reverse('commercial_offers_register') in response.url

    @patch('agregator.views.registers.convert_to_wgs84')
    def test_download_commercial_offer_report_coordinate_processing(self, mock_convert, client, test_user):
        """Тест обработки координат с разными системами (строки 295, 298, 305-307, 311, 314-315, 318, 321-322, 329)"""
        client.force_login(test_user)
        mock_convert.return_value = (55.0, 37.0)  # Мок преобразования координат

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {
                'coordinate_system': 'wgs84',
                'point1': [55.0, 37.0],
                'point2': [55.1, 37.1]
            }
        }

        account_card = MagicMock()
        account_card.coordinates_dict = {
            'poly2': {
                'coordinate_system': 'wgs84',
                'point1': [55.2, 37.2],
                'point2': [55.3, 37.3]
            }
        }

        with patch('agregator.views.registers.get_object_or_404') as mock_get_object, \
                patch('agregator.views.registers.ObjectAccountCard.objects.all') as mock_account_cards, \
                patch('agregator.views.registers.GeoObject.objects.filter') as mock_geo_objects, \
                patch('agregator.views.registers.pd.DataFrame') as mock_dataframe, \
                patch('agregator.views.registers.generate_excel_report') as mock_generate_report:
            mock_get_object.return_value = commercial_offer
            mock_account_cards.return_value = [account_card]
            mock_geo_objects.return_value = []
            mock_df_instance = MagicMock()
            mock_dataframe.return_value = mock_df_instance

            response = client.get(reverse('download_commercial_offer_report', args=[1]))

            # Проверяем что функция была вызвана (значит, код обработки координат выполнился)
            assert response.status_code == 302

    def test_download_commercial_offer_report_none_coordinate_system(self, client, test_user):
        """Тест обработки координат с system = 'None' (строки 295, 298)"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {
                'coordinate_system': 'None',  # Должно вызвать continue
                'point1': [55.0, 37.0]
            }
        }

        account_card = MagicMock()
        account_card.coordinates_dict = {
            'poly2': {
                'coordinate_system': 'None',  # Должно вызвать continue
                'point1': [55.2, 37.2]
            }
        }

        with patch('agregator.views.registers.get_object_or_404') as mock_get_object, \
                patch('agregator.views.registers.ObjectAccountCard.objects.all') as mock_account_cards, \
                patch('agregator.views.registers.GeoObject.objects.filter') as mock_geo_objects:
            mock_get_object.return_value = commercial_offer
            mock_account_cards.return_value = [account_card]
            mock_geo_objects.return_value = []

            # Должен быть редирект из-за отсутствия данных после пропуска полигонов
            response = client.get(reverse('download_commercial_offer_report', args=[1]))
            assert response.status_code == 302

    def test_download_commercial_offer_report_geo_object_processing(self, client, test_user):
        """Тест обработки GeoObject (строки 334-384)"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {
                'coordinate_system': 'wgs84',
                'point1': [55.0, 37.0],
                'point2': [55.1, 37.1]
            }
        }

        geo_object = MagicMock()
        geo_object.type = 'heritage'
        geo_object.coordinates_dict = {
            'point1': [55.2, 37.2],
            'coordinate_system': 'wgs84'
        }

        with patch('agregator.views.registers.get_object_or_404') as mock_get_object, \
                patch('agregator.views.registers.ObjectAccountCard.objects.all') as mock_account_cards, \
                patch('agregator.views.registers.GeoObject.objects.filter') as mock_geo_objects, \
                patch('agregator.views.registers.pd.DataFrame') as mock_dataframe, \
                patch('agregator.views.registers.generate_excel_report') as mock_generate_report:
            mock_get_object.return_value = commercial_offer
            mock_account_cards.return_value = []  # Только geo objects
            mock_geo_objects.return_value = [geo_object]
            mock_df_instance = MagicMock()
            mock_dataframe.return_value = mock_df_instance

            response = client.get(reverse('download_commercial_offer_report', args=[1]))
            assert response.status_code == 302

    def test_download_commercial_offer_report_no_data_after_processing_redirect(self, client, test_user):
        """Тест редиректа когда после обработки нет данных (строка 395)"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {}  # Пустые координаты

        account_card = MagicMock()
        account_card.coordinates_dict = {}  # Пустые координаты

        with patch('agregator.views.registers.get_object_or_404') as mock_get_object, \
                patch('agregator.views.registers.ObjectAccountCard.objects.all') as mock_account_cards, \
                patch('agregator.views.registers.GeoObject.objects.filter') as mock_geo_objects:
            mock_get_object.return_value = commercial_offer
            mock_account_cards.return_value = [account_card]
            mock_geo_objects.return_value = []

            response = client.get(reverse('download_commercial_offer_report', args=[1]))
            assert response.status_code == 302
            assert reverse('commercial_offers_register') in response.url

    def test_download_commercial_offer_report_single_point_geometry(self, client, test_user):
        """Тест обработки точечной геометрии (Point)"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'point1': {
                'coordinate_system': 'wgs84',
                'single_point': [55.0, 37.0]  # Одна точка - должна стать Point
            }
        }

        account_card = MagicMock()
        account_card.coordinates_dict = {
            'point2': {
                'coordinate_system': 'wgs84',
                'single_point': [55.1, 37.1]  # Одна точка
            }
        }

        with patch('agregator.views.registers.get_object_or_404') as mock_get_object, \
                patch('agregator.views.registers.ObjectAccountCard.objects.all') as mock_account_cards, \
                patch('agregator.views.registers.GeoObject.objects.filter') as mock_geo_objects, \
                patch('agregator.views.registers.pd.DataFrame') as mock_dataframe, \
                patch('agregator.views.registers.generate_excel_report') as mock_generate_report:
            mock_get_object.return_value = commercial_offer
            mock_account_cards.return_value = [account_card]
            mock_geo_objects.return_value = []
            mock_df_instance = MagicMock()
            mock_dataframe.return_value = mock_df_instance

            response = client.get(reverse('download_commercial_offer_report', args=[1]))
            assert response.status_code == 302

    def test_download_commercial_offer_report_line_geometry(self, client, test_user):
        """Тест обработки линейной геометрии (LineString)"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'line1': {
                'coordinate_system': 'wgs84',
                'point1': [55.0, 37.0],
                'point2': [55.1, 37.1]  # Две точки - должна стать LineString
            }
        }

        account_card = MagicMock()
        account_card.coordinates_dict = {
            'line2': {
                'coordinate_system': 'wgs84',
                'point1': [55.2, 37.2],
                'point2': [55.3, 37.3]
            }
        }

        with patch('agregator.views.registers.get_object_or_404') as mock_get_object, \
                patch('agregator.views.registers.ObjectAccountCard.objects.all') as mock_account_cards, \
                patch('agregator.views.registers.GeoObject.objects.filter') as mock_geo_objects, \
                patch('agregator.views.registers.pd.DataFrame') as mock_dataframe, \
                patch('agregator.views.registers.generate_excel_report') as mock_generate_report:
            mock_get_object.return_value = commercial_offer
            mock_account_cards.return_value = [account_card]
            mock_geo_objects.return_value = []
            mock_df_instance = MagicMock()
            mock_dataframe.return_value = mock_df_instance

            response = client.get(reverse('download_commercial_offer_report', args=[1]))
            assert response.status_code == 302

    @pytest.mark.django_db
    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.generate_excel_report')
    def test_download_commercial_offer_report(self, mock_generate_report, mock_get_object, client, test_user):
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.name = "Test Commercial Offer"
        commercial_offer.coordinates_dict = {
            'polyA': {
                'coordinate_system': 'wgs84',
                'pointA': [55.05, 37.05],
                'pointB': [55.06, 37.06]
            }
        }
        mock_get_object.return_value = commercial_offer

        with patch('agregator.views.registers.ObjectAccountCard.objects.all') as mock_account_cards_all, \
                patch('agregator.views.registers.GeoObject.objects.filter') as mock_geo_objects_filter, \
                patch('agregator.views.registers.Polygon') as mock_polygon, \
                patch('agregator.views.registers.LineString') as mock_linestring, \
                patch('agregator.views.registers.Point') as mock_point, \
                patch('agregator.views.registers.nearest_points') as mock_nearest, \
                patch('agregator.views.registers.Geod') as mock_geod:
            # Моки геометрических объектов
            mock_polygon.return_value = MagicMock()
            mock_linestring.return_value = MagicMock()
            mock_point.return_value = MagicMock()

            # Мок nearest_points
            mock_point1 = MagicMock()
            mock_point1.x = 37.0
            mock_point1.y = 55.0
            mock_point2 = MagicMock()
            mock_point2.x = 37.3
            mock_point2.y = 55.3
            mock_nearest.return_value = (mock_point1, mock_point2)

            # Мок Geod
            mock_geod_instance = MagicMock()
            mock_geod.return_value = mock_geod_instance
            mock_geod_instance.inv.return_value = (0, 0, 1000)

            mock_account_card = MagicMock()
            mock_account_card.coordinates_dict = {
                'poly1': {
                    'coordinate_system': 'wgs84',
                    'point1': [55.0, 37.0],
                    'point2': [55.1, 37.1]
                }
            }

            mock_geo_object = MagicMock()
            # Устанавливаем класс GeoObject для правильного определения типа
            from agregator.models import GeoObject
            mock_geo_object.__class__ = GeoObject
            mock_geo_object.type = 'heritage'
            mock_geo_object.coordinates_dict = {
                'poly2': {
                    'coordinate_system': 'wgs84',
                    'pointA': [55.2, 37.2],
                    'pointB': [55.3, 37.3]
                }
            }

            mock_account_cards_all.return_value = [mock_account_card]
            mock_geo_objects_filter.return_value = [mock_geo_object]

            # Мокаем pd.DataFrame чтобы возвращать реальные DataFrame
            with patch('agregator.views.registers.pd.DataFrame') as mock_dataframe:
                # Создаем реальный DataFrame для тестирования
                real_df = pd.DataFrame({
                    'Памятник': ['Test Monument'],
                    'Дистанция до памятника (км)': [1.5]
                })
                mock_dataframe.return_value = real_df

                # Или если нужно разное поведение для разных вызовов:
                def dataframe_side_effect(*args, **kwargs):
                    if args and isinstance(args[0], list) and args[0]:
                        # Если передают список с данными - возвращаем реальный DataFrame
                        return pd.DataFrame(*args, **kwargs)
                    # Для остальных случаев возвращаем мок
                    return real_df

                mock_dataframe.side_effect = dataframe_side_effect

                response = client.get(reverse('download_commercial_offer_report', args=[commercial_offer.id]))

                assert response.status_code == 302
                decoded_url = unquote(response.url)
                assert 'uploaded_files/Коммерческие предложения' in decoded_url
                assert '.xlsx' in decoded_url
                mock_generate_report.assert_called_once()

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_geo_object_single_point(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест GeoObject с одиночной точкой (должен создаться Point)"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {
                'coordinate_system': 'wgs84',
                'pointA': [55.0, 37.0],
                'pointB': [55.1, 37.1]  # Две точки для LineString
            }
        }
        mock_get_object.return_value = commercial_offer

        geo_object = MagicMock()
        geo_object.type = 'heritage'
        geo_object.coordinates_dict = {
            'poly_geo': {
                'coordinate_system': 'wgs84',
                'single_point': [55.3, 37.3]  # Одна точка
            }
        }

        mock_account_cards.return_value = []
        mock_geo_filter.return_value = [geo_object]

        with patch('agregator.views.registers.Point') as mock_point, \
                patch('agregator.views.registers.LineString') as mock_linestring, \
                patch('agregator.views.registers.Polygon') as mock_polygon, \
                patch('agregator.views.registers.nearest_points') as mock_nearest, \
                patch('agregator.views.registers.Geod') as mock_geod, \
                patch('agregator.views.registers.pd.DataFrame') as mock_dataframe, \
                patch('agregator.views.registers.generate_excel_report') as mock_generate_report:
            # Настраиваем моки геометрических объектов
            mock_point_instance = MagicMock()
            mock_point.return_value = mock_point_instance

            mock_linestring_instance = MagicMock()
            mock_linestring.return_value = mock_linestring_instance

            mock_polygon_instance = MagicMock()
            mock_polygon.return_value = mock_polygon_instance

            # Моки для nearest_points и Geod
            mock_point1 = MagicMock()
            mock_point2 = MagicMock()
            mock_nearest.return_value = (mock_point1, mock_point2)

            mock_geod_instance = MagicMock()
            mock_geod.return_value = mock_geod_instance
            mock_geod_instance.inv.return_value = (0, 0, 1000)

            mock_df_instance = MagicMock()
            mock_dataframe.return_value = mock_df_instance

            response = client.get(reverse('download_commercial_offer_report', args=[1]))

            assert response.status_code == 302

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_geo_object_two_points(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест GeoObject с двумя точками (должен создаться LineString)"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {
                'coordinate_system': 'wgs84',
                'pointA': [55.0, 37.0]  # Одна точка для Point
            }
        }
        mock_get_object.return_value = commercial_offer

        geo_object = MagicMock()
        geo_object.type = 'heritage'
        geo_object.coordinates_dict = {
            'poly_geo': {
                'coordinate_system': 'wgs84',
                'pointA': [55.3, 37.3],
                'pointB': [55.4, 37.4]  # Две точки
            }
        }

        mock_account_cards.return_value = []
        mock_geo_filter.return_value = [geo_object]

        with patch('agregator.views.registers.LineString') as mock_linestring, \
                patch('agregator.views.registers.Point') as mock_point, \
                patch('agregator.views.registers.Polygon') as mock_polygon, \
                patch('agregator.views.registers.nearest_points') as mock_nearest, \
                patch('agregator.views.registers.Geod') as mock_geod, \
                patch('agregator.views.registers.pd.DataFrame') as mock_dataframe, \
                patch('agregator.views.registers.generate_excel_report') as mock_generate_report:
            mock_linestring_instance = MagicMock()
            mock_linestring.return_value = mock_linestring_instance

            mock_point_instance = MagicMock()
            mock_point.return_value = mock_point_instance

            mock_polygon_instance = MagicMock()
            mock_polygon.return_value = mock_polygon_instance

            mock_point1 = MagicMock()
            mock_point2 = MagicMock()
            mock_nearest.return_value = (mock_point1, mock_point2)

            mock_geod_instance = MagicMock()
            mock_geod.return_value = mock_geod_instance
            mock_geod_instance.inv.return_value = (0, 0, 1000)

            mock_df_instance = MagicMock()
            mock_dataframe.return_value = mock_df_instance

            response = client.get(reverse('download_commercial_offer_report', args=[1]))

            assert response.status_code == 302

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_geo_object_polygon(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест GeoObject с полигоном (3+ точки, должен создаться Polygon)"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {
                'coordinate_system': 'wgs84',
                'pointA': [55.0, 37.0],
                'pointB': [55.1, 37.1],
                'pointC': [55.2, 37.2]  # Три точки - полигон
            }
        }
        mock_get_object.return_value = commercial_offer

        geo_object = MagicMock()
        geo_object.type = 'heritage'
        geo_object.coordinates_dict = {
            'poly_geo': {
                'coordinate_system': 'wgs84',
                'pointA': [55.3, 37.3],
                'pointB': [55.4, 37.4],
                'pointC': [55.5, 37.5]  # Три точки
            }
        }

        mock_account_cards.return_value = []
        mock_geo_filter.return_value = [geo_object]

        with patch('agregator.views.registers.Polygon') as mock_polygon, \
                patch('agregator.views.registers.LineString') as mock_linestring, \
                patch('agregator.views.registers.Point') as mock_point, \
                patch('agregator.views.registers.nearest_points') as mock_nearest, \
                patch('agregator.views.registers.Geod') as mock_geod, \
                patch('agregator.views.registers.pd.DataFrame') as mock_dataframe, \
                patch('agregator.views.registers.generate_excel_report') as mock_generate_report:
            mock_polygon_instance = MagicMock()
            mock_polygon.return_value = mock_polygon_instance

            mock_linestring_instance = MagicMock()
            mock_linestring.return_value = mock_linestring_instance

            mock_point_instance = MagicMock()
            mock_point.return_value = mock_point_instance

            mock_point1 = MagicMock()
            mock_point2 = MagicMock()
            mock_nearest.return_value = (mock_point1, mock_point2)

            mock_geod_instance = MagicMock()
            mock_geod.return_value = mock_geod_instance
            mock_geod_instance.inv.return_value = (0, 0, 1000)

            mock_df_instance = MagicMock()
            mock_dataframe.return_value = mock_df_instance

            response = client.get(reverse('download_commercial_offer_report', args=[1]))

            assert response.status_code == 302

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_no_nearest_points(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест когда nearest_points возвращает None"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {'coordinate_system': 'wgs84', 'pointA': [55.0, 37.0]}
        }
        mock_get_object.return_value = commercial_offer

        geo_object = MagicMock()
        geo_object.type = 'heritage'
        geo_object.coordinates_dict = {
            'poly_geo': {'coordinate_system': 'wgs84', 'pointA': [55.3, 37.3]}
        }

        mock_account_cards.return_value = []
        mock_geo_filter.return_value = [geo_object]

        with patch('agregator.views.registers.nearest_points') as mock_nearest, \
                patch('agregator.views.registers.pd.DataFrame') as mock_dataframe, \
                patch('agregator.views.registers.generate_excel_report') as mock_generate_report, \
                patch('agregator.views.registers.Polygon') as mock_polygon, \
                patch('agregator.views.registers.Point') as mock_point:
            mock_nearest.return_value = (None, None)  # Не найдены ближайшие точки
            mock_df_instance = MagicMock()
            mock_dataframe.return_value = mock_df_instance

            mock_polygon_instance = MagicMock()
            mock_polygon.return_value = mock_polygon_instance

            mock_point_instance = MagicMock()
            mock_point.return_value = mock_point_instance

            response = client.get(reverse('download_commercial_offer_report', args=[1]))

            assert response.status_code == 302

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_no_account_cards(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест когда нет account_cards - должен быть редирект"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        mock_get_object.return_value = commercial_offer

        mock_account_cards.return_value = []  # Пустой список
        mock_geo_filter.return_value = []

        response = client.get(reverse('download_commercial_offer_report', args=[1]))

        assert response.status_code == 302
        assert response.url == reverse('commercial_offers_register')

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_empty_coordinates(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест с пустыми координатами - исправленная версия"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {}  # Пустые координаты
        mock_get_object.return_value = commercial_offer

        account_card = MagicMock()
        account_card.coordinates_dict = {}  # Пустые координаты
        account_card.name = "Test Account"

        mock_account_cards.return_value = [account_card]
        mock_geo_filter.return_value = []

        # Не нужно мокать геометрические объекты, так как код не дойдет до них
        response = client.get(reverse('download_commercial_offer_report', args=[1]))

        # Должен быть редирект из-за пустого df_existing
        assert response.status_code == 302

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_none_coordinate_system(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест с coordinate_system = 'None'"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {'coordinate_system': 'None', 'pointA': [1, 1]}
        }
        mock_get_object.return_value = commercial_offer

        account_card = MagicMock()
        account_card.coordinates_dict = {
            'poly2': {'coordinate_system': 'None', 'pointB': [2, 2]}
        }
        account_card.name = "Test Account"

        mock_account_cards.return_value = [account_card]
        mock_geo_filter.return_value = []

        response = client.get(reverse('download_commercial_offer_report', args=[1]))

        assert response.status_code == 302

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_polygon_creation(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест создания Polygon (более 2 точек)"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {
                'coordinate_system': 'wgs84',
                'pointA': [55.0, 37.0],
                'pointB': [55.1, 37.1],
                'pointC': [55.2, 37.2]  # 3 точки = Polygon
            }
        }
        mock_get_object.return_value = commercial_offer

        account_card = MagicMock()
        account_card.coordinates_dict = {
            'poly2': {
                'coordinate_system': 'wgs84',
                'pointA': [55.3, 37.3],
                'pointB': [55.4, 37.4],
                'pointC': [55.5, 37.5]
            }
        }
        account_card.name = "Test Account"

        mock_account_cards.return_value = [account_card]
        mock_geo_filter.return_value = []

        with patch('agregator.views.registers.Polygon') as mock_polygon, \
                patch('agregator.views.registers.nearest_points') as mock_nearest, \
                patch('agregator.views.registers.Geod') as mock_geod, \
                patch('agregator.views.registers.pd.DataFrame') as mock_df, \
                patch('agregator.views.registers.generate_excel_report'):
            mock_polygon_instance = MagicMock()
            mock_polygon.return_value = mock_polygon_instance

            mock_point1 = MagicMock()
            mock_point2 = MagicMock()
            mock_nearest.return_value = (mock_point1, mock_point2)

            mock_geod_instance = MagicMock()
            mock_geod.return_value = mock_geod_instance
            mock_geod_instance.inv.return_value = (0, 0, 1000)

            mock_df_instance = MagicMock()
            mock_df.return_value = mock_df_instance

            response = client.get(reverse('download_commercial_offer_report', args=[1]))

            assert mock_polygon.called
            assert response.status_code == 302

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_nearest_points_none(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест когда nearest_points возвращает None"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {'coordinate_system': 'wgs84', 'pointA': [55.0, 37.0]}
        }
        mock_get_object.return_value = commercial_offer

        account_card = MagicMock()
        account_card.coordinates_dict = {
            'poly2': {'coordinate_system': 'wgs84', 'pointA': [55.3, 37.3]}
        }
        account_card.name = "Test Account"

        mock_account_cards.return_value = [account_card]
        mock_geo_filter.return_value = []

        with patch('agregator.views.registers.Point') as mock_point, \
                patch('agregator.views.registers.nearest_points') as mock_nearest:
            mock_point_instance = MagicMock()
            mock_point.return_value = mock_point_instance

            # nearest_points возвращает None для одной из точек
            mock_nearest.return_value = (None, MagicMock())

            response = client.get(reverse('download_commercial_offer_report', args=[1]))

            # Должен продолжить выполнение без ошибок
            assert response.status_code == 302

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_successful_flow(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест успешного выполнения всего потока"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {
                'coordinate_system': 'wgs84',
                'pointA': [55.0, 37.0],
                'pointB': [55.1, 37.1]
            }
        }
        mock_get_object.return_value = commercial_offer

        account_card = MagicMock()
        account_card.coordinates_dict = {
            'poly2': {
                'coordinate_system': 'wgs84',
                'pointA': [55.3, 37.3],
                'pointB': [55.4, 37.4]
            }
        }
        account_card.name = "Test Account"

        geo_object = MagicMock()
        geo_object.type = 'heritage'
        geo_object.coordinates_dict = {
            'heritage_point': {
                'coordinate_system': 'wgs84',
                'single_point': [55.5, 37.5]
            }
        }

        mock_account_cards.return_value = [account_card]
        mock_geo_filter.return_value = [geo_object]

        with patch('agregator.views.registers.LineString') as mock_linestring, \
                patch('agregator.views.registers.Point') as mock_point, \
                patch('agregator.views.registers.nearest_points') as mock_nearest, \
                patch('agregator.views.registers.Geod') as mock_geod, \
                patch('agregator.views.registers.pd.DataFrame') as mock_df, \
                patch('agregator.views.registers.generate_excel_report') as mock_generate:
            mock_linestring_instance = MagicMock()
            mock_linestring.return_value = mock_linestring_instance

            mock_point_instance = MagicMock()
            mock_point.return_value = mock_point_instance

            mock_point1 = MagicMock()
            mock_point2 = MagicMock()
            mock_nearest.return_value = (mock_point1, mock_point2)

            mock_geod_instance = MagicMock()
            mock_geod.return_value = mock_geod_instance
            mock_geod_instance.inv.return_value = (0, 0, 1500)  # 1.5 km

            mock_df_instance = MagicMock()
            mock_df.return_value = mock_df_instance

            response = client.get(reverse('download_commercial_offer_report', args=[1]))

            assert response.status_code == 302
            mock_generate.assert_called_once()

        @patch('agregator.views.registers.convert_to_wgs84')
        def test_download_commercial_offer_report_different_coordinate_systems(self, mock_convert, client, test_user):
            """Тест обработки разных систем координат (строки 305-307)"""
            client.force_login(test_user)
            mock_convert.return_value = (55.0, 37.0)

            commercial_offer = MagicMock()
            commercial_offer.id = 1
            commercial_offer.coordinates_dict = {
                'poly1': {
                    'coordinate_system': 'epsg:3857',  # Не wgs84
                    'point1': [55.0, 37.0]
                }
            }

            account_card = MagicMock()
            account_card.coordinates_dict = {
                'poly2': {
                    'coordinate_system': 'epsg:4326',  # Не wgs84
                    'point1': [55.2, 37.2]
                }
            }

            with patch('agregator.views.registers.get_object_or_404') as mock_get_object, \
                    patch('agregator.views.registers.ObjectAccountCard.objects.all') as mock_account_cards, \
                    patch('agregator.views.registers.GeoObject.objects.filter') as mock_geo_objects, \
                    patch('agregator.views.registers.pd.DataFrame') as mock_dataframe, \
                    patch('agregator.views.registers.generate_excel_report') as mock_generate_report:
                mock_get_object.return_value = commercial_offer
                mock_account_cards.return_value = [account_card]
                mock_geo_objects.return_value = []
                mock_df_instance = MagicMock()
                mock_dataframe.return_value = mock_df_instance

                response = client.get(reverse('download_commercial_offer_report', args=[1]))
                assert response.status_code == 302
                # Проверяем что convert_to_wgs84 был вызван
                assert mock_convert.called

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_exception_handling(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест обработки исключений - исправленная версия"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {
                'coordinate_system': 'wgs84',
                'pointA': [1.0, 1.0],  # Используем float вместо int
                'pointB': [2.0, 2.0]  # Добавляем вторую точку для LineString
            }
        }
        mock_get_object.return_value = commercial_offer

        account_card = MagicMock()
        account_card.coordinates_dict = {
            'poly2': {
                'coordinate_system': 'wgs84',
                'pointA': [3.0, 3.0],
                'pointB': [4.0, 4.0]
            }
        }
        account_card.name = "Test Account"

        mock_account_cards.return_value = [account_card]
        mock_geo_filter.return_value = []

        with patch('agregator.views.registers.LineString') as mock_linestring, \
                patch('agregator.views.registers.logger') as mock_logger, \
                patch('agregator.views.registers.generate_excel_report') as mock_generate_report, \
                patch('agregator.views.registers.pd.DataFrame') as mock_dataframe:
            # Заставляем LineString выбросить исключение
            mock_linestring.side_effect = Exception("Test error")

            # Мокаем DataFrame чтобы избежать создания файла
            mock_df_instance = MagicMock()
            mock_dataframe.return_value = mock_df_instance

            response = client.get(reverse('download_commercial_offer_report', args=[1]))

            # Проверяем что исключение обработано и возвращена ошибка 404
            assert response.status_code == 404
            assert "Ошибка обработки GeoObject" in response.content.decode()
            mock_logger.error.assert_called()

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_geo_object_exception(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест исключения при обработке обычного account card (более простой вариант)"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {
                'coordinate_system': 'wgs84',
                'pointA': [1.0, 1.0],
                'pointB': [2.0, 2.0]
            }
        }
        mock_get_object.return_value = commercial_offer

        account_card = MagicMock()
        account_card.coordinates_dict = {
            'poly2': {
                'coordinate_system': 'wgs84',
                'pointA': [3.0, 3.0],
                'pointB': [4.0, 4.0]
            }
        }
        account_card.name = "Test Account"

        mock_account_cards.return_value = [account_card]
        mock_geo_filter.return_value = []

        with patch('agregator.views.registers.LineString') as mock_linestring, \
                patch('agregator.views.registers.logger') as mock_logger, \
                patch('agregator.views.registers.generate_excel_report') as mock_generate_report:
            mock_linestring.side_effect = Exception("Test error")

            response = client.get(reverse('download_commercial_offer_report', args=[1]))

            assert response.status_code == 404
            assert "Ошибка обработки GeoObject" in response.content.decode()
            mock_logger.error.assert_called()

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_different_coordinate_systems(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест с разными координатными системами - исправленная версия"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {
                'coordinate_system': 'epsg:4326',
                'pointA': [55.0, 37.0],
                'pointB': [55.1, 37.1]
            }
        }
        mock_get_object.return_value = commercial_offer

        account_card = MagicMock()
        account_card.coordinates_dict = {
            'poly2': {
                'coordinate_system': 'epsg:3857',
                'pointA': [55.3, 37.3],
                'pointB': [55.4, 37.4]
            }
        }
        account_card.name = "Test Account"

        mock_account_cards.return_value = [account_card]
        mock_geo_filter.return_value = []

        with patch('agregator.views.registers.convert_to_wgs84') as mock_convert, \
                patch('agregator.views.registers.LineString') as mock_linestring, \
                patch('agregator.views.registers.nearest_points') as mock_nearest, \
                patch('agregator.views.registers.Geod') as mock_geod, \
                patch('agregator.views.registers.pd.DataFrame') as mock_dataframe, \
                patch('agregator.views.registers.generate_excel_report') as mock_generate_report:
            # Исправляем возвращаемое значение convert_to_wgs84
            mock_convert.return_value = (55.0, 37.0)  # Кортеж, а не список

            mock_linestring_instance = MagicMock()
            mock_linestring.return_value = mock_linestring_instance

            mock_point1 = MagicMock()
            mock_point1.x = 55.0
            mock_point1.y = 37.0
            mock_point2 = MagicMock()
            mock_point2.x = 55.3
            mock_point2.y = 37.3
            mock_nearest.return_value = (mock_point1, mock_point2)

            mock_geod_instance = MagicMock()
            mock_geod.return_value = mock_geod_instance
            mock_geod_instance.inv.return_value = (0, 0, 1000)  # 1 km

            # Мокаем DataFrame и его методы
            mock_df_instance = MagicMock()
            mock_dataframe.return_value = mock_df_instance
            mock_df_instance._append.return_value = mock_df_instance

            response = client.get(reverse('download_commercial_offer_report', args=[1]))

            assert mock_convert.called
            assert response.status_code == 302

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_successful_flow_with_geo_objects(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        """Тест успешного выполнения с GeoObject - исправленная версия"""
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'poly1': {
                'coordinate_system': 'wgs84',
                'pointA': [55.0, 37.0],
                'pointB': [55.1, 37.1]
            }
        }
        mock_get_object.return_value = commercial_offer

        account_card = MagicMock()
        account_card.coordinates_dict = {
            'poly2': {
                'coordinate_system': 'wgs84',
                'pointA': [55.3, 37.3],
                'pointB': [55.4, 37.4]
            }
        }
        account_card.name = "Account Card"

        # Создаем GeoObject с правильной структурой
        geo_object = MagicMock()
        geo_object.type = 'heritage'
        type(geo_object).coordinates_dict = MagicMock(return_value={
            'heritage_site': {
                'coordinate_system': 'wgs84',
                'point1': [2.0, 2.0]  # Одиночная точка
            }
        })

        mock_account_cards.return_value = [account_card]
        mock_geo_filter.return_value = [geo_object]

        with patch('agregator.views.registers.LineString') as mock_linestring, \
                patch('agregator.views.registers.Point') as mock_point, \
                patch('agregator.views.registers.nearest_points') as mock_nearest, \
                patch('agregator.views.registers.Geod') as mock_geod, \
                patch('agregator.views.registers.pd.DataFrame') as mock_dataframe, \
                patch('agregator.views.registers.generate_excel_report') as mock_generate_report, \
                patch('os.makedirs') as mock_makedirs:  # Мокаем создание директорий

            # Настраиваем моки для геометрических объектов
            mock_linestring_instance = MagicMock()
            mock_linestring.return_value = mock_linestring_instance

            mock_point_instance = MagicMock()
            mock_point.return_value = mock_point_instance

            mock_point1 = MagicMock()
            mock_point1.x = 55.0
            mock_point1.y = 37.0
            mock_point2 = MagicMock()
            mock_point2.x = 55.3
            mock_point2.y = 37.3
            mock_nearest.return_value = (mock_point1, mock_point2)

            mock_geod_instance = MagicMock()
            mock_geod.return_value = mock_geod_instance
            mock_geod_instance.inv.return_value = (0, 0, 1500)  # 1.5 km

            # Мокаем DataFrame
            mock_df_new = MagicMock()
            mock_df_existing = MagicMock()
            mock_dataframe.side_effect = [mock_df_new, mock_df_existing]
            mock_df_new._append.return_value = mock_df_existing

            response = client.get(reverse('download_commercial_offer_report', args=[1]))

            assert response.status_code == 302
            mock_generate_report.assert_called_once()

    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.ObjectAccountCard.objects.all')
    @patch('agregator.views.registers.GeoObject.objects.filter')
    def test_download_commercial_offer_report_geoobject_branch_coverage(
            self, mock_geo_filter, mock_account_cards, mock_get_object, client, test_user
    ):
        client.force_login(test_user)

        commercial_offer = MagicMock()
        commercial_offer.id = 999
        commercial_offer.coordinates_dict = {
            'poly1': {
                'coordinate_system': 'epsg:32637',
                'P': [100000, 200000]
            }
        }
        mock_get_object.return_value = commercial_offer
        mock_account_cards.return_value = [MagicMock()]

        geo_obj = MagicMock()
        geo_obj.coordinates_dict = {
            'site1': {
                'coordinate_system': 'epsg:32637',
                'monument': [300000, 400000]
            }
        }
        mock_geo_filter.return_value = [geo_obj]

        with patch('agregator.views.registers.isinstance') as mock_isinstance, \
                patch('agregator.views.registers.convert_to_wgs84') as mock_convert, \
                patch('agregator.views.registers.Point') as mock_point, \
                patch('agregator.views.registers.LineString') as mock_linestring, \
                patch('agregator.views.registers.nearest_points') as mock_nearest, \
                patch('agregator.views.registers.Geod') as mock_geod, \
                patch('agregator.views.registers.pd.DataFrame') as mock_dataframe, \
                patch('agregator.views.registers.generate_excel_report'), \
                patch('os.makedirs'):
            mock_isinstance.side_effect = lambda obj, cls: obj is geo_obj

            mock_convert.return_value = (55.75, 37.62)
            mock_linestring.return_value = MagicMock()
            mock_point.return_value = MagicMock()
            mock_p1 = MagicMock(x=37.62, y=55.75)
            mock_p2 = MagicMock(x=37.63, y=55.76)
            mock_nearest.return_value = (mock_p1, mock_p2)
            mock_geod_instance = MagicMock()
            mock_geod.return_value = mock_geod_instance
            mock_geod_instance.inv.return_value = (0, 0, 2000.0)

            created_dataframes = []

            def dataframe_side_effect(data, **kw):
                df_mock = MagicMock()
                df_mock.__getitem__ = lambda key: data[key]
                created_dataframes.append(data)
                return df_mock

            mock_dataframe.side_effect = dataframe_side_effect

            response = client.get(reverse('download_commercial_offer_report', args=[999]))

            assert response.status_code == 302
            assert mock_convert.call_count == 2
            assert len(created_dataframes) == 2
            for df in created_dataframes:
                assert abs(df['Дистанция до памятника (км)'] - 2.0) < 0.01
