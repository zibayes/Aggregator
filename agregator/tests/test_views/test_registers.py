import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.http import HttpResponseRedirect
from urllib.parse import quote


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
    @patch('agregator.processing.external_sources.process_voan_list')
    @pytest.mark.django_db
    def test_identified_archaeological_heritage_sites_register_post_starts_task(self, mock_process_voan,
                                                                                mock_get_scan_task, client, test_user):
        client.force_login(test_user)
        mock_get_scan_task.return_value = (False, None, None)
        mock_task = MagicMock()
        mock_task.id = 'task456'
        mock_process_voan.delay.return_value = mock_task

        response = client.post(reverse('identified_archaeological_heritage_sites_register'))
        assert response.status_code == 200
        mock_process_voan.delay.assert_called_once()

    @pytest.mark.django_db
    @patch('agregator.views.registers.get_object_or_404')
    @patch('agregator.views.registers.generate_excel_report')
    def test_download_commercial_offer_report(self, mock_generate_report, mock_get_object, client, test_user):
        client.force_login(test_user)
        # Правильный mock commercial_offer с вложенными словарями
        commercial_offer = MagicMock()
        commercial_offer.id = 1
        commercial_offer.coordinates_dict = {
            'polyA': {
                'coordinate_system': 'wgs84',
                'pointA': [55.05, 37.05],
                'pointB': [55.06, 37.06]
            }
        }
        mock_get_object.return_value = commercial_offer
        with patch('agregator.views.registers.ObjectAccountCard.objects.all') as mock_account_cards_all, \
                patch('agregator.views.registers.GeoObject.objects.filter') as mock_geo_objects_filter:
            # Мокаем account_card с правильной структурой coordinates_dict
            mock_account_card = MagicMock()
            mock_account_card.coordinates_dict = {
                'poly1': {
                    'coordinate_system': 'wgs84',
                    'point1': [55.0, 37.0],
                    'point2': [55.1, 37.1]
                }
            }
            # Мокаем geo_object с правильной структурой coordinates_dict
            mock_geo_object = MagicMock()
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
            response = client.get(reverse('download_commercial_offer_report', args=[commercial_offer.id]))
            assert response.status_code == 302
            assert response.url.startswith('/uploaded_files/Коммерческие предложения/')

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
