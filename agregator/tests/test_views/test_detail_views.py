import pytest
import json
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from unittest.mock import patch, MagicMock

User = get_user_model()


@pytest.mark.django_db
class TestDetailViews:
    """Тесты для функций отображения детальной информации"""

    def test_acts_view_existing(self, client, test_act):
        """Тест отображения существующего акта"""
        response = client.get(reverse('acts', kwargs={'pk': test_act.id}))

        assert response.status_code == 200
        assert 'act.html' in [t.name for t in response.templates]
        assert response.context['report'] == test_act
        assert 'Test Act' in response.content.decode('utf-8')

    def test_acts_view_nonexistent(self, client):
        """Тест отображения несуществующего акта (должен вернуть 404)"""
        response = client.get(reverse('acts', kwargs={'pk': 9999}))
        assert response.status_code == 404

    def test_scientific_reports_view_existing(self, client, test_scientific_report):
        """Тест отображения существующего научного отчета"""
        response = client.get(reverse('scientific_reports', kwargs={'pk': test_scientific_report.id}))

        assert response.status_code == 200
        assert 'scientific_report.html' in [t.name for t in response.templates]
        assert response.context['report'] == test_scientific_report
        assert 'Test Scientific Report' in response.content.decode('utf-8')

    def test_scientific_reports_view_nonexistent(self, client):
        """Тест отображения несуществующего научного отчета"""
        response = client.get(reverse('scientific_reports', kwargs={'pk': 9999}))
        assert response.status_code == 404

    def test_tech_reports_view_existing(self, client, test_tech_report):
        """Тест отображения существующего техотчета"""
        response = client.get(reverse('tech_reports', kwargs={'pk': test_tech_report.id}))

        assert response.status_code == 200
        assert 'tech_report.html' in [t.name for t in response.templates]
        assert response.context['report'] == test_tech_report
        assert 'Реестр научно-технических отчётов' in response.content.decode('utf-8')

    def test_tech_reports_view_nonexistent(self, client):
        """Тест отображения несуществующего техотчета"""
        response = client.get(reverse('tech_reports', kwargs={'pk': 9999}))
        assert response.status_code == 404

    def test_open_lists_view_existing(self, client, test_open_list):
        """Тест отображения существующего открытого листа"""
        response = client.get(reverse('open_lists', kwargs={'pk': test_open_list.id}))

        assert response.status_code == 200
        assert 'open_list.html' in [t.name for t in response.templates]
        assert response.context['open_list'] == test_open_list
        assert 'TEST-001' in response.content.decode('utf-8')

    def test_open_lists_view_nonexistent(self, client):
        """Тест отображения несуществующего открытого листа"""
        response = client.get(reverse('open_lists', kwargs={'pk': 9999}))
        assert response.status_code == 404

    def test_archaeological_heritage_site_view_existing(self, client, test_archaeological_heritage_site):
        """Тест отображения существующего ОАН"""
        response = client.get(
            reverse('archaeological_heritage_sites', kwargs={'pk': test_archaeological_heritage_site.id}))

        assert response.status_code == 200
        assert 'archaeological_heritage_site.html' in [t.name for t in response.templates]
        assert response.context['archaeological_heritage_site'] == test_archaeological_heritage_site
        assert 'Test OAN' in response.content.decode('utf-8')

    def test_archaeological_heritage_site_view_nonexistent(self, client):
        """Тест отображения несуществующего ОАН"""
        response = client.get(reverse('archaeological_heritage_sites', kwargs={'pk': 9999}))
        assert response.status_code == 404

    def test_identified_heritage_site_view_existing(self, client, test_identified_heritage_site):
        """Тест отображения существующего ВОАН"""
        response = client.get(
            reverse('identified_archaeological_heritage_sites', kwargs={'pk': test_identified_heritage_site.id}))

        assert response.status_code == 200
        assert 'identified_archaeological_heritage_site.html' in [t.name for t in response.templates]
        assert response.context['identified_archaeological_heritage_site'] == test_identified_heritage_site
        assert 'Test VOAN' in response.content.decode('utf-8')

    def test_identified_heritage_site_view_nonexistent(self, client):
        """Тест отображения несуществующего ВОАН"""
        response = client.get(reverse('identified_archaeological_heritage_sites', kwargs={'pk': 9999}))
        assert response.status_code == 404

    def test_account_cards_view_existing_with_heritage(self, client, test_account_card, test_identified_heritage_site):
        """Тест отображения учетной карточки с привязанным heritage site"""
        response = client.get(reverse('account_cards', kwargs={'pk': test_account_card.id}))

        assert response.status_code == 200
        assert 'account_card.html' in [t.name for t in response.templates]
        assert response.context['account_card'] == test_account_card

        content = response.content.decode('utf-8')
        assert 'Test Account Card' in content
        # Проверяем что heritage link присутствует
        assert f'/identified_archaeological_heritage_sites/{test_identified_heritage_site.id}/' in content

    def test_account_cards_view_existing_no_heritage(self, client, test_user):
        """Тест отображения учетной карточки без heritage site"""
        from agregator.models import ObjectAccountCard
        card = ObjectAccountCard.objects.create(
            user=test_user,
            name='Test Card No Heritage',
            creation_time='Test Period',
            address='Test Address'
        )

        response = client.get(reverse('account_cards', kwargs={'pk': card.id}))

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Test Card No Heritage' in content
        # Не должно быть ссылки на heritage
        assert '/identified_archaeological_heritage_sites/' not in content
        assert '/archaeological_heritage_sites/' not in content

    def test_account_cards_view_existing_with_archaeological_heritage(self, client, test_user,
                                                                      test_archaeological_heritage_site):
        """Тест отображения учетной карточки с archaeological heritage site"""
        from agregator.models import ObjectAccountCard
        card = ObjectAccountCard.objects.create(
            user=test_user,
            name=test_archaeological_heritage_site.doc_name,  # Совпадающее имя
            creation_time='Test Period',
            address='Test Address'
        )
        test_archaeological_heritage_site.account_card = card
        test_archaeological_heritage_site.save()

        response = client.get(reverse('account_cards', kwargs={'pk': card.id}))

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert test_archaeological_heritage_site.doc_name in content
        # Должна быть ссылка на archaeological heritage
        assert f'/archaeological_heritage_sites/{test_archaeological_heritage_site.id}/' in content

    def test_account_cards_view_nonexistent(self, client):
        """Тест отображения несуществующей учетной карточки"""
        response = client.get(reverse('account_cards', kwargs={'pk': 9999}))
        assert response.status_code == 404

    @pytest.mark.parametrize('view_name, model_fixture', [
        ('acts', 'test_act'),
        ('scientific_reports', 'test_scientific_report'),
        ('tech_reports', 'test_tech_report'),
        ('open_lists', 'test_open_list'),
        ('archaeological_heritage_sites', 'test_archaeological_heritage_site'),
        ('identified_archaeological_heritage_sites', 'test_identified_heritage_site'),
        ('account_cards', 'test_account_card'),
    ])
    def test_all_detail_views_template_usage(self, client, request, view_name, model_fixture):
        """Параметризированный тест что все detail views используют правильные шаблоны"""
        model_instance = request.getfixturevalue(model_fixture)
        response = client.get(reverse(view_name, kwargs={'pk': model_instance.id}))

        assert response.status_code == 200
        # Проверяем что используется правильный шаблон
        template_names = {
            'acts': 'act.html',
            'scientific_reports': 'scientific_report.html',
            'tech_reports': 'tech_report.html',
            'open_lists': 'open_list.html',
            'archaeological_heritage_sites': 'archaeological_heritage_site.html',
            'identified_archaeological_heritage_sites': 'identified_archaeological_heritage_site.html',
            'account_cards': 'account_card.html'
        }
        expected_template = template_names[view_name]

        assert expected_template in [t.name for t in response.templates]

    def test_account_cards_multiple_heritage_matches(self, client, test_user):
        """Тест когда несколько heritage sites подходят к учетной карточке"""
        from agregator.models import ObjectAccountCard, IdentifiedArchaeologicalHeritageSite

        card = ObjectAccountCard.objects.create(
            user=test_user,
            name='Test Multi Heritage',
            creation_time='Test Period',
            address='Test Address'
        )

        # Создаем несколько heritage sites с одинаковым именем
        for i in range(3):
            IdentifiedArchaeologicalHeritageSite.objects.create(
                name='Test Multi Heritage',
                address=f'Test Address {i}',
                obj_info='Test Info',
                account_card=card
            )

        response = client.get(reverse('account_cards', kwargs={'pk': card.id}))

        assert response.status_code == 200
        # Должен взять первый попавшийся heritage site
        assert response.context['account_card'].heritage_url is not None

    def test_account_cards_heritage_url_generation(self, client, test_account_card, test_identified_heritage_site):
        """Тест генерации URL для heritage site"""
        response = client.get(reverse('account_cards', kwargs={'pk': test_account_card.id}))

        assert response.status_code == 200
        account_card = response.context['account_card']
        expected_url = f'/identified_archaeological_heritage_sites/{test_identified_heritage_site.id}/'
        assert account_card.heritage_url == expected_url

    @patch('agregator.views.detail_views.get_object_or_404')
    def test_detail_views_exception_handling(self, mock_get_object, client):
        """Тест обработки исключений в detail views"""
        mock_get_object.side_effect = Exception("Test error")

        response = client.get(reverse('acts', kwargs={'pk': 1}))

        # Должен вернуть 404 или обработать ошибку
        assert response.status_code == 404


