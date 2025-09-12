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
def test_act(db, test_user):
    from agregator.models import Act
    return Act.objects.create(
        user=test_user,
        year='2023',
        name_number='test-123'
    )


@pytest.fixture
def test_user(db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username='testuser',
        password='testpass123',
        email='test@example.com'
    )


@pytest.fixture
def test_image():
    return SimpleUploadedFile(
        "test_avatar.jpg",
        b"file_content",
        content_type="image/jpeg"
    )
