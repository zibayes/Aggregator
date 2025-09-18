import pytest
import json
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from unittest.mock import patch, MagicMock
from django.contrib import messages
from django.core.files.uploadedfile import SimpleUploadedFile

User = get_user_model()


@pytest.mark.django_db
class TestEditViews:
    """Тесты для функций редактирования"""

    # Параметризированные тесты для GET запросов всех edit views
    @pytest.mark.parametrize('view_name, model_fixture, template_name', [
        ('acts_edit', 'test_act', 'act_edit.html'),
        ('scientific_reports_edit', 'test_scientific_report', 'scientific_report_edit.html'),
        ('tech_reports_edit', 'test_tech_report', 'tech_report_edit.html'),
        ('open_lists_edit', 'test_open_list', 'open_list_edit.html'),
        ('account_cards_edit', 'test_account_card', 'account_card_edit.html'),
        ('commercial_offers_edit', 'test_commercial_offer', 'commercial_offer_edit.html'),
        ('geo_objects_edit', 'test_geo_object', 'geo_object_edit.html'),
    ])
    def test_edit_views_get_authenticated_owner(self, client, test_user, request,
                                                view_name, model_fixture, template_name):
        """Тест GET запросов для авторизованного владельца"""
        client.login(username='testuser', password='testpass123')
        model_instance = request.getfixturevalue(model_fixture)

        response = client.get(reverse(view_name, kwargs={'pk': model_instance.id}))

        assert response.status_code == 200
        assert template_name in [t.name for t in response.templates]

    @pytest.mark.parametrize('view_name, model_fixture', [
        ('archaeological_heritage_sites_edit', 'test_archaeological_heritage_site'),
        ('identified_archaeological_heritage_sites_edit', 'test_identified_heritage_site'),
    ])
    def test_edit_views_get_authenticated_owner_for_admin_only(self, client, test_user, request, view_name,
                                                               model_fixture):
        """Тест что обычный пользователь не может редактировать admin-only объекты"""
        client.login(username='testuser', password='testpass123')
        model_instance = request.getfixturevalue(model_fixture)

        response = client.get(reverse(view_name, kwargs={'pk': model_instance.id}))
        assert response.status_code == 403

    @pytest.mark.parametrize('view_name, model_fixture, template_name', [
        ('archaeological_heritage_sites_edit', 'test_archaeological_heritage_site',
         'archaeological_heritage_site_edit.html'),
        ('identified_archaeological_heritage_sites_edit', 'test_identified_heritage_site',
         'identified_archaeological_heritage_site_edit.html'),
    ])
    def test_edit_views_get_authenticated_admin(self, client, admin_user, request, view_name, model_fixture,
                                                template_name):
        """Тест GET запросов для админа (admin-only объекты)"""
        client.login(username='admin', password='adminpass123')
        model_instance = request.getfixturevalue(model_fixture)

        response = client.get(reverse(view_name, kwargs={'pk': model_instance.id}))

        assert response.status_code == 200
        assert template_name in [t.name for t in response.templates]

    @pytest.mark.parametrize('view_name, model_fixture', [
        ('acts_edit', 'test_act'),
        ('scientific_reports_edit', 'test_scientific_report'),
        ('tech_reports_edit', 'test_tech_report'),
        ('open_lists_edit', 'test_open_list'),
        ('archaeological_heritage_sites_edit', 'test_archaeological_heritage_site'),
        ('identified_archaeological_heritage_sites_edit', 'test_identified_heritage_site'),
        ('account_cards_edit', 'test_account_card'),
        ('commercial_offers_edit', 'test_commercial_offer'),
        ('geo_objects_edit', 'test_geo_object'),
    ])
    def test_edit_views_get_unauthenticated(self, client, request, view_name, model_fixture):
        """Тест GET запросов для неавторизованного пользователя"""
        model_instance = request.getfixturevalue(model_fixture)

        response = client.get(reverse(view_name, kwargs={'pk': model_instance.id}))

        assert response.status_code == 302  # Редирект на логин

    @pytest.mark.parametrize('view_name, model_fixture', [
        ('acts_edit', 'test_act'),
        ('scientific_reports_edit', 'test_scientific_report'),
        ('tech_reports_edit', 'test_tech_report'),
        ('open_lists_edit', 'test_open_list'),
        ('archaeological_heritage_sites_edit', 'test_archaeological_heritage_site'),
        ('identified_archaeological_heritage_sites_edit', 'test_identified_heritage_site'),
        ('account_cards_edit', 'test_account_card'),
        ('commercial_offers_edit', 'test_commercial_offer'),
        ('geo_objects_edit', 'test_geo_object'),
    ])
    def test_edit_views_get_authenticated_not_owner(self, client, admin_user, request, view_name, model_fixture):
        """Тест GET запросов для авторизованного НЕ владельца (должен иметь доступ админ)"""
        client.login(username='admin', password='adminpass123')
        model_instance = request.getfixturevalue(model_fixture)

        response = client.get(reverse(view_name, kwargs={'pk': model_instance.id}))

        # Админ должен иметь доступ ко всем объектам
        assert response.status_code == 200

    @pytest.mark.parametrize('view_name, model_fixture', [
        ('acts_edit', 'test_act'),
        ('scientific_reports_edit', 'test_scientific_report'),
        ('tech_reports_edit', 'test_tech_report'),
        ('open_lists_edit', 'test_open_list'),
        ('archaeological_heritage_sites_edit', 'test_archaeological_heritage_site'),
        ('identified_archaeological_heritage_sites_edit', 'test_identified_heritage_site'),
        ('account_cards_edit', 'test_account_card'),
        ('commercial_offers_edit', 'test_commercial_offer'),
        ('geo_objects_edit', 'test_geo_object'),
    ])
    def test_edit_views_get_nonexistent(self, client, test_user, view_name, model_fixture):
        """Тест GET запросов для несуществующих объектов"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse(view_name, kwargs={'pk': 9999}))

        assert response.status_code == 404

    # Параметризированные тесты для POST запросов
    @pytest.mark.parametrize('view_name, model_fixture, post_data, redirect_url', [
        ('acts_edit', 'test_act', {
            'year': '2024',
            'name_number': 'Updated Act',
            'place': 'Updated Location'
        }, '/acts/{id}'),
        ('scientific_reports_edit', 'test_scientific_report', {
            'name': 'Updated Scientific Report',
            'organization': 'Updated Org'
        }, '/scientific_reports/{id}'),
        ('tech_reports_edit', 'test_tech_report', {
            'name': 'Updated Tech Report',
            'organization': 'Updated Org'
        }, '/tech_reports/{id}'),
        ('open_lists_edit', 'test_open_list', {
            'number': 'UPD-001',
            'holder': 'Updated Holder'
        }, '/open_lists/{id}'),
        ('account_cards_edit', 'test_account_card', {
            'name': 'Updated Account Card',
            'address': 'Updated Address'
        }, '/account_cards/{id}'),
    ])
    def test_edit_views_post_valid_data(self, client, test_user, request, view_name,
                                        model_fixture, post_data, redirect_url):
        """Тест POST запросов с валидными данными"""
        client.login(username='testuser', password='testpass123')
        model_instance = request.getfixturevalue(model_fixture)

        response = client.post(
            reverse(view_name, kwargs={'pk': model_instance.id}),
            post_data
        )

        assert response.status_code == 302
        assert response.url == redirect_url.format(id=model_instance.id)

        # Проверяем что объект обновлен
        model_instance.refresh_from_db()
        for field, value in post_data.items():
            assert getattr(model_instance, field) == value

    @pytest.mark.parametrize('view_name, model_fixture', [
        ('acts_edit', 'test_act'),
        ('scientific_reports_edit', 'test_scientific_report'),
        ('tech_reports_edit', 'test_tech_report'),
        ('open_lists_edit', 'test_open_list'),
        ('account_cards_edit', 'test_account_card'),
        ('commercial_offers_edit', 'test_commercial_offer'),
        ('geo_objects_edit', 'test_geo_object'),
    ])
    def test_edit_views_post_invalid_data(self, client, test_user, request, view_name, model_fixture):
        """Тест POST запросов с невалидными данными (должен остаться на форме)"""
        client.login(username='testuser', password='testpass123')
        model_instance = request.getfixturevalue(model_fixture)

        original_values = {}
        for field in model_instance._meta.fields:
            if hasattr(model_instance, field.name):
                original_values[field.name] = getattr(model_instance, field.name)

        # Пустой POST - должен вернуть форму с ошибками
        response = client.post(
            reverse(view_name, kwargs={'pk': model_instance.id}),
            {}
        )

        assert response.status_code in [200, 302]

        # Объект не должен измениться
        for field_name, original_value in original_values.items():
            if hasattr(model_instance, field_name):
                current_value = getattr(model_instance, field_name)
                # Особое обращение для поля coordinates
                if field_name == 'coordinates' and original_value is None and current_value == {}:
                    continue
                assert current_value == original_value

    # Тесты для delete views
    @pytest.mark.parametrize('view_name, model_fixture, redirect_name', [
        ('acts_delete', 'test_act', 'acts_register'),
        ('scientific_reports_delete', 'test_scientific_report', 'scientific_reports_register'),
        ('tech_reports_delete', 'test_tech_report', 'tech_reports_register'),
        ('open_lists_delete', 'test_open_list', 'open_lists_register'),
        ('account_cards_delete', 'test_account_card', 'account_cards_register'),
        ('commercial_offers_delete', 'test_commercial_offer', 'commercial_offers_register'),
        ('geo_objects_delete', 'test_geo_object', 'geo_objects_register'),
    ])
    def test_delete_views_authenticated_owner(self, client, test_user, request,
                                              view_name, model_fixture, redirect_name):
        """Тест удаления объектов владельцем"""
        client.login(username='testuser', password='testpass123')
        model_instance = request.getfixturevalue(model_fixture)
        model_class = model_instance.__class__

        response = client.post(reverse(view_name, kwargs={'pk': model_instance.id}))

        assert response.status_code == 302
        assert response.url == reverse(redirect_name)
        # Объект должен быть удален
        assert not model_class.objects.filter(id=model_instance.id).exists()

    @pytest.mark.parametrize('view_name, model_fixture', [
        ('acts_delete', 'test_act'),
        ('scientific_reports_delete', 'test_scientific_report'),
    ])
    def test_delete_views_unauthenticated(self, client, request, view_name, model_fixture):
        """Тест удаления неавторизованным пользователем"""
        model_instance = request.getfixturevalue(model_fixture)
        model_class = model_instance.__class__

        response = client.post(reverse(view_name, kwargs={'pk': model_instance.id}))

        assert response.status_code == 302  # Редирект на логин
        # Объект не должен быть удален
        assert model_class.objects.filter(id=model_instance.id).exists()

    @pytest.mark.parametrize('view_name, model_fixture', [
        ('acts_delete', 'test_act'),
        ('scientific_reports_delete', 'test_scientific_report'),
    ])
    def test_delete_views_nonexistent(self, client, test_user, view_name, model_fixture):
        """Тест удаления несуществующего объекта"""
        client.login(username='testuser', password='testpass123')

        response = client.post(reverse(view_name, kwargs={'pk': 9999}))

        assert response.status_code == 404

    # Тесты для обработки файлов и координат
    @patch('agregator.views.edit_views.process_coords_from_edit_page')
    @patch('agregator.views.edit_views.process_supplement')
    def test_edit_with_file_processing(self, mock_process_supplement, mock_process_coords,
                                       client, test_user, test_act):
        """Тест редактирования с обработкой файлов и координат"""
        client.login(username='testuser', password='testpass123')

        mock_process_coords.return_value = {'type': 'Point', 'coordinates': [1, 2]}
        mock_process_supplement.return_value = {'test': 'supplement'}

        response = client.post(
            reverse('acts_edit', kwargs={'pk': test_act.id}),
            {
                'year': '2024',
                'name_number': 'Updated Act',
                'place': 'Updated Location'
            }
        )

        assert response.status_code == 302
        test_act.refresh_from_db()

        import json
        if isinstance(test_act.coordinates, str):
            assert json.loads(test_act.coordinates) == {'type': 'Point', 'coordinates': [1, 2]}
        else:
            assert test_act.coordinates == {'type': 'Point', 'coordinates': [1, 2]}

        if isinstance(test_act.supplement, str):
            assert json.loads(test_act.supplement) == {'test': 'supplement'}
        else:
            assert test_act.supplement == {'test': 'supplement'}

    # Тесты безопасности
    @pytest.mark.parametrize('view_name, model_fixture', [
        ('acts_edit', 'test_act'),
        ('scientific_reports_edit', 'test_scientific_report'),
    ])
    def test_xss_protection_in_edit_forms(self, client, test_user, request, view_name, model_fixture):
        """Тест защиты от XSS в формах редактирования"""
        client.login(username='testuser', password='testpass123')
        model_instance = request.getfixturevalue(model_fixture)

        xss_data = {
            'place': '<script>alert("xss")</script>',
            'conclusion': '<script>alert("xss")</script>'
        }

        response = client.post(
            reverse(view_name, kwargs={'pk': model_instance.id}),
            xss_data
        )

        assert response.status_code == 302  # Успешное сохранение
        model_instance.refresh_from_db()
        # Данные должны быть сохранены как есть (экранирование на уровне шаблона)
        assert model_instance.place == '<script>alert("xss")</script>'

    @pytest.mark.parametrize('pk_value', [
        '-1',
        '9999999',
        '0',
        '1+1',
        'invalid'
    ])
    def test_sql_injection_protection(self, client, test_user, pk_value):
        """Тест защиты от SQL инъекций в параметрах"""
        client.login(username='testuser', password='testpass123')

        response = client.get(f'/acts_edit/{pk_value}/')

        # Должен корректно обработать невалидный PK
        assert response.status_code in [404, 302]

    # Тесты для декоратора owner_or_admin_required
    @pytest.mark.parametrize('view_name, model_fixture', [
        ('acts_edit', 'test_act'),
        ('scientific_reports_edit', 'test_scientific_report'),
    ])
    def test_owner_or_admin_required_decorator(self, client, test_user_2, request, view_name, model_fixture):
        """Тест что обычный пользователь не может редактировать чужие объекты"""
        client.login(username='otheruser', password='otherpass123')
        model_instance = request.getfixturevalue(model_fixture)

        response = client.get(reverse(view_name, kwargs={'pk': model_instance.id}))

        # Должен вернуть 403 или редирект
        assert response.status_code in [403, 302]

    @pytest.mark.parametrize('view_name, model_fixture, template_name, patch_targets', [
        ('acts_edit', 'test_act', 'act_edit.html',
         ['agregator.views.edit_views.process_edit_form', 'agregator.views.edit_views.process_coords_from_edit_page',
          'agregator.views.edit_views.process_supplement']),
        ('scientific_reports_edit', 'test_scientific_report', 'scientific_report_edit.html',
         ['agregator.views.edit_views.process_edit_form', 'agregator.views.edit_views.process_coords_from_edit_page',
          'agregator.views.edit_views.process_supplement']),
        ('tech_reports_edit', 'test_tech_report', 'tech_report_edit.html',
         ['agregator.views.edit_views.process_edit_form', 'agregator.views.edit_views.process_coords_from_edit_page',
          'agregator.views.edit_views.process_supplement']),
        ('open_lists_edit', 'test_open_list', 'open_list_edit.html', ['agregator.views.edit_views.process_edit_form']),
        ('archaeological_heritage_sites_edit', 'test_archaeological_heritage_site',
         'archaeological_heritage_site_edit.html', ['agregator.views.edit_views.process_edit_form']),
        ('identified_archaeological_heritage_sites_edit', 'test_identified_heritage_site',
         'identified_archaeological_heritage_site_edit.html', ['agregator.views.edit_views.process_edit_form']),
        ('account_cards_edit', 'test_account_card', 'account_card_edit.html',
         ['agregator.views.edit_views.process_edit_form', 'agregator.views.edit_views.process_coords_from_edit_page',
          'agregator.views.edit_views.process_supplement']),
        ('commercial_offers_edit', 'test_commercial_offer', 'commercial_offer_edit.html',
         ['agregator.views.edit_views.process_coords_from_edit_page']),
        ('geo_objects_edit', 'test_geo_object', 'geo_object_edit.html',
         ['agregator.views.edit_views.process_coords_from_edit_page']),
    ])
    def test_edit_views_exception_handling(self, client, admin_user, request, view_name, model_fixture, template_name,
                                           patch_targets):
        client.login(username='admin', password='adminpass123')
        model_instance = request.getfixturevalue(model_fixture)
        # Создаем патчи для всех указанных функций
        patches = [patch(target) for target in patch_targets]
        mocks = [p.start() for p in patches]
        # Заставляем первый мок вызывать исключение
        mocks[0].side_effect = Exception("Test error")
        try:
            response = client.post(
                reverse(view_name, kwargs={'pk': model_instance.id}),
                {}  # Можно передать пустые данные или минимальные валидные
            )
        finally:
            for p in patches:
                p.stop()
        assert response.status_code == 200
        assert template_name in [t.name for t in response.templates]
        assert 'Ошибка при обновлении' in response.content.decode('utf-8')

    @pytest.mark.parametrize('view_name, model_fixture, post_data, redirect_url', [
        ('archaeological_heritage_sites_edit', 'test_archaeological_heritage_site', {
            'doc_name': 'Updated OAN',
            'district': 'Updated District'
        }, '/archaeological_heritage_sites/{id}'),
        ('identified_archaeological_heritage_sites_edit', 'test_identified_heritage_site', {
            'name': 'Updated VOAN',
            'address': 'Updated Address'
        }, '/identified_archaeological_heritage_sites/{id}'),
    ])
    def test_edit_views_post_valid_data_admin_only(self, client, admin_user, request, view_name,
                                                   model_fixture, post_data, redirect_url):
        """Тест POST запросов для admin-only объектов"""
        client.login(username='admin', password='adminpass123')
        model_instance = request.getfixturevalue(model_fixture)

        response = client.post(
            reverse(view_name, kwargs={'pk': model_instance.id}),
            post_data
        )

        assert response.status_code == 302
        assert response.url == redirect_url.format(id=model_instance.id)

        # Проверяем что объект обновлен
        model_instance.refresh_from_db()
        for field, value in post_data.items():
            assert getattr(model_instance, field) == value

    @pytest.mark.parametrize('view_name, model_fixture, redirect_name', [
        ('archaeological_heritage_sites_delete', 'test_archaeological_heritage_site',
         'archaeological_heritage_sites_register'),
        ('identified_archaeological_heritage_sites_delete', 'test_identified_heritage_site',
         'identified_archaeological_heritage_sites_register'),
    ])
    def test_delete_views_authenticated_admin(self, client, admin_user, request, view_name, model_fixture,
                                              redirect_name):
        """Тест удаления admin-only объектов админом"""
        client.login(username='admin', password='adminpass123')
        model_instance = request.getfixturevalue(model_fixture)
        model_class = model_instance.__class__

        response = client.post(reverse(view_name, kwargs={'pk': model_instance.id}))

        assert response.status_code == 302
        assert response.url == reverse(redirect_name)
        # Объект должен быть удален
        assert not model_class.objects.filter(id=model_instance.id).exists()

    @pytest.mark.parametrize('view_name, model_fixture, post_data', [
        ('commercial_offers_edit', 'test_commercial_offer', {
            'group[0]': 'Каталог координат (мск167)',
            'coordinate_system[0]': 'wgs84',
            'point[0]': '1;56,01121389;92,88724444',
            'point[1]': '2;56,01123333;92,88773611',
            'point[2]': '3;56,01104722;92,88849167',
            'point[3]': '4;56,01052778;92,88853056',
            'point[4]': '5;56,01052222;92,88831111',
            'point[5]': '6;56,01059722;92,88743333',
            'point[6]': '7;56,01084722;92,88780833',
            'point[7]': '8;56,01082222;92,88730000',
        }),
        ('geo_objects_edit', 'test_geo_object', {
            'group[0]': 'Каталог координат (мск167)',
            'coordinate_system[0]': 'wgs84',
            'point[0]': '1;56,01121389;92,88724444',
            'point[1]': '2;56,01123333;92,88773611',
            'point[2]': '3;56,01104722;92,88849167',
            'point[3]': '4;56,01052778;92,88853056',
            'point[4]': '5;56,01052222;92,88831111',
            'point[5]': '6;56,01059722;92,88743333',
            'point[6]': '7;56,01084722;92,88780833',
            'point[7]': '8;56,01082222;92,88730000',
        }),
    ])
    def test_edit_views_with_coordinates(self, client, test_user, request, view_name, model_fixture, post_data):
        """Тест редактирования объектов с координатами"""
        client.login(username='testuser', password='testpass123')
        model_instance = request.getfixturevalue(model_fixture)

        response = client.post(
            reverse(view_name, kwargs={'pk': model_instance.id}),
            post_data
        )

        assert response.status_code == 302
        model_instance.refresh_from_db()

        # Проверяем что координаты обновлены
        expected_coords = {
            'Каталог координат (мск167)': {
                'coordinate_system': 'wgs84',
                'area': 4703.224419657607,
                '1': ['56.01121389', '92.88724444'],
                '2': ['56.01123333', '92.88773611'],
                '3': ['56.01104722', '92.88849167'],
                '4': ['56.01052778', '92.88853056'],
                '5': ['56.01052222', '92.88831111'],
                '6': ['56.01059722', '92.88743333'],
                '7': ['56.01084722', '92.88780833'],
                '8': ['56.01082222', '92.88730000'],
            }
        }

        if hasattr(model_instance, 'coordinates_dict'):
            assert model_instance.coordinates_dict == expected_coords

    def test_acts_edit_get_request(self, client, test_user, test_act):
        """Тест GET запроса для acts_edit (покрытие последних строк)"""
        client.login(username='testuser', password='testpass123')

        response = client.get(reverse('acts_edit', kwargs={'pk': test_act.id}))

        assert response.status_code == 200
        assert 'act_edit.html' in [t.name for t in response.templates]
        assert response.context['report'] == test_act


@pytest.mark.django_db
class TestEditViewsIntegration:
    """Интеграционные тесты для edit views"""

    def test_full_edit_flow(self, client, test_user, test_act):
        """Полный тест потока редактирования: GET форма -> POST данных -> редирект -> проверка изменений"""
        client.login(username='testuser', password='testpass123')

        # 1. Получаем форму редактирования
        response = client.get(reverse('acts_edit', kwargs={'pk': test_act.id}))
        assert response.status_code == 200
        assert 'act_edit.html' in [t.name for t in response.templates]

        # 2. Отправляем измененные данные
        update_data = {
            'year': '2024',
            'name_number': 'Completely Updated Act',
            'place': 'New Test Location',
            'customer': 'New Customer',
            'area': '100',
            'expert': 'New Expert'
        }

        response = client.post(
            reverse('acts_edit', kwargs={'pk': test_act.id}),
            update_data
        )

        # 3. Проверяем редирект
        assert response.status_code == 302
        assert response.url == f'/acts/{test_act.id}'

        # 4. Проверяем что данные сохранились
        test_act.refresh_from_db()
        for field, value in update_data.items():
            assert getattr(test_act, field) == value

        # 5. Проверяем что можем посмотреть обновленный объект
        response = client.get(reverse('acts', kwargs={'pk': test_act.id}))
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Completely Updated Act' in content

    def test_edit_with_messages(self, client, test_user, test_act):
        """Тест что сообщения об успешном обновлении показываются"""
        client.login(username='testuser', password='testpass123')

        # Мокаем систему сообщений чтобы проверить их наличие
        with patch('agregator.views.edit_views.messages.success') as mock_success:
            response = client.post(
                reverse('acts_edit', kwargs={'pk': test_act.id}),
                {'year': '2024', 'name_number': 'Updated'}
            )

            mock_success.assert_called_once()
            args, kwargs = mock_success.call_args
            assert 'Акт успешно обновлен.' in args[1]

    @pytest.mark.parametrize('view_name, model_fixture', [
        ('acts_delete', 'test_act'),
        ('scientific_reports_delete', 'test_scientific_report'),
    ])
    def test_delete_integration(self, client, test_user, request, view_name, model_fixture):
        """Интеграционный тест удаления"""
        client.login(username='testuser', password='testpass123')
        model_instance = request.getfixturevalue(model_fixture)
        model_class = model_instance.__class__

        # Убедимся что объект существует
        assert model_class.objects.filter(id=model_instance.id).exists()

        # Удаляем
        response = client.post(reverse(view_name, kwargs={'pk': model_instance.id}))

        # Проверяем редирект
        assert response.status_code == 302

        # Проверяем что объект удален
        assert not model_class.objects.filter(id=model_instance.id).exists()

        # Проверяем что не можем получить доступ к удаленному объекту
        response = client.get(reverse('acts', kwargs={'pk': model_instance.id}))
        assert response.status_code == 404

    @pytest.mark.parametrize('view_name, model_fixture, edit_data', [
        ('acts_edit', 'test_act', {'year': '2024', 'name_number': 'Updated'}),
        ('scientific_reports_edit', 'test_scientific_report', {'name': 'Updated', 'organization': 'New Org'}),
        ('tech_reports_edit', 'test_tech_report', {'name': 'Updated', 'organization': 'New Org'}),
        ('open_lists_edit', 'test_open_list', {'number': 'UPD-001', 'holder': 'New Holder'}),
        ('account_cards_edit', 'test_account_card', {'name': 'Updated', 'address': 'New Address'}),
        ('commercial_offers_edit', 'test_commercial_offer', {}),
        ('geo_objects_edit', 'test_geo_object', {}),
    ])
    def test_integration_edit_all_models(self, client, test_user, request, view_name, model_fixture, edit_data):
        """Интеграционный тест редактирования для всех моделей"""
        client.login(username='testuser', password='testpass123')
        model_instance = request.getfixturevalue(model_fixture)

        # Для объектов с координатами добавляем специальные данные
        if 'commercial' in view_name or 'geo' in view_name:
            edit_data['coordinates'] = json.dumps({'type': 'Point', 'coordinates': [37.6, 55.7]})

        response = client.post(
            reverse(view_name, kwargs={'pk': model_instance.id}),
            edit_data
        )

        assert response.status_code == 302
        model_instance.refresh_from_db()

        # Проверяем обновление полей
        for field, value in edit_data.items():
            if field != 'coordinates':  # Координаты проверяем отдельно
                assert getattr(model_instance, field) == value


# Тесты для граничных случаев
@pytest.mark.django_db
class TestEditViewsEdgeCases:
    """Тесты граничных случаев для edit views"""

    @pytest.mark.parametrize('field_name, field_value', [
        ('year', ''),  # Пустое обязательное поле
        ('name_number', ' ' * 1000),  # Очень длинная строка
        ('place', ''),  # Еще одно пустое поле
    ])
    def test_edit_with_edge_case_data(self, client, test_user, test_act, field_name, field_value):
        """Тест редактирования с граничными значениями данных"""
        client.login(username='testuser', password='testpass123')

        response = client.post(
            reverse('acts_edit', kwargs={'pk': test_act.id}),
            {field_name: field_value, 'year': '2023'}  # year обязательное
        )

        # Должен обработать граничные случаи (либо успех, либо остаться на форме с ошибками)
        assert response.status_code in [200, 302]

    def test_concurrent_edit(self, client, test_user, test_act):
        """Тест конкурентного редактирования (последнее изменение побеждает)"""
        client.login(username='testuser', password='testpass123')

        # Первое изменение
        response1 = client.post(
            reverse('acts_edit', kwargs={'pk': test_act.id}),
            {'year': '2024', 'name_number': 'First Update'}
        )
        assert response1.status_code == 302

        # Второе изменение
        response2 = client.post(
            reverse('acts_edit', kwargs={'pk': test_act.id}),
            {'year': '2025', 'name_number': 'Second Update'}
        )
        assert response2.status_code == 302

        # Проверяем что сохранилось последнее изменение
        test_act.refresh_from_db()
        assert test_act.year == '2025'
        assert test_act.name_number == 'Second Update'

    @patch('agregator.views.edit_views.process_edit_form')
    def test_edit_form_processing_error(self, mock_process_edit_form, client, test_user, test_act):
        """Тест обработки ошибок при обработке формы"""
        client.login(username='testuser', password='testpass123')
        mock_process_edit_form.side_effect = Exception("Form processing error")

        # Теперь ожидаем, что исключение будет обработано и вернется 200 с формой
        response = client.post(
            reverse('acts_edit', kwargs={'pk': test_act.id}),
            {'year': '2024'}
        )

        # Должен вернуть форму с ошибкой
        assert response.status_code == 200
        # Объект не должен измениться
        test_act.refresh_from_db()
        assert test_act.year == '2023'  # Исходное значение

    def test_csrf_protection(self, client, test_user, test_act):
        """Тест защиты CSRF"""
        client.login(username='testuser', password='testpass123')

        # Создаем запрос без CSRF токена
        client = Client(enforce_csrf_checks=True)
        client.login(username='testuser', password='testpass123')

        response = client.post(
            reverse('acts_edit', kwargs={'pk': test_act.id}),
            {'year': '2024'},
            follow=True
        )

        # Должен вернуть ошибку CSRF
        assert response.status_code == 403

    @patch('agregator.views.edit_views.process_coords_from_edit_page')
    @patch('agregator.views.edit_views.process_supplement')
    def test_edit_with_file_processing_errors(self, mock_process_supplement, mock_process_coords,
                                              client, test_user, test_act):
        """Тест обработки ошибок при обработке файлов и координат"""
        client.login(username='testuser', password='testpass123')

        mock_process_coords.side_effect = Exception("Coord processing error")
        mock_process_supplement.side_effect = Exception("Supplement processing error")

        response = client.post(
            reverse('acts_edit', kwargs={'pk': test_act.id}),
            {'year': '2024', 'name_number': 'Test'}
        )

        # Должен вернуть форму с ошибкой
        assert response.status_code == 200
        assert 'Ошибка при обновлении' in response.content.decode('utf-8')

    @pytest.mark.parametrize('view_name, model_fixture', [
        ('archaeological_heritage_sites_edit', 'test_archaeological_heritage_site'),
        ('identified_archaeological_heritage_sites_edit', 'test_identified_heritage_site'),
        ('archaeological_heritage_sites_delete', 'test_archaeological_heritage_site'),
        ('identified_archaeological_heritage_sites_delete', 'test_identified_heritage_site'),
    ])
    def test_admin_only_endpoints_security(self, client, test_user, request, view_name, model_fixture):
        """Тест безопасности admin-only endpoints для обычных пользователей"""
        client.login(username='testuser', password='testpass123')
        model_instance = request.getfixturevalue(model_fixture)

        if 'delete' in view_name:
            response = client.post(reverse(view_name, kwargs={'pk': model_instance.id}))
        else:
            response = client.get(reverse(view_name, kwargs={'pk': model_instance.id}))

        assert response.status_code == 403  # Forbidden

    @pytest.mark.parametrize('coord_data', [
        'invalid_json',
        '{"type": "InvalidType", "coordinates": "invalid"}',
        '{}',
        '{"type": "Point", "coordinates": []}',
        '{"type": "Point", "coordinates": [1000, 1000]}',  # Невалидные координаты
    ])
    def test_edit_with_invalid_coordinates(self, client, test_user, test_commercial_offer, coord_data):
        """Тест редактирования с невалидными координатами"""
        client.login(username='testuser', password='testpass123')

        response = client.post(
            reverse('commercial_offers_edit', kwargs={'pk': test_commercial_offer.id}),
            {'coordinates': coord_data}
        )

        # Должен обработать корректно (либо успех, либо вернуть форму с ошибкой)
        assert response.status_code in [200, 302]


# Тесты производительности
@pytest.mark.django_db
class TestEditViewsPerformance:
    """Тесты производительности для edit views"""

    @pytest.mark.parametrize('view_name, model_fixture', [
        ('acts_edit', 'test_act'),
        ('scientific_reports_edit', 'test_scientific_report'),
    ])
    def test_edit_response_time(self, client, test_user, request, view_name, model_fixture):
        """Тест времени ответа для edit views"""
        client.login(username='testuser', password='testpass123')
        model_instance = request.getfixturevalue(model_fixture)

        # Измеряем время GET запроса
        import time
        start_time = time.time()
        response = client.get(reverse(view_name, kwargs={'pk': model_instance.id}))
        end_time = time.time()

        assert response.status_code == 200
        # Время ответа должно быть меньше 500ms
        assert (end_time - start_time) < 0.5

    def test_multiple_sequential_edits(self, client, test_user, test_act):
        """Тест множественных последовательных редактирований"""
        client.login(username='testuser', password='testpass123')

        for i in range(10):  # 10 последовательных изменений
            response = client.post(
                reverse('acts_edit', kwargs={'pk': test_act.id}),
                {'year': str(2020 + i), 'name_number': f'Update {i}'}
            )
            assert response.status_code == 302

        test_act.refresh_from_db()
        assert test_act.year == '2029'
        assert test_act.name_number == 'Update 9'

    @pytest.mark.parametrize('view_name, model_fixture', [
        ('acts_edit', 'test_act'),
        ('scientific_reports_edit', 'test_scientific_report'),
        ('tech_reports_edit', 'test_tech_report'),
        ('open_lists_edit', 'test_open_list'),
        ('account_cards_edit', 'test_account_card'),
        ('commercial_offers_edit', 'test_commercial_offer'),
        ('geo_objects_edit', 'test_geo_object'),
    ])
    def test_all_edit_views_performance(self, client, test_user, request, view_name, model_fixture):
        """Тест производительности для всех edit views"""
        client.login(username='testuser', password='testpass123')
        model_instance = request.getfixturevalue(model_fixture)

        import time
        start_time = time.time()
        response = client.get(reverse(view_name, kwargs={'pk': model_instance.id}))
        end_time = time.time()

        assert response.status_code == 200
        assert (end_time - start_time) < 1.0  # Более мягкий лимит для всех views
