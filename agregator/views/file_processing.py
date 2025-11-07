import os.path
import re
import json
import logging
from time import time

import pandas as pd
import simplekml
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth import logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django_celery_results.models import TaskResult
from celery.result import AsyncResult
from pyproj import Geod
from rest_framework import generics
from shapely.geometry import Polygon, LineString
from shapely.geometry import shape, Point
from shapely.ops import nearest_points

from agregator.models import User, Act, ScientificReport, TechReport, UserTasks
from agregator.views.utils import get_scan_task
from agregator.forms import UploadReportsForm, UploadOpenListsForm, UploadCommercialOffersForm, UploadGeoObjectsForm
from agregator.processing.files_saving import raw_reports_save, raw_open_lists_save, raw_account_cards_save, \
    raw_geo_objects_save, raw_commercial_offers_save
from agregator.processing.acts_processing import process_acts, error_handler_acts
from agregator.processing.scientific_reports_processing import process_scientific_reports, \
    error_handler_scientific_reports
from agregator.processing.tech_reports_processing import process_tech_reports, error_handler_tech_reports
from agregator.processing.open_lists_ocr import process_open_lists, error_handler_open_lists
from agregator.processing.external_sources import external_sources_processing
from agregator.processing.account_cards_processing import process_account_cards, error_handler_account_cards
from agregator.processing.commercial_offers_processing import process_commercial_offers, error_handler_commercial_offers
from agregator.processing.geo_objects_processing import process_geo_objects, error_handler_geo_objects
from agregator.processing.utils import str_is_int
from agregator.views.utils import upload_entity_view, get_user_tasks
from agregator.redis_config import redis_client

logger = logging.getLogger(__name__)


@login_required
def deconstructor(request):
    user = request.user
    tasks_id = get_user_tasks(user.id, ('act', 'scientific_report', 'tech_report'))
    if request.method == 'POST':
        if 'acts' in request.POST:
            form = UploadReportsForm()
            return render(request, 'deconstructor.html',
                          {'form': form, 'tasks_id': tasks_id})
        else:
            form = UploadReportsForm(request.POST, request.FILES)
            if form.is_valid():
                uploaded_files = form.cleaned_data['files']
                file_groups = {}
                if 'file_type' in request.POST and 'upload_type' in request.POST:
                    file_type = request.POST['file_type']
                    upload_type = request.POST['upload_type']
                    if user.is_superuser:
                        is_public = True if request.POST['storage_type'] == 'public' else False
                    else:
                        is_public = False
                else:
                    return render(request, 'deconstructor.html', {'form': form, 'tasks_id': tasks_id})
                types_convert = {'текст': 'text', 'приложение': 'images', 'иллюстрации': 'images'}
                if upload_type == 'fully':
                    file_groups['fully'] = []
                    for file in uploaded_files:
                        filename = file.name.lower()
                        report_type = 'all'
                        for typename in types_convert.keys():
                            if typename in filename:
                                index = filename.find(typename)
                                if index >= 0:
                                    report_type = types_convert[typename]
                                    break
                        file_groups['fully'].append({'type': report_type, 'file': file})
                    uploaded_files = []
                elif upload_type == 'mixed':
                    for i in range(len(uploaded_files) - 1, -1, -1):
                        group_name = None
                        filename = uploaded_files[i].name.lower()
                        report_type = 'all'
                        for typename in types_convert.keys():
                            if typename in filename:
                                index = filename.find(typename)
                                if index >= 0:
                                    if index == 0:
                                        group_name = filename[len(typename):]
                                    else:
                                        group_name = filename[:index]
                                    report_type = types_convert[typename]
                                    break
                        if group_name:
                            if group_name in file_groups.keys():
                                file_groups[group_name].append({'type': report_type, 'file': uploaded_files.pop(i)})
                            else:
                                file_groups[group_name] = [{'type': report_type, 'file': uploaded_files.pop(i)}]
                select_text = select_enrich = select_image = select_coord = False
                if 'select_text' in request.POST:
                    select_text = True
                if 'select_enrich' in request.POST:
                    select_enrich = True
                if 'select_image' in request.POST:
                    select_image = True
                if 'select_coord' in request.POST:
                    select_coord = True

                try:
                    if file_type == 'act':
                        acts_ids = raw_reports_save(file_groups, uploaded_files, Act, user.id, is_public)
                        task = process_acts.apply_async(
                            (acts_ids, user.id, select_text, select_enrich, select_image, select_coord),
                            link_error=error_handler_acts.s())
                    elif file_type == 'scientific_report':
                        scientific_reports_ids = raw_reports_save(file_groups, uploaded_files, ScientificReport,
                                                                  user.id, is_public)
                        task = process_scientific_reports.apply_async(
                            (scientific_reports_ids, user.id, select_text, select_enrich, select_image, select_coord),
                            link_error=error_handler_scientific_reports.s())
                    elif file_type == 'tech_report':
                        tech_reports_ids = raw_reports_save(file_groups, uploaded_files, TechReport,
                                                            user.id, is_public)
                        task = process_tech_reports.apply_async(
                            (tech_reports_ids, user.id, select_text, select_enrich, select_image, select_coord),
                            link_error=error_handler_tech_reports.s())
                except Exception as e:
                    form.add_error(None, f"Ошибка при сохранении файлов: {str(e)}")
                    return render(request, 'deconstructor.html', {'form': form, 'tasks_id': tasks_id})

                tasks_id = [task.task_id] + tasks_id
                user_task = UserTasks(user_id=user.id, task_id=task.task_id, files_type=file_type,
                                      upload_source={'source': 'Пользовательский файл'})
                user_task.save()

                return render(request, 'deconstructor.html', {'form': form,
                                                              'tasks_id': tasks_id})

    else:
        form = UploadReportsForm()
    return render(request, 'deconstructor.html', {'form': form, 'tasks_id': tasks_id})


