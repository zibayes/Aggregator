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
import json
import os

from agregator.models import Act, ScientificReport, TechReport, ObjectAccountCard, CommercialOffers, GeoObject, \
    GeojsonData


def interactive_map(request):
    acts = Act.objects.filter(is_processing=False)
    scientific_reports = ScientificReport.objects.filter(is_processing=False)
    tech_report = TechReport.objects.filter(is_processing=False)
    all_coordinates = {'Акты': {}, 'Научные отчёты': {}, 'Научно-технические отчёты': {}}
    for act in acts:
        all_coordinates['Акты'][
            act.id] = {'coordinates': act.coordinates_dict,
                       'report_name': act.source_dict[0]['origin_filename'] if act.source_dict and len(
                           act.source_dict) > 0 else 'Неизвестный файл'}
    for report in scientific_reports:
        all_coordinates['Научные отчёты'][report.id] = {'coordinates': report.coordinates_dict,
                                                        'report_name': report.source_dict[0][
                                                            'origin_filename'] if report.source_dict and len(
                                                            report.source_dict) > 0 else 'Неизвестный файл'}
    for report in tech_report:
        all_coordinates['Научно-технические отчёты'][report.id] = {'coordinates': report.coordinates_dict,
                                                                   'report_name': report.source_dict[0][
                                                                       'origin_filename'] if report.source_dict and len(
                                                                       report.source_dict) > 0 else 'Неизвестный файл'}
    return render(request, 'interactive_map.html', {'all_coordinates': all_coordinates})


def download_all_coordinates(request):
    if request.method == 'POST':
        acts = Act.objects.filter(is_processing=False)
        scientific_reports = ScientificReport.objects.filter(is_processing=False)
        tech_report = TechReport.objects.filter(is_processing=False)
        all_coordinates = {'Акты': {}, 'Научные отчёты': {}, 'Научно-технические отчёты': {}}
        coordinates_to_download = {}

        for act in acts:
            all_coordinates['Акты'][
                act.source_dict[0]['origin_filename']] = act.coordinates_dict  # TODO: Подобрать более удачный нейминг?
        for report in scientific_reports:
            all_coordinates['Научные отчёты'][report.source_dict[0]['origin_filename']] = report.coordinates_dict
        for report in tech_report:
            all_coordinates['Научно-технические отчёты'][report.source[0]['origin_filename']] = report.coordinates_dict

        for report_type, reports in all_coordinates.items():
            for report, groups in reports.items():
                for group, point in groups.items():
                    for point_name, coords in point.items():
                        for key in request.POST.keys():
                            if f'{report_type}-{report}-{group}-{point_name}' == key:
                                if report_type not in coordinates_to_download.keys():
                                    coordinates_to_download[report_type] = {}
                                if report not in coordinates_to_download[report_type].keys():
                                    coordinates_to_download[report_type][report] = {}
                                if group not in coordinates_to_download[report_type][report].keys():
                                    coordinates_to_download[report_type][report][group] = {}
                                coordinates_to_download[report_type][report][group][point_name] = coords

        if coordinates_to_download:
            kml = simplekml.Kml()
            catalog_style = simplekml.Style()
            catalog_style.iconstyle.color = simplekml.Color.blue
            catalog_style.polystyle.color = simplekml.Color.blue
            photos_style = simplekml.Style()
            photos_style.iconstyle.color = simplekml.Color.green
            pits_style = simplekml.Style()
            pits_style.iconstyle.color = simplekml.Color.red
            current_style = current_group = None
            for report_type, reports in coordinates_to_download.items():
                report_type_folder = kml.newfolder(name=report_type)
                for report, groups in reports.items():
                    report_folder = report_type_folder.newfolder(name=report)
                    for group, point in groups.items():
                        system_check = True  # 'WGS-84' in group or 'WGS84' in group or 'WGS 84' in group or 'Шурф' in group
                        if 'фотофиксации' in group:
                            current_style = photos_style
                            photos_group = report_folder.newfolder(name=group)
                            current_group = photos_group
                        elif 'Каталог' in group:
                            current_style = catalog_style
                            catalog_group = report_folder.newfolder(name=group)
                            current_group = catalog_group
                            # Собираем все координаты из point в один список
                            polygon_coords = []  # Список для координат полигона
                            for point_name, coords in point.items():
                                if isinstance(coords, list) and len(coords) == 2:  # Проверяем, что это [lat, lon]
                                    polygon_coords.append(coords)  # Добавляем в список
                                else:
                                    print(f"Пропущен некорректный элемент для {point_name}: {coords}")

                            if polygon_coords:  # Если есть координаты, создаём полигон
                                polygon = current_group.newpolygon(
                                    name="Полигон")  # Один полигон для всей группы
                                outer_boundary = polygon.outerboundaryis
                                outer_coords = [(c[1], c[0], 0) for c in
                                                polygon_coords]  # Преобразуем: [lat, lon] -> [lon, lat, 0]
                                outer_boundary.coords = outer_coords  # Устанавливаем координаты
                                polygon.style = current_style  # Применяем стиль
                            else:
                                print(f"Для группы '{group}' нет валидных координат для полигона")
                        elif 'Шурфы' in group:
                            current_style = pits_style
                            pits_group = report_folder.newfolder(name=group)
                            current_group = pits_group
                        for point_name, coords in point.items():
                            if current_group and system_check:
                                photo_point = current_group.newpoint(name=str(point_name),
                                                                     coords=[
                                                                         (coords[1],
                                                                          coords[
                                                                              0])])  # TODO: менять их местами или нет?!
                                photo_point.style = current_style

            response = HttpResponse(kml.kml(), content_type='application/vnd.google-earth.kml+xml')
            filename = f'all_coordinates.kml'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        return HttpResponse('Координаты для экспорта не выбраны', status=404)
    return JsonResponse({'response': f'Method {request.method} is not available for this URL'})


