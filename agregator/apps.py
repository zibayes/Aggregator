from django.apps import AppConfig


class AgregatorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agregator'

    '''  Занесение всех районов Красноярского Края в БД
    
    def ready(self):
        from .coordinates_extraction import save_geojson_polygons_to_db
        save_geojson_polygons_to_db()
    '''