@login_required
def external_sources(request):
    is_processing, scan_task_id, active_scan_task = get_scan_task(
        'agregator.processing.external_sources.external_sources_processing')
    base_path = 'uploaded_files/Акты ГИКЭ/'
    report_files = [
        'download_report.html',
        'final_report.html',
        'interrupted_report.html',
        'intermediate_report.html',
    ]

    if request.method == 'POST' and scan_task_id is None:
        try:
            for report_file in report_files:
                report_path = os.path.join(base_path, report_file)
                if os.path.exists(report_path):
                    os.remove(report_path)
                    logger.info(f"🗑️ Удален старый отчет: {report_file}")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось очистить старые отчеты: {e}")

        start_date = end_date = None
        if 'enableDateRange' in request.POST.keys() and 'startDate' in request.POST.keys() and 'endDate' in request.POST.keys():
            start_date = request.POST['startDate']
            end_date = request.POST['endDate']

            match = re.search(r"\d{2}-\d{2}-\d{4}", start_date)
            if match:
                date_str = match.group(0)
                start_date = [int(x) for x in date_str.split('-')][::-1]
            else:
                start_date = None
            match = re.search(r"\d{2}-\d{2}-\d{4}", end_date)
            if match:
                date_str = match.group(0)
                end_date = [int(x) for x in date_str.split('-')][::-1]
            else:
                end_date = None

        start_page = end_page = None
        if 'enablePageRange' in request.POST.keys() and (
                'startPage' in request.POST.keys() or 'endPage' in request.POST.keys()):
            start_page = request.POST['startPage']
            end_page = request.POST['endPage']
            if str_is_int(start_page):
                start_page = int(start_page)
            else:
                start_page = None
            if str_is_int(end_page):
                end_page = int(end_page)
            else:
                end_page = None

            if start_page and end_page and start_page > end_page:
                start_page, end_page = end_page, start_page

        select_text = select_enrich = select_image = select_coord = False
        if 'select_text' in request.POST:
            select_text = True
        if 'select_enrich' in request.POST:
            select_enrich = True
        if 'select_image' in request.POST:
            select_image = True
        if 'select_coord' in request.POST:
            select_coord = True

        scan_task = external_sources_processing.delay(start_date, end_date, start_page, end_page, select_text,
                                                      select_enrich,
                                                      select_image, select_coord)
        scan_task_id = scan_task.id
        is_processing = True
    try:
        admin = User.objects.get(is_superuser=True)
    except User.DoesNotExist:
        admin = request.user
    tasks_id = get_user_tasks(admin.id, ('act', 'scientific_report', 'tech_report', 'open_list'), True)

    download_report = final_report = interrupted_report = intermediate_report = False
    for report_file in report_files:
        report_path = os.path.join(base_path, report_file)
        try:
            if os.path.isfile(report_path):
                # ПРОВЕРЯЕМ ДАТУ МОДИФИКАЦИИ ФАЙЛА С ОБРАБОТКОЙ ОШИБОК
                try:
                    file_mtime = os.path.getmtime(report_path)
                    file_age = time() - file_mtime

                    # ЕСЛИ ФАЙЛ СВЕЖИЙ (МЕНЕЕ 1 ЧАСА), ТО ПОКАЗЫВАЕМ ЕГО
                    if file_age < 3600:  # 3600 секунд = 1 час
                        if report_file == 'download_report.html':
                            download_report = True
                        elif report_file == 'final_report.html':
                            final_report = True
                        elif report_file == 'interrupted_report.html':
                            interrupted_report = True
                        elif report_file == 'intermediate_report.html':
                            intermediate_report = True
                        logger.info(f"📄 Актуальный отчет найден: {report_file}, возраст: {file_age:.0f} сек")
                    else:
                        logger.info(f"🗑️ Устаревший отчет (возраст {file_age:.0f} сек): {report_file}")
                except (OSError, FileNotFoundError) as e:
                    logger.warning(f"⚠️ Не удалось получить время модификации файла {report_path}: {e}")
                    # Если не удалось получить время, всё равно показываем файл
                    if report_file == 'download_report.html':
                        download_report = True
                    elif report_file == 'final_report.html':
                        final_report = True
                    elif report_file == 'interrupted_report.html':
                        interrupted_report = True
                    elif report_file == 'intermediate_report.html':
                        intermediate_report = True
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке файла {report_path}: {e}")
            continue

    current_timestamp = int(time())

    return render(request, 'external_sources.html',
                  {'is_processing': is_processing, 'tasks_id': tasks_id, 'scan_task_id': scan_task_id,
                   'active_scan_task': active_scan_task, 'download_report': download_report,
                   'final_report': final_report, 'interrupted_report': interrupted_report,
                   'intermediate_report': intermediate_report, 'current_timestamp': current_timestamp})


