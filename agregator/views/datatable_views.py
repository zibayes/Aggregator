from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from agregator.processing.datatable_utils import DataTableServerSide
from agregator.models import Act, OpenLists, ScientificReport, TechReport, ObjectAccountCard


@login_required
def acts_datatable(request):
    # Конфигурация колонок для актов
    columns_config = [
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
    ]

    # Базовый queryset с оптимизацией
    queryset = Act.objects.select_related('user').prefetch_related('source_files').all()

    def format_act_data(act):
        """Форматирует данные акта для таблицы"""
        return [
            act.year,
            act.finish_date,
            act.type,
            act.name_number,
            act.place,
            act.customer,
            act.area,
            act.expert,
            act.executioner,
            act.open_list,
            act.conclusion,
            act.border_objects,
            f'<a href="/users/{act.user.id}">'
            f'<img src="{act.user.avatar.url}" class="rounded-circle" height="25" width="25" style="object-fit: cover;" alt=""/>'
            f'{act.user.username}'
            f'</a>',
            f'<a href="{act.upload_source_dict.link}">{act.upload_source_dict.source}</a>' if act.upload_source_dict.link else act.upload_source_dict.source,
            act.date_uploaded.strftime('%Y-%m-%d %H:%M'),
            # Кнопка просмотра
            f'<a href="/acts/{act.id}" class="btn btn-primary btn-sm">Просмотр</a>',
            # Исходные документы
            '<br>'.join([f'<a href="/{source.path}">{source.origin_filename}</a>' for source in act.source_dict]),
            # Кнопки действий
            f'''
            <a href="/acts/{act.id}/edit" class="btn btn-warning btn-sm">Редактировать</a>
            <button class="btn btn-danger btn-sm" data-bs-toggle="modal" data-bs-target="#deleteActModal{act.id}">Удалить</button>
            '''
        ]

    datatable = DataTableServerSide(request, queryset, columns_config)
    return datatable.get_response(format_act_data)


# Аналогично для других моделей...
@login_required
def scientific_reports_datatable(request):
    columns_config = [
        {'field': 'writing_date', 'searchable': True, 'orderable': True},
        {'field': 'name', 'searchable': True, 'orderable': True},
        {'field': 'organization', 'searchable': True, 'orderable': True},
        {'field': 'author', 'searchable': True, 'orderable': True},
        {'field': 'open_list', 'searchable': True, 'orderable': True},
        {'field': 'place', 'searchable': True, 'orderable': True},
        {'field': 'contractors', 'searchable': True, 'orderable': True},
        {'field': 'area_info', 'searchable': True, 'orderable': True},
        {'field': 'user__username', 'searchable': True, 'orderable': True},
        {'field': 'date_uploaded', 'searchable': True, 'orderable': True},
    ]

    queryset = ScientificReport.objects.select_related('user').all()

    def format_report_data(report):
        return [
            report.writing_date,
            report.name,
            report.organization,
            report.author,
            report.open_list,
            report.place,
            report.contractors,
            report.area_info,
            f'<a href="/users/{report.user.id}">{report.user.username}</a>',
            report.date_uploaded.strftime('%Y-%m-%d %H:%M'),
            f'<a href="/scientific_reports/{report.id}" class="btn btn-primary btn-sm">Просмотр</a>',
            f'<a href="/{report.source}">{report.origin_filename}</a>' if report.source else '',
            f'''
            <a href="/scientific_reports/{report.id}/edit" class="btn btn-warning btn-sm">Редактировать</a>
            <button class="btn btn-danger btn-sm" data-bs-toggle="modal" data-bs-target="#deleteReportModal{report.id}">Удалить</button>
            '''
        ]

    datatable = DataTableServerSide(request, queryset, columns_config)
    return datatable.get_response(format_report_data)
