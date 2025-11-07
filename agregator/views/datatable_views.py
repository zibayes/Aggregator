from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.apps import apps
from agregator.processing.datatable_utils import DataTableServerSide
import json
import html


@csrf_exempt
def universal_datatable(request, register_type):
    """
    Универсальная Datatable для всех типов реестров
    """
    try:
        print(f"=== UNIVERSAL DATATABLE CALLED ===")
        print(f"Register type: {register_type}, Method: {request.method}, User: {request.user}")

        # Конфигурация для всех типов реестров
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
            },
            'acts': {
                'model': 'Act',
                'columns': [
                    {'field': 'year', 'searchable': True, 'orderable': True},
                    {'field': 'finish_date', 'searchable': True, 'orderable': True},
                    {'field': 'type', 'searchable': True, 'orderable': True},
                    {'field': 'name_number', 'searchable': True, 'orderable': True},
                    {'field': 'place', 'searchable': True, 'orderable': True},
                    {'field': 'customer', 'searchable': True, 'orderable': True},
                    {'field': 'area', 'searchable': True, 'orderable': True},
                    {'field': 'expert', 'searchable': True, 'orderable': True},
                    {'field': 'executioner', 'searchable': True, 'orderable': True},
                    {'field': 'open_list', 'searchable': True, 'orderable': True},
                    {'field': 'conclusion', 'searchable': True, 'orderable': True},
                    {'field': 'border_objects', 'searchable': True, 'orderable': True},
                    {'field': 'user__username', 'searchable': True, 'orderable': True},
                    {'field': 'upload_source', 'searchable': True, 'orderable': True},
                    {'field': 'date_uploaded', 'searchable': True, 'orderable': True},
                ],
                'name_field': 'name_number',
                'edit_url': 'acts_edit',
                'view_url': 'acts',
                'delete_modal_id': 'delete_act'
            },
            'scientific_reports': {
                'model': 'ScientificReport',
                'columns': [
                    {'field': 'name', 'searchable': True, 'orderable': True},
                    {'field': 'organization', 'searchable': True, 'orderable': True},
                    {'field': 'author', 'searchable': True, 'orderable': True},
                    {'field': 'open_list', 'searchable': True, 'orderable': True},
                    {'field': 'writing_date', 'searchable': True, 'orderable': True},
                    {'field': 'user__username', 'searchable': True, 'orderable': True},
                    {'field': 'upload_source', 'searchable': True, 'orderable': True},
                    {'field': 'date_uploaded', 'searchable': True, 'orderable': True},
                ],
                'name_field': 'name',
                'edit_url': 'scientific_reports_edit',
                'view_url': 'scientific_reports',
                'delete_modal_id': 'delete_scientific_report'
            },
            'tech_reports': {
                'model': 'TechReport',
                'columns': [
                    {'field': 'name', 'searchable': True, 'orderable': True},
                    {'field': 'organization', 'searchable': True, 'orderable': True},
                    {'field': 'author', 'searchable': True, 'orderable': True},
                    {'field': 'open_list', 'searchable': True, 'orderable': True},
                    {'field': 'writing_date', 'searchable': True, 'orderable': True},
                    {'field': 'user__username', 'searchable': True, 'orderable': True},
                    {'field': 'upload_source', 'searchable': True, 'orderable': True},
                    {'field': 'date_uploaded', 'searchable': True, 'orderable': True},
                ],
                'name_field': 'name',
                'edit_url': 'tech_reports_edit',
                'view_url': 'tech_reports',
                'delete_modal_id': 'delete_tech_report'
            },
            'open_lists': {
                'model': 'OpenLists',
                'columns': [
                    {'field': 'number', 'searchable': True, 'orderable': True},
                    {'field': 'holder', 'searchable': True, 'orderable': True},
                    {'field': 'object', 'searchable': True, 'orderable': True},
                    {'field': 'works', 'searchable': True, 'orderable': True},
                    {'field': 'start_date', 'searchable': True, 'orderable': True},
                    {'field': 'end_date', 'searchable': True, 'orderable': True},
                    {'field': 'user__username', 'searchable': True, 'orderable': True},
                    {'field': 'upload_source', 'searchable': True, 'orderable': True},
                    {'field': 'date_uploaded', 'searchable': True, 'orderable': True},
                ],
                'name_field': 'number',
                'edit_url': 'open_lists_edit',
                'view_url': 'open_lists',
                'delete_modal_id': 'delete_open_list'
            },
            'account_cards': {
                'model': 'ObjectAccountCard',
                'columns': [
                    {'field': 'name', 'searchable': True, 'orderable': True},
                    {'field': 'creation_time', 'searchable': True, 'orderable': True},
                    {'field': 'address', 'searchable': True, 'orderable': True},
                    {'field': 'object_type', 'searchable': True, 'orderable': True},
                    {'field': 'general_classification', 'searchable': True, 'orderable': True},
                    {'field': 'description', 'searchable': True, 'orderable': True},
                    {'field': 'usage', 'searchable': True, 'orderable': True},
                    {'field': 'discovery_info', 'searchable': True, 'orderable': True},
                    {'field': 'compiler', 'searchable': True, 'orderable': True},
                    {'field': 'compile_date', 'searchable': True, 'orderable': True},
                    {'field': 'user__username', 'searchable': True, 'orderable': True},
                    {'field': 'date_uploaded', 'searchable': True, 'orderable': True},
                    {'field': 'upload_source', 'searchable': True, 'orderable': True},
                ],
                'name_field': 'name',
                'edit_url': 'account_cards_edit',
                'view_url': 'account_cards',
                'delete_modal_id': 'delete_account_card'
            },
            'commercial_offers': {
                'model': 'CommercialOffers',
                'columns': [
                    {'field': 'origin_filename', 'searchable': True, 'orderable': True},
                    {'field': 'upload_source', 'searchable': True, 'orderable': True},
                    {'field': 'user__username', 'searchable': True, 'orderable': True},
                    {'field': 'date_uploaded', 'searchable': True, 'orderable': True},
                    {'field': 'id', 'searchable': False, 'orderable': False},  # Для колонки "Координаты"
                    {'field': 'id', 'searchable': False, 'orderable': False},  # Для колонки "Редактирование"
                ],
                'name_field': 'origin_filename',
                'edit_url': 'commercial_offers_edit',
                'view_url': 'map/commercial_offer',
                'delete_modal_id': 'delete_commercial_offer'
            },
            'geo_objects': {
                'model': 'GeoObject',
                'columns': [
                    {'field': 'origin_filename', 'searchable': True, 'orderable': True},
                    {'field': 'upload_source', 'searchable': True, 'orderable': True},
                    {'field': 'user__username', 'searchable': True, 'orderable': True},
                    {'field': 'date_uploaded', 'searchable': True, 'orderable': True},
                    {'field': 'id', 'searchable': False, 'orderable': False},  # Для колонки "Координаты"
                    {'field': 'id', 'searchable': False, 'orderable': False},  # Для колонки "Редактирование"
                ],
                'name_field': 'origin_filename',
                'edit_url': 'geo_objects_edit',
                'view_url': 'map/geo_object',
                'delete_modal_id': 'delete_geo_object'
            },
        }

        if register_type not in CONFIG:
            return JsonResponse({'error': 'Unknown register type'}, status=400)

        config = CONFIG[register_type]

        if request.method == 'GET':
            # Тестовые данные для отладки
            return JsonResponse({
                'draw': 1,
                'recordsTotal': 100,
                'recordsFiltered': 100,
                'data': [
                    [f'Тестовый {register_type} 1', '2023', '2024-01-01', 'Тип 1'] + [''] * 14,
                    [f'Тестовый {register_type} 2', '2024', '2024-01-02', 'Тип 2'] + [''] * 14,
                ]
            })

        # Импортируем модель
        Model = apps.get_model('agregator', config['model'])

        # Базовый queryset с оптимизацией
        if register_type in ['archaeological', 'identified']:
            queryset = Model.objects.select_related('account_card', 'account_card__user').all()
        else:
            queryset = Model.objects.select_related('user').all()

        def format_data(obj):
            """Универсальная функция форматирования данных"""
            try:
                if register_type in ['archaeological', 'identified']:
                    return format_heritage_site_data(obj, register_type, config)
                elif register_type == 'acts':
                    return format_act_data(obj, config)
                elif register_type == 'scientific_reports':
                    return format_scientific_report_data(obj, config)
                elif register_type == 'tech_reports':
                    return format_tech_report_data(obj, config)
                elif register_type == 'open_lists':
                    return format_open_list_data(obj, config)
                elif register_type == 'account_cards':
                    return format_account_card_data(obj, config)
                elif register_type == 'commercial_offers':
                    return format_commercial_offer_data(obj, config)
                elif register_type == 'geo_objects':
                    return format_geo_object_data(obj, config)
                else:
                    return []
            except Exception as e:
                print(f"Error formatting data for {register_type}: {e}")
                return [f"Error: {str(e)}"] * 20  # Возвращаем пустые ячейки в случае ошибки

        datatable = DataTableServerSide(request, queryset, config['columns'])
        return datatable.get_response(format_data)
    except Exception as e:
        import traceback

        print(f"Error in universal_datatable: {e}")
        print(traceback.format_exc())
        return JsonResponse({
            'draw': 1,
            'recordsTotal': 0,
            'recordsFiltered': 0,
            'data': [],
            'error': str(e)
        })