# Интеграционные тесты
@pytest.mark.django_db
class TestDetailViewsIntegration:
    """Интеграционные тесты для detail views"""

    def test_detail_views_content_rendering(self, client, test_act, test_scientific_report, test_tech_report,
                                            test_open_list, test_archaeological_heritage_site,
                                            test_identified_heritage_site, test_account_card):
        """Интеграционный тест рендеринга контента всех detail views"""
        test_cases = [
            (reverse('acts', kwargs={'pk': test_act.id}), 'Test Act'),
            (reverse('scientific_reports', kwargs={'pk': test_scientific_report.id}), 'Test Scientific Report'),
            (reverse('tech_reports', kwargs={'pk': test_tech_report.id}), 'Реестр научно-технических отчётов'),
            # 'Test Tech Report'
            (reverse('open_lists', kwargs={'pk': test_open_list.id}), 'TEST-001'),
            (reverse('archaeological_heritage_sites', kwargs={'pk': test_archaeological_heritage_site.id}), 'Test OAN'),
            (reverse('identified_archaeological_heritage_sites', kwargs={'pk': test_identified_heritage_site.id}),
             'Test VOAN'),
            (reverse('account_cards', kwargs={'pk': test_account_card.id}), 'Test Account Card'),
        ]

        for url, expected_content in test_cases:
            response = client.get(url)
            assert response.status_code == 200
            assert expected_content in response.content.decode('utf-8')

    def test_detail_views_context_data(self, client, test_act, test_account_card, test_identified_heritage_site):
        """Тест что в контекст передаются правильные данные"""
        # Тест для act
        response = client.get(reverse('acts', kwargs={'pk': test_act.id}))
        assert response.context['report'] == test_act
        assert hasattr(response.context['report'], 'year')
        assert hasattr(response.context['report'], 'name_number')

        # Тест для account card с heritage
        response = client.get(reverse('account_cards', kwargs={'pk': test_account_card.id}))
        assert response.context['account_card'] == test_account_card
        assert hasattr(response.context['account_card'], 'heritage_url')
        assert hasattr(response.context['account_card'], 'heritage_source')


