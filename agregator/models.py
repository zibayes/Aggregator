from django.db import models
from django.contrib.auth.models import AbstractUser
from archeology.settings import AUTH_USER_MODEL
from django.core.files.storage import default_storage
import os
import shutil


def delete_files(source):
    if source:
        file_path = source.path
        if os.path.isfile(file_path):
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
                    os.rmdir(folder_path)
                except OSError:
                    print(f"Ошибка удаления: не все файлы внутри папки были удалены")


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
        if self.avatar.name != 'avatars/default.png':
            delete_files(self.avatar)
        super().delete(*args, **kwargs)


# Модель для приложений
class Supplement(models.Model):
    maps = models.TextField()
    object_fotos = models.TextField()
    pits_fotos = models.TextField()
    plans = models.TextField()
    material_fotos = models.TextField()
    heritage_info = models.TextField()

    def __str__(self):
        return f"Supplement {self.id}"

    class Meta:
        db_table = 'supplements'


# Модель для актов
class Act(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    supplement = models.ForeignKey(Supplement, on_delete=models.CASCADE, null=True, blank=True)

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
    source = models.FileField(upload_to='acts/')

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

    def __str__(self):
        return f"Act {self.id} by {self.user.username}"

    class Meta:
        db_table = 'acts'

    def delete(self, *args, **kwargs):
        supplement = Supplement.objects.get(id=self.supplement.id)
        supplement.delete()
        delete_files(self.source)
        super().delete(*args, **kwargs)


# Модель для научных отчетов
class ScientificReport(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    supplement = models.ForeignKey(Supplement, on_delete=models.CASCADE, null=True, blank=True)
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
    source = models.FileField(upload_to='reports/')

    def __str__(self):
        return f"Scientific Report {self.id} by {self.user.username}"

    class Meta:
        db_table = 'scientific_reports'

    def delete(self, *args, **kwargs):
        supplement = Supplement.objects.get(id=self.supplement.id)
        supplement.delete()
        delete_files(self.source)
        super().delete(*args, **kwargs)


# Модель для научно-технических отчетов
class TechReport(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    supplement = models.ForeignKey(Supplement, on_delete=models.CASCADE, null=True, blank=True)
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
    source = models.FileField(upload_to='reports/')

    def __str__(self):
        return f"Tech Report {self.id} by {self.user.username}"

    class Meta:
        db_table = 'tech_reports'

    def delete(self, *args, **kwargs):
        supplement = Supplement.objects.get(id=self.supplement.id)
        supplement.delete()
        delete_files(self.source)
        super().delete(*args, **kwargs)


# Модель для открытых листов
class OpenLists(models.Model):
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
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

    def delete(self, *args, **kwargs):
        delete_files(self.source)
        super().delete(*args, **kwargs)
