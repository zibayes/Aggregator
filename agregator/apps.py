import json
import traceback
from pathlib import Path

from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from celery import current_app
from agregator.redis_config import redis_client
import logging

logger = logging.getLogger(__name__)


class AgregatorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agregator'

    '''  Занесение всех районов Красноярского Края в БД
    '''

    def ready(self):
        print("AgregatorConfig.ready() вызван")
        import agregator.signals
        # Подключаем сигналы для автоматического создания ссылок
        self.connect_model_signals()
        # Создаем папки при запуске
        self.create_folders()
        # Возобновление обработки при перезапуске сервера
        self.recover_tasks()

        # self.revoke_all_tasks()

    def recover_tasks(self):
        r = redis_client
        task_ids = r.hvals('unacked')

        for task_id in task_ids:
            logger.info(f'task_id = {task_id}')
            try:
                progress_json = redis_client.get(json.loads(task_id)[0]['headers']['id'])
                if progress_json is not None:
                    progress_json = json.loads(progress_json)
                    logger.info(f'TASK IS IN WORK')
                    current_app.send_task(
                        progress_json['task_name'],
                        args=progress_json['args'],
                        kwargs=progress_json['kwargs'],
                        task_id=progress_json['task_id']
                    )
                else:
                    logger.info(f'TASK NOT FOUND')
            except Exception as e:
                logger.error(f'Ошибка при возобновлении задачи: {e}')
                logger.error(traceback.format_exc())
                continue

        # После перезапуска можно очистить unacked
        r.delete('unacked', 'unacked_index')

    def revoke_all_tasks(self):
        app = current_app
        if not app:
            return

        # 1. Отзываем все активные задачи с сигналом SIGTERM (9)
        inspector = app.control.inspect()
        active = inspector.active() or {}
        reserved = inspector.reserved() or {}
        scheduled = inspector.scheduled() or {}

        for worker, tasks in {**active, **reserved, **scheduled}.items():
            for task in tasks:
                task_id = task.get('id')
                if task_id:
                    app.control.revoke(task_id, terminate=True, signal='SIGKILL')

        # 2. Чистим очередь (удаляем сообщения из брокера)
        app.control.purge()

    @receiver(post_migrate)
    def load_geojson_data(sender, **kwargs):
        if sender.name == 'agregator':
            logger.info("Сигнал post_migrate получен")
            from .processing.coordinates_extraction import save_geojson_polygons_to_db
            save_geojson_polygons_to_db()

    def connect_model_signals(self):
        """Подключаем сигналы для моделей"""
        from django.db.models.signals import post_save, post_delete
        from agregator.models import (Act, ScientificReport, TechReport, OpenLists,
                                      ObjectAccountCard, ArchaeologicalHeritageSite,
                                      IdentifiedArchaeologicalHeritageSite, CommercialOffers, GeoObject)
        from agregator.signals import auto_create_links, auto_delete_links

        models = [Act, ScientificReport, TechReport, OpenLists,
                  ObjectAccountCard, ArchaeologicalHeritageSite,
                  IdentifiedArchaeologicalHeritageSite, CommercialOffers, GeoObject]

        for model in models:
            post_save.connect(auto_create_links, sender=model)
            post_delete.connect(auto_delete_links, sender=model)

        logger.info("Сигналы для автоматических ссылок подключены")

    @receiver(post_migrate)
    def create_links_for_existing(sender, **kwargs):
        if sender.name == 'agregator':
            logger.info("Создание ссылок для существующих объектов...")
            from agregator.processing.links import create_links_for_all_existing
            create_links_for_all_existing()

    def create_folders(self):
        """Создание системных папок"""
        folders = [
            'uploaded_files',

            'uploaded_files/avatars',

            'uploaded_files/regions_polygons/Красноярский край/ЗАТО (городские округа)',
            'uploaded_files/regions_polygons/Красноярский край/Краевые города (городские округа)',
            'uploaded_files/regions_polygons/Красноярский край/Округа (муниципальные округа)',
            'uploaded_files/regions_polygons/Красноярский край/Районы (муниципальные районы)',

            'uploaded_files/Акты ГИКЭ',
            'uploaded_files/Научные отчёты',
            'uploaded_files/Научно-технические отчёты',

            'uploaded_files/Открытые листы',

            'uploaded_files/Учётные карты',
            'uploaded_files/Памятники',
            'uploaded_files/Коммерческие предложения',

            'uploaded_files/Географические объекты',
        ]
        for folder in folders:
            nested_folders = Path(folder)
            nested_folders.mkdir(parents=True, exist_ok=True)
