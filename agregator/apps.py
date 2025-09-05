from pathlib import Path

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AgregatorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agregator'

    '''  Занесение всех районов Красноярского Края в БД
    '''

    def ready(self):
        print("AgregatorConfig.ready() вызван")
        # Подключаем сигнал
        post_migrate.connect(self.load_geojson_data)

        # Создаем папки при запуске
        self.create_folders()

    def load_geojson_data(self, **kwargs):
        print("Сигнал post_migrate получен")
        from .processing.coordinates_extraction import save_geojson_polygons_to_db
        save_geojson_polygons_to_db()

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
        ]
        for folder in folders:
            nested_folders = Path(folder)
            nested_folders.mkdir(parents=True, exist_ok=True)
