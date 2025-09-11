import os
from django.urls import reverse
from django.conf import settings
from archeology.settings import BASE_URL


def create_url_file(file_path, target_url):
    """Создает .url файл"""
    url_content = f"""[InternetShortcut]
URL={target_url}
"""
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(url_content)


def get_object_url(instance):
    """Генерирует URL для объекта"""
    model_name = instance.__class__.__name__.lower()
    base_url = BASE_URL

    # Маппинг моделей на URL patterns
    url_map = {
        'act': 'acts',
        'scientificreport': 'scientific_reports',
        'techreport': 'tech_reports',
        'openlists': 'open_lists',
        'objectaccountcard': 'account_cards',
        'archaeologicalheritagesite': 'archaeological_heritage_sites',
        'identifiedarchaeologicalheritagesite': 'identified_archaeological_heritage_sites',
        'commercialoffers': 'map/commercial_offer',  # или commercial_offers если есть
        'geoobject': 'map/geo_object'  # или geo_objects если есть
    }

    url_name = url_map.get(model_name)
    if url_name:
        return f"{base_url}/{url_name}/{instance.pk}/"

    # Фолбэк на админку
    return f"{base_url}/admin/agregator/{model_name}/{instance.pk}/"


def create_link_for_instance(instance):
    """Создает ссылку для экземпляра модели"""
    try:
        source_path = None

        # Определяем путь к исходному файлу/папке
        if instance.__class__.__name__ == 'OpenLists':
            if hasattr(instance, 'source') and instance.source:
                source_path = instance.source.path
        elif hasattr(instance, 'source_dict') and instance.source_dict:
            source_path = instance.source_dict[0]['path']
        elif hasattr(instance, 'source') and instance.source:
            source_path = instance.source
        elif hasattr(instance, 'document_source_dict') and instance.document_source_dict:
            source_path = instance.document_source_dict[0]['path']

        if source_path and os.path.exists(source_path):
            if not (instance.__class__.__name__ in ['ArchaeologicalHeritageSite',
                                                    'IdentifiedArchaeologicalHeritageSite'] and hasattr(instance,
                                                                                                        'source') and instance.source):
                link_dir = os.path.dirname(source_path)
            else:
                link_dir = source_path
            target_url = get_object_url(instance)
            link_filename = f"{instance.__class__.__name__}_{instance.id}.url"
            link_path = os.path.join(link_dir, link_filename)

            create_url_file(link_path, target_url)
            return link_path

    except Exception as e:
        print(f"Error creating link for {instance}: {e}")
    return None


def create_links_for_all_existing():
    """Создает ссылки для всех существующих объектов"""
    from agregator.models import (Act, ScientificReport, TechReport, OpenLists,
                                  ObjectAccountCard, ArchaeologicalHeritageSite,
                                  IdentifiedArchaeologicalHeritageSite, CommercialOffers, GeoObject)

    models = [Act, ScientificReport, TechReport, OpenLists,
              ObjectAccountCard, ArchaeologicalHeritageSite,
              IdentifiedArchaeologicalHeritageSite, CommercialOffers, GeoObject]

    created_count = 0
    for model in models:
        for obj in model.objects.all():
            if create_link_for_instance(obj):
                created_count += 1

    return created_count