def format_heritage_site_data(site, site_type, config):
    """Форматирование данных для археологических памятников"""
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
                onclick="openDeleteModal({site.id}, '{html.escape(json.dumps(name_value))}', '{config["delete_modal_id"]}')">
            Удалить
        </button>
    </td>
    '''

    # БАЗОВЫЕ ДАННЫЕ
    base_data = [
        card_data['creation_time'],
        card_data['address'],
        card_data['object_type'],
        card_data['general_classification'],
        card_data['description'],
        card_data['usage'],
        card_data['discovery_info'],
        card_data['compiler'],
        card_data['compile_date'],
        owner_cell,
        card_date_uploaded,
        source_cell,
        formalized_doc_cell,
        original_doc_cell,
        actions_cell
    ]

    # ФОРМИРУЕМ ПОЛНЫЙ СПИСОК КОЛОНОК
    if site_type == 'archaeological':
        return [
            name_cell,
            site.district,
            document_cell,
            site.register_num,
            site.date_uploaded.strftime('%Y-%m-%d %H:%M') if site.date_uploaded else '',
            is_excluded_cell,
        ] + base_data
    else:  # identified
        return [
            name_cell,
            site.address,
            site.obj_info,
            document_cell,
            site.date_uploaded.strftime('%Y-%m-%d %H:%M') if site.date_uploaded else '',
            is_excluded_cell,
        ] + base_data


def format_act_data(act, config):
    """Форматирование данных для актов"""
    # Основные данные
    year = act.year or ''
    finish_date = act.finish_date if act.finish_date else ''
    type_cell = act.type or ''

    # Наименование и номер
    name_number_cell = act.name_number or ''
    if hasattr(act, 'id'):
        name_number_cell = f'<a href="/acts/{act.id}/" target="_blank">{act.name_number}</a>'

    place = act.place or ''
    customer = act.customer or ''
    area = act.area or ''
    expert = act.expert or ''
    executioner = act.executioner or ''
    open_list = act.open_list or ''
    conclusion = act.conclusion or ''
    border_objects = act.border_objects or ''

    # Владелец документа
    owner_cell = ''
    if act.user:
        avatar_url = act.user.avatar.url if act.user.avatar else '/static/images/default-avatar.png'
        owner_cell = f'''
        <a href="/users/{act.user.id}" target="_blank">
            <img src="{avatar_url}" class="rounded-circle" height="25" width="25" style="object-fit: cover;" alt=""/>
            {act.user.username}
        </a>
        '''

    # Источник
    source_cell = ''
    if hasattr(act, 'upload_source_dict'):
        source_dict = act.upload_source_dict
        if source_dict and source_dict.get('link'):
            source_cell = f'<a href="{source_dict["link"]}" target="_blank">{source_dict["source"]}</a>'
        elif source_dict:
            source_cell = source_dict.get('source', '')

    # Дата загрузки
    date_uploaded = act.date_uploaded.strftime('%Y-%m-%d %H:%M') if act.date_uploaded else ''

    # Формализованный документ
    formalized_doc_cell = f'''
    <a href="/acts/{act.id}/">
        <button type="button" class="btn btn-primary" style="border-radius: 12px; margin-bottom: 8px;">
            Просмотр акта
        </button>
    </a>
    '''

    # Исходный документ
    original_doc_cell = ''
    if hasattr(act, 'source_dict') and act.source_dict:
        for source in act.source_dict:
            if source.get('path'):
                original_doc_cell += f'<a href="/{source["path"]}" target="_blank">{source.get("origin_filename", "Документ")}</a><br>'

    # Кнопки действий
    actions_cell = f'''
    <td>
        <a href="/acts_edit/{act.id}/" class="btn btn-primary" style="border-radius: 12px; margin-right: 10px;">
            Редактировать
        </a>
        <button type="button" class="btn btn-danger" style="margin-top: 8px;" 
                onclick="openDeleteModal({act.id}, {html.escape(json.dumps(act.name_number or 'Акт'))}, 'delete_act')">
            Удалить
        </button>
    </td>
    '''

    return [
        year,
        finish_date,
        type_cell,
        name_number_cell,
        place,
        customer,
        area,
        expert,
        executioner,
        open_list,
        conclusion,
        border_objects,
        owner_cell,
        source_cell,
        date_uploaded,
        formalized_doc_cell,
        original_doc_cell,
        actions_cell
    ]


# Обертки для обратной совместимости
@csrf_exempt
def archaeological_heritage_sites_datatable(request):
    return universal_datatable(request, 'archaeological')


@csrf_exempt
def identified_archaeological_heritage_sites_datatable(request):
    return universal_datatable(request, 'identified')


@csrf_exempt
def acts_datatable(request):
    return universal_datatable(request, 'acts')


def format_scientific_report_data(report, config):
    """Форматирование данных для научных отчетов"""
    # Основные данные
    name = report.name or ''
    name_cell = f'<a href="/{config["view_url"]}/{report.id}/" target="_blank">{name}</a>'

    organization = report.organization or ''
    author = report.author or ''
    open_list = report.open_list or ''
    writing_date = report.writing_date.strftime('%d.%m.%Y') if report.writing_date else ''

    # Владелец документа
    owner_cell = ''
    if report.user:
        avatar_url = report.user.avatar.url if report.user.avatar else '/static/images/default-avatar.png'
        owner_cell = f'''
        <a href="/users/{report.user.id}" target="_blank">
            <img src="{avatar_url}" class="rounded-circle" height="25" width="25" style="object-fit: cover;" alt=""/>
            {report.user.username}
        </a>
        '''

    # Источник
    source_cell = ''
    if hasattr(report, 'upload_source_dict'):
        source_dict = report.upload_source_dict
        if source_dict and source_dict.get('link'):
            source_cell = f'<a href="{source_dict["link"]}" target="_blank">{source_dict["source"]}</a>'
        elif source_dict:
            source_cell = source_dict.get('source', '')

    # Дата загрузки
    date_uploaded = report.date_uploaded.strftime('%Y-%m-%d %H:%M') if report.date_uploaded else ''

    # Формализованный документ
    formalized_doc_cell = f'''
    <a href="/{config["view_url"]}/{report.id}/">
        <button type="button" class="btn btn-primary" style="border-radius: 12px; margin-bottom: 8px;">
            Просмотр отчёта
        </button>
    </a>
    '''

    # Исходный документ
    original_doc_cell = ''
    if hasattr(report, 'source_dict') and report.source_dict:
        for source in report.source_dict:
            if source.get('path'):
                original_doc_cell += f'<a href="/{source["path"]}" target="_blank">{source.get("origin_filename", "Документ")}</a><br>'

    # Кнопки действий
    actions_cell = f'''
    <td>
        <a href="/{config["edit_url"]}/{report.id}/" class="btn btn-primary" style="border-radius: 12px; margin-right: 10px;">
            Редактировать
        </a>
        <button type="button" class="btn btn-danger" style="margin-top: 8px;" 
                onclick="openDeleteModal({report.id}, '{html.escape(json.dumps(name)) if name else "Научный отчет"}', '{config["delete_modal_id"]}')">
            Удалить
        </button>
    </td>
    '''

    return [
        name_cell,
        organization,
        author,
        open_list,
        writing_date,
        owner_cell,
        source_cell,
        date_uploaded,
        formalized_doc_cell,
        original_doc_cell,
        actions_cell
    ]


@csrf_exempt
def scientific_reports_datatable(request):
    return universal_datatable(request, 'scientific_reports')


def format_tech_report_data(tech_report, config):
    """Форматирование данных для научно-технических отчётов"""

    # Основные данные
    name_cell = tech_report.name or ''
    if hasattr(tech_report, 'id'):
        name_cell = f'<a href="/tech_reports/{tech_report.id}/" target="_blank">{tech_report.name}</a>'

    organization = tech_report.organization or ''
    author = tech_report.author or ''
    open_list = tech_report.open_list or ''
    writing_date = tech_report.writing_date if tech_report.writing_date else ''

    # Владелец документа
    owner_cell = ''
    if tech_report.user:
        avatar_url = tech_report.user.avatar.url if tech_report.user.avatar else '/static/images/default-avatar.png'
        owner_cell = f'''
        <a href="/users/{tech_report.user.id}" target="_blank">
            <img src="{avatar_url}" class="rounded-circle" height="25" width="25" style="object-fit: cover;" alt=""/>
            {tech_report.user.username}
        </a>
        '''

    # Источник
    source_cell = ''
    if hasattr(tech_report, 'upload_source_dict'):
        source_dict = tech_report.upload_source_dict
        if source_dict and source_dict.get('link'):
            source_cell = f'<a href="{source_dict["link"]}" target="_blank">{source_dict["source"]}</a>'
        elif source_dict:
            source_cell = source_dict.get('source', '')

    # Дата загрузки
    date_uploaded = tech_report.date_uploaded.strftime('%Y-%m-%d %H:%M') if tech_report.date_uploaded else ''

    # Формализованный документ
    formalized_doc_cell = f'''
    <a href="/{config["view_url"]}/{tech_report.id}/">
        <button type="button" class="btn btn-primary" style="border-radius: 12px; margin-bottom: 8px;">
            Просмотр отчёта
        </button>
    </a>
    '''

    # Исходный документ
    original_doc_cell = ''
    if hasattr(tech_report, 'source_dict') and tech_report.source_dict:
        for source in tech_report.source_dict:
            if source.get('path'):
                original_doc_cell += f'<a href="/{source["path"]}" target="_blank">{source.get("origin_filename", "Документ")}</a><br>'

    # Кнопки действий
    actions_cell = f'''
    <td>
        <a href="/tech_reports_edit/{tech_report.id}/" class="btn btn-primary" style="border-radius: 12px; margin-right: 10px;">
            Редактировать
        </a>
        <button type="button" class="btn btn-danger" style="margin-top: 8px;" 
                onclick="openDeleteModal({tech_report.id}, '{html.escape(json.dumps(tech_report.name)) if tech_report.name else "Отчёт"}', 'delete_tech_report')">
            Удалить
        </button>
    </td>
    '''

    return [
        name_cell,
        organization,
        author,
        open_list,
        writing_date,
        owner_cell,
        source_cell,
        date_uploaded,
        formalized_doc_cell,
        original_doc_cell,
        actions_cell
    ]


@csrf_exempt
def tech_reports_datatable(request):
    return universal_datatable(request, 'tech_reports')


def format_open_list_data(open_list, config):
    """Форматирование данных для открытых листов"""

    # Основные данные
    number_cell = open_list.number or ''
    if hasattr(open_list, 'id'):
        number_cell = f'<a href="/open_lists/{open_list.id}/" target="_blank">{open_list.number}</a>'

    holder = open_list.holder or ''
    object_text = open_list.object or ''
    works = open_list.works or ''
    start_date = open_list.start_date if open_list.start_date else ''
    end_date = open_list.end_date if open_list.end_date else ''

    # Владелец документа
    owner_cell = ''
    if open_list.user:
        avatar_url = open_list.user.avatar.url if open_list.user.avatar else '/static/images/default-avatar.png'
        owner_cell = f'''
        <a href="/users/{open_list.user.id}" target="_blank">
            <img src="{avatar_url}" class="rounded-circle" height="25" width="25" style="object-fit: cover;" alt=""/>
            {open_list.user.username}
        </a>
        '''

    # Источник
    source_cell = ''
    if hasattr(open_list, 'upload_source_dict'):
        source_dict = open_list.upload_source_dict
        if source_dict and source_dict.get('link'):
            source_cell = f'<a href="{source_dict["link"]}" target="_blank">{source_dict["source"]}</a>'
        elif source_dict:
            source_cell = source_dict.get('source', '')

    # Дата загрузки
    date_uploaded = open_list.date_uploaded.strftime('%Y-%m-%d %H:%M') if open_list.date_uploaded else ''

    # Формализованный документ
    formalized_doc_cell = f'''
    <a href="/open_lists/{open_list.id}/">
        <button type="button" class="btn btn-primary" style="border-radius: 12px; margin-bottom: 8px;">
            Просмотр открытого листа
        </button>
    </a>
    '''

    # Исходный документ
    original_doc_cell = ''
    if hasattr(open_list, 'source_dict') and open_list.source_dict:
        for source in open_list.source_dict:
            if source.get('path'):
                original_doc_cell += f'<a href="/{source["path"]}" target="_blank">{source.get("origin_filename", "Документ")}</a><br>'

    # Кнопки действий
    actions_cell = f'''
    <td>
        <a href="/open_lists_edit/{open_list.id}/" class="btn btn-primary" style="border-radius: 12px; margin-right: 10px;">
            Редактировать
        </a>
        <button type="button" class="btn btn-danger" style="margin-top: 8px;" 
                onclick="openDeleteModal({open_list.id}, '{html.escape(json.dumps(open_list.number)) if open_list.number else "Открытый лист"}', 'delete_open_list')">
            Удалить
        </button>
    </td>
    '''

    return [
        number_cell,
        holder,
        object_text,
        works,
        start_date,
        end_date,
        owner_cell,
        source_cell,
        date_uploaded,
        formalized_doc_cell,
        original_doc_cell,
        actions_cell
    ]


@csrf_exempt
def open_lists_datatable(request):
    return universal_datatable(request, 'open_lists')


def format_account_card_data(account_card, config):
    """Форматирование данных для учётных карт"""

    # Основные данные
    name_cell = account_card.name or ''
    if hasattr(account_card, 'id'):
        name_cell = f'<a href="/account_cards/{account_card.id}/" target="_blank">{account_card.name}</a>'

    creation_time = account_card.creation_time if account_card.creation_time else ''
    address = account_card.address or ''
    object_type = account_card.object_type or ''
    general_classification = account_card.general_classification or ''
    description = account_card.description or ''
    usage = account_card.usage or ''
    discovery_info = account_card.discovery_info or ''
    compiler = account_card.compiler or ''
    compile_date = account_card.compile_date if account_card.compile_date else ''

    # Владелец документа
    owner_cell = ''
    if account_card.user:
        avatar_url = account_card.user.avatar.url if account_card.user.avatar else '/static/images/default-avatar.png'
        owner_cell = f'''
        <a href="/users/{account_card.user.id}" target="_blank">
            <img src="{avatar_url}" class="rounded-circle" height="25" width="25" style="object-fit: cover;" alt=""/>
            {account_card.user.username}
        </a>
        '''

    # Дата загрузки
    date_uploaded = account_card.date_uploaded.strftime('%Y-%m-%d %H:%M') if account_card.date_uploaded else ''

    # Источник
    source_cell = ''
    if hasattr(account_card, 'upload_source_dict'):
        source_dict = account_card.upload_source_dict
        if source_dict and source_dict.get('link'):
            source_cell = f'<a href="{source_dict["link"]}" target="_blank">{source_dict["source"]}</a>'
        elif source_dict:
            source_cell = source_dict.get('source', '')

    # Формализованный документ
    formalized_doc_cell = f'''
    <a href="/account_cards/{account_card.id}/">
        <button type="button" class="btn btn-primary" style="border-radius: 12px; margin-bottom: 8px;">
            Просмотр учётной карты
        </button>
    </a>
    '''

    # Исходный документ
    original_doc_cell = ''
    if hasattr(account_card, 'source_dict') and account_card.source_dict:
        for source in account_card.source_dict:
            if source.get('path'):
                original_doc_cell += f'<a href="/{source["path"]}" target="_blank">{source.get("origin_filename", "Документ")}</a><br>'

    # Кнопки действий
    actions_cell = f'''
    <td>
        <a href="/account_cards_edit/{account_card.id}/" class="btn btn-primary" style="border-radius: 12px; margin-right: 10px;">
            Редактировать
        </a>
        <button type="button" class="btn btn-danger" style="margin-top: 8px;" 
                onclick="openDeleteModal({account_card.id}, '{html.escape(json.dumps(account_card.name)) if account_card.name else "Учётная карта"}', 'delete_account_card')">
            Удалить
        </button>
    </td>
    '''

    return [
        name_cell,
        creation_time,
        address,
        object_type,
        general_classification,
        description,
        usage,
        discovery_info,
        compiler,
        compile_date,
        owner_cell,
        date_uploaded,
        source_cell,
        formalized_doc_cell,
        original_doc_cell,
        actions_cell
    ]


@csrf_exempt
def account_cards_datatable(request):
    return universal_datatable(request, 'account_cards')


def format_commercial_offer_data(commercial_offer, config):
    """Форматирование данных для коммерческих предложений"""

    # Исходный документ
    origin_filename = commercial_offer.origin_filename or ''
    source_path = commercial_offer.source
    first_cell = f'<a href="/{source_path}">{origin_filename}</a>' if source_path else origin_filename

    # Источник
    source_cell = ''
    if hasattr(commercial_offer, 'upload_source_dict'):
        source_dict = commercial_offer.upload_source_dict
        source_cell = source_dict.get('source', '') if source_dict else ''

    # Владелец документа
    owner_cell = ''
    if commercial_offer.user:
        avatar_url = commercial_offer.user.avatar.url if commercial_offer.user.avatar else '/static/images/default-avatar.png'
        owner_cell = f'''
        <a href="/users/{commercial_offer.user.id}" target="_blank">
            <img src="{avatar_url}" class="rounded-circle" height="25" width="25" style="object-fit: cover;" alt=""/>
            {commercial_offer.user.username}
        </a>
        '''

    # Дата загрузки
    date_uploaded = commercial_offer.date_uploaded.strftime('%Y-%m-%d %H:%M') if commercial_offer.date_uploaded else ''

    # Координаты (кнопка просмотра)
    coordinates_cell = f'''
    <a href="/{config["view_url"]}/{commercial_offer.id}/">
        <button type="button" class="btn btn-primary" style="border-radius: 12px;">
            Просмотр
        </button>
    </a>
    '''

    # Кнопки действий
    actions_cell = f'''
    <td>
        <a href="/{config["edit_url"]}/{commercial_offer.id}/" class="btn btn-primary" style="border-radius: 12px; margin-right: 10px;">
            Редактировать
        </a>
        <button type="button" class="btn btn-danger" style="margin-top: 8px;" 
                onclick="openDeleteModal({commercial_offer.id}, '{html.escape(json.dumps(origin_filename))}', '{config["delete_modal_id"]}')">
            Удалить
        </button>
    </td>
    '''

    return [
        first_cell,
        source_cell,
        owner_cell,
        date_uploaded,
        coordinates_cell,
        actions_cell
    ]


def format_geo_object_data(geo_object, config):
    """Форматирование данных для географических объектов"""

    # Исходный документ
    origin_filename = geo_object.origin_filename or ''
    source_path = geo_object.source
    first_cell = f'<a href="/{source_path}">{origin_filename}</a>' if source_path else origin_filename

    # Источник
    source_cell = ''
    if hasattr(geo_object, 'upload_source_dict'):
        source_dict = geo_object.upload_source_dict
        source_cell = source_dict.get('source', '') if source_dict else ''

    # Владелец документа
    owner_cell = ''
    if geo_object.user:
        avatar_url = geo_object.user.avatar.url if geo_object.user.avatar else '/static/images/default-avatar.png'
        owner_cell = f'''
        <a href="/users/{geo_object.user.id}" target="_blank">
            <img src="{avatar_url}" class="rounded-circle" height="25" width="25" style="object-fit: cover;" alt=""/>
            {geo_object.user.username}
        </a>
        '''

    # Дата загрузки
    date_uploaded = geo_object.date_uploaded.strftime('%Y-%m-%d %H:%M') if geo_object.date_uploaded else ''

    # Координаты (кнопка просмотра)
    coordinates_cell = f'''
    <a href="/{config["view_url"]}/{geo_object.id}/">
        <button type="button" class="btn btn-primary" style="border-radius: 12px;">
            Просмотр
        </button>
    </a>
    '''

    # Кнопки действий
    actions_cell = f'''
    <td>
        <a href="/{config["edit_url"]}/{geo_object.id}/" class="btn btn-primary" style="border-radius: 12px; margin-right: 10px;">
            Редактировать
        </a>
        <button type="button" class="btn btn-danger" style="margin-top: 8px;" 
                onclick="openDeleteModal({geo_object.id}, '{html.escape(json.dumps(origin_filename))}', '{config["delete_modal_id"]}')">
            Удалить
        </button>
    </td>
    '''

    return [
        first_cell,
        source_cell,
        owner_cell,
        date_uploaded,
        coordinates_cell,
        actions_cell
    ]
