from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.apps import apps
from agregator.processing.datatable_utils import DataTableServerSide


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
                'edit_url': 'edit_scientific_report',
                'view_url': 'scientific_reports',
                'delete_modal_id': 'delete_scientific_report'
            },
            'tech_reports': {
                'model': 'TechReport',
                'columns': [
                    {'field': 'name', 'searchable': True, 'orderable': True},
                    {'field': 'organization', 'searchable': True, 'orderable': True},
                    {'field': 'author', 'searchable': True, 'orderable': True},
                    {'field': 'writing_date', 'searchable': True, 'orderable': True},
                    {'field': 'user__username', 'searchable': True, 'orderable': True},
                    {'field': 'upload_source', 'searchable': True, 'orderable': True},
                    {'field': 'date_uploaded', 'searchable': True, 'orderable': True},
                ],
                'name_field': 'name',
                'edit_url': 'tech_reports_edit',
                'view_url': 'tech_reports',
                'delete_modal_id': 'delete_tech_report'
            }
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
                onclick="openDeleteModal({site.id}, '{name_value.replace("'", "\\'")}', '{config["delete_modal_id"]}')">
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
                onclick="openDeleteModal({act.id}, '{act.name_number.replace("'", "\\'") if act.name_number else "Акт".replace("'", "\\'")}', 'delete_act')">
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
                onclick="openDeleteModal({report.id}, '{name.replace("'", "\\'") if name else "Научный отчет".replace("'", "\\'")}', '{config["delete_modal_id"]}')">
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
    <a href="/tech_reports/{tech_report.id}/">
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
                onclick="openDeleteModal({tech_report.id}, '{tech_report.name.replace("'", "\\'") if tech_report.name else "Отчёт".replace("'", "\\'")}', 'delete_tech_report')">
            Удалить
        </button>
    </td>
    '''

    return [
        name_cell,
        organization,
        author,
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