def map(request, report_type, pk):
    report = None
    if report_type == 'account_card':
        report = get_object_or_404(ObjectAccountCard, id=pk)
        report_name = report.origin_filename
    elif report_type == 'commercial_offer':
        report = get_object_or_404(CommercialOffers, id=pk)
        report_name = report.origin_filename
    elif report_type == 'geo_object':
        report = get_object_or_404(GeoObject, id=pk)
        report_name = report.origin_filename
    else:
        if report_type == 'act':
            report = get_object_or_404(Act, id=pk)
        elif report_type == 'scientific_report':
            report = get_object_or_404(ScientificReport, id=pk)
        elif report_type == 'tech_report':
            report = get_object_or_404(TechReport, id=pk)
        else:
            return HttpResponse("Некорректный тип отчёта", status=404)

        report_name = report.source_dict[0]['origin_filename'] if report.source_dict and len(
            report.source_dict) > 0 else report.origin_filename if hasattr(report,
                                                                           'origin_filename') else 'Неизвестный файл'
    coordinates = report.coordinates_dict if report else {}
    matching_polygons = {'matching_polygons': get_geojson_polygons_sync(coordinates)}
    return render(request, 'interactive_map.html',
                  {'coordinates': coordinates, 'matching_polygons': matching_polygons,
                   'report_type': report_type, 'pk': pk, 'report_name': report_name})


