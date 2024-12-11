import os
from celery import Celery

# Устанавливаем переменную окружения для Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'archeology.settings')

# Создаём экземпляр Celery
app = Celery('archeology')

# Загружаем настройки Django и добавляем конфигурацию Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически загружает задачи из всех зарегистрированных Django приложений
app.autodiscover_tasks()
