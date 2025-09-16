import json
import os
from urllib.parse import quote

import pandas as pd
import simplekml
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth import logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django_celery_results.models import TaskResult
from celery.result import AsyncResult
from pyproj import Geod
from rest_framework import generics
from shapely.geometry import Polygon, LineString
from shapely.geometry import shape, Point
from shapely.ops import nearest_points

from agregator.models import Act, OpenLists, ScientificReport, TechReport, ArchaeologicalHeritageSite, \
    IdentifiedArchaeologicalHeritageSite, ObjectAccountCard, CommercialOffers, GeoObject
from agregator.processing.external_sources import process_oan_list, process_voan_list
from agregator.processing.geo_utils import convert_to_wgs84
from agregator.views import get_register_view, create_model_dataframe, generate_excel_report, get_scan_task


def acts_register(request):
    only_fields = [
        'id', 'user_id', 'date_uploaded', 'is_processing', 'year',
        'finish_date', 'type', 'name_number', 'place', 'customer',
        'area', 'expert', 'executioner', 'open_list', 'conclusion',
        'border_objects', 'source'
    ]
    view = get_register_view(request, Act, 'acts', public_only_fields=only_fields, private_only_fields=only_fields,
                             template_name='acts_register.html')
    return view


def open_lists_register(request):
    view = get_register_view(request, OpenLists, 'open_lists', template_name='open_lists_register.html')
    return view


def open_lists_register_download(request):
    table_path = "uploaded_files/Открытые листы/Открытые листы.xlsx"
    fields_mapping = {
        'Номер листа': 'number',
        'Держатель': 'holder',
        'Объект': 'object',
        'Работы': 'works',
        'Начало срока': 'start_date',
        'Конец срока': 'end_date'
    }
    df_existing = create_model_dataframe(OpenLists, fields_mapping)
    if df_existing is None:
        return redirect(open_lists_register)
    column_widths = {
        'A': 14,
        'B': 20,
        'C': 100,
        'D': 100,
        'E': 14,
        'F': 14
    }
    generate_excel_report(df_existing, table_path, column_widths)
    return redirect('/' + table_path)


def acts_register_download(request):
    table_path = "uploaded_files/Акты ГИКЭ/РЕЕСТР актов ГИКЭ.xlsx"
    fields_mapping = {
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
    }
    df_existing = create_model_dataframe(Act, fields_mapping)
    if df_existing is None:
        return redirect(acts_register)
    column_widths = {
        'A': 6.86,
        'B': 10.14,
        'C': 10.14,
        'D': 66.43,
        'E': 24,
        'F': 26,
        'G': 20.71,
        'H': 18.43,
        'I': 24.71,
        'J': 21.29,
        'K': 26,
        'L': 27.29
    }
    generate_excel_report(df_existing, table_path, column_widths)
    return redirect('/' + table_path)


def scientific_reports_register_download(request):
    table_path = "uploaded_files/Научные отчёты/РЕЕСТР ПНО.xlsx"
    fields_mapping = {
        'Год написания отчёта': 'writing_date',
        'Название отчёта': 'name',
        'Организация': 'organization',
        'Автор': 'author',
        'Открытый лист': 'open_list',
        'Населённый пункт': 'place',
        'Исполнители': 'contractors',
        'Площадь': 'area_info'
    }
    df_existing = create_model_dataframe(ScientificReport, fields_mapping)
    if df_existing is None:
        return redirect(scientific_reports_register)
    column_widths = {
        'A': 24,
        'B': 24,
        'C': 24,
        'D': 24,
        'E': 24,
        'F': 26,
        'G': 20.71,
        'H': 18.43,
        'I': 24.71,
        'J': 21.29,
        'K': 26,
        'L': 27.29
    }
    generate_excel_report(df_existing, table_path, column_widths)
    return redirect('/' + table_path)