@login_required
def check_external_scan_progress(request, task_id):
    """Защищенная версия проверки прогресса"""
    try:
        # Пытаемся получить задачу через AsyncResult
        task = AsyncResult(task_id)

        # Безопасное получение состояния
        try:
            state = task.state
            result = task.result if hasattr(task, 'result') else None
            info = task.info if hasattr(task, 'info') else None
        except Exception as e:
            # Если возникает ошибка при получении состояния, пробуем через БД напрямую
            try:
                db_task = TaskResult.objects.get(task_id=task_id)
                state = db_task.status
                result = json.loads(db_task.result) if db_task.result else None
            except TaskResult.DoesNotExist:
                state = 'PENDING'
                result = None
            except Exception as db_error:
                state = 'UNKNOWN'
                result = f"Database error: {db_error}"
            info = None

        # Формируем ответ в зависимости от состояния
        if state == 'PENDING':
            response = {
                'state': state,
                'message': 'Задача ожидает выполнения...'
            }
        elif state == 'PROGRESS':
            response = {
                'state': state,
                'meta': result
            }
        elif state == 'SUCCESS':
            response = {
                'state': state,
                'result': result
            }
        else:
            # Для других состояний (FAILURE, REVOKED, RETRY)
            message = str(info) if info else f"Состояние: {state}"
            response = {'state': state, 'message': message}

    except Exception as e:
        # Если все совсем сломалось
        response = {
            'state': 'ERROR',
            'message': f'Ошибка при проверке задачи: {str(e)}'
        }

    return JsonResponse(response)


