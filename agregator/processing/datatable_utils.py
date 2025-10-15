from django.db.models import Q
from django.http import JsonResponse
import json


class DataTableServerSide:
    def __init__(self, request, queryset, columns_config):
        self.request = request
        self.queryset = queryset
        self.columns_config = columns_config  # { 'field': 'name', 'searchable': True, 'orderable': True }

    def get_parameters(self):
        """Извлекает параметры от DataTables"""
        draw = int(self.request.GET.get('draw', 1))
        start = int(self.request.GET.get('start', 0))
        length = int(self.request.GET.get('length', 25))
        search_value = self.request.GET.get('search[value]', '')

        # Параметры сортировки
        order_column_index = self.request.GET.get('order[0][column]', '0')
        order_direction = self.request.GET.get('order[0][dir]', 'asc')

        # Параметры поиска по колонкам
        column_search = {}
        for key, value in self.request.GET.items():
            if key.startswith('columns[') and key.endswith('][search][value]'):
                col_index = key.split('[')[1].split(']')[0]
                column_search[col_index] = value

        return {
            'draw': draw,
            'start': start,
            'length': length,
            'search_value': search_value,
            'order_column_index': order_column_index,
            'order_direction': order_direction,
            'column_search': column_search
        }

    def apply_global_search(self, queryset, search_value):
        """Применяет глобальный поиск"""
        if not search_value:
            return queryset

        search_filters = Q()
        for column in self.columns_config:
            if column.get('searchable', True):
                field_name = column['field']
                # Для связанных полей
                if '__' in field_name:
                    search_filters |= Q(**{f"{field_name}__icontains": search_value})
                else:
                    search_filters |= Q(**{f"{field_name}__icontains": search_value})

        return queryset.filter(search_filters)

    def apply_column_search(self, queryset, column_search):
        """Применяет поиск по конкретным колонкам"""
        for col_index, search_value in column_search.items():
            if search_value and col_index.isdigit():
                col_index = int(col_index)
                if col_index < len(self.columns_config):
                    column_config = self.columns_config[col_index]
                    if column_config.get('searchable', True) and search_value:
                        field_name = column_config['field']
                        queryset = queryset.filter(**{f"{field_name}__icontains": search_value})
        return queryset

    def apply_ordering(self, queryset, order_column_index, order_direction):
        """Применяет сортировку"""
        if order_column_index.isdigit():
            col_index = int(order_column_index)
            if col_index < len(self.columns_config):
                column_config = self.columns_config[col_index]
                if column_config.get('orderable', True):
                    field_name = column_config['field']
                    if order_direction == 'desc':
                        field_name = f"-{field_name}"
                    return queryset.order_by(field_name)
        return queryset

    def get_response(self, data_formatter):
        """Генерирует ответ для DataTables"""
        params = self.get_parameters()

        # Применяем фильтрацию и сортировку
        filtered_queryset = self.apply_global_search(self.queryset, params['search_value'])
        filtered_queryset = self.apply_column_search(filtered_queryset, params['column_search'])
        filtered_queryset = self.apply_ordering(filtered_queryset, params['order_column_index'],
                                                params['order_direction'])

        # Получаем итоговые данные
        total_records = self.queryset.count()
        filtered_records = filtered_queryset.count()

        # Пагинация
        paginated_queryset = filtered_queryset[params['start']:params['start'] + params['length']]

        # Форматируем данные
        data = [data_formatter(obj) for obj in paginated_queryset]

        return JsonResponse({
            'draw': params['draw'],
            'recordsTotal': total_records,
            'recordsFiltered': filtered_records,
            'data': data
        })
