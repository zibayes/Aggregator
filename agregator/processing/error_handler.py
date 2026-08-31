import json
import traceback
from datetime import datetime

from celery import shared_task
import logging

from agregator.redis_config import redis_client, get_progress_json
from agregator.models import CommercialOffers, ObjectAccountCard, Act, ScientificReport, TechReport, GeoObject, \
    OpenLists

logger = logging.getLogger(__name__)


@shared_task
def error_handler(model, task, exception, exception_desc):
    logger.error(f"Задача {task.id} для {model} завершилась с ошибкой: {exception} {exception_desc}")
    progress_json = delete_instances_on_task_revoke(task.id)
    progress_json['time_ended'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raise type(exception)({"error_text": str(exception), "progress_json": progress_json}) from exception


def delete_instances_on_task_revoke(task_id, raw_delete=False):
    progress_json = get_progress_json(task_id)
    if progress_json is None:
        return None
    if 'is_reprocess' in progress_json and raw_delete is False:
        raw_delete = progress_json['is_reprocess']

    model = progress_json['file_types']
    is_report = 'report' in model or 'act' in model
    model = get_model(model)

    if 'file_groups' in progress_json:
        if is_report:
            for report_id, sources in progress_json['file_groups'].items():
                deleted_report = False
                for source in sources:
                    if source['processed'] != 'True':
                        report = model.objects.filter(id=report_id).first()
                        if report:
                            if raw_delete:
                                report._raw_delete = True
                            report.delete()
                        deleted_report = True
                        break
                if deleted_report:
                    continue
        else:
            for object_id, source in progress_json['file_groups'].items():
                if source['processed'] != 'True':
                    model_object = model.objects.filter(id=object_id).first()
                    if raw_delete:
                        model_object._raw_delete = True
                    if model_object:
                        model_object.delete()
    return progress_json


def get_model(model_name):
    if 'commercial_offer' in model_name:
        return CommercialOffers
    if 'account_card' in model_name:
        return ObjectAccountCard
    if 'act' in model_name:
        return Act
    if 'scientific_report' in model_name:
        return ScientificReport
    if 'tech_report' in model_name:
        return TechReport
    if 'geo_object' in model_name:
        return GeoObject
    if 'open_list' in model_name:
        return OpenLists
    return None