@login_required
def cancel_external_scan_task(request, task_id):
    """View для прерывания задачи сканирования"""
    try:
        task = AsyncResult(task_id)
        # Revoke the task, terminate if it's running
        task.revoke(terminate=True)
        TaskResult.objects.filter(task_id=task_id).update(
            status='REVOKED',
            result='{"message": "Задача отменена пользователем"}'
        )
        return JsonResponse({'status': 'success', 'message': 'Задача сканирования была прервана.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


@login_required
def open_list_ocr(request):
    tasks_id = get_user_tasks(request.user.id, ('open_list',))
    view = upload_entity_view(request, tasks_id, 'open_list', UploadOpenListsForm, raw_open_lists_save,
                              process_open_lists,
                              error_handler_open_lists, 'open_list_ocr.html')
    return view


@login_required
def doc_reprocess(request, pk):
    if request.method == 'POST':
        url = request.META.get('HTTP_REFERER')
        if url:
            if 'act' in url:
                report_type = 'act'
            elif 'scientific' in url:
                report_type = 'scientific_report'
            elif 'tech' in url:
                report_type = 'tech_report'
            else:
                return HttpResponse("Некорректный тип отчёта", status=404)
        else:
            return HttpResponse("Тип отчёта не определён", status=404)
        user = request.user
        tasks_id = get_user_tasks(user.id, ('act', 'scientific_report', 'tech_report'))
        form = UploadReportsForm()
        select_text = select_enrich = select_image = select_coord = False
        if 'select_text' in request.POST:
            select_text = True
        if 'select_enrich' in request.POST:
            select_enrich = True
        if 'select_image' in request.POST:
            select_image = True
        if 'select_coord' in request.POST:
            select_coord = True
        if report_type == 'act':
            task = process_acts.apply_async(([pk], user.id, select_text, select_enrich, select_image, select_coord),
                                            link_error=error_handler_acts.s())
        elif report_type == 'scientific_report':
            task = process_scientific_reports.apply_async(
                ([pk], user.id, select_text, select_enrich, select_image, select_coord),
                link_error=error_handler_scientific_reports.s())
        elif report_type == 'tech_report':
            task = process_tech_reports.apply_async(
                ([pk], user.id, select_text, select_enrich, select_image, select_coord),
                link_error=error_handler_tech_reports.s())
        else:
            return HttpResponse("Некорректный тип отчёта", status=404)
        tasks_id = [task.task_id] + tasks_id
        user_task = UserTasks(user_id=user.id, task_id=task.task_id, files_type=report_type,
                              upload_source={'source': 'Пользовательский файл'})
        user_task.save()

        return render(request, 'deconstructor.html', {'form': form,
                                                      'tasks_id': tasks_id})
    return JsonResponse({'response': 'invalid method'})


@login_required
# @owner_or_admin_required(UserTasks)
def download_delete(request, task_id):
    try:
        redis_client.delete(task_id)
        redis_client.delete('celery-task-meta-' + str(task_id))
    except Exception:
        print("Ошибка подключения к Redis")
    UserTasks.objects.filter(task_id=task_id).delete()
    TaskResult.objects.filter(task_id=task_id).delete()
    return JsonResponse({'response': 'deleted'})


@login_required
def account_cards_upload(request):
    tasks_id = get_user_tasks(request.user.id, ('account_card',))
    view = upload_entity_view(request, tasks_id, 'account_card', UploadReportsForm, raw_account_cards_save,
                              process_account_cards,
                              error_handler_account_cards, 'account_cards_upload.html')
    return view


@login_required
def commercial_offers_upload(request):
    tasks_id = get_user_tasks(request.user.id, ('commercial_offer',))
    view = upload_entity_view(request, tasks_id, 'commercial_offer', UploadCommercialOffersForm,
                              raw_commercial_offers_save,
                              process_commercial_offers,
                              error_handler_commercial_offers, 'commercial_offers_upload.html')
    return view


@login_required
def geo_objects_upload(request):
    tasks_id = get_user_tasks(request.user.id, ('geo_object',))
    view = upload_entity_view(request, tasks_id, 'geo_object', UploadGeoObjectsForm,
                              raw_geo_objects_save,
                              process_geo_objects,
                              error_handler_geo_objects, 'geo_object_upload.html')
    return view