def tech_reports_register_download(request):
    table_path = "uploaded_files/Научно-технические отчёты/РЕЕСТР ПНТО.xlsx"
    fields_mapping = {
        'Год написания отчёта': 'writing_date',
        'Название отчёта': 'name',
        'Организация': 'organization',
        'Автор': 'author',
        'Открытый лист': 'open_list',
        'Населённый пункт': 'place',
        'Исполнители': 'contractors',
        'Площадь': 'area_info'
    }
    df_existing = create_model_dataframe(TechReport, fields_mapping)
    if df_existing is None:
        return redirect(tech_reports_register)
    column_widths = {
        'A': 24,
        'B': 24,
        'C': 24,
        'D': 24,
        'E': 24,
        'F': 26,
        'G': 20.71,
        'H': 18.43,
        'I': 24.71,
        'J': 21.29,
        'K': 26,
        'L': 27.29
    }
    generate_excel_report(df_existing, table_path, column_widths)
    return redirect("/" + table_path)


def scientific_reports_register(request):
    only_fields = [
        'id', 'user_id', 'date_uploaded', 'upload_source', 'is_processing',
        'name', 'organization', 'author', 'open_list', 'writing_date',
        'contractors', 'source', 'place', 'area_info', 'results', 'conclusion'
    ]
    view = get_register_view(request, ScientificReport, 'reports', public_only_fields=only_fields,
                             private_only_fields=only_fields, template_name='scientific_reports_register.html')
    return view


def tech_reports_register(request):
    only_fields = [
        'id', 'user_id', 'date_uploaded', 'upload_source', 'is_processing',
        'name', 'organization', 'author', 'open_list', 'writing_date',
        'contractors', 'source', 'place', 'area_info', 'results', 'conclusion'
    ]
    view = get_register_view(request, TechReport, 'reports', public_only_fields=only_fields,
                             private_only_fields=only_fields, template_name='tech_reports_register.html')
    return view


def archaeological_heritage_sites(request):
    is_processing, scan_task_id, active_scan_task = get_scan_task(
        'agregator.processing.external_sources.process_oan_list')

    if request.method == 'POST' and scan_task_id is None:
        scan_task = process_oan_list.delay()
        scan_task_id = scan_task.id
        is_processing = True
    oan = ArchaeologicalHeritageSite.objects.all()
    return render(request, 'archaeological_heritage_site_register.html',
                  {'oan': oan, 'is_processing': is_processing, 'scan_task_id': scan_task_id,
                   'active_scan_task': active_scan_task})


def identified_archaeological_heritage_sites(request):
    is_processing, scan_task_id, active_scan_task = get_scan_task(
        'agregator.processing.external_sources.process_voan_list')

    if request.method == 'POST' and scan_task_id is None:
        scan_task = process_voan_list.delay()
        scan_task_id = scan_task.id
        is_processing = True
    voan = IdentifiedArchaeologicalHeritageSite.objects.all()
    return render(request, 'identified_archaeological_heritage_site_register.html',
                  {'voan': voan, 'is_processing': is_processing, 'scan_task_id': scan_task_id,
                   'active_scan_task': active_scan_task})


def account_cards_register_download(request):
    table_path = "uploaded_files/Учётные карты/РЕЕСТР Учётных карт.xlsx"
    fields_mapping = {
        'Наименование объекта': 'name',
        'Время создания (возникновения) объекта': 'creation_time',
        'Адрес (местонахождение) объекта': 'address',
        'Вид объекта': 'object_type',
        'Общая видовая принадлежность объекта': 'general_classification',
        'Общее описание объекта и вывод о его историко-культурной ценности': 'description',
        'Использование объекта культурного наследия или пользователь': 'usage',
        'Сведения о дате и обстоятельствах выявления (обнаружения) объекта': 'discovery_info',
        'Составитель учетной карты': 'compiler'
    }
    df_existing = create_model_dataframe(ObjectAccountCard, fields_mapping)
    if df_existing is None:
        return redirect(account_cards_register)
    column_widths = {
        'A': 24,
        'B': 24,
        'C': 50,
        'D': 16,
        'E': 18,
        'F': 62,
        'G': 20,
        'H': 28,
        'I': 25
    }
    generate_excel_report(df_existing, table_path, column_widths, height_title=80, height_cell=100)
    return redirect("/" + table_path)


