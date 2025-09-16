import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.fixture
def client():
    from django.test import Client
    return Client()


@pytest.fixture
def api_client():
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def test_user(db):
    """Создает основного тестового пользователя"""
    return User.objects.create_user(
        username='testuser',
        password='testpass123',
        email='test@example.com',
        first_name='Test',
        last_name='User'
    )


@pytest.fixture
def test_user_2(db):
    """Создает второго тестового пользователя"""
    return User.objects.create_user(
        username='otheruser',
        password='otherpass123',
        email='other@example.com'
    )


@pytest.fixture
def avatar_file():
    """Создает тестовый файл аватара"""
    return SimpleUploadedFile(
        "avatar.jpg",
        b"file_content",
        content_type="image/jpeg"
    )


@pytest.fixture
def test_image():
    return SimpleUploadedFile(
        "test_avatar.jpg",
        b"file_content",
        content_type="image/jpeg"
    )


@pytest.fixture
def test_act(db, test_user):
    from agregator.models import Act
    return Act.objects.create(
        user=test_user,
        year='2023',
        name_number='test-123'
    )


@pytest.fixture
def test_scientific_report(db, test_user):
    from agregator.models import ScientificReport
    return ScientificReport.objects.create(
        user=test_user,
        name='Test Report'
    )


@pytest.fixture
def test_open_list(db, test_user):
    from agregator.models import OpenLists
    return OpenLists.objects.create(
        user=test_user,
        number='TEST-001'
    )


@pytest.fixture
def test_account_card(db, test_user):
    from agregator.models import ObjectAccountCard
    return ObjectAccountCard.objects.create(
        user=test_user,
        name='Test Account Card'
    )