def get_geojson_polygons(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            points = json.loads(data.get('points', []))
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Неверный формат данных'}, status=400)

        geojson_folder = os.path.join(os.getcwd(), 'uploaded_files/regions_polygons')
        geojson_data = {
            "type": "FeatureCollection",
            "features": []
        }

        for filename in os.listdir(geojson_folder):
            if filename.endswith('.geojson'):
                file_path = os.path.join(geojson_folder, filename)
                with open(file_path, 'r', encoding='utf-8') as file:
                    try:
                        data = json.load(file)
                        geojson_data['features'].extend(data['features'])
                    except json.JSONDecodeError:
                        return JsonResponse({'error': f'Ошибка при чтении файла {filename}'}, status=400)

        matching_polygons = {'Russia': [], 'Subject': [], 'Regions': []}
        for feature in geojson_data['features']:
            matching_polygons['Russia'].append(feature)

        for dirpath, dirnames, filenames in os.walk(geojson_folder):
            if 'Красноярский край' not in dirpath:
                continue
            for filename in filenames:
                if filename.endswith('.geojson'):
                    file_path = os.path.join(dirpath, filename)
                    with open(file_path, 'r', encoding='utf-8') as file:
                        try:
                            data = json.load(file)
                            for feature in data['features']:
                                polygon = shape(feature['geometry'])
                                for group, elements in points.items():
                                    for name, point_coords in elements.items():
                                        if isinstance(point_coords, list) and len(point_coords) == 2:
                                            point = Point([point_coords[1], point_coords[0]])
                                            if polygon.contains(point):
                                                if filename == 'Красноярский край.geojson':
                                                    matching_polygons['Subject'].append(feature)
                                                else:
                                                    matching_polygons['Regions'].append(feature)
                                                    break
                        except json.JSONDecodeError:
                            return JsonResponse({'error': f'Ошибка при чтении файла {filename}'}, status=400)

        if matching_polygons:
            return JsonResponse({'matching_polygons': matching_polygons}, status=200)
        else:
            return HttpResponse("Нет совпадений с полигонами", status=404)

    return HttpResponse("Метод не поддерживается", status=405)


def check_point_in_polygon(feature, point_coords):
    polygon = shape(feature.geojson['geometry'])
    point = Point([point_coords[1], point_coords[0]])
    return polygon.contains(point)


def get_geojson_polygons_sync(points):
    if points is None:
        return {}
    matching_polygons = {
        'Russia': [get_object_or_404(GeojsonData, name='Россия').geojson],
        'Subject': [get_object_or_404(GeojsonData, name='Красноярский край').geojson],
        'Regions': []
    }
    regions = GeojsonData.objects.exclude(name__in=('Россия', 'Красноярский край'))
    for feature in regions:
        polygon = shape(feature.geojson['geometry'])
        for group, elements in points.items():
            for name, point_coords in elements.items():
                if isinstance(point_coords, list) and len(point_coords) == 2:
                    point = Point([point_coords[1], point_coords[0]])
                    if polygon.contains(point):
                        matching_polygons['Regions'].append(feature.geojson)

    return matching_polygons


def download_coordinates(request, report_type, pk):
    if request.method == 'POST':
        if report_type == 'act':
            report = get_object_or_404(Act, id=pk)
        elif report_type == 'scientific_report':
            report = get_object_or_404(ScientificReport, id=pk)
        elif report_type == 'tech_report':
            report = get_object_or_404(TechReport, id=pk)
        elif report_type == 'account_card':
            report = get_object_or_404(ObjectAccountCard, id=pk)
        elif report_type == 'commercial_offer':
            report = get_object_or_404(CommercialOffers, id=pk)
        elif report_type == 'geo_object':
            report = get_object_or_404(GeoObject, id=pk)
        else:
            return HttpResponse("Некорректный тип отчёта", status=404)
        coordinates = report.coordinates_dict if report else {}
        coordinates_to_download = {}
        print('request.POST.keys(): ' + str(request.POST.keys()))
        print('coordinates.items(): ' + str(coordinates.items()))

        post_keys = list(request.POST.keys())
        for group, points in coordinates.items():
            for point_name, coords in points.items():
                key = f'{group}-{point_name}'
                if key in post_keys:
                    if group not in coordinates_to_download:
                        coordinates_to_download[group] = {}
                    coordinates_to_download[group][point_name] = coords

        if coordinates_to_download:
            kml = simplekml.Kml()
            catalog_style = simplekml.Style()
            catalog_style.iconstyle.color = simplekml.Color.blue
            catalog_style.polystyle.color = simplekml.Color.blue
            photos_style = simplekml.Style()
            photos_style.iconstyle.color = simplekml.Color.green
            pits_style = simplekml.Style()
            pits_style.iconstyle.color = simplekml.Color.red
            obj_center = simplekml.Style()
            obj_center.iconstyle.color = simplekml.Color.yellow
            current_style = current_group = None
            for group, point in coordinates_to_download.items():
                system_check = True  # 'WGS-84' in group or 'WGS84' in group or 'WGS 84' in group or 'Шурф' in group
                if 'фотофиксации' in group:
                    current_style = photos_style
                    photos_group = kml.newfolder(name=group)
                    current_group = photos_group
                elif 'Каталог' in group:
                    current_style = catalog_style
                    catalog_group = kml.newfolder(name=group)
                    current_group = catalog_group
                    # Собираем все координаты из point в один список
                    polygon_coords = []  # Список для координат полигона
                    for point_name, coords in point.items():
                        if isinstance(coords, list) and len(coords) == 2:  # Проверяем, что это [lat, lon]
                            polygon_coords.append(coords)  # Добавляем в список
                        else:
                            print(f"Пропущен некорректный элемент для {point_name}: {coords}")

                    if polygon_coords:  # Если есть координаты, создаём полигон
                        polygon = current_group.newpolygon(
                            name="Полигон")  # Один полигон для всей группы
                        outer_boundary = polygon.outerboundaryis
                        outer_coords = [(c[1], c[0], 0) for c in
                                        polygon_coords]  # Преобразуем: [lat, lon] -> [lon, lat, 0]
                        outer_boundary.coords = outer_coords  # Устанавливаем координаты
                        polygon.style = current_style  # Применяем стиль
                    else:
                        print(f"Для группы '{group}' нет валидных координат для полигона")
                elif 'Шурфы' in group:
                    current_style = pits_style
                    pits_group = kml.newfolder(name=group)
                    current_group = pits_group
                elif 'Центр' in group:
                    current_style = obj_center
                    center_group = kml.newfolder(name=group)
                    current_group = center_group
                for point_name, coords in point.items():
                    if current_group and system_check:
                        photo_point = current_group.newpoint(name=str(point_name),
                                                             coords=[
                                                                 (coords[1],
                                                                  coords[0])])  # TODO: менять их местами или нет?!
                        photo_point.style = current_style

            response = HttpResponse(kml.kml(), content_type='application/vnd.google-earth.kml+xml')
            filename = f'coordinates-{report_type}-{pk}.kml'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        return HttpResponse('Координаты для экспорта не выбраны', status=404)
    return JsonResponse({'response': f'Method {request.method} is not available for this URL'})
