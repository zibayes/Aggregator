from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from agregator.models import ( \
    ArchaeologicalHeritageSite, IdentifiedArchaeologicalHeritageSite
)
from agregator.processing.datatable_utils import DataTableServerSide


@csrf_exempt
def universal_heritage_sites_datatable(request, site_type):
    """
    Универсальная Datatable для всех типов археологических памятников
    """
    print(f"=== UNIVERSAL DATATABLES API CALLED ===")
    print(f"Site type: {site_type}, Method: {request.method}, User: {request.user}")

    # Конфигурация для разных типов памятников
    CONFIG = {
        'archaeological': {
            'model': 'ArchaeologicalHeritageSite',
            'columns': [
                {'field': 'doc_name', 'searchable': True, 'orderable': True},
                {'field': 'district', 'searchable': True, 'orderable': True},
                {'field': 'document', 'searchable': True, 'orderable': True},
                {'field': 'register_num', 'searchable': True, 'orderable': True},
                {'field': 'date_uploaded', 'searchable': True, 'orderable': True},
                {'field': 'is_excluded', 'searchable': True, 'orderable': True},
                {'field': 'account_card__creation_time', 'searchable': True, 'orderable': True},
                {'field': 'account_card__address', 'searchable': True, 'orderable': True},
                {'field': 'account_card__object_type', 'searchable': True, 'orderable': True},
                {'field': 'account_card__general_classification', 'searchable': True, 'orderable': True},
                {'field': 'account_card__description', 'searchable': True, 'orderable': True},
                {'field': 'account_card__usage', 'searchable': True, 'orderable': True},
                {'field': 'account_card__discovery_info', 'searchable': True, 'orderable': True},
                {'field': 'account_card__compiler', 'searchable': True, 'orderable': True},
                {'field': 'account_card__compile_date', 'searchable': True, 'orderable': True},
                {'field': 'account_card__user__username', 'searchable': True, 'orderable': True},
                {'field': 'account_card__date_uploaded', 'searchable': True, 'orderable': True},
                {'field': 'account_card__upload_source', 'searchable': True, 'orderable': True},
            ],
            'name_field': 'doc_name',
            'edit_url': 'archaeological_heritage_sites_edit',
            'view_url': 'archaeological_heritage_sites',
            'delete_modal_id': 'delete_archaeological_heritage_site'
        },
        'identified': {
            'model': 'IdentifiedArchaeologicalHeritageSite',
            'columns': [
                {'field': 'name', 'searchable': True, 'orderable': True},
                {'field': 'address', 'searchable': True, 'orderable': True},
                {'field': 'obj_info', 'searchable': True, 'orderable': True},
                {'field': 'document', 'searchable': True, 'orderable': True},
                {'field': 'date_uploaded', 'searchable': True, 'orderable': True},
                {'field': 'is_excluded', 'searchable': True, 'orderable': True},
                {'field': 'account_card__creation_time', 'searchable': True, 'orderable': True},
                {'field': 'account_card__address', 'searchable': True, 'orderable': True},
                {'field': 'account_card__object_type', 'searchable': True, 'orderable': True},
                {'field': 'account_card__general_classification', 'searchable': True, 'orderable': True},
                {'field': 'account_card__description', 'searchable': True, 'orderable': True},
                {'field': 'account_card__usage', 'searchable': True, 'orderable': True},
                {'field': 'account_card__discovery_info', 'searchable': True, 'orderable': True},
                {'field': 'account_card__compiler', 'searchable': True, 'orderable': True},
                {'field': 'account_card__compile_date', 'searchable': True, 'orderable': True},
                {'field': 'account_card__user__username', 'searchable': True, 'orderable': True},
                {'field': 'account_card__date_uploaded', 'searchable': True, 'orderable': True},
                {'field': 'account_card__upload_source', 'searchable': True, 'orderable': True},
            ],
            'name_field': 'name',
            'edit_url': 'identified_archaeological_heritage_sites_edit',
            'view_url': 'identified_archaeological_heritage_sites',
            'delete_modal_id': 'delete_identified_site'
        }
    }

    if site_type not in CONFIG:
        return JsonResponse({'error': 'Unknown site type'}, status=400)

    config = CONFIG[site_type]

    if request.method == 'GET':
        # Тестовые данные для отладки
        return JsonResponse({
            'draw': 1,
            'recordsTotal': 100,
            'recordsFiltered': 100,
            'data': [
                [f'Тестовый {site_type} 1', 'Тест район', 'Тест документ', '123', '2024-01-01', 'Нет'] + [''] * 15,
                [f'Тестовый {site_type} 2', 'Тест район', 'Тест документ', '124', '2024-01-02', 'Нет'] + [''] * 15,
            ]
        })

    # Импортируем модели динамически
    from django.apps import apps
    Model = apps.get_model('agregator', config['model'])

    # Базовый queryset с оптимизацией
    queryset = Model.objects.select_related('account_card', 'account_card__user').all()

    def format_site_data(site):
        """Универсальная функция форматирования данных"""
        account_card = site.account_card

        # Наименование (разные поля для разных типов)
        name_value = getattr(site, config['name_field'])
        name_cell = name_value
        if account_card and hasattr(account_card, 'id'):
            name_cell = f'<a href="/account_cards/{account_card.id}" target="_blank">{name_value}</a>'

        # Документ
        document_cell = site.document
        if hasattr(site, 'document_source_dict') and site.document_source_dict:
            doc_path = site.document_source_dict[0].get('path', '')
            if doc_path:
                document_cell = f'<a href="/{doc_path}" target="_blank">{site.document}</a>'

        # Исключён
        is_excluded_cell = 'Да' if site.is_excluded else 'Нет'

        # Данные из account_card
        card_data = {
            'creation_time': account_card.creation_time if account_card else '',
            'address': account_card.address if account_card else '',
            'object_type': account_card.object_type if account_card else '',
            'general_classification': account_card.general_classification if account_card else '',
            'description': account_card.description if account_card else '',
            'usage': account_card.usage if account_card else '',
            'discovery_info': account_card.discovery_info if account_card else '',
            'compiler': account_card.compiler if account_card else '',
            'compile_date': account_card.compile_date if account_card else '',
        }

        # Владелец документа
        owner_cell = ''
        if account_card and account_card.user:
            avatar_url = account_card.user.avatar.url if account_card.user.avatar else '/static/images/default-avatar.png'
            owner_cell = f'''
            <a href="/users/{account_card.user.id}" target="_blank">
                <img src="{avatar_url}" class="rounded-circle" height="25" width="25" style="object-fit: cover;" alt=""/>
                {account_card.user.username}
            </a>
            '''

        # Дата загрузки учётной карты
        card_date_uploaded = ''
        if account_card and account_card.date_uploaded:
            card_date_uploaded = account_card.date_uploaded.strftime('%Y-%m-%d %H:%M')

        # Источник
        source_cell = ''
        if account_card and hasattr(account_card, 'upload_source_dict'):
            source_dict = account_card.upload_source_dict
            if source_dict and source_dict.get('link'):
                source_cell = f'<a href="{source_dict["link"]}" target="_blank">{source_dict["source"]}</a>'
            elif source_dict:
                source_cell = source_dict.get('source', '')

        # Формализованный документ
        formalized_doc_cell = f'''
        <a href="/{config["view_url"]}/{site.id}/">
            <button type="button" class="btn btn-primary" style="border-radius: 12px; margin-bottom: 8px;" {'' if getattr(site, 'coordinates_dict', True) else 'disabled'}>
                Просмотр памятника
            </button>
        </a>
        '''

        if account_card:
            formalized_doc_cell += f'''
            <a href="/account_cards/{account_card.id}/">
                <button type="button" class="btn btn-secondary" style="border-radius: 12px; margin-bottom: 8px;">
                    Просмотр учётной карты
                </button>
            </a>
            '''

        # Исходный документ
        original_doc_cell = ''
        if account_card and account_card.source:
            original_doc_cell = f'<a href="/{account_card.source}" target="_blank">{account_card.origin_filename}</a>'

        # Кнопки действий
        actions_cell = f'''
        <td>
            <a href="/{config["edit_url"]}/{site.id}/" class="btn btn-primary" style="border-radius: 12px; margin-right: 10px;">
                Редактировать
            </a>
            <button type="button" class="btn btn-danger" style="margin-top: 8px;" 
                    onclick="openDeleteModal({site.id}, '{name_value.replace("'", "\\'")}', '{config["delete_modal_id"]}')">
                Удалить
            </button>
        </td>
        '''

        # БАЗОВЫЕ ДАННЫЕ (одинаковые для всех типов)
        base_data = [
            card_data['creation_time'],  # 0: Время создания
            card_data['address'],  # 1: Адрес учётной карты
            card_data['object_type'],  # 2: Вид объекта
            card_data['general_classification'],  # 3: Общая видовая принадлежность
            card_data['description'],  # 4: Описание
            card_data['usage'],  # 5: Использование
            card_data['discovery_info'],  # 6: Сведения о выявлении
            card_data['compiler'],  # 7: Составитель
            card_data['compile_date'],  # 8: Дата составления
            owner_cell,  # 9: Владелец документа
            card_date_uploaded,  # 10: Дата загрузки учётной карты
            source_cell,  # 11: Источник
            formalized_doc_cell,  # 12: Формализованный документ
            original_doc_cell,  # 13: Исходный документ
            actions_cell  # 14: Действия
        ]

        # ФОРМИРУЕМ ПОЛНЫЙ СПИСОКО КОЛОНОК В ПРАВИЛЬНОМ ПОРЯДКЕ
        if site_type == 'archaeological':
            # Правильный порядок для archaeological:
            # 0: Наименование, 1: Район, 2: Документ, 3: Рег.номер, 4: Дата памятника, 5: Исключён, затем base_data
            return [
                name_cell,  # 0: Наименование
                site.district,  # 1: Район
                document_cell,  # 2: Документ
                site.register_num,  # 3: Регистрационный номер
                site.date_uploaded.strftime('%Y-%m-%d %H:%M') if site.date_uploaded else '',
                # 4: Дата загрузки памятника
                is_excluded_cell,  # 5: Исключён
            ] + base_data  # 6-20: остальные колонки

        else:  # identified
            # Правильный порядок для identified:
            # 0: Наименование, 1: Адрес, 2: Информация, 3: Документ, 4: Дата памятника, 5: Исключён, затем base_data
            return [
                name_cell,  # 0: Наименование
                site.address,  # 1: Адрес
                site.obj_info,  # 2: Информация
                document_cell,  # 3: Документ
                site.date_uploaded.strftime('%Y-%m-%d %H:%M') if site.date_uploaded else '',
                # 4: Дата загрузки памятника
                is_excluded_cell,  # 5: Исключён
            ] + base_data  # 6-20: остальные колонки

    datatable = DataTableServerSide(request, queryset, config['columns'])
    return datatable.get_response(format_site_data)
