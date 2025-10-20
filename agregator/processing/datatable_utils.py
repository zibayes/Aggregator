from django.db.models import Q
from django.http import JsonResponse
import json
import sys


class DataTableServerSide:
    def __init__(self, request, queryset, columns_config):
        self.request = request
        self.queryset = queryset
        self.columns_config = columns_config

    def get_parameters(self):
        """Извлекает параметры от DataTables из POST данных"""
        if self.request.method == 'POST':
            data = self.request.POST
        else:
            data = self.request.GET

        draw = int(data.get('draw', 1))
        start = int(data.get('start', 0))
        length = int(data.get('length', 25))
        search_value = data.get('search[value]', '')

        # Параметры сортировки
        order_column_index = data.get('order[0][column]', '0')
        order_direction = data.get('order[0][dir]', 'asc')

        # Параметры поиска по колонкам
        column_search = {}
        for key, value in data.items():
            if key.startswith('columns[') and key.endswith('][search][value]'):
                col_index = key.split('[')[1].split(']')[0]
                column_search[col_index] = value

        # Кастомные фильтры
        custom_search = {}
        custom_search_json = data.get('custom_search', '')
        if custom_search_json:
            try:
                custom_search = json.loads(custom_search_json)
            except:
                pass

        return {
            'draw': draw,
            'start': start,
            'length': length,
            'search_value': search_value,
            'order_column_index': order_column_index,
            'order_direction': order_direction,
            'column_search': column_search,
            'custom_search': custom_search
        }

    def apply_global_search(self, queryset, search_value):
        """Применяет глобальный поиск"""
        if not search_value:
            return queryset

        search_filters = Q()
        for column in self.columns_config:
            if column.get('searchable', True):
                field_name = column['field']
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

    def apply_custom_search(self, queryset, custom_search):
        """Применяет кастомные фильтры"""
        print(f"=== APPLY CUSTOM SEARCH DEBUG ===", file=sys.stderr)
        print(f"Initial queryset count: {queryset.count()}", file=sys.stderr)
        print(f"Custom search params: {custom_search}", file=sys.stderr)

        if not custom_search:
            print("No custom search params, returning original queryset", file=sys.stderr)
            return queryset

        # ФИЛЬТРАЦИЯ ПО ХРАНИЛИЩУ - ВАЖНО!
        storage_type = custom_search.get('storage_type')
        print(f"STORAGE TYPE: {storage_type}", file=sys.stderr)

        if hasattr(queryset.model, 'is_public'):
            if storage_type == 'private':
                print("🔒 PRIVATE STORAGE: Filtering for current user only", file=sys.stderr)
                if hasattr(self.request, 'user') and self.request.user.is_authenticated:
                    print(f"User: {self.request.user}, ID: {self.request.user.id}", file=sys.stderr)
                    # Для моделей с прямым полем user (акты)
                    if hasattr(queryset.model, 'user'):
                        print(f"Model has 'user' field, filtering by user={self.request.user}", file=sys.stderr)
                        queryset = queryset.filter(user=self.request.user, is_public=False)
                        print(f"After user filter: {queryset.count()} records", file=sys.stderr)
                    else:
                        print("❌ Model doesn't have 'user' or 'account_card' field - CANNOT FILTER BY USER",
                              file=sys.stderr)
                else:
                    print("❌ User is not authenticated - CANNOT FILTER BY USER", file=sys.stderr)
            elif storage_type == 'public':
                print("🔓 PUBLIC STORAGE: Showing all public records", file=sys.stderr)
                # Для публичного хранилища применяем фильтрацию по типу хранилища
                queryset = queryset.filter(is_public=True)
                print("No user filter applied for public storage", file=sys.stderr)
            else:
                print(f"❓ UNKNOWN STORAGE TYPE: {storage_type}", file=sys.stderr)

        print(f"Queryset count after storage filter: {queryset.count()}", file=sys.stderr)

        # Фильтры для научных отчетов
        if custom_search.get('name'):
            queryset = queryset.filter(name__icontains=custom_search['name'])
        if custom_search.get('organization'):
            queryset = queryset.filter(organization__icontains=custom_search['organization'])
        if custom_search.get('author'):
            queryset = queryset.filter(author__icontains=custom_search['author'])
        if custom_search.get('writing_date'):
            queryset = queryset.filter(writing_date__icontains=custom_search['writing_date'])
        if custom_search.get('upload_source'):
            queryset = queryset.filter(upload_source__icontains=custom_search['upload_source'])

        # Фильтры по актам
        if custom_search.get('year'):
            queryset = queryset.filter(year__icontains=custom_search['year'])
        if custom_search.get('finish_date'):
            queryset = queryset.filter(finish_date__icontains=custom_search['finish_date'])
        if custom_search.get('type'):
            queryset = queryset.filter(type__icontains=custom_search['type'])
        if custom_search.get('name_number'):
            queryset = queryset.filter(name_number__icontains=custom_search['name_number'])
        if custom_search.get('place'):
            queryset = queryset.filter(place__icontains=custom_search['place'])
        if custom_search.get('customer'):
            queryset = queryset.filter(customer__icontains=custom_search['customer'])
        if custom_search.get('area'):
            queryset = queryset.filter(area__icontains=custom_search['area'])
        if custom_search.get('expert'):
            queryset = queryset.filter(expert__icontains=custom_search['expert'])
        if custom_search.get('executioner'):
            queryset = queryset.filter(executioner__icontains=custom_search['executioner'])
        if custom_search.get('open_list'):
            queryset = queryset.filter(open_list__icontains=custom_search['open_list'])
        if custom_search.get('conclusion'):
            queryset = queryset.filter(conclusion__icontains=custom_search['conclusion'])
        if custom_search.get('border_objects'):
            queryset = queryset.filter(border_objects__icontains=custom_search['border_objects'])
        if custom_search.get('owner'):
            queryset = queryset.filter(user__username__icontains=custom_search['owner'])
        if custom_search.get('source'):
            queryset = queryset.filter(upload_source__icontains=custom_search['source'])
        if custom_search.get('date_uploaded'):
            queryset = queryset.filter(date_uploaded__icontains=custom_search['date_uploaded'])

        # Применяем текстовые фильтры
        if custom_search.get('doc_name'):
            queryset = queryset.filter(doc_name__icontains=custom_search['doc_name'])
            print(f"DEBUG: After doc_name filter: {queryset.count()} records", file=sys.stderr)
        if custom_search.get('district'):
            queryset = queryset.filter(district__icontains=custom_search['district'])
            print(f"DEBUG: After district filter: {queryset.count()} records", file=sys.stderr)
        if custom_search.get('document'):
            queryset = queryset.filter(document__icontains=custom_search['document'])
            print(f"DEBUG: After document filter: {queryset.count()} records", file=sys.stderr)
        if custom_search.get('register_num'):
            queryset = queryset.filter(register_num__icontains=custom_search['register_num'])
            print(f"DEBUG: After register_num filter: {queryset.count()} records", file=sys.stderr)

        # Фильтры по account_card
        if custom_search.get('creation_time'):
            queryset = queryset.filter(account_card__creation_time__icontains=custom_search['creation_time'])
            print(f"DEBUG: After creation_time filter: {queryset.count()} records", file=sys.stderr)
        if custom_search.get('address'):
            queryset = queryset.filter(account_card__address__icontains=custom_search['address'])
            print(f"DEBUG: After address filter: {queryset.count()} records", file=sys.stderr)
        if custom_search.get('object_type'):
            queryset = queryset.filter(account_card__object_type__icontains=custom_search['object_type'])
            print(f"DEBUG: After object_type filter: {queryset.count()} records", file=sys.stderr)
        if custom_search.get('general_classification'):
            queryset = queryset.filter(
                account_card__general_classification__icontains=custom_search['general_classification'])
            print(f"DEBUG: After general_classification filter: {queryset.count()} records", file=sys.stderr)
        if custom_search.get('description'):
            queryset = queryset.filter(account_card__description__icontains=custom_search['description'])
            print(f"DEBUG: After description filter: {queryset.count()} records", file=sys.stderr)
        if custom_search.get('usage'):
            queryset = queryset.filter(account_card__usage__icontains=custom_search['usage'])
            print(f"DEBUG: After usage filter: {queryset.count()} records", file=sys.stderr)
        if custom_search.get('discovery_info'):
            queryset = queryset.filter(account_card__discovery_info__icontains=custom_search['discovery_info'])
            print(f"DEBUG: After discovery_info filter: {queryset.count()} records", file=sys.stderr)
        if custom_search.get('compiler'):
            queryset = queryset.filter(account_card__compiler__icontains=custom_search['compiler'])
            print(f"DEBUG: After compiler filter: {queryset.count()} records", file=sys.stderr)
        if custom_search.get('owner'):
            queryset = queryset.filter(account_card__user__username__icontains=custom_search['owner'])
            print(f"DEBUG: After owner filter: {queryset.count()} records", file=sys.stderr)

        # Специальные фильтры
        if custom_search.get('account_card_filter') == 'available':
            queryset = queryset.filter(account_card__isnull=False)
            print(f"DEBUG: After account_card available filter: {queryset.count()} records", file=sys.stderr)
        elif custom_search.get('account_card_filter') == 'not_available':
            queryset = queryset.filter(account_card__isnull=True)
            print(f"DEBUG: After account_card not_available filter: {queryset.count()} records", file=sys.stderr)

        if not custom_search.get('show_excluded', True):
            queryset = queryset.filter(is_excluded=False)
            print(f"DEBUG: After show_excluded filter: {queryset.count()} records", file=sys.stderr)

        print(f"=== FINAL QUERYSET COUNT: {queryset.count()} ===", file=sys.stderr)
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

        # ПРИНУДИТЕЛЬНАЯ ОТЛАДКА
        import sys
        print(f"=== DATATABLE DEBUG ===", file=sys.stderr)
        print(f"Total records in queryset: {self.queryset.count()}", file=sys.stderr)

        # Применяем фильтрацию и сортировку
        filtered_queryset = self.apply_global_search(self.queryset, params['search_value'])
        print(f"After global search: {filtered_queryset.count()}", file=sys.stderr)

        filtered_queryset = self.apply_column_search(filtered_queryset, params['column_search'])
        print(f"After column search: {filtered_queryset.count()}", file=sys.stderr)

        filtered_queryset = self.apply_custom_search(filtered_queryset, params['custom_search'])
        print(f"After custom search: {filtered_queryset.count()}", file=sys.stderr)

        filtered_queryset = self.apply_ordering(filtered_queryset, params['order_column_index'],
                                                params['order_direction'])

        # Получаем итоговые данные
        total_records = self.queryset.count()
        filtered_records = filtered_queryset.count()

        print(f"Final - Total: {total_records}, Filtered: {filtered_records}", file=sys.stderr)

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
