import json

from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from archeology.settings import AUTH_USER_MODEL
from django.core.files.storage import default_storage
from django_celery_results.models import TaskResult
from django.db.models.query import QuerySet
from agregator.hash import calculate_file_hash
from agregator.processing.utils import get_file_size
import os
import shutil
import logging

logger = logging.getLogger(__name__)


def to_json(value):
    if value is not None and not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    return value


def from_json(value):
    if value is not None and not isinstance(value, dict) and not isinstance(value, list):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def delete_files(file_path):
    if os.path.isfile(file_path):
        if '\\' in file_path:
            deter = '\\'
        else:
            deter = '/'
        folder_path = file_path[:file_path.rfind(deter)]
        if os.path.isdir(folder_path):
            try:
                shutil.rmtree(folder_path)
            except OSError:
                print(f"Ошибка удаления директории")
        '''
        os.remove(file_path)
        folder_path = file_path[:file_path.rfind('.')]
        if os.path.exists(folder_path) and os.path.isdir(folder_path):
            for filename in os.listdir(folder_path):
                file_to_delete = os.path.join(folder_path, filename)
                try:
                    if os.path.isfile(file_to_delete):
                        os.remove(file_to_delete)  # удаляем файл
                except Exception as e:
                    print(f"Ошибка при удалении файла {file_to_delete}: {e}")
            try:
                shutil.rmtree(folder_path)
            except OSError:
                print(f"Ошибка удаления: не все файлы внутри папки были удалены")
        '''


def delete_files_from_json_field(field_value):
    if not field_value:
        return
    if isinstance(field_value, str):
        try:
            field_value = json.loads(field_value)
        except (json.JSONDecodeError, TypeError):
            return
    if isinstance(field_value, list) and len(field_value) > 0:
        if isinstance(field_value[0], dict):
            path = field_value[0].get('path')
            if path:
                delete_files(path)
    elif isinstance(field_value, dict):
        path = field_value.get('path')
        if path:
            delete_files(path)
    elif isinstance(field_value, QuerySet) and len(field_value) > 0 and isinstance(field_value[0], DocumentFile):
        for source in field_value:
            delete_files(source.path)
            source.delete()


def delete_document_file_instances(source_dict):
    logger.info('DELETEEEEE!!!')
    if isinstance(source_dict, QuerySet) and len(source_dict) > 0 and isinstance(source_dict[0], DocumentFile):
        for source in source_dict:
            logger.info(F'DELETEEEEE!!! {source}')
            source.delete()


# Модель для пользователей
class User(AbstractUser):
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png')

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        db_table = 'users'

    def save(self, *args, **kwargs):
        # Если у нас есть старый аватар и он не является значением по умолчанию
        if self.pk:  # Проверяем, что объект уже существует
            old_avatar = User.objects.get(pk=self.pk).avatar
            if self._should_delete_old_avatar(old_avatar):
                # Удаляем старый файл
                if default_storage.exists(old_avatar.name):
                    default_storage.delete(old_avatar.name)

        # Сохраняем новый аватар
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.avatar.name != 'avatars/default.png' and self.avatar:
            delete_files(self.avatar.path)
        super().delete(*args, **kwargs)

    def _should_delete_old_avatar(self, old_avatar):
        """Вспомогательный метод для тестирования логики удаления аватара"""
        if old_avatar and old_avatar.name != 'avatars/default.png' and \
                self.avatar and self.avatar.name != old_avatar.name:
            return True
        return False


