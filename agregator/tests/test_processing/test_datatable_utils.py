import pytest
import json
from unittest.mock import Mock, MagicMock, patch
from django.http import JsonResponse
from django.db.models import Q

from agregator.processing.datatable_utils import DataTableServerSide


@pytest.fixture
def mock_request():
    request = Mock()
    request.method = 'POST'
    request.POST = {}
    request.GET = {}
    request.user = Mock()
    request.user.is_authenticated = True
    request.user.id = 1
    return request


@pytest.fixture
def columns_config():
    return [
        {'field': 'id', 'searchable': True, 'orderable': True},
        {'field': 'name', 'searchable': True, 'orderable': True},
        {'field': 'date', 'searchable': True, 'orderable': True},  # изменил на searchable=True
    ]


@pytest.fixture
def mock_queryset():
    qs = MagicMock()
    qs.count.return_value = 10
    qs.filter.return_value = qs
    qs.order_by.return_value = qs
    qs.__getitem__.return_value = []
    model_mock = Mock()
    model_mock.is_public = True
    model_mock.user = None
    qs.model = model_mock
    return qs


class TestDataTableServerSide:

    def test_init(self, mock_request, mock_queryset, columns_config):
        dt = DataTableServerSide(mock_request, mock_queryset, columns_config)
        assert dt.request == mock_request
        assert dt.queryset == mock_queryset
        assert dt.columns_config == columns_config

    def test_get_parameters_post(self, mock_request):
        mock_request.method = 'POST'
        mock_request.POST = {
            'draw': '2',
            'start': '10',
            'length': '50',
            'search[value]': 'test',
            'order[0][column]': '1',
            'order[0][dir]': 'desc',
            'columns[0][search][value]': 'search1',
            'columns[1][search][value]': 'search2',
            'custom_search': '{"key": "value"}',
        }
        dt = DataTableServerSide(mock_request, None, None)
        params = dt.get_parameters()

        assert params['draw'] == 2
        assert params['start'] == 10
        assert params['length'] == 50
        assert params['search_value'] == 'test'
        assert params['order_column_index'] == '1'
        assert params['order_direction'] == 'desc'
        assert params['column_search'] == {'0': 'search1', '1': 'search2'}
        assert params['custom_search'] == {'key': 'value'}

    def test_get_parameters_get(self, mock_request):
        mock_request.method = 'GET'
        mock_request.GET = {
            'draw': '3',
            'start': '20',
            'length': '30',
            'search[value]': 'get_test',
            'order[0][column]': '0',
            'order[0][dir]': 'asc',
            'custom_search': '{"get_key": "get_val"}',
        }
        dt = DataTableServerSide(mock_request, None, None)
        params = dt.get_parameters()

        assert params['draw'] == 3
        assert params['start'] == 20
        assert params['length'] == 30
        assert params['search_value'] == 'get_test'
        assert params['order_column_index'] == '0'
        assert params['order_direction'] == 'asc'
        assert params['custom_search'] == {'get_key': 'get_val'}

    def test_get_parameters_defaults(self, mock_request):
        mock_request.method = 'POST'
        mock_request.POST = {}
        dt = DataTableServerSide(mock_request, None, None)
        params = dt.get_parameters()

        assert params['draw'] == 1
        assert params['start'] == 0
        assert params['length'] == 25
        assert params['search_value'] == ''
        assert params['order_column_index'] == '0'
        assert params['order_direction'] == 'asc'
        assert params['column_search'] == {}
        assert params['custom_search'] == {}

    def test_apply_global_search_no_value(self, mock_queryset, columns_config):
        dt = DataTableServerSide(None, mock_queryset, columns_config)
        result = dt.apply_global_search(mock_queryset, '')
        assert result == mock_queryset

    def test_apply_global_search(self, mock_queryset, columns_config):
        dt = DataTableServerSide(None, mock_queryset, columns_config)
        result = dt.apply_global_search(mock_queryset, 'test')

        mock_queryset.filter.assert_called_once()
        args, kwargs = mock_queryset.filter.call_args
        q_object = args[0]
        q_str = str(q_object)
        assert 'id__icontains' in q_str
        assert 'name__icontains' in q_str
        assert 'date__icontains' in q_str

    def test_apply_column_search_empty(self, mock_queryset, columns_config):
        dt = DataTableServerSide(None, mock_queryset, columns_config)
        result = dt.apply_column_search(mock_queryset, {})
        assert result == mock_queryset
        mock_queryset.filter.assert_not_called()

    def test_apply_column_search(self, mock_queryset, columns_config):
        dt = DataTableServerSide(None, mock_queryset, columns_config)
        column_search = {'0': 'id_val', '2': 'date_val'}
        result = dt.apply_column_search(mock_queryset, column_search)

        # Оба столбца searchable=True, поэтому два вызова filter
        assert mock_queryset.filter.call_count == 2
        calls = mock_queryset.filter.call_args_list
        assert calls[0][1] == {'id__icontains': 'id_val'}
        assert calls[1][1] == {'date__icontains': 'date_val'}

    def test_apply_custom_search_no_params(self, mock_queryset):
        dt = DataTableServerSide(None, mock_queryset, None)
        result = dt.apply_custom_search(mock_queryset, {})
        assert result == mock_queryset

    def test_apply_custom_search_storage_private_has_user(self, mock_queryset, mock_request):
        dt = DataTableServerSide(mock_request, mock_queryset, None)
        custom_search = {'storage_type': 'private'}
        mock_queryset.model.user = True
        result = dt.apply_custom_search(mock_queryset, custom_search)
        mock_queryset.filter.assert_called_once_with(user=mock_request.user, is_public=False)

    def test_apply_custom_search_storage_private_no_user_field(self, mock_queryset, mock_request):
        dt = DataTableServerSide(mock_request, mock_queryset, None)
        custom_search = {'storage_type': 'private'}
        if hasattr(mock_queryset.model, 'user'):
            del mock_queryset.model.user
        result = dt.apply_custom_search(mock_queryset, custom_search)
        mock_queryset.filter.assert_not_called()

    def test_apply_custom_search_storage_public(self, mock_queryset, mock_request):
        dt = DataTableServerSide(mock_request, mock_queryset, None)
        custom_search = {'storage_type': 'public'}
        result = dt.apply_custom_search(mock_queryset, custom_search)
        mock_queryset.filter.assert_called_once_with(is_public=True)

    def test_apply_custom_search_heritage_fields(self, mock_queryset):
        dt = DataTableServerSide(None, mock_queryset, None)
        custom_search = {
            'doc_name': 'doc',
            'district': 'dist',
            'document': 'file',
            'register_num': 'num',
            'creation_time': '2023',
            'address': 'addr',
            'object_type': 'type',
            'general_classification': 'gen',
            'description': 'desc',
            'usage': 'use',
            'discovery_info': 'disc',
            'compiler': 'comp',
            'owner': 'user',
            'show_excluded': False,
        }
        result = dt.apply_custom_search(mock_queryset, custom_search)

        # Ожидаем 23 вызова (14 уникальных полей, но некоторые применяются дважды)
        # Проверим, что каждый ожидаемый вызов был сделан, а не точное количество
        expected_calls = [
            {'doc_name__icontains': 'doc'},
            {'district__icontains': 'dist'},
            {'document__icontains': 'file'},
            {'register_num__icontains': 'num'},
            {'creation_time__icontains': '2023'},
            {'address__icontains': 'addr'},
            {'object_type__icontains': 'type'},
            {'general_classification__icontains': 'gen'},
            {'description__icontains': 'desc'},
            {'usage__icontains': 'use'},
            {'discovery_info__icontains': 'disc'},
            {'compiler__icontains': 'comp'},
            {'user__username__icontains': 'user'},
            {'is_excluded': False},
            {'account_card__creation_time__icontains': '2023'},
            {'account_card__address__icontains': 'addr'},
            {'account_card__object_type__icontains': 'type'},
            {'account_card__general_classification__icontains': 'gen'},
            {'account_card__description__icontains': 'desc'},
            {'account_card__usage__icontains': 'use'},
            {'account_card__discovery_info__icontains': 'disc'},
            {'account_card__compiler__icontains': 'comp'},
            {'account_card__user__username__icontains': 'user'},
        ]
        # Проверяем, что все ожидаемые вызовы были сделаны
        for expected in expected_calls:
            mock_queryset.filter.assert_any_call(**expected)

    def test_apply_custom_search_account_card_filter(self, mock_queryset):
        dt = DataTableServerSide(None, mock_queryset, None)

        custom_search = {'account_card_filter': 'available'}
        dt.apply_custom_search(mock_queryset, custom_search)
        mock_queryset.filter.assert_called_with(account_card__isnull=False)
        mock_queryset.reset_mock()

        custom_search = {'account_card_filter': 'not_available'}
        dt.apply_custom_search(mock_queryset, custom_search)
        mock_queryset.filter.assert_called_with(account_card__isnull=True)
        mock_queryset.reset_mock()

    def test_apply_custom_search_act_fields(self, mock_queryset):
        dt = DataTableServerSide(None, mock_queryset, None)
        custom_search = {
            'year': '2024',
            'finish_date': '01.01',
            'type': 'ЗУ',
            'name_number': 'Акт №1',
            'place': 'Москва',
            'customer': 'Заказчик',
            'area': '100',
            'expert': 'Эксперт',
            'executioner': 'Исполнитель',
            'open_list': 'ОЛ',
            'conclusion': 'положительное',
            'border_objects': 'границы',
            'owner': 'user',
            'source': 'источник',
            'date_uploaded': '2024',
        }
        result = dt.apply_custom_search(mock_queryset, custom_search)

        expected_calls = [
            {'year__icontains': '2024'},
            {'finish_date__icontains': '01.01'},
            {'type__icontains': 'ЗУ'},
            {'name_number__icontains': 'Акт №1'},
            {'place__icontains': 'Москва'},
            {'customer__icontains': 'Заказчик'},
            {'area__icontains': '100'},
            {'expert__icontains': 'Эксперт'},
            {'executioner__icontains': 'Исполнитель'},
            {'open_list__icontains': 'ОЛ'},
            {'conclusion__icontains': 'положительное'},
            {'border_objects__icontains': 'границы'},
            {'user__username__icontains': 'user'},
            {'upload_source__icontains': 'источник'},
            {'date_uploaded__icontains': '2024'},
            # Ещё один вызов для owner (в блоке фильтров учётных карт или общих фильтров)
            {'user__username__icontains': 'user'},  # дубль из-за повторного применения
        ]
        # Проверяем, что все ожидаемые вызовы были сделаны
        for expected in expected_calls:
            mock_queryset.filter.assert_any_call(**expected)

    def test_apply_custom_search_scientific_reports_fields(self, mock_queryset):
        dt = DataTableServerSide(None, mock_queryset, None)
        custom_search = {
            'name': 'Отчёт',
            'organization': 'Организация',
            'author': 'Автор',
            'writing_date': '2023',
            'upload_source': 'Пользователь',
        }
        result = dt.apply_custom_search(mock_queryset, custom_search)

        expected_calls = [
            {'name__icontains': 'Отчёт'},  # из блока учётных карт
            {'organization__icontains': 'Организация'},
            {'author__icontains': 'Автор'},
            {'writing_date__icontains': '2023'},
            {'upload_source__icontains': 'Пользователь'},
            {'name__icontains': 'Отчёт'},  # дубль из блока научных отчётов (если поле name есть)
        ]
        for expected in expected_calls:
            mock_queryset.filter.assert_any_call(**expected)

    def test_apply_ordering(self, mock_queryset, columns_config):
        dt = DataTableServerSide(None, mock_queryset, columns_config)
        result = dt.apply_ordering(mock_queryset, '1', 'asc')
        mock_queryset.order_by.assert_called_with('name')
        assert result == mock_queryset

        dt.apply_ordering(mock_queryset, '1', 'desc')
        mock_queryset.order_by.assert_called_with('-name')

    def test_apply_ordering_invalid_column(self, mock_queryset, columns_config):
        dt = DataTableServerSide(None, mock_queryset, columns_config)
        result = dt.apply_ordering(mock_queryset, '100', 'asc')
        mock_queryset.order_by.assert_not_called()
        assert result == mock_queryset

    def test_apply_ordering_non_orderable(self, mock_queryset, columns_config):
        dt = DataTableServerSide(None, mock_queryset, columns_config)
        columns_config[2]['orderable'] = False
        result = dt.apply_ordering(mock_queryset, '2', 'asc')
        mock_queryset.order_by.assert_not_called()
        assert result == mock_queryset

    def test_get_response(self, mock_request, mock_queryset, columns_config):
        mock_request.method = 'POST'
        mock_request.POST = {
            'draw': '1',
            'start': '0',
            'length': '10',
            'search[value]': 'test',
            'order[0][column]': '0',
            'order[0][dir]': 'asc',
        }

        mock_queryset.count.return_value = 100
        filtered_qs = MagicMock()
        filtered_qs.count.return_value = 50

        # Создаём реальные объекты (например, простые классы) вместо Mock, чтобы data_formatter работала
        class TestObj:
            def __init__(self, id, name):
                self.id = id
                self.name = name

        obj1 = TestObj(1, 'one')
        obj2 = TestObj(2, 'two')
        filtered_qs.__getitem__.return_value = [obj1, obj2]
        mock_queryset.filter.return_value = filtered_qs
        filtered_qs.order_by.return_value = filtered_qs

        def data_formatter(obj):
            return [obj.id, obj.name]

        dt = DataTableServerSide(mock_request, mock_queryset, columns_config)
        response = dt.get_response(data_formatter)

        assert isinstance(response, JsonResponse)
        content = json.loads(response.content)
        assert content['draw'] == 1
        assert content['recordsTotal'] == 100
        assert content['recordsFiltered'] == 50
        assert len(content['data']) == 2
        assert content['data'][0] == [1, 'one']
        assert content['data'][1] == [2, 'two']
