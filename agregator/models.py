import json

from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from archeology.settings import AUTH_USER_MODEL
from django.core.files.storage import default_storage
from django_celery_results.models import TaskResult
import os
import shutil


def to_json(value):
    if value is not None and not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
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


# Модель для пользователей
class User(AbstractUser):
    avatar = models.ImageField(upload_to='avatars/', default='avatars/default.png')

    def __str__(self):
        return self.username

    class Meta:
        db_table = 'users'

    def save(self, *args, **kwargs):
        # Если у нас есть старый аватар и он не является значением по умолчанию
        if self.pk:  # Проверяем, что объект уже существует
            old_avatar = User.objects.get(pk=self.pk).avatar
            if old_avatar and old_avatar.name != 'avatars/default.png' and \
                    self.avatar and self.avatar.name != old_avatar.name:
                # Удаляем старый файл
                if default_storage.exists(old_avatar.name):
                    default_storage.delete(old_avatar.name)

        # Сохраняем новый аватар
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.avatar.name != 'avatars/default.png' and self.avatar:
            delete_files(self.avatar.path)
        super().delete(*args, **kwargs)


# Модель для пользовательских загрузок
class UserTasks(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    task_id = models.CharField(max_length=255)
    files_type = models.CharField(max_length=255)
    upload_source = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"User task {self.id}"

    class Meta:
        db_table = 'user_tasks'

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        super().save(*args, **kwargs)


# Модель для актов
class Act(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    date_uploaded = models.DateTimeField(auto_now_add=True)
    upload_source = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    year = models.TextField()
    finish_date = models.TextField()
    type = models.TextField()
    name_number = models.TextField()
    place = models.TextField()
    customer = models.TextField()
    area = models.TextField()
    expert = models.TextField()
    executioner = models.TextField()
    open_list = models.TextField()
    conclusion = models.TextField()
    border_objects = models.TextField()
    source = models.JSONField(null=True, blank=True)

    act = models.TextField()
    start_date = models.TextField()
    exp_place = models.TextField()
    exp_customer = models.TextField()
    exp_expert = models.TextField()
    relationship = models.TextField()
    goal = models.TextField()
    object = models.TextField()
    docs = models.TextField()
    exp_info = models.TextField()
    exp_facts = models.TextField()
    literature = models.TextField()
    exp_conclusion = models.TextField()
    supplement = models.JSONField(null=True, blank=True)
    coordinates = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Act {self.id} by {self.user.username}"

    class Meta:
        db_table = 'acts'

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        self.source = to_json(self.source)
        self.supplement = to_json(self.supplement)
        self.coordinates = to_json(self.coordinates)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.source and len(self.source) > 0:
            delete_files(self.source[0]['path'])
        super().delete(*args, **kwargs)


# Модель для научных отчетов
class ScientificReport(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    date_uploaded = models.DateTimeField(auto_now_add=True)
    upload_source = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    name = models.TextField()
    organization = models.TextField()
    author = models.TextField()
    open_list = models.TextField()
    writing_date = models.TextField()
    introduction = models.TextField()
    contractors = models.TextField()
    place = models.TextField()
    area_info = models.TextField()
    research_history = models.TextField()
    results = models.TextField()
    conclusion = models.TextField()
    source = models.JSONField(null=True, blank=True)
    content = models.JSONField(null=True, blank=True)
    supplement = models.JSONField(null=True, blank=True)
    coordinates = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Scientific Report {self.id} by {self.user.username}"

    class Meta:
        db_table = 'scientific_reports'

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        self.source = to_json(self.source)
        self.supplement = to_json(self.supplement)
        self.content = to_json(self.content)
        self.coordinates = to_json(self.coordinates)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.source and len(self.source) > 0:
            delete_files(self.source[0]['path'])
        super().delete(*args, **kwargs)


# Модель для научно-технических отчетов
class TechReport(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    date_uploaded = models.DateTimeField(auto_now_add=True)
    upload_source = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    name = models.TextField()
    organization = models.TextField()
    author = models.TextField()
    open_list = models.TextField()
    writing_date = models.TextField()
    introduction = models.TextField()
    contractors = models.TextField()
    place = models.TextField()
    area_info = models.TextField()
    research_history = models.TextField()
    results = models.TextField()
    conclusion = models.TextField()
    source = models.JSONField(null=True, blank=True)
    content = models.JSONField(null=True, blank=True)
    supplement = models.JSONField(null=True, blank=True)
    coordinates = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Tech Report {self.id} by {self.user.username}"

    class Meta:
        db_table = 'tech_reports'

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        self.source = to_json(self.source)
        self.supplement = to_json(self.supplement)
        self.content = to_json(self.content)
        self.coordinates = to_json(self.coordinates)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.source and len(self.source) > 0:
            delete_files(self.source[0]['path'])
        super().delete(*args, **kwargs)


# Модель для открытых листов
class OpenLists(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    origin_filename = models.TextField()
    date_uploaded = models.DateTimeField(auto_now_add=True)
    upload_source = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)

    number = models.TextField()
    holder = models.TextField()
    object = models.TextField()
    works = models.TextField()
    start_date = models.TextField()
    end_date = models.TextField()
    source = models.FileField(upload_to='open_lists/')

    def __str__(self):
        return f"Open list {self.id}"

    class Meta:
        db_table = 'open_lists'

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.source:
            delete_files(self.source.path)
        super().delete(*args, **kwargs)


class ObjectAccountCard(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)

    date_uploaded = models.DateTimeField(auto_now_add=True)
    upload_source = models.JSONField(null=True, blank=True)
    is_processing = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    origin_filename = models.TextField()

    name = models.TextField()
    creation_time = models.TextField()
    address = models.TextField()
    object_type = models.TextField()
    general_classification = models.TextField()
    description = models.TextField()
    usage = models.TextField()
    discovery_info = models.TextField()
    compiler = models.TextField()
    supplement = models.JSONField(null=True, blank=True)
    coordinates = models.JSONField(null=True, blank=True)
    source = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Object Account Card {self.id} by {self.user.username}"

    class Meta:
        db_table = 'object_account_cards'

    def save(self, *args, **kwargs):
        self.upload_source = to_json(self.upload_source)
        self.supplement = to_json(self.supplement)
        self.coordinates = to_json(self.coordinates)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.source and len(self.source) > 0:
            delete_files(self.source)
        super().delete(*args, **kwargs)


class ArchaeologicalHeritageSite(models.Model):
    account_card = models.ForeignKey(ObjectAccountCard, on_delete=models.CASCADE)
    date_uploaded = models.DateTimeField(auto_now_add=True)
    doc_name = models.TextField(null=True, blank=True)
    district = models.TextField(null=True, blank=True)
    document = models.TextField(null=True, blank=True)
    register_num = models.TextField(null=True, blank=True)
    is_excluded = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Археологический объект культурного наследия"
        verbose_name_plural = "Археологические объекты культурного наследия"
        db_table = 'archaeological_heritage_sites'

    def __str__(self):
        return self.doc_name or f"Объект {self.id}"


class IdentifiedArchaeologicalHeritageSite(models.Model):
    account_card = models.ForeignKey(ObjectAccountCard, on_delete=models.CASCADE)
    date_uploaded = models.DateTimeField(auto_now_add=True)
    name = models.TextField(null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    obj_info = models.TextField(null=True, blank=True)
    document = models.TextField(null=True, blank=True)
    is_excluded = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Выявленный археологический объект культурного наследия"
        verbose_name_plural = "Выявленные археологические объекты культурного наследия"
        db_table = 'identified_archaeological_heritage_sites'

    def __str__(self):
        return self.name or f"Объект {self.id}"


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
