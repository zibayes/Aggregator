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


def api_map_coordinates(request, report_type, pk):
    """API для получения координат одного отчёта"""
    report_models = {
        'act': Act,
        'scientific_report': ScientificReport,
        'tech_report': TechReport,
        'account_card': ObjectAccountCard,
        'commercial_offer': CommercialOffers,
        'geo_object': GeoObject,
    }
    model = report_models.get(report_type)
    if not model:
        return JsonResponse({'error': 'Invalid report type'}, status=400)

    report = get_object_or_404(model, id=pk)
    data = {
        'report_type': report_type,
        'report_id': pk,
        'report_name': get_report_name(report, report_type),
        'coordinates': report.coordinates_dict,
    }
    return JsonResponse(data)


def api_interactive_map_coordinates(request):
    """API для получения координат всех отчётов (общая карта)"""
    acts = Act.objects.filter(is_processing=False)
    scientific_reports = ScientificReport.objects.filter(is_processing=False)
    tech_reports = TechReport.objects.filter(is_processing=False)

    all_coordinates = {
        'Акты': {},
        'Научные отчёты': {},
        'Научно-технические отчёты': {}
    }

    for act in acts:
        all_coordinates['Акты'][act.id] = {
            'coordinates': act.coordinates_dict,
            'report_name': get_report_name(act, 'act')
        }
    for report in scientific_reports:
        all_coordinates['Научные отчёты'][report.id] = {
            'coordinates': report.coordinates_dict,
            'report_name': get_report_name(report, 'scientific_report')
        }
    for report in tech_reports:
        all_coordinates['Научно-технические отчёты'][report.id] = {
            'coordinates': report.coordinates_dict,
            'report_name': get_report_name(report, 'tech_report')
        }

    return JsonResponse({'all_coordinates': all_coordinates})


def get_report_name(report, report_type):
    """Вспомогательная функция для извлечения имени отчёта"""
    if report_type in ('act', 'scientific_report', 'tech_report'):
        if report.source_dict and len(report.source_dict) > 0:
            return report.source_dict[0]['origin_filename']
        else:
            return getattr(report, 'origin_filename', 'Неизвестный файл')
    elif report_type == 'account_card':
        if report.source_dict and len(report.source_dict) > 0:
            return report.source_dict[0]['origin_filename']
        else:
            return 'Учётная карта'
    else:
        return report.origin_filename


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
        # Получаем все отчеты
        acts = Act.objects.filter(is_processing=False)
        scientific_reports = ScientificReport.objects.filter(is_processing=False)
        tech_reports = TechReport.objects.filter(is_processing=False)

        all_coordinates = {
            'Акты': {},
            'Научные отчёты': {},
            'Научно-технические отчёты': {}
        }
        coordinates_to_download = {}

        # Собираем координаты из всех отчетов
        for act in acts:
            all_coordinates['Акты'][act.source_dict[0]['origin_filename']] = act.coordinates_dict
        for report in scientific_reports:
            all_coordinates['Научные отчёты'][report.source_dict[0]['origin_filename']] = report.coordinates_dict
        for report in tech_reports:
            all_coordinates['Научно-технические отчёты'][
                report.source_dict[0]['origin_filename']] = report.coordinates_dict

        # Фильтруем по выбранным в запросе
        for report_type, reports in all_coordinates.items():
            for report_name, groups in reports.items():
                for group, points in groups.items():
                    for point_name, coords in points.items():
                        key = f'{report_type}-{report_name}-{group}-{point_name}'
                        if key in request.POST:
                            if report_type not in coordinates_to_download:
                                coordinates_to_download[report_type] = {}
                            if report_name not in coordinates_to_download[report_type]:
                                coordinates_to_download[report_type][report_name] = {}
                            if group not in coordinates_to_download[report_type][report_name]:
                                coordinates_to_download[report_type][report_name][group] = {}
                            coordinates_to_download[report_type][report_name][group][point_name] = coords

        if coordinates_to_download:
            kml = simplekml.Kml()

            # Стили (такие же как в первой функции)
            styles = {
                'catalog': simplekml.Style(),
                'photos': simplekml.Style(),
                'pits': simplekml.Style(),
                'center': simplekml.Style()
            }
            styles['catalog'].iconstyle.color = simplekml.Color.blue
            styles['catalog'].polystyle.color = simplekml.Color.changealphaint(60, simplekml.Color.blue)
            styles['catalog'].linestyle.color = simplekml.Color.blue
            styles['catalog'].linestyle.width = 2
            styles['photos'].iconstyle.color = simplekml.Color.green
            styles['pits'].iconstyle.color = simplekml.Color.red
            styles['center'].iconstyle.color = simplekml.Color.yellow

            for report_type, reports in coordinates_to_download.items():
                report_type_folder = kml.newfolder(name=report_type)

                for report_name, groups in reports.items():
                    report_folder = report_type_folder.newfolder(name=report_name)

                    for group, points in groups.items():
                        current_style = None
                        current_group = None

                        # Определяем стиль и группу
                        if 'фотофиксации' in group:
                            current_style = styles['photos']
                            current_group = report_folder.newfolder(name=group)
                        elif 'Каталог' in group:
                            current_style = styles['catalog']
                            current_group = report_folder.newfolder(name=group)

                            # Полигон для каталога
                            polygon_coords = []
                            for coords in points.values():
                                if isinstance(coords, list) and len(coords) == 2:
                                    polygon_coords.append(coords)

                            if polygon_coords:
                                polygon = current_group.newpolygon(name="Полигон")
                                outer_coords = [(c[1], c[0], 0) for c in polygon_coords]
                                polygon.outerboundaryis.coords = outer_coords
                                polygon.style = current_style

                        elif 'Шурфы' in group:
                            current_style = styles['pits']
                            current_group = report_folder.newfolder(name=group)
                        elif 'Центр' in group:
                            current_style = styles['center']
                            current_group = report_folder.newfolder(name=group)

                        # Создаем точки
                        if current_group and 'Каталог' not in group:
                            for point_name, coords in points.items():
                                if isinstance(coords, list) and len(coords) == 2:
                                    point = current_group.newpoint(
                                        name=str(point_name),
                                        coords=[(coords[1], coords[0])]
                                    )
                                    point.style = current_style

            # Формируем ответ
            response = HttpResponse(kml.kml(), content_type='application/vnd.google-earth.kml+xml')
            filename = 'all_coordinates.kml'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        return HttpResponse('Координаты для экспорта не выбраны', status=404)
    return JsonResponse({'response': f'Method {request.method} is not available for this URL'})


