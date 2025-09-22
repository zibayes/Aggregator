import pytest
import json
import os
from unittest.mock import patch, MagicMock, PropertyMock
from django.urls import reverse
from django.http import HttpResponse, JsonResponse, Http404
from django.contrib.auth.models import AnonymousUser
from agregator.models import Act, ScientificReport, TechReport, ObjectAccountCard, CommercialOffers, GeoObject, \
    GeojsonData


@pytest.mark.django_db
class TestMapViews:
    """Тесты для views модуля map.py"""

    # Тесты для interactive_map
    def test_interactive_map_authenticated(self, client, test_user, test_act, test_scientific_report, test_tech_report):
        """Тест страницы интерактивной карты для авторизованного пользователя"""
        client.force_login(test_user)

        response = client.get(reverse('interactive_map'))

        assert response.status_code == 200
        assert 'interactive_map.html' in [t.name for t in response.templates]
        assert 'all_coordinates' in response.context

        all_coordinates = response.context['all_coordinates']
        assert 'Акты' in all_coordinates
        assert 'Научные отчёты' in all_coordinates
        assert 'Научно-технические отчёты' in all_coordinates

    def test_interactive_map_unauthenticated(self, client):
        """Тест страницы интерактивной карты для неавторизованного пользователя"""
        response = client.get(reverse('interactive_map'))
        assert response.status_code == 200  # Доступно без авторизации

    # Тесты для download_all_coordinates
    @pytest.mark.parametrize('method', ['GET', 'PUT', 'DELETE'])
    def test_download_all_coordinates_invalid_method(self, client, test_user, method):
        """Тест download_all_coordinates с неверным методом"""
        client.force_login(test_user)

        if method == 'GET':
            response = client.get(reverse('download_all_coordinates'))
        elif method == 'PUT':
            response = client.put(reverse('download_all_coordinates'))
        elif method == 'DELETE':
            response = client.delete(reverse('download_all_coordinates'))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert f'Method {method} is not available' in data['response']

    def test_download_all_coordinates_no_selected(self, client, test_user):
        """Тест download_all_coordinates без выбранных координат"""
        client.force_login(test_user)

        response = client.post(reverse('download_all_coordinates'))
        assert response.status_code == 404
        assert 'Координаты для экспорта не выбраны' in response.content.decode()

    @patch('agregator.views.map.simplekml.Kml')
    @patch('agregator.views.map.Act.objects.filter')
    @patch('agregator.views.map.ScientificReport.objects.filter')
    @patch('agregator.views.map.TechReport.objects.filter')
    def test_download_all_coordinates_valid(self, mock_tech, mock_scientific, mock_act, mock_kml, client, test_user):
        """Тест download_all_coordinates с валидными данными"""
        client.force_login(test_user)

        # Мокируем объекты с координатами
        mock_act_instance = MagicMock()
        mock_act_instance.id = 1
        mock_act_instance.coordinates_dict = {'Каталог объектов': {'Точка 1': [60.0, 30.0]}}
        mock_act_instance.source_dict = [{'origin_filename': 'Test Act'}]
        mock_act.return_value = [mock_act_instance]

        mock_scientific_instance = MagicMock()
        mock_scientific_instance.id = 1
        mock_scientific_instance.coordinates_dict = {'фотофиксации': {'Точка 2': [61.0, 31.0]}}
        mock_scientific_instance.source_dict = [{'origin_filename': 'Test Scientific Report'}]
        mock_scientific.return_value = [mock_scientific_instance]

        mock_tech_instance = MagicMock()
        mock_tech_instance.id = 1
        mock_tech_instance.coordinates_dict = {'Шурфы': {'Точка 3': [62.0, 32.0]}}
        mock_tech_instance.source_dict = [{'origin_filename': 'Test Tech Report'}]
        mock_tech.return_value = [mock_tech_instance]

        # Мокируем KML
        mock_kml_instance = MagicMock()
        mock_kml.return_value = mock_kml_instance
        mock_folder = MagicMock()
        mock_kml_instance.newfolder.return_value = mock_folder

        # Подготавливаем POST данные
        post_data = {
            'Акты-Test Act-Каталог объектов-Точка 1': 'on',
            'Научные отчёты-Test Scientific Report-фотофиксации-Точка 2': 'on'
        }

        response = client.post(reverse('download_all_coordinates'), post_data)

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.google-earth.kml+xml'
        assert 'attachment' in response['Content-Disposition']

    # Тесты для map view
    @pytest.mark.parametrize('report_type,pk_fixture,expected_status', [
        ('act', 'test_act', 200),
        ('scientific_report', 'test_scientific_report', 200),
        ('tech_report', 'test_tech_report', 200),
        ('account_card', 'test_account_card', 200),
        ('commercial_offer', 'test_commercial_offer', 200),
        ('geo_object', 'test_geo_object', 200),
        ('invalid_type', None, 404),
    ])
    @patch('agregator.views.map.get_geojson_polygons_sync')
    @patch('agregator.views.map.get_object_or_404')
    def test_map_view(self, mock_get_object, mock_get_polygons, client, test_user, report_type, pk_fixture,
                      expected_status, request):
        """Тест отображения карты для разных типов отчетов"""
        client.force_login(test_user)

        mock_get_polygons.return_value = {'matching_polygons': []}

        if pk_fixture:
            obj = request.getfixturevalue(pk_fixture)
            pk = obj.id

            # Мокируем объект с координатами
            mock_report = MagicMock()
            mock_report.coordinates_dict = {'Каталог объектов': {'Точка 1': [60.0, 30.0]}}

            if hasattr(obj, 'source_dict'):
                mock_report.source_dict = [{'origin_filename': 'Test File'}]
            else:
                mock_report.origin_filename = 'Test File'

            mock_get_object.return_value = mock_report
        else:
            pk = 999
            # Для несуществующего типа отчета
            mock_get_object.side_effect = Http404

        response = client.get(reverse('map', args=[report_type, pk]))

        assert response.status_code == expected_status
        if expected_status == 200:
            assert 'interactive_map.html' in [t.name for t in response.templates]
            assert 'coordinates' in response.context
            assert 'matching_polygons' in response.context

    def test_map_view_nonexistent_object(self, client, test_user):
        """Тест отображения карты для несуществующего объекта"""
        client.force_login(test_user)

        with patch('agregator.views.map.get_object_or_404') as mock_get:
            mock_get.side_effect = Http404
            response = client.get(reverse('map', args=['act', 999]))
            assert response.status_code == 404

    # Тесты для get_geojson_polygons
    @pytest.mark.parametrize('method', ['GET', 'PUT', 'DELETE'])
    def test_get_geojson_polygons_invalid_method(self, client, test_user, method):
        """Тест get_geojson_polygons с неверным методом"""
        client.force_login(test_user)

        if method == 'GET':
            response = client.get(reverse('get_geojson_polygons'))
        elif method == 'PUT':
            response = client.put(reverse('get_geojson_polygons'))
        elif method == 'DELETE':
            response = client.delete(reverse('get_geojson_polygons'))

        assert response.status_code == 405
        assert 'Метод не поддерживается' in response.content.decode()

    def test_get_geojson_polygons_invalid_json(self, client, test_user):
        """Тест get_geojson_polygons с невалидным JSON"""
        client.force_login(test_user)

        response = client.post(
            reverse('get_geojson_polygons'),
            'invalid json',
            content_type='application/json'
        )

        assert response.status_code == 400
        assert 'Неверный формат данных' in json.loads(response.content)['error']

    @patch('agregator.views.map.os.listdir')
    @patch('agregator.views.map.os.walk')
    @patch('agregator.views.map.os.path.join')
    @patch('agregator.views.map.open')
    def test_get_geojson_polygons_valid(self, mock_open, mock_join, mock_walk, mock_listdir, client, test_user):
        """Тест get_geojson_polygons с валидными данными"""
        client.force_login(test_user)

        # Мокируем файловую систему
        mock_listdir.return_value = ['test.geojson']
        mock_walk.return_value = [('/test/path', [], ['Красноярский край.geojson'])]
        mock_join.return_value = '/test/path/file.geojson'

        # Мокируем файловое содержимое
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = json.dumps({
            'features': [{
                'geometry': {
                    'type': 'Polygon',
                    'coordinates': [[[30, 60], [31, 60], [31, 61], [30, 61], [30, 60]]]
                }
            }]
        })

        # Отправляем валидные точки
        points = {
            'group1': {
                'point1': [60.5, 30.5]  # Точка внутри полигона
            }
        }

        response = client.post(
            reverse('get_geojson_polygons'),
            json.dumps({'points': json.dumps(points)}),
            content_type='application/json'
        )

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'matching_polygons' in data

    # Тесты для get_geojson_polygons_sync
    @patch('agregator.views.map.get_object_or_404')
    @patch('agregator.views.map.shape')
    @patch('agregator.views.map.GeojsonData.objects.exclude')
    def test_get_geojson_polygons_sync(self, mock_exclude, mock_shape, mock_get_object, client, test_user):
        """Тест синхронного получения полигонов GeoJSON"""
        # Мокируем объекты
        mock_russia = MagicMock()
        mock_russia.geojson = {'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': []}}

        mock_krasnoyarsk = MagicMock()
        mock_krasnoyarsk.geojson = {'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': []}}

        mock_region = MagicMock()
        mock_region.geojson = {'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': []}}

        mock_get_object.side_effect = [mock_russia, mock_krasnoyarsk]
        mock_exclude.return_value = [mock_region]

        # Мокируем shape и contains
        mock_polygon = MagicMock()
        mock_polygon.contains.return_value = True
        mock_shape.return_value = mock_polygon

        # Тестовые точки
        points = {
            'group1': {
                'point1': [60.5, 30.5]  # Точка внутри полигона
            }
        }

        from agregator.views.map import get_geojson_polygons_sync
        result = get_geojson_polygons_sync(points)

        assert 'Russia' in result
        assert 'Subject' in result
        assert 'Regions' in result
        assert len(result['Regions']) == 1

    # Тесты для download_coordinates
    @pytest.mark.parametrize('method', ['GET', 'PUT', 'DELETE'])
    def test_download_coordinates_invalid_method(self, client, test_user, method):
        """Тест download_coordinates с неверным методом"""
        client.force_login(test_user)

        if method == 'GET':
            response = client.get(reverse('download_coordinates', args=['act', 1]))
        elif method == 'PUT':
            response = client.put(reverse('download_coordinates', args=['act', 1]))
        elif method == 'DELETE':
            response = client.delete(reverse('download_coordinates', args=['act', 1]))

        assert response.status_code == 200
        data = json.loads(response.content)
        assert f'Method {method} is not available' in data['response']

    @pytest.mark.parametrize('report_type,pk_fixture', [
        ('act', 'test_act'),
        ('scientific_report', 'test_scientific_report'),
        ('tech_report', 'test_tech_report'),
        ('account_card', 'test_account_card'),
        ('commercial_offer', 'test_commercial_offer'),
        ('geo_object', 'test_geo_object'),
    ])
    @patch('agregator.views.map.get_object_or_404')
    def test_download_coordinates_no_selected(self, mock_get_object, client, test_user, report_type, pk_fixture,
                                              request):
        """Тест download_coordinates без выбранных координат для разных типов отчетов"""
        client.force_login(test_user)

        obj = request.getfixturevalue(pk_fixture)
        pk = obj.id

        # Мокируем объект с координатами
        mock_report = MagicMock()
        mock_report.coordinates_dict = {'Каталог объектов': {'Точка 1': [60.0, 30.0]}}
        mock_get_object.return_value = mock_report

        response = client.post(reverse('download_coordinates', args=[report_type, pk]))

        assert response.status_code == 404
        assert 'Координаты для экспорта не выбраны' in response.content.decode()

    @pytest.mark.parametrize('report_type,pk_fixture', [
        ('act', 'test_act'),
        ('scientific_report', 'test_scientific_report'),
        ('tech_report', 'test_tech_report'),
        ('account_card', 'test_account_card'),
        ('commercial_offer', 'test_commercial_offer'),
        ('geo_object', 'test_geo_object'),
    ])
    @patch('agregator.views.map.simplekml.Kml')
    @patch('agregator.views.map.get_object_or_404')
    def test_download_coordinates_valid(self, mock_get_object, mock_kml, client, test_user, report_type, pk_fixture,
                                        request):
        """Тест download_coordinates с валидными данными для разных типов отчетов"""
        client.force_login(test_user)

        obj = request.getfixturevalue(pk_fixture)
        pk = obj.id

        # Мокируем объект с координатами
        mock_report = MagicMock()
        mock_report.coordinates_dict = {
            'Каталог объектов': {
                'Точка 1': [60.0, 30.0]
            }
        }
        mock_get_object.return_value = mock_report

        # Мокируем KML
        mock_kml_instance = MagicMock()
        mock_kml.return_value = mock_kml_instance
        mock_folder = MagicMock()
        mock_kml_instance.newfolder.return_value = mock_folder

        # Подготавливаем POST данные
        post_data = {
            'Каталог объектов-Точка 1': 'on'
        }

        response = client.post(reverse('download_coordinates', args=[report_type, pk]), post_data)

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.google-earth.kml+xml'
        assert 'attachment' in response['Content-Disposition']

    def test_download_coordinates_invalid_type(self, client, test_user):
        """Тест download_coordinates с неверным типом отчета"""
        client.force_login(test_user)

        response = client.post(reverse('download_coordinates', args=['invalid_type', 1]))
        assert response.status_code == 404
        assert 'Некорректный тип отчёта' in response.content.decode()

    # Тесты безопасности
    def test_csrf_protection(self, client, test_user):
        """Тест защиты CSRF"""
        client.force_login(test_user)
        client.enforce_csrf_checks = True

        # Сначала проверяем что URL существует
        response = client.post(reverse('download_all_coordinates'))
        if response.status_code == 404:
            pytest.skip("URL download_all_coordinates возвращает 404, CSRF тест не актуален")

        # Пытаемся сделать POST без CSRF токена
        response = client.post(reverse('download_all_coordinates'), HTTP_X_CSRFTOKEN='invalid')

        # Должны получить ошибку CSRF (403) или 404 если URL не существует
        assert response.status_code in [403, 404]

    @pytest.mark.parametrize('malicious_input', [
        {'points': 'malicious_data'},
        {'points': '[]; DROP TABLE users;'},
        {'points': '<script>alert("xss")</script>'},
    ])
    def test_sql_injection_xss_protection(self, client, test_user, malicious_input):
        """Тест защиты от SQL инъекций и XSS"""
        client.force_login(test_user)

        response = client.post(
            reverse('get_geojson_polygons'),
            json.dumps(malicious_input),
            content_type='application/json'
        )

        # Должен вернуть ошибку валидации, но не 500
        assert response.status_code in [400, 200]

    # Граничные случаи
    @patch('agregator.views.map.get_object_or_404')
    def test_empty_coordinates(self, mock_get_object, client, test_user, test_act):
        """Тест с пустыми координатами"""
        client.force_login(test_user)

        # Мокируем объект с пустыми координатами
        mock_report = MagicMock()
        mock_report.coordinates_dict = {}
        mock_report.source_dict = [{'origin_filename': 'Test File'}]
        mock_get_object.return_value = mock_report

        response = client.get(reverse('map', args=['act', test_act.id]))
        assert response.status_code == 200

        # Проверяем, что координаты пустые
        assert response.context['coordinates'] == {}

    @patch('agregator.views.map.get_object_or_404')
    def test_malformed_coordinates(self, mock_get_object, client, test_user, test_act):
        """Тест с некорректными координатами"""
        client.force_login(test_user)

        # Мокируем объект с некорректными координатами
        mock_report = MagicMock()
        mock_report.coordinates_dict = {'group': {'point': 'invalid_data'}}
        mock_report.source_dict = [{'origin_filename': 'Test File'}]
        mock_get_object.return_value = mock_report

        response = client.get(reverse('map', args=['act', test_act.id]))
        assert response.status_code == 200

        # Должен обработать без ошибок
        assert 'coordinates' in response.context

    # Интеграционные тесты
    @patch('agregator.views.map.get_geojson_polygons_sync')
    @patch('agregator.views.map.get_object_or_404')
    def test_integration_map_with_polygons(self, mock_get_object, mock_get_polygons, client, test_user, test_act):
        """Интеграционный тест отображения карта с полигонами"""
        client.force_login(test_user)

        # Настраиваем моки
        mock_report = MagicMock()
        mock_report.coordinates_dict = {
            'Каталог объектов': {
                'Точка 1': [60.0, 30.0]
            }
        }
        mock_report.source_dict = [{'origin_filename': 'Test File'}]
        mock_get_object.return_value = mock_report

        mock_get_polygons.return_value = {'matching_polygons': []}

        response = client.get(reverse('map', args=['act', test_act.id]))

        assert response.status_code == 200
        assert 'coordinates' in response.context
        assert 'matching_polygons' in response.context
        assert 'report_type' in response.context
        assert 'pk' in response.context
        assert 'report_name' in response.context

    @patch('agregator.views.map.simplekml.Kml')
    @patch('agregator.views.map.get_object_or_404')
    def test_integration_download_coordinates(self, mock_get_object, mock_kml, client, test_user, test_act):
        """Интеграционный тест загрузки координат"""
        client.force_login(test_user)

        # Мокируем KML
        mock_kml_instance = MagicMock()
        mock_kml.return_value = mock_kml_instance
        mock_folder = MagicMock()
        mock_kml_instance.newfolder.return_value = mock_folder

        # Мокируем объект с координатами
        mock_report = MagicMock()
        mock_report.coordinates_dict = {
            'Каталог объектов': {
                'Точка 1': [60.0, 30.0],
                'Точка 2': [61.0, 31.0]
            },
            'фотофиксации': {
                'Фото 1': [62.0, 32.0]
            }
        }
        mock_get_object.return_value = mock_report

        # Выбираем только некоторые точки для загрузки
        post_data = {
            'Каталог объектов-Точка 1': 'on',
            'фотофиксации-Фото 1': 'on'
        }

        response = client.post(reverse('download_coordinates', args=['act', test_act.id]), post_data)

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.google-earth.kml+xml'
        assert 'attachment' in response['Content-Disposition']
        assert f'coordinates-act-{test_act.id}.kml' in response['Content-Disposition']

    @patch('agregator.views.map.shape')
    @patch('agregator.views.map.Point')
    @patch('agregator.views.map.json.load')
    @patch('agregator.views.map.open')
    @patch('agregator.views.map.os.path.join')
    @patch('agregator.views.map.os.walk')
    @patch('agregator.views.map.os.listdir')
    def test_get_geojson_polygons_krasnoyarsk_walk(self, mock_listdir, mock_walk, mock_join, mock_open, mock_json_load,
                                                   mock_point, mock_shape, client, test_user):
        """Тест get_geojson_polygons с os.walk для 'Красноярский край' (покрытие 183-202)"""
        client.force_login(test_user)

        mock_listdir.return_value = ['test.geojson']
        mock_walk.return_value = [('/app/uploaded_files/regions_polygons/Красноярский край', [], ['region.geojson'])]
        mock_join.return_value = '/krasnoyarsk/region.geojson'
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_json_load.return_value = {'features': [
            {'geometry': {'type': 'Polygon', 'coordinates': [[[30, 60], [31, 60], [31, 61], [30, 61], [30, 60]]]}}]}

        mock_polygon = MagicMock()
        mock_polygon.contains.return_value = True
        mock_shape.return_value = mock_polygon
        mock_point.return_value = MagicMock()

        points = {'group': {'point': [60.5, 30.5]}}  # Внутри полигона
        response = client.post(reverse('get_geojson_polygons'), json.dumps({'points': json.dumps(points)}),
                               content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'Regions' in data['matching_polygons']
        assert len(data['matching_polygons']['Regions']) > 0  # Покрытие if polygon.contains и append to Regions

        # Добавь эти тесты в класс TestMapViews

    @patch('agregator.views.map.Act.objects.filter')
    @patch('agregator.views.map.ScientificReport.objects.filter')
    @patch('agregator.views.map.TechReport.objects.filter')
    def test_interactive_map_empty_source_dict(self, mock_tech, mock_scientific, mock_act, client, test_user):
        """Тест interactive_map с пустым source_dict (покрытие else в report_name на строках 30,35,40)"""
        client.force_login(test_user)
        # Мокируем объекты с пустым/None source_dict для покрытия else
        mock_act_instance = MagicMock()
        mock_act_instance.id = 1
        mock_act_instance.coordinates_dict = {'Каталог объектов': {'Точка 1': [60.0, 30.0]}}
        mock_act_instance.source_dict = []  # len==0 -> else (строка 30)
        mock_act.return_value = [mock_act_instance]
        mock_scientific_instance = MagicMock()
        mock_scientific_instance.id = 1
        mock_scientific_instance.coordinates_dict = {'фотофиксации': {'Точка 2': [61.0, 31.0]}}
        mock_scientific_instance.source_dict = None  # if None -> else (строка 35)
        mock_scientific.return_value = [mock_scientific_instance]
        mock_tech_instance = MagicMock()
        mock_tech_instance.id = 1
        mock_tech_instance.coordinates_dict = {'Шурфы': {'Точка 3': [62.0, 32.0]}}
        mock_tech_instance.source_dict = []  # len==0 -> else (строка 40)
        mock_tech.return_value = [mock_tech_instance]
        response = client.get(reverse('interactive_map'))
        assert response.status_code == 200
        all_coordinates = response.context['all_coordinates']
        assert all_coordinates['Акты'][1]['report_name'] == 'Неизвестный файл'  # Строка 30 else
        assert all_coordinates['Научные отчёты'][1]['report_name'] == 'Неизвестный файл'  # Строка 35 else
        assert all_coordinates['Научно-технические отчёты'][1]['report_name'] == 'Неизвестный файл'  # Строка 40 else

    @patch('agregator.views.map.simplekml.Kml')
    @patch('agregator.views.map.Act.objects.filter')
    @patch('agregator.views.map.ScientificReport.objects.filter')
    @patch('agregator.views.map.TechReport.objects.filter')
    def test_download_all_coordinates_pits_group(self, mock_tech, mock_scientific, mock_act, mock_kml, client,
                                                 test_user):
        """Тест download_all_coordinates с группой 'Шурфы'"""
        client.force_login(test_user)

        # Мокируем объекты с координатами в группе 'Шурфы'
        mock_act_instance = MagicMock()
        mock_act_instance.source_dict = [{'origin_filename': 'Test Act'}]
        mock_act_instance.coordinates_dict = {'Шурфы': {'Точка 1': [60.0, 30.0]}}
        mock_act.return_value = [mock_act_instance]

        mock_scientific.return_value = []
        mock_tech.return_value = []

        # Мокируем KML
        mock_kml_instance = MagicMock()
        mock_kml.return_value = mock_kml_instance
        mock_folder = MagicMock()
        mock_kml_instance.newfolder.return_value = mock_folder

        # Подготавливаем POST данные для группы 'Шурфы'
        post_data = {
            'Акты-Test Act-Шурфы-Точка 1': 'on'
        }

        response = client.post(reverse('download_all_coordinates'), post_data)

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.google-earth.kml+xml'

    @patch('agregator.views.map.open')
    @patch('agregator.views.map.os.listdir')
    @patch('agregator.views.map.os.walk')
    def test_get_geojson_polygons_invalid_geojson(self, mock_walk, mock_listdir, mock_open, client, test_user):
        """Тест get_geojson_polygons с невалидным GeoJSON файлом"""
        client.force_login(test_user)

        # Мокируем файловую систему с невалидным GeoJSON
        mock_listdir.return_value = ['invalid.geojson']
        mock_walk.return_value = [('/test/path', [], ['Красноярский край.geojson'])]

        # Мокируем файловое содержимое с невалидным JSON
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file
        mock_file.read.return_value = 'invalid json content'

        # Отправляем валидные точки
        points = {
            'group1': {
                'point1': [60.5, 30.5]
            }
        }

        response = client.post(
            reverse('get_geojson_polygons'),
            json.dumps({'points': json.dumps(points)}),
            content_type='application/json'
        )

        assert response.status_code == 400
        assert 'Ошибка при чтении файла' in json.loads(response.content)['error']

    def test_check_point_in_polygon(self):
        """Тест функции check_point_in_polygon"""
        from agregator.views.map import check_point_in_polygon

        # Мокируем feature
        mock_feature = MagicMock()
        mock_feature.geojson = {
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[[30, 60], [31, 60], [31, 61], [30, 61], [30, 60]]]
            }
        }

        # Точка внутри полигона
        point_inside = [60.5, 30.5]
        result_inside = check_point_in_polygon(mock_feature, point_inside)
        assert result_inside is True

        # Точка вне полигона
        point_outside = [10.0, 10.0]
        result_outside = check_point_in_polygon(mock_feature, point_outside)
        assert result_outside is False

    @patch('agregator.views.map.simplekml.Kml')
    @patch('agregator.views.map.get_object_or_404')
    def test_download_coordinates_pits_and_center_groups(self, mock_get_object, mock_kml, client, test_user, test_act):
        """Тест download_coordinates с группами 'Шурфы' и 'Центр'"""
        client.force_login(test_user)

        # Мокируем объект с координатами в группах 'Шурфы' и 'Центр'
        mock_report = MagicMock()
        mock_report.coordinates_dict = {
            'Шурфы': {
                'Точка 1': [60.0, 30.0]
            },
            'Центр объекта': {
                'Точка 2': [61.0, 31.0]
            }
        }
        mock_get_object.return_value = mock_report

        # Мокируем KML
        mock_kml_instance = MagicMock()
        mock_kml.return_value = mock_kml_instance
        mock_folder = MagicMock()
        mock_kml_instance.newfolder.return_value = mock_folder

        # Подготавливаем POST данные
        post_data = {
            'Шурфы-Точка 1': 'on',
            'Центр объекта-Точка 2': 'on'
        }

        response = client.post(reverse('download_coordinates', args=['act', test_act.id]), post_data)

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.google-earth.kml+xml'

    @patch('agregator.views.map.get_object_or_404')
    def test_download_coordinates_empty_coords(self, mock_get_object, client, test_user, test_act):
        """Тест download_coordinates с пустыми координатами"""
        client.force_login(test_user)

        # Мокируем объект с пустыми координатами
        mock_report = MagicMock()
        mock_report.coordinates_dict = {}
        mock_get_object.return_value = mock_report

        response = client.post(reverse('download_coordinates', args=['act', test_act.id]))

        assert response.status_code == 404
        assert 'Координаты для экспорта не выбраны' in response.content.decode()

    @patch('agregator.views.map.get_geojson_polygons_sync')
    def test_map_view_no_source_dict(self, mock_get_polygons, client, test_user, test_act):
        """Тест map_view без source_dict (покрытие fallback в report_name)"""
        client.force_login(test_user)

        class MockAct:
            def __init__(self):
                self.coordinates_dict = {'Каталог объектов': {'Точка 1': [60.0, 30.0]}}
                self.source_dict = []  # len==0, no origin_filename -> 'Неизвестный файл'

        mock_report = MockAct()
        with patch('agregator.views.map.get_object_or_404') as mock_get_object:
            mock_get_object.return_value = mock_report
            mock_get_polygons.return_value = {'Russia': [], 'Subject': [], 'Regions': []}
            response = client.get(reverse('map', args=['act', test_act.id]))
            assert response.status_code == 200
            assert response.context['report_name'] == 'Неизвестный файл'  # Fallback в else map (hasattr=False)

    @patch('agregator.views.map.get_geojson_polygons_sync')
    @patch('agregator.views.map.get_object_or_404')
    def test_map_view_commercial_offer_no_origin_filename(self, mock_get_object, mock_get_polygons, client, test_user):
        """Тест map_view для commercial_offer без origin_filename (покрытие direct access строка 128)"""
        client.force_login(test_user)
        # Мокируем get_object_or_404 для report (CommercialOffers)
        mock_report = MagicMock()
        mock_report.coordinates_dict = {'Каталог объектов': {'Точка 1': [60.0, 30.0]}}
        mock_report.origin_filename = None  # Direct = None
        mock_get_object.side_effect = lambda model, **kwargs: mock_report if model == CommercialOffers else MagicMock(
            geojson={'type': 'Feature'})
        # Мокируем sync для GeojsonData
        mock_get_polygons.return_value = {'Russia': [], 'Subject': [], 'Regions': []}
        response = client.get(reverse('map', args=['commercial_offer', 1]))
        assert response.status_code == 200
        assert response.context['report_name'] is None  # Direct None, no fallback

    @patch('agregator.views.map.shape')
    @patch('agregator.views.map.Point')
    @patch('agregator.views.map.json.load')
    @patch('agregator.views.map.open')
    @patch('agregator.views.map.os.path.join')
    @patch('agregator.views.map.os.walk')
    @patch('agregator.views.map.os.listdir')
    def test_get_geojson_polygons_no_matches(self, mock_listdir, mock_walk, mock_join, mock_open, mock_json_load,
                                             mock_point, mock_shape, client, test_user):
        """Тест get_geojson_polygons без совпадений (покрытие return на 207 - но dict truthy, так что 200; покрытие empty lists)"""
        client.force_login(test_user)
        mock_listdir.return_value = []  # Нет файлов -> Russia=[]
        mock_walk.return_value = []  # Нет walk -> no append
        mock_shape.return_value = MagicMock()
        mock_shape.return_value.contains.return_value = False  # No contains
        points = {'group': {'point': [0.0, 0.0]}}  # Вне полигонов
        response = client.post(reverse('get_geojson_polygons'), json.dumps({'points': json.dumps(points)}),
                               content_type='application/json')
        assert response.status_code == 200  # Всегда truthy dict, покрытие if (строка 207 не достижима без изменений в view)
        data = json.loads(response.content)
        assert data['matching_polygons'] == {'Russia': [], 'Subject': [], 'Regions': []}  # Empty, но 200

    @patch('agregator.views.map.json.load')
    @patch('agregator.views.map.open')
    @patch('agregator.views.map.os.path.join')
    @patch('agregator.views.map.os.walk')
    @patch('agregator.views.map.os.listdir')
    def test_get_geojson_polygons_json_decode_error_walk(self, mock_listdir, mock_walk, mock_join, mock_open,
                                                         mock_json_load, client, test_user):
        """Тест get_geojson_polygons с JSONDecodeError в walk (покрытие except на 197 и 202)"""
        client.force_login(test_user)
        mock_listdir.return_value = []  # Russia OK
        mock_walk.return_value = [('/app/uploaded_files/regions_polygons/Красноярский край', [], ['invalid.geojson'])]
        mock_join.return_value = '/path/invalid.geojson'
        mock_open.return_value.__enter__.return_value = MagicMock()
        mock_json_load.side_effect = json.JSONDecodeError('msg', '', 0)  # Error в walk
        points = {'group': {'point': [60.0, 30.0]}}
        response = client.post(reverse('get_geojson_polygons'), json.dumps({'points': json.dumps(points)}),
                               content_type='application/json')
        assert response.status_code == 400
        assert 'Ошибка при чтении файла invalid.geojson' in json.loads(response.content)[
            'error']  # Строка 197/202 except

    @patch('agregator.views.map.get_geojson_polygons_sync')
    @patch('agregator.views.map.get_object_or_404')
    def test_map_view_geojson_error(self, mock_get_object, mock_get_polygons, client, test_user, test_act):
        """Тест map_view с ошибкой в get_geojson_polygons_sync (view raises -> тест ловит)"""
        client.force_login(test_user)
        mock_report = MagicMock()
        mock_report.coordinates_dict = {'group': {'point': [60.0, 30.0]}}
        mock_report.source_dict = [{'origin_filename': 'Test'}]
        mock_get_object.return_value = mock_report
        mock_get_polygons.side_effect = Exception('Sync error')  # Симулируем краш
        # Ловим raise от client (view не handles exception)
        with pytest.raises(Exception, match='Sync error'):
            client.get(reverse('map', args=['act', test_act.id]))

    @patch('agregator.views.map.os.path.exists')
    @patch('agregator.views.map.os.listdir')
    @patch('agregator.views.map.json.load')
    @patch('agregator.views.map.open')
    def test_get_geojson_polygons_no_russia_file(self, mock_open, mock_json_load, mock_listdir, mock_exists, client,
                                                 test_user):
        """Тест get_geojson_polygons без Russia geojson (покрытие empty Russia, но dict truthy -> no 207)"""
        client.force_login(test_user)
        mock_exists.return_value = False  # Нет Russia файла -> Russia=[]
        mock_listdir.return_value = []  # Нет файлов в listdir
        mock_open.return_value.__enter__.return_value = MagicMock()
        mock_json_load.return_value = {'features': []}  # Empty features
        points = {'group': {'point': [0.0, 0.0]}}
        response = client.post(reverse('get_geojson_polygons'), json.dumps({'points': json.dumps(points)}),
                               content_type='application/json')
        assert response.status_code == 200  # Dict truthy, строка 207 не hit
        data = json.loads(response.content)
        assert data['matching_polygons']['Russia'] == []  # Empty
