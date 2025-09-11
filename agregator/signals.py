from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from agregator.processing.links import create_link_for_instance
import os


@receiver(post_save)
def auto_create_links(sender, instance, created, **kwargs):
    """Автоматическое создание ссылок после сохранения"""
    if sender.__name__ in ['Act', 'ScientificReport', 'TechReport', 'OpenLists',
                           'ObjectAccountCard', 'ArchaeologicalHeritageSite',
                           'IdentifiedArchaeologicalHeritageSite', 'CommercialOffers', 'GeoObject']:
        if created:
            create_link_for_instance(instance)


@receiver(post_delete)
def auto_delete_links(sender, instance, **kwargs):
    """Автоматическое удаление ссылок после удаления объекта"""
    if sender.__name__ in ['Act', 'ScientificReport', 'TechReport', 'OpenLists',
                           'ObjectAccountCard', 'ArchaeologicalHeritageSite',
                           'IdentifiedArchaeologicalHeritageSite', 'CommercialOffers', 'GeoObject']:
        try:
            source_path = None
            if hasattr(instance, 'source_dict') and instance.source_dict:
                source_path = instance.source_dict[0]['path']
            elif hasattr(instance, 'source') and instance.source:
                source_path = instance.source

            if source_path:
                link_dir = os.path.dirname(source_path)
                link_path = os.path.join(link_dir, f"{instance.__class__.__name__}_{instance.id}.url")
                if os.path.exists(link_path):
                    os.remove(link_path)

        except Exception as e:
            print(f"Error deleting link for {instance}: {e}")