def map(request, report_type, pk):
    report = None
    if report_type == 'account_card':
        report = get_object_or_404(ObjectAccountCard, id=pk)
        if report.source_dict and len(report.source_dict) > 0:
            report_name = report.source_dict[0]['origin_filename']
        else:
            report_name = 'Учётная карта'
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
        # Определяем тип отчета
        report_models = {
            'act': Act,
            'scientific_report': ScientificReport,
            'tech_report': TechReport,
            'account_card': ObjectAccountCard,
            'commercial_offer': CommercialOffers,
            'geo_object': GeoObject,
        }

        if report_type not in report_models:
            return HttpResponse("Некорректный тип отчёта", status=404)

        report = get_object_or_404(report_models[report_type], id=pk)
        coordinates = report.coordinates_dict if report else {}
        coordinates_to_download = {}

        # Фильтруем координаты по выбранным в запросе
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

            # Стили для разных типов точек
            styles = {
                'catalog': simplekml.Style(),
                'photos': simplekml.Style(),
                'pits': simplekml.Style(),
                'center': simplekml.Style()
            }
            styles['catalog'].iconstyle.color = simplekml.Color.blue
            styles['catalog'].polystyle.color = simplekml.Color.changealphaint(60, simplekml.Color.blue)
            styles['catalog'].linestyle.color = simplekml.Color.blue
            styles['catalog'].linestyle.width = 2
            styles['photos'].iconstyle.color = simplekml.Color.green
            styles['pits'].iconstyle.color = simplekml.Color.red
            styles['center'].iconstyle.color = simplekml.Color.yellow

            for group, points in coordinates_to_download.items():
                current_style = None
                current_group = None

                # Определяем стиль и группу по названию
                if 'фотофиксации' in group:
                    current_style = styles['photos']
                    current_group = kml.newfolder(name=group)
                elif 'Каталог' in group:
                    current_style = styles['catalog']
                    current_group = kml.newfolder(name=group)

                    # Создаем полигон для каталога
                    polygon_coords = []
                    for coords in points.values():
                        if isinstance(coords, list) and len(coords) == 2:
                            polygon_coords.append(coords)

                    if polygon_coords:
                        polygon = current_group.newpolygon(name="Полигон")
                        outer_coords = [(c[1], c[0], 0) for c in polygon_coords]
                        outer_coords.append((polygon_coords[0][1], polygon_coords[0][0], 0))
                        polygon.outerboundaryis.coords = outer_coords
                        polygon.style = current_style

                elif 'Шурфы' in group:
                    current_style = styles['pits']
                    current_group = kml.newfolder(name=group)
                elif 'Центр' in group:
                    current_style = styles['center']
                    current_group = kml.newfolder(name=group)

                # Создаем точки (кроме каталога, где создается только полигон)
                if current_group and 'Каталог' not in group:
                    for point_name, coords in points.items():
                        if isinstance(coords, list) and len(coords) == 2:
                            point = current_group.newpoint(
                                name=str(point_name),
                                coords=[(coords[1], coords[0])]
                            )
                            point.style = current_style

            # Формируем ответ с KML
            response = HttpResponse(kml.kml(), content_type='application/vnd.google-earth.kml+xml')
            filename = f'coordinates-{report_type}-{pk}.kml'
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        return HttpResponse('Координаты для экспорта не выбраны', status=404)
    return JsonResponse({'response': f'Method {request.method} is not available for this URL'})
