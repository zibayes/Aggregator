import json
import traceback
from datetime import datetime

from celery import shared_task
from agregator.models import CommercialOffers, ObjectAccountCard, Act, ScientificReport, TechReport, GeoObject, \
    OpenLists
import logging

from agregator.redis_config import redis_client

logger = logging.getLogger(__name__)


def get_model(model_name):
    if model_name == 'commercial_offer':
        return CommercialOffers
    if model_name == 'account_card':
        return ObjectAccountCard
    if model_name == 'act':
        return Act
    if model_name == 'scientific_report':
        return ScientificReport
    if model_name == 'tech_report':
        return TechReport
    if model_name == 'geo_object':
        return GeoObject
    if model_name == 'open_list':
        return OpenLists
    return None


@shared_task
def error_handler(model, task, exception, exception_desc):
    logger.error(f"Задача {task.id} для {model} завершилась с ошибкой: {exception} {exception_desc}")
    is_report = 'report' in model or model == 'act'
    model = get_model(model)
    progress_json = redis_client.get(task.id)
    if progress_json is None:
        progress_json = redis_client.get('celery-task-meta-' + str(task.id))
    progress_json = json.loads(progress_json)
    if is_report:
        for report_id, sources in progress_json['file_groups'].items():
            deleted_report = False
            for source in sources:
                if source['processed'] != 'True':
                    report = model.objects.get(id=report_id)
                    report.delete()
                    deleted_report = True
                    break
            if deleted_report:
                continue
    else:
        for object_id, source in progress_json['file_groups'].items():
            logger.info(object_id, source)
            if source['processed'] != 'True':
                model_object = model.objects.get(id=object_id)
                model_object.delete()
    progress_json['time_ended'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raise type(exception)({"error_text": str(exception), "progress_json": progress_json}) from exception
