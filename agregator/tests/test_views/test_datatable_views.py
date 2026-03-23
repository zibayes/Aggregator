import pytest
import json
from unittest.mock import patch, MagicMock
from django.urls import reverse
from django.test import RequestFactory
from django.http import JsonResponse
from django.contrib.auth.models import AnonymousUser

from agregator.views.datatable_views import universal_datatable, format_heritage_site_data, \
    format_act_data, format_scientific_report_data, format_tech_report_data, format_open_list_data, \
    format_account_card_data, format_commercial_offer_data, format_geo_object_data


@pytest.mark.django_db
class TestDatatableViews:
    """Тесты для представлений DataTables"""

    # ---------------------- universal_datatable ----------------------

    def test_universal_datatable_get_returns_test_data(self, client):
        """GET запрос должен возвращать тестовые данные (для отладки)"""
        url = reverse('acts_datatable')
        response = client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert data['draw'] == 1
        assert data['recordsTotal'] == 100
        assert data['recordsFiltered'] == 100
        assert len(data['data']) == 2
        assert 'Тестовый' in data['data'][0][0]

    def test_universal_datatable_unknown_register_type(self, rf):
        request = rf.get('/fake/')
        request.user = AnonymousUser()
        response = universal_datatable(request, 'unknown')
        assert response.status_code == 400
        data = json.loads(response.content)
        assert data['error'] == 'Unknown register type'

    @patch('agregator.views.datatable_views.DataTableServerSide')
    def test_universal_datatable_post_success(self, mock_datatable_class, client, test_act):
        """POST запрос успешно обрабатывается DataTableServerSide"""
        mock_datatable = MagicMock()
        expected_response = {'draw': 1, 'recordsTotal': 1, 'recordsFiltered': 1, 'data': [['test']]}
        mock_datatable.get_response.return_value = JsonResponse(expected_response)
        mock_datatable_class.return_value = mock_datatable

        url = reverse('acts_datatable')
        post_data = {
            'draw': '1',
            'start': '0',
            'length': '10',
            'search[value]': '',
            'order[0][column]': '0',
            'order[0][dir]': 'asc',
        }
        response = client.post(url, post_data)
        assert response.status_code == 200
        assert response.json() == expected_response

        # Проверяем, что DataTableServerSide вызван с правильными аргументами
        mock_datatable_class.assert_called_once()
        args, kwargs = mock_datatable_class.call_args
        assert args[0].method == 'POST'
        from agregator.models import Act
        assert args[1].model == Act

    @patch('agregator.views.datatable_views.apps.get_model')
    def test_universal_datatable_model_not_found(self, mock_get_model, rf):
        """Ошибка при получении модели → возвращается ответ с ошибкой"""
        mock_get_model.side_effect = Exception("Model not found")
        request = rf.post('/fake/')
        request.user = AnonymousUser()
        response = universal_datatable(request, 'acts')
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data['draw'] == 1
        assert data['recordsTotal'] == 0
        assert data['recordsFiltered'] == 0
        assert data['data'] == []
        assert 'error' in data

    def test_universal_datatable_queryset_filter_is_processing(self, rf):
        from agregator.models import Act
        with patch.object(Act, 'is_processing', True, create=True):
            with patch('agregator.views.datatable_views.apps.get_model') as mock_get_model:
                mock_model = MagicMock()
                # Создаем цепочку: objects.select_related().all().filter
                mock_queryset = MagicMock()
                mock_model.objects.select_related.return_value.all.return_value = mock_queryset
                mock_get_model.return_value = mock_model

                request = rf.post('/fake/')
                request.user = AnonymousUser()
                universal_datatable(request, 'acts')

                mock_queryset.filter.assert_called_once_with(is_processing=False)

    # ---------------------- format_* functions ----------------------

    def test_format_heritage_site_data_archaeological(self, test_archaeological_heritage_site, test_account_card):
        """Проверка форматирования для archaeological heritage site"""
        site = test_archaeological_heritage_site
        site.account_card = test_account_card
        site.save()

        config = {
            'name_field': 'doc_name',
            'view_url': 'archaeological_heritage_sites',
            'edit_url': 'archaeological_heritage_sites_edit',
            'delete_modal_id': 'delete_archaeological_heritage_site'
        }
        result = format_heritage_site_data(site, 'archaeological', config)
        # Ожидаемая длина: 6 специфичных + 15 из base_data = 21
        assert len(result) == 21
        # Проверяем, что первая ячейка содержит ссылку на account_card
        assert 'account_cards' in result[0]
        # Проверяем наличие кнопок
        assert 'Редактировать' in result[-1]
        assert 'Удалить' in result[-1]
        # Проверяем, что поле document преобразовано в ссылку (если есть)
        # result[2] может быть None, если нет документа
        assert result[2] is None or 'document' in result[2]
        # Проверяем is_excluded
        assert result[5] in ['Да', 'Нет']

    def test_format_heritage_site_data_identified(self, test_identified_heritage_site, test_account_card):
        """Проверка форматирования для identified heritage site"""
        site = test_identified_heritage_site
        site.account_card = test_account_card
        site.save()

        config = {
            'name_field': 'name',
            'view_url': 'identified_archaeological_heritage_sites',
            'edit_url': 'identified_archaeological_heritage_sites_edit',
            'delete_modal_id': 'delete_identified_site'
        }
        result = format_heritage_site_data(site, 'identified', config)
        assert len(result) == 21
        assert 'account_cards' in result[0]
        # Проверяем, что поле obj_info не пустое
        assert result[2] == 'Test Info'  # именно значение, а не подстрока

    def test_format_act_data(self, test_act):
        """Проверка форматирования акта"""
        config = {
            'view_url': 'acts',
            'edit_url': 'acts_edit',
            'delete_modal_id': 'delete_act'
        }
        result = format_act_data(test_act, config)
        # Ожидаемое количество колонок: 18 (согласно format_act_data)
        assert len(result) == 18
        # Проверяем, что name_number - ссылка
        assert 'href="/acts/' in result[3]
        # Проверяем наличие кнопок
        assert 'Редактировать' in result[-1]
        assert 'Удалить' in result[-1]
        # Проверяем владельца
        assert test_act.user.username in result[12]

    def test_format_scientific_report_data(self, test_scientific_report):
        """Проверка форматирования научного отчёта"""
        config = {
            'view_url': 'scientific_reports',
            'edit_url': 'scientific_reports_edit',
            'delete_modal_id': 'delete_scientific_report'
        }
        result = format_scientific_report_data(test_scientific_report, config)
        assert len(result) == 11
        assert 'href="/scientific_reports/' in result[0]
        assert 'Редактировать' in result[-1]
        assert 'Удалить' in result[-1]

    def test_format_tech_report_data(self, test_tech_report):
        """Проверка форматирования тех. отчёта"""
        config = {
            'view_url': 'tech_reports',
            'edit_url': 'tech_reports_edit',
            'delete_modal_id': 'delete_tech_report'
        }
        result = format_tech_report_data(test_tech_report, config)
        assert len(result) == 11
        assert 'href="/tech_reports/' in result[0]

    def test_format_open_list_data(self, test_open_list):
        """Проверка форматирования открытого листа"""
        config = {
            'view_url': 'open_lists',
            'edit_url': 'open_lists_edit',
            'delete_modal_id': 'delete_open_list'
        }
        result = format_open_list_data(test_open_list, config)
        assert len(result) == 12
        assert 'href="/open_lists/' in result[0]

    def test_format_account_card_data(self, test_account_card):
        """Проверка форматирования учётной карты"""
        config = {
            'view_url': 'account_cards',
            'edit_url': 'account_cards_edit',
            'delete_modal_id': 'delete_account_card'
        }
        result = format_account_card_data(test_account_card, config)
        assert len(result) == 16
        assert 'href="/account_cards/' in result[0]

    def test_format_commercial_offer_data(self, test_commercial_offer):
        """Проверка форматирования коммерческого предложения"""
        config = {
            'view_url': 'map/commercial_offer',
            'edit_url': 'commercial_offers_edit',
            'delete_modal_id': 'delete_commercial_offer'
        }
        result = format_commercial_offer_data(test_commercial_offer, config)
        assert len(result) == 6
        # Проверяем, что есть ссылка на исходный документ (source добавлен в фикстуре)
        assert 'href="/' in result[0]
        # Проверяем кнопку просмотра координат
        assert 'Просмотр' in result[4]
        # Проверяем кнопки редактирования и удаления
        assert 'Редактировать' in result[5]
        assert 'Удалить' in result[5]

    def test_format_geo_object_data(self, test_geo_object):
        """Проверка форматирования географического объекта"""
        config = {
            'view_url': 'map/geo_object',
            'edit_url': 'geo_objects_edit',
            'delete_modal_id': 'delete_geo_object'
        }
        result = format_geo_object_data(test_geo_object, config)
        assert len(result) == 6
        assert 'href="/' in result[0]
        assert 'Просмотр' in result[4]
        assert 'Редактировать' in result[5]

    # ---------------------- Обёртки (wrapper functions) ----------------------

    @patch('agregator.views.datatable_views.universal_datatable')
    def test_archaeological_heritage_sites_datatable(self, mock_universal):
        from agregator.views.datatable_views import archaeological_heritage_sites_datatable
        request = MagicMock()
        archaeological_heritage_sites_datatable(request)
        mock_universal.assert_called_once_with(request, 'archaeological')

    @patch('agregator.views.datatable_views.universal_datatable')
    def test_identified_archaeological_heritage_sites_datatable(self, mock_universal):
        from agregator.views.datatable_views import identified_archaeological_heritage_sites_datatable
        request = MagicMock()
        identified_archaeological_heritage_sites_datatable(request)
        mock_universal.assert_called_once_with(request, 'identified')

    @patch('agregator.views.datatable_views.universal_datatable')
    def test_acts_datatable(self, mock_universal):
        from agregator.views.datatable_views import acts_datatable
        request = MagicMock()
        acts_datatable(request)
        mock_universal.assert_called_once_with(request, 'acts')

    @patch('agregator.views.datatable_views.universal_datatable')
    def test_scientific_reports_datatable(self, mock_universal):
        from agregator.views.datatable_views import scientific_reports_datatable
        request = MagicMock()
        scientific_reports_datatable(request)
        mock_universal.assert_called_once_with(request, 'scientific_reports')

    @patch('agregator.views.datatable_views.universal_datatable')
    def test_tech_reports_datatable(self, mock_universal):
        from agregator.views.datatable_views import tech_reports_datatable
        request = MagicMock()
        tech_reports_datatable(request)
        mock_universal.assert_called_once_with(request, 'tech_reports')

    @patch('agregator.views.datatable_views.universal_datatable')
    def test_open_lists_datatable(self, mock_universal):
        from agregator.views.datatable_views import open_lists_datatable
        request = MagicMock()
        open_lists_datatable(request)
        mock_universal.assert_called_once_with(request, 'open_lists')

    @patch('agregator.views.datatable_views.universal_datatable')
    def test_account_cards_datatable(self, mock_universal):
        from agregator.views.datatable_views import account_cards_datatable
        request = MagicMock()
        account_cards_datatable(request)
        mock_universal.assert_called_once_with(request, 'account_cards')
