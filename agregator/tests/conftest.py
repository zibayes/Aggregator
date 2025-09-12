import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile


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