# Модель для пользовательских загрузок
class UserTasks(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    task_id = models.CharField(max_length=255)
    files_type = models.CharField(max_length=255)
    upload_source = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"User task {self.id}"

    class Meta:
        verbose_name = "Пользовательская загрузка"
        verbose_name_plural = "Пользовательские загрузки"
        db_table = 'user_tasks'

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        super().save(*args, **kwargs)

    @property
    def upload_source_dict(self):
        return from_json(self.upload_source)


# Модель для файлов документов
class DocumentFile(models.Model):
    DOCUMENT_TYPES = (
        ('Act', 'Акт'),
        ('ScientificReport', 'Научный отчёт'),
        ('TechReport', 'Научно-технический отчёт'),
        ('OpenLists', 'Открытый лист'),
        ('ObjectAccountCard', 'Учётная карта'),
        ('ArchaeologicalHeritageSite', 'ОАН'),
        ('IdentifiedArchaeologicalHeritageSite', 'ВОАН'),
        ('CommercialOffers', 'Коммерческое предложение'),
        ('GeoObject', 'Географический объект'),
    )
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    document_id = models.PositiveIntegerField()

    file_type = models.CharField(max_length=50, null=True, blank=True)  # main, supplement, map, etc.
    path = models.TextField()
    origin_filename = models.CharField(max_length=255, null=True)
    file_hash = models.CharField(max_length=64, null=True, blank=True)
    file_size = models.CharField(max_length=20, null=True, blank=True)
    date_uploaded = models.DateTimeField(auto_now_add=True)

    metadata = models.JSONField(default=dict, null=True, blank=True)

    def __str__(self):
        return f"DocumentFile {self.id} / {self.document_type} = {self.document_id}"

    def save(self, *args, **kwargs):
        if self.file_type != 'folder':
            self.file_hash = calculate_file_hash(self.path)
            self.file_size = get_file_size(self.path)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Исходный файл"
        verbose_name_plural = "Исходные файлы"
        db_table = 'document_files'


# Модель для актов
class Act(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    date_uploaded = models.DateTimeField(auto_now_add=True)
    upload_source = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    year = models.TextField(blank=True)
    finish_date = models.TextField(blank=True)
    type = models.TextField(blank=True)
    name_number = models.TextField(blank=True)
    place = models.TextField(blank=True)
    customer = models.TextField(blank=True)
    area = models.TextField(blank=True)
    expert = models.TextField(blank=True)
    executioner = models.TextField(blank=True)
    open_list = models.TextField(blank=True)
    conclusion = models.TextField(blank=True)
    border_objects = models.TextField(blank=True)
    source_files = None

    act = models.TextField(blank=True)
    start_date = models.TextField(blank=True)
    exp_place = models.TextField(blank=True)
    exp_customer = models.TextField(blank=True)
    exp_expert = models.TextField(blank=True)
    relationship = models.TextField(blank=True)
    goal = models.TextField(blank=True)
    object = models.TextField(blank=True)
    docs = models.TextField(blank=True)
    exp_info = models.TextField(blank=True)
    exp_facts = models.TextField(blank=True)
    literature = models.TextField(blank=True)
    exp_conclusion = models.TextField(blank=True)
    supplement = models.JSONField(null=True, blank=True)
    coordinates = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Act {self.id} by {self.user.username}"

    class Meta:
        verbose_name = "Акт ГИКЭ"
        verbose_name_plural = "Акты ГИКЭ"
        db_table = 'acts'

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        self.supplement = to_json(self.supplement)
        self.coordinates = to_json(self.coordinates)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        logger.info(f'has attr: {hasattr(self, '_raw_delete')}')
        if hasattr(self, '_raw_delete'):
            logger.info(f'_raw_delete: {self._raw_delete}')
        if hasattr(self, '_raw_delete') and self._raw_delete:
            delete_document_file_instances(self.source_dict)
            super().delete(*args, **kwargs)
        else:
            delete_files_from_json_field(self.source_dict)
            super().delete(*args, **kwargs)

    @property
    def upload_source_dict(self):
        return from_json(self.upload_source)

    @property
    def source_dict(self):
        if self.source_files is None:
            self.source_files = DocumentFile.objects.filter(document_type='Act', document_id=self.id)
        return self.source_files

    @property
    def supplement_dict(self):
        return from_json(self.supplement)

    @property
    def coordinates_dict(self):
        return from_json(self.coordinates)


# Модель для научных отчетов
class ScientificReport(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    date_uploaded = models.DateTimeField(auto_now_add=True)
    upload_source = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    name = models.TextField(blank=True)
    organization = models.TextField(blank=True)
    author = models.TextField(blank=True)
    open_list = models.TextField(blank=True)
    writing_date = models.TextField(blank=True)
    introduction = models.TextField(blank=True)
    contractors = models.TextField(blank=True)
    place = models.TextField(blank=True)
    area_info = models.TextField(blank=True)
    research_history = models.TextField(blank=True)
    results = models.TextField(blank=True)
    conclusion = models.TextField(blank=True)
    source_files = None
    content = models.JSONField(null=True, blank=True)
    supplement = models.JSONField(null=True, blank=True)
    coordinates = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Scientific Report {self.id} by {self.user.username}"

    class Meta:
        verbose_name = "Научный отчёт"
        verbose_name_plural = "Научные отчёты"
        db_table = 'scientific_reports'

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        self.supplement = to_json(self.supplement)
        self.content = to_json(self.content)
        self.coordinates = to_json(self.coordinates)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if hasattr(self, '_raw_delete') and self._raw_delete:
            delete_document_file_instances(self.source_dict)
            super().delete(*args, **kwargs)
        else:
            delete_files_from_json_field(self.source_dict)
            super().delete(*args, **kwargs)

    @property
    def upload_source_dict(self):
        return from_json(self.upload_source)

    @property
    def source_dict(self):
        if self.source_files is None:
            self.source_files = DocumentFile.objects.filter(document_type='ScientificReport', document_id=self.id)
        return self.source_files

    @property
    def supplement_dict(self):
        return from_json(self.supplement)

    @property
    def content_dict(self):
        return from_json(self.content)

    @property
    def coordinates_dict(self):
        return from_json(self.coordinates)


# Модель для научно-технических отчетов
class TechReport(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    date_uploaded = models.DateTimeField(auto_now_add=True)
    upload_source = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    name = models.TextField(blank=True)
    organization = models.TextField(blank=True)
    author = models.TextField(blank=True)
    open_list = models.TextField(blank=True)
    writing_date = models.TextField(blank=True)
    introduction = models.TextField(blank=True)
    contractors = models.TextField(blank=True)
    place = models.TextField(blank=True)
    area_info = models.TextField(blank=True)
    research_history = models.TextField(blank=True)
    results = models.TextField(blank=True)
    conclusion = models.TextField(blank=True)
    source_files = None
    content = models.JSONField(null=True, blank=True)
    supplement = models.JSONField(null=True, blank=True)
    coordinates = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Tech Report {self.id} by {self.user.username}"

    class Meta:
        verbose_name = "Научно-технический отчёт"
        verbose_name_plural = "Научно-технические отчёты"
        db_table = 'tech_reports'

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        self.supplement = to_json(self.supplement)
        self.content = to_json(self.content)
        self.coordinates = to_json(self.coordinates)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if hasattr(self, '_raw_delete') and self._raw_delete:
            delete_document_file_instances(self.source_dict)
            super().delete(*args, **kwargs)
        else:
            delete_files_from_json_field(self.source_dict)
            super().delete(*args, **kwargs)

    @property
    def upload_source_dict(self):
        return from_json(self.upload_source)

    @property
    def source_dict(self):
        if self.source_files is None:
            self.source_files = DocumentFile.objects.filter(document_type='TechReport', document_id=self.id)
        return self.source_files

    @property
    def supplement_dict(self):
        return from_json(self.supplement)

    @property
    def content_dict(self):
        return from_json(self.content)

    @property
    def coordinates_dict(self):
        return from_json(self.coordinates)


# Модель для открытых листов
class OpenLists(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    date_uploaded = models.DateTimeField(auto_now_add=True)
    upload_source = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    number = models.TextField(blank=True)
    holder = models.TextField(blank=True)
    object = models.TextField(blank=True)
    works = models.TextField(blank=True)
    start_date = models.TextField(blank=True)
    end_date = models.TextField(blank=True)
    source_files = None

    def __str__(self):
        return f"Open list {self.id}"

    class Meta:
        verbose_name = "Открытый лист"
        verbose_name_plural = "Открытые листы"
        db_table = 'open_lists'

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if hasattr(self, '_raw_delete') and self._raw_delete:
            delete_document_file_instances(self.source_dict)
            super().delete(*args, **kwargs)
        else:
            delete_files_from_json_field(self.source_dict)
            super().delete(*args, **kwargs)

    @property
    def upload_source_dict(self):
        return from_json(self.upload_source)

    @property
    def source_dict(self):
        if self.source_files is None:
            self.source_files = DocumentFile.objects.filter(document_type='OpenLists', document_id=self.id)
        return self.source_files


class ObjectAccountCard(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    date_uploaded = models.DateTimeField(auto_now_add=True)
    upload_source = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    name = models.TextField()
    creation_time = models.TextField()
    address = models.TextField()
    object_type = models.TextField()
    general_classification = models.TextField()
    description = models.TextField()
    usage = models.TextField()
    discovery_info = models.TextField()
    compiler = models.TextField()
    compile_date = models.TextField()
    supplement = models.JSONField(null=True, blank=True)
    coordinates = models.JSONField(null=True, blank=True)
    source_files = None

    def __str__(self):
        return f"Object Account Card {self.id} by {self.user.username}"

    class Meta:
        verbose_name = "Учётная карта"
        verbose_name_plural = "Учётные карты"
        db_table = 'object_account_cards'

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        self.supplement = to_json(self.supplement)
        self.coordinates = to_json(self.coordinates)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if hasattr(self, '_raw_delete') and self._raw_delete:
            delete_document_file_instances(self.source_dict)
            super().delete(*args, **kwargs)
        else:
            delete_files_from_json_field(self.source_dict)
            super().delete(*args, **kwargs)

    @property
    def upload_source_dict(self):
        return from_json(self.upload_source)

    @property
    def source_dict(self):
        if self.source_files is None:
            self.source_files = DocumentFile.objects.filter(document_type='ObjectAccountCard', document_id=self.id)
        return self.source_files

    @property
    def supplement_dict(self):
        return from_json(self.supplement)

    @property
    def coordinates_dict(self):
        return from_json(self.coordinates)


class ArchaeologicalHeritageSite(models.Model):
    account_card = models.ForeignKey(ObjectAccountCard, on_delete=models.SET_NULL, null=True,
                                     blank=True)  # , on_delete=models.CASCADE
    date_uploaded = models.DateTimeField(auto_now_add=True)
    doc_name = models.TextField(null=True, blank=True)
    district = models.TextField(null=True, blank=True)
    document = models.TextField(null=True, blank=True)
    register_num = models.TextField(null=True, blank=True)
    is_excluded = models.BooleanField(default=False)
    source = models.TextField(null=True, blank=True)
    source_files = None

    class Meta:
        verbose_name = "Объект археологического наследия"
        verbose_name_plural = "Объекты археологического наследия"
        db_table = 'archaeological_heritage_sites'

    def __str__(self):
        return self.doc_name or f"ОАН {self.id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if hasattr(self, '_raw_delete') and self._raw_delete:
            delete_document_file_instances(self.document_source_dict)
            super().delete(*args, **kwargs)
        else:
            delete_files_from_json_field(self.document_source_dict)
            if self.source and len(self.source) > 0:
                delete_files(self.source)
            super().delete(*args, **kwargs)

    @property
    def document_source_dict(self):
        if self.source_files is None:
            self.source_files = DocumentFile.objects.filter(document_type='ArchaeologicalHeritageSite',
                                                            document_id=self.id,
                                                            file_type='document')
        return self.source_files
        # return from_json(self.document_source)


class IdentifiedArchaeologicalHeritageSite(models.Model):
    account_card = models.ForeignKey(ObjectAccountCard, on_delete=models.SET_NULL, null=True,
                                     blank=True)  # , on_delete=models.CASCADE
    date_uploaded = models.DateTimeField(auto_now_add=True)
    name = models.TextField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    obj_info = models.TextField(null=True, blank=True)
    document = models.TextField(null=True, blank=True)
    is_excluded = models.BooleanField(default=False)
    source = models.TextField(null=True, blank=True)
    source_files = None

    class Meta:
        verbose_name = "Выявленный объект археологического наследия"
        verbose_name_plural = "Выявленные объекты археологического наследия"
        db_table = 'identified_archaeological_heritage_sites'

    def __str__(self):
        return self.name or f"ВОАН {self.id}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if hasattr(self, '_raw_delete') and self._raw_delete:
            delete_document_file_instances(self.document_source_dict)
            super().delete(*args, **kwargs)
        else:
            delete_files_from_json_field(self.document_source_dict)
            if self.source and len(self.source) > 0:
                delete_files(self.source)
            super().delete(*args, **kwargs)

    @property
    def document_source_dict(self):
        if self.source_files is None:
            self.source_files = DocumentFile.objects.filter(document_type='ArchaeologicalHeritageSite',
                                                            document_id=self.id,
                                                            file_type='document')
        return self.source_files


class CommercialOffers(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    date_uploaded = models.DateTimeField(auto_now_add=True)
    upload_source = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    coordinates = models.JSONField(null=True, blank=True)
    source_files = None

    def __str__(self):
        return f"Commercial Offer {self.id} by {self.user.username}"

    class Meta:
        verbose_name = "Коммерческое предложение"
        verbose_name_plural = "Коммерческие предложения"
        db_table = 'commercial_offers'

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        self.coordinates = to_json(self.coordinates)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if hasattr(self, '_raw_delete') and self._raw_delete:
            delete_document_file_instances(self.source_dict)
            super().delete(*args, **kwargs)
        else:
            delete_files_from_json_field(self.source_dict)
            super().delete(*args, **kwargs)

    @property
    def source_dict(self):
        if self.source_files is None:
            self.source_files = DocumentFile.objects.filter(document_type='Act', document_id=self.id)
        return self.source_files

    @property
    def upload_source_dict(self):
        return from_json(self.upload_source)

    @property
    def coordinates_dict(self):
        return from_json(self.coordinates)


class GeoObject(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    date_uploaded = models.DateTimeField(auto_now_add=True)
    upload_source = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    name = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(max_length=255, null=True, blank=True)
    coordinates = models.JSONField(null=True, blank=True)
    source_files = None

    class Meta:
        verbose_name = "Географический объект"
        verbose_name_plural = "Географические объекты"
        db_table = 'geo_object'

    def __str__(self):
        return self.name or f"Географический объект {self.id}"

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        self.coordinates = to_json(self.coordinates)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if hasattr(self, '_raw_delete') and self._raw_delete:
            delete_document_file_instances(self.source_dict)
            super().delete(*args, **kwargs)
        else:
            delete_files_from_json_field(self.source_dict)
            super().delete(*args, **kwargs)

    @property
    def source_dict(self):
        if self.source_files is None:
            self.source_files = DocumentFile.objects.filter(document_type='Act', document_id=self.id)
        return self.source_files

    @property
    def upload_source_dict(self):
        return from_json(self.upload_source)

    @property
    def coordinates_dict(self):
        return from_json(self.coordinates)


class GeojsonData(models.Model):
    name = models.CharField(max_length=255, null=True, blank=True)
    geojson = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = "Геоданные"
        verbose_name_plural = "Геоданные"
        db_table = 'geojson_data'

    def __str__(self):
        return self.name or f"Запись {self.id}"


class Chat(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Чат"
        verbose_name_plural = "Чаты"
        db_table = 'chats'

    def __str__(self):
        return self.name or f"Чат {self.id}"


class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE)
    sender = models.CharField(max_length=255)
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        db_table = 'messages'

    def __str__(self):
        return f"Сообщение от {self.sender} в чате {self.chat.name}"