# Тесты безопасности
@pytest.mark.django_db
class TestDetailViewsSecurity:
    """Тесты безопасности для detail views"""

    def test_xss_protection_in_detail_views(self, client, test_user):
        """Тест что HTML/JS не исполняется в детальных представлениях"""
        from agregator.models import Act

        # Создаем акт с потенциально опасным контентом
        act = Act.objects.create(
            user=test_user,
            year='2023',
            name_number='<script>alert("xss")</script>',
            place='Test Location'
        )

        response = client.get(reverse('acts', kwargs={'pk': act.id}))

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        # Скрипт должен быть экранирован, а не исполнен
        assert '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;' in content
        assert '<script>alert("xss")</script>' not in content

    def test_sql_injection_protection(self, client):
        """Тест защиты от SQL инъекций в параметрах"""
        # Пытаемся сделать SQL инъекцию через параметр pk
        response = client.get("/acts/1'; DROP TABLE agregator_act; --/")

        # Должен вернуть 404, а не выполнить SQL
        assert response.status_code == 404

    @pytest.mark.parametrize('pk_value', [
        '-1',
        '9999999',
        '0',
        '1+1'
        'invalid'
    ])
    def test_invalid_primary_key_handling(self, client, pk_value):
        """Тест обработки невалидных primary key"""
        response = client.get(f'/acts/{pk_value}/')

        # Должен корректно обработать невалидный PK (вернуть 404)
        assert response.status_code == 404