def account_cards_register(request):
    only_fields = [
        'id', 'user_id', 'date_uploaded', 'upload_source', 'is_processing',
        'is_public', 'origin_filename', 'name', 'creation_time',
        'address', 'object_type', 'general_classification', 'description',
        'usage', 'discovery_info', 'source'
    ]
    view = get_register_view(request, ObjectAccountCard, 'account_cards', public_only_fields=only_fields,
                             private_only_fields=only_fields, template_name='account_cards_register.html')
    return view


def commercial_offers_register(request):
    view = get_register_view(request, CommercialOffers, 'commercial_offers',
                             template_name='commercial_offers_register.html')
    return view


def download_commercial_offer_report(request, pk):
    commercial_offer = get_object_or_404(CommercialOffers, id=pk)
    table_path = f"uploaded_files/Коммерческие предложения/{commercial_offer.id}_commercial_offer/Отчёт.xlsx"
    table_columns = ['Памятник', 'Дистанция до памятника (км)']
    account_cards = ObjectAccountCard.objects.all()
    if not account_cards:
        return redirect(commercial_offers_register)
    df_existing = None
    geo_objects = GeoObject.objects.filter(type='heritage')
    print('geo_objects' + str(geo_objects))
    account_cards = list(account_cards) + list(geo_objects)
    counter = 0
    for account_card in account_cards:
        table_columns_info = {i: '' for i in table_columns}
        print('TYPE: ' + str(type(account_card)))

        min_distance = None
        if hasattr(account_card, 'coordinates_dict') and account_card.coordinates_dict and hasattr(commercial_offer,
                                                                                                   'coordinates_dict') and commercial_offer.coordinates_dict:
            if type(account_card) != GeoObject:
                for ac_polygon in account_card.coordinates_dict.values():
                    if 'coordinate_system' not in ac_polygon.keys() or ac_polygon['coordinate_system'] == 'None':
                        continue
                    for co_polygon in commercial_offer.coordinates_dict.values():
                        if 'coordinate_system' not in co_polygon.keys() or co_polygon['coordinate_system'] == 'None':
                            continue
                        polygon1 = [[float(value[0]), float(value[1])] for key, value in co_polygon.items() if
                                    key not in ('coordinate_system', 'area')]
                        polygon2 = [[float(value[0]), float(value[1])] for key, value in ac_polygon.items() if
                                    key not in ('coordinate_system', 'area')]

                        if not (co_polygon['coordinate_system'] == ac_polygon['coordinate_system'] == 'wgs84'):
                            polygon1 = [[convert_to_wgs84(x[0], x[1], co_polygon['coordinate_system'])] for x in
                                        polygon1]
                            polygon2 = [[convert_to_wgs84(x[0], x[1], ac_polygon['coordinate_system'])] for x in
                                        polygon2]

                        if len(polygon1) > 2:
                            polygon1 = Polygon(polygon1)
                        elif len(polygon1) == 2:
                            polygon1 = LineString(polygon1)
                        elif len(polygon1) == 1:
                            polygon1 = Point(polygon1)

                        if len(polygon2) > 2:
                            polygon2 = Polygon(polygon2)
                        elif len(polygon2) == 2:
                            polygon2 = LineString(polygon2)
                        elif len(polygon2) == 1:
                            polygon2 = Point(polygon2)

                        point1, point2 = nearest_points(polygon1, polygon2)
                        geod = Geod(ellps="WGS84")
                        # print(str(polygon1) + ' HERE ' + str(polygon2))
                        # print(str(point1) + ' HERE ' + str(point2))
                        if not point1 or not point2:
                            continue
                        az12, az21, distance = geod.inv(point1.y, point1.x, point2.y, point2.x)
                        if min_distance is None or min_distance > distance:
                            min_distance = distance
            else:
                for ac_polygon in account_card.coordinates_dict.values():
                    for point_name, coords in ac_polygon.items():
                        print(str(counter) + '/' + str(len(ac_polygon.items())))
                        counter += 1
                        if 'coordinate_system' not in ac_polygon.keys() or ac_polygon[
                            'coordinate_system'] == 'None' or point_name == 'coordinate_system':
                            continue
                        for co_polygon in commercial_offer.coordinates_dict.values():
                            if 'coordinate_system' not in co_polygon.keys() or co_polygon[
                                'coordinate_system'] == 'None':
                                continue
                            polygon1 = [[float(value[0]), float(value[1])] for key, value in co_polygon.items() if
                                        key not in ('coordinate_system', 'area')]
                            polygon2 = [[float(value) for value in coords]]

                            if not (co_polygon['coordinate_system'] == ac_polygon['coordinate_system'] == 'wgs84'):
                                polygon1 = [[convert_to_wgs84(x[0], x[1], co_polygon['coordinate_system'])] for x in
                                            polygon1]
                                polygon2 = [[convert_to_wgs84(x[0], x[1], ac_polygon['coordinate_system'])] for x in
                                            polygon2]

                            if len(polygon1) > 2:
                                polygon1 = Polygon(polygon1)
                            elif len(polygon1) == 2:
                                polygon1 = LineString(polygon1)
                            elif len(polygon1) == 1:
                                polygon1 = Point(polygon1)

                            if len(polygon2) > 2:
                                polygon2 = Polygon(polygon2)
                            elif len(polygon2) == 2:
                                polygon2 = LineString(polygon2)
                            elif len(polygon2) == 1:
                                polygon2 = Point(polygon2)

                            point1, point2 = nearest_points(polygon1, polygon2)
                            geod = Geod(ellps="WGS84")
                            # print(str(polygon1) + ' HERE ' + str(polygon2))
                            # print(str(point1) + ' HERE ' + str(point2))
                            if not point1 or not point2:
                                continue
                            az12, az21, distance = geod.inv(point1.y, point1.x, point2.y, point2.x)
                            if min_distance is None or min_distance > distance:
                                min_distance = distance
                        table_columns_info['Памятник'] = point_name
                        table_columns_info['Дистанция до памятника (км)'] = distance / 1000
                        df_new = pd.DataFrame(table_columns_info, columns=table_columns_info.keys(), index=[0])
                        if df_existing is None:
                            df_existing = df_new
                        else:
                            df_existing = df_existing._append(df_new, ignore_index=True)

        if min_distance is not None and type(account_card) != GeoObject:
            table_columns_info['Памятник'] = account_card.name
            table_columns_info['Дистанция до памятника (км)'] = min_distance / 1000
            df_new = pd.DataFrame(table_columns_info, columns=table_columns_info.keys(), index=[0])
            if df_existing is None:
                df_existing = df_new
            else:
                df_existing = df_existing._append(df_new, ignore_index=True)
    if df_existing is None:
        return redirect(commercial_offers_register)
    df_existing = df_existing.sort_values(by='Дистанция до памятника (км)', ascending=True).reset_index(drop=True)
    column_widths = {
        'A': 100,
        'B': 40
    }
    generate_excel_report(df_existing, table_path, column_widths, height_title=15, height_cell=15)
    return redirect('/' + table_path)


def geo_objects_register(request):
    view = get_register_view(request, GeoObject, 'geo_objects', template_name='geo_object_register.html')
    return view


def archaeological_heritage_sites_download(request):
    current_lists = 'uploaded_files/Памятники/current_lists.txt'
    link = None
    with open(current_lists, 'r', encoding='utf-8') as file:
        for line in file.readlines():
            if 'list_oan - ' in line:
                link = line.replace('list_oan - ', '').strip()
    if link is None:
        return redirect(request.META.get('HTTP_REFERER', '/'))
    return redirect('/' + quote(link))


def identified_archaeological_heritage_sites_download(request):
    current_lists = 'uploaded_files/Памятники/current_lists.txt'
    link = None
    with open(current_lists, 'r', encoding='utf-8') as file:
        for line in file.readlines():
            if 'list_voan - ' in line:
                link = line.replace('list_voan - ', '').strip()
    if link is None:
        return redirect(request.META.get('HTTP_REFERER', '/'))
    return redirect('/' + quote(link))
