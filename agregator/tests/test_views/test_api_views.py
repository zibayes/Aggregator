import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from agregator.models import Act, ScientificReport

User = get_user_model()


@pytest.mark.django_db
class TestAPIViews:

    def test_user_list_api(self):
        """Тест API списка пользователей"""
        client = APIClient()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.force_authenticate(user=user)

        response = client.get(reverse('user-list'))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_act_detail_api(self):
        """Тест API детальной информации акта"""
        client = APIClient()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.force_authenticate(user=user)

        act = Act.objects.create(
            user=user,
            year='2023',
            name_number='test-123'
        )

        response = client.get(reverse('act-detail', kwargs={'pk': act.id}))

        assert response.status_code == status.HTTP_200_OK
        assert response.data['name_number'] == 'test-123'


@pytest.mark.django_db
class TestScientificReportAPI:
    def test_scientific_report_list_api(self, api_client, test_user):
        """Тест API списка научных отчётов"""
        api_client.force_authenticate(user=test_user)
        ScientificReport.objects.create(
            user=test_user,
            name="Test Report",
            is_processing=False
        )

        response = api_client.get(reverse('scientificreport-list'))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_scientific_report_detail_api(self, api_client, test_user):
        """Тест API деталей научного отчёта"""
        api_client.force_authenticate(user=test_user)
        report = ScientificReport.objects.create(
            user=test_user,
            name="Test Report",
            is_processing=False
        )

        response = api_client.get(reverse('scientificreport-detail', kwargs={'pk': report.id}))
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == 'Test Report'
