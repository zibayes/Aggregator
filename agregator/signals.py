from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from agregator.processing.links import create_link_for_instance
import os
import logging

logger = logging.getLogger(__name__)

# Словарь сопоставления имен классов (используем __qualname__)
MODEL_NAMES = {
    'Act',
    'ScientificReport',
    'TechReport',
    'OpenLists',
    'ObjectAccountCard',
    'ArchaeologicalHeritageSite',
    'IdentifiedArchaeologicalHeritageSite',
    'CommercialOffers',
    'GeoObject'
}


@receiver(post_save)
def auto_create_links(sender, instance, created, **kwargs):
    """Автоматическое создание ссылок после сохранения"""
    class_name = sender.__name__
    logger.info(f"Сигнал post_save: sender={sender}, class_name={class_name}, created={created}")

    if class_name in MODEL_NAMES:
        if created:
            logger.info(f"Создание ссылки для {class_name} (id={instance.id})")
            try:
                link_path = create_link_for_instance(instance)
                if link_path:
                    logger.info(f"Ссылка успешно создана: {link_path}")
                else:
                    logger.warning(f"Ссылка не создана для {class_name} (id={instance.id})")
            except Exception as e:
                logger.error(f"Ошибка при создании ссылки: {str(e)}", exc_info=True)
        else:
            logger.debug(f"Обновление объекта {class_name} (id={instance.id}) - ссылка не создается")
    else:
        logger.debug(f"Модель {class_name} не требует создания ссылки")


@receiver(post_delete)
def auto_delete_links(sender, instance, **kwargs):
    """Автоматическое удаление ссылок после удаления объекта"""
    class_name = sender.__name__
    logger.info(f"Сигнал post_delete: sender={sender}, class_name={class_name}")

    if class_name in MODEL_NAMES:
        try:
            source_path = None
            if hasattr(instance, 'source_dict') and instance.source_dict:
                source_path = instance.source_dict[0]['path']
            elif hasattr(instance, 'source') and instance.source:
                source_path = instance.source

            if source_path:
                link_dir = os.path.dirname(source_path)
                link_path = os.path.join(link_dir, f"{class_name}_{instance.id}.url")
                if os.path.exists(link_path):
                    os.remove(link_path)
                    logger.info(f"Ссылка удалена: {link_path}")
                else:
                    logger.warning(f"Ссылка не найдена для удаления: {link_path}")
            else:
                logger.warning(f"Не найден source_path для удаления ссылки {class_name} (id={instance.id})")
        except Exception as e:
            logger.error(f"Ошибка при удалении ссылки: {str(e)}", exc_info=True)
