import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django_celery_results.models import TaskResult

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
def admin_user(db):
    return User.objects.create_user(
        username='admin',
        password='adminpass123',
        email='admin@example.com',
        is_superuser=True
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
        name_number='Test Act',
        type='ГИКЭ',
        place='Test Location'
    )


@pytest.fixture
def test_scientific_report(db, test_user):
    from agregator.models import ScientificReport
    return ScientificReport.objects.create(
        user=test_user,
        name='Test Scientific Report',
        organization='Test Org',
        author='Test Author'
    )


@pytest.fixture
def test_tech_report(db, test_user):
    from agregator.models import TechReport
    return TechReport.objects.create(
        user=test_user,
        name='Test Tech Report',
        organization='Test Org',
        author='Test Author'
    )


@pytest.fixture
def test_open_list(db, test_user):
    from agregator.models import OpenLists
    return OpenLists.objects.create(
        user=test_user,
        number='TEST-001',
        holder='Test Holder',
        object='Test Object'
    )


@pytest.fixture
def test_archaeological_heritage_site(db):
    from agregator.models import ArchaeologicalHeritageSite
    return ArchaeologicalHeritageSite.objects.create(
        doc_name='Test OAN',
        district='Test District',
        register_num='TEST-OAN-001'
    )


@pytest.fixture
def test_identified_heritage_site(db):
    from agregator.models import IdentifiedArchaeologicalHeritageSite
    return IdentifiedArchaeologicalHeritageSite.objects.create(
        name='Test VOAN',
        address='Test Address',
        obj_info='Test Info'
    )


@pytest.fixture
def test_account_card(db, test_user, test_identified_heritage_site):
    from agregator.models import ObjectAccountCard
    card = ObjectAccountCard.objects.create(
        user=test_user,
        name='Test Account Card',
        creation_time='Test Period',
        address='Test Address'
    )
    # Связываем с heritage site
    test_identified_heritage_site.account_card = card
    test_identified_heritage_site.save()
    return card


@pytest.fixture
def test_tasks(db, test_user):
    """Создает тестовые задачи для пользователя"""
    from agregator.models import UserTasks

    tasks = []
    for i, task_type in enumerate(
            ['act', 'scientific_report', 'tech_report', 'open_list', 'account_card', 'commercial_offer', 'geo_object']):
        task = UserTasks.objects.create(
            user=test_user,
            task_id=f'test_task_{i}',
            files_type=task_type,
            upload_source={'source': 'Пользовательский файл'}
        )
        tasks.append(task)

    # Создаем TaskResult для этих задач
    for task in tasks:
        TaskResult.objects.create(
            task_id=task.task_id,
            status='SUCCESS',
            result='{"message": "success"}'
        )

    return tasks


@pytest.fixture
def admin_tasks(db, admin_user):
    """Создает тестовые задачи для админа (external source)"""
    from agregator.models import UserTasks

    tasks = []
    for i, task_type in enumerate(['act', 'scientific_report', 'tech_report', 'open_list']):
        task = UserTasks.objects.create(
            user=admin_user,
            task_id=f'admin_task_{i}',
            files_type=task_type,
            upload_source={'source': 'external'}
        )
        tasks.append(task)

    for task in tasks:
        TaskResult.objects.create(
            task_id=task.task_id,
            status='SUCCESS',
            result='{"message": "success"}'
        )

    return tasks
