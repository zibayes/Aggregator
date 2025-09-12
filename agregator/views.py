import json
import os
import re
from urllib.parse import quote

import pandas as pd
import simplekml
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth import logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django_celery_results.models import TaskResult
from celery.result import AsyncResult
from pyproj import Geod
from rest_framework import generics
from shapely.geometry import Polygon, LineString
from shapely.geometry import shape, Point
from shapely.ops import nearest_points

from agregator.processing.account_cards_processing import process_account_cards, error_handler_account_cards
from agregator.processing.acts_processing import process_acts, error_handler_acts
from agregator.llm.ask import ask_question_with_context
from agregator.processing.commercial_offers_processing import process_commercial_offers, error_handler_commercial_offers
from agregator.processing.coordinates_extraction import process_coords_from_edit_page
from agregator.processing.coordinates_tables import convert_to_wgs84
from .decorators import owner_or_admin_required
from agregator.processing.external_sources import external_sources_processing, process_oan_list, process_voan_list
from agregator.processing.files_saving import raw_open_lists_save, raw_reports_save, raw_account_cards_save, \
    raw_commercial_offers_save, \
    raw_geo_objects_save
from .forms import UploadReportsForm, UploadOpenListsForm, UploadCommercialOffersForm, UploadGeoObjectsForm
from .forms import UserRegisterForm
from agregator.processing.geo_objects_processing import process_geo_objects, error_handler_geo_objects
from .models import User, Act, ScientificReport, TechReport, OpenLists, UserTasks, \
    ArchaeologicalHeritageSite, IdentifiedArchaeologicalHeritageSite, ObjectAccountCard, CommercialOffers, GeoObject, \
    GeojsonData, \
    Chat, Message
from agregator.processing.open_lists_ocr import process_open_lists, error_handler_open_lists
from agregator.processing.scientific_reports_processing import process_scientific_reports, \
    error_handler_scientific_reports
from .serializers import UserSerializer, ActSerializer, ScientificReportSerializer, \
    TechReportSerializer, OpenListsSerializer, ObjectAccountCardSerializer, ArchaeologicalHeritageSiteSerializer, \
    IdentifiedArchaeologicalHeritageSiteSerializer, CommercialOffersSerializer, GeoObjectSerializer, \
    GeojsonDataSerializer, ChatSerializer, MessageSerializer
from agregator.processing.tech_reports_processing import process_tech_reports, error_handler_tech_reports
from .views_utils import generate_excel_report, upload_entity_view, get_register_view, process_edit_form, \
    process_supplement, create_model_dataframe, get_scan_task


def get_user_tasks(user_id, file_types, upload_source=False):
    user_tasks = list(UserTasks.objects.filter(user_id=user_id, files_type__in=file_types))
    '''
    for i in range(len(user_tasks)):
        user_tasks[i].upload_source = json.loads(user_tasks[i].upload_source) if not isinstance(
            user_tasks[i].upload_source, dict) else user_tasks[i].upload_source
    '''
    if upload_source:
        user_tasks = [x for x in user_tasks if x.upload_source_dict['source'] != 'Пользовательский файл']
    else:
        user_tasks = [x for x in user_tasks if x.upload_source_dict['source'] == 'Пользовательский файл']
    user_tasks = [x.task_id for x in user_tasks]
    user_tasks = list(TaskResult.objects.filter(task_id__in=user_tasks).order_by('-date_created'))
    tasks_id = [x.task_id for x in user_tasks]
    return tasks_id


def index(request):
    return render(request, 'index.html')


@login_required
def get_user_tasks_reports(request):
    user = request.user
    tasks_id = get_user_tasks(user.id, ('act', 'scientific_report', 'tech_report'))
    return JsonResponse({'tasks_id': tasks_id})


@login_required
def get_user_tasks_open_lists(request):
    user = request.user
    tasks_id = get_user_tasks(user.id, ('open_list',))
    return JsonResponse({'tasks_id': tasks_id})


@login_required
def get_user_tasks_external(request):
    try:
        admin = User.objects.get(is_superuser=True)
    except User.DoesNotExist:
        admin = request.user
    tasks_id = get_user_tasks(admin.id, ('act', 'scientific_report', 'tech_report', 'open_list'), True)
    return JsonResponse({'tasks_id': tasks_id})


@login_required
def get_user_tasks_object_account_cards(request):
    user = request.user
    tasks_id = get_user_tasks(user.id, ('account_card',))
    return JsonResponse({'tasks_id': tasks_id})


@login_required
def get_user_tasks_commercial_offers(request):
    user = request.user
    tasks_id = get_user_tasks(user.id, ('commercial_offer',))
    return JsonResponse({'tasks_id': tasks_id})


@login_required
def get_user_tasks_geo_objects(request):
    user = request.user
    tasks_id = get_user_tasks(user.id, ('geo_object',))
    return JsonResponse({'tasks_id': tasks_id})


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
                select_text = select_image = select_coord = False
                if 'select_text' in request.POST:
                    select_text = True
                if 'select_image' in request.POST:
                    select_image = True
                if 'select_coord' in request.POST:
                    select_coord = True

                if file_type == 'act':
                    acts_ids = raw_reports_save(file_groups, uploaded_files, Act, user.id, is_public)
                    task = process_acts.apply_async((acts_ids, user.id, select_text, select_image, select_coord),
                                                    link_error=error_handler_acts.s())
                elif file_type == 'scientific_report':
                    scientific_reports_ids = raw_reports_save(file_groups, uploaded_files, ScientificReport,
                                                              user.id, is_public)
                    task = process_scientific_reports.apply_async(
                        (scientific_reports_ids, user.id, select_text, select_image, select_coord),
                        link_error=error_handler_scientific_reports.s())
                elif file_type == 'tech_report':
                    tech_reports_ids = raw_reports_save(file_groups, uploaded_files, TechReport,
                                                        user.id, is_public)
                    task = process_tech_reports.apply_async(
                        (tech_reports_ids, user.id, select_text, select_image, select_coord),
                        link_error=error_handler_tech_reports.s())
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

    if request.method == 'POST' and scan_task_id is None:
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

        select_text = select_image = select_coord = False
        if 'select_text' in request.POST:
            select_text = True
        if 'select_image' in request.POST:
            select_image = True
        if 'select_coord' in request.POST:
            select_coord = True

        scan_task = external_sources_processing.delay(start_date, end_date, select_text, select_image, select_coord)
        scan_task_id = scan_task.id
        is_processing = True
    try:
        admin = User.objects.get(is_superuser=True)
    except User.DoesNotExist:
        admin = request.user
    tasks_id = get_user_tasks(admin.id, ('act', 'scientific_report', 'tech_report', 'open_list'), True)
    return render(request, 'external_sources.html',
                  {'is_processing': is_processing, 'tasks_id': tasks_id, 'scan_task_id': scan_task_id,
                   'active_scan_task': active_scan_task})


@login_required
def check_external_scan_progress(request, task_id):
    """Защищенная версия проверки прогресса"""
    try:
        # Пытаемся получить задачу через AsyncResult
        task = AsyncResult(task_id)

        # Безопасное получение состояния
        try:
            state = task.state
        except Exception as e:
            # Если возникает ошибка при получении состояния, пробуем через БД напрямую
            try:
                db_task = TaskResult.objects.get(task_id=task_id)
                state = db_task.status
                result = db_task.result
            except TaskResult.DoesNotExist:
                state = 'PENDING'
                result = None
            except Exception as db_error:
                state = 'UNKNOWN'
                result = f"Database error: {db_error}"

        # Формируем ответ в зависимости от состояния
        if state == 'PENDING':
            response = {
                'state': state,
                'message': 'Задача ожидает выполнения...'
            }
        elif state == 'PROGRESS':
            response = {
                'state': state,
                'meta': task.result
            }
        elif state == 'SUCCESS':
            # Безопасно получаем результат
            try:
                result = task.result
            except:
                result = "Задача завершена"

            response = {
                'state': state,
                'result': result
            }
        else:
            # Для других состояний (FAILURE, REVOKED, RETRY)
            response = {
                'state': state,
                'message': str(task.info) if hasattr(task, 'info') else f"Состояние: {state}"
            }

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


def constructor(request):
    return render(request, 'constructor.html')


def interactive_map(request):
    acts = Act.objects.filter(is_processing=False)
    scientific_reports = ScientificReport.objects.filter(is_processing=False)
    tech_report = TechReport.objects.filter(is_processing=False)
    all_coordinates = {'Акты': {}, 'Научные отчёты': {}, 'Научно-технические отчёты': {}}
    for act in acts:
        all_coordinates['Акты'][
            act.id] = {'coordinates': act.coordinates_dict,
                       'report_name': act.source_dict[0]['origin_filename'] if act.source_dict and len(
                           act.source_dict) > 0 else 'Неизвестный файл'}
    for report in scientific_reports:
        all_coordinates['Научные отчёты'][report.id] = {'coordinates': report.coordinates_dict,
                                                        'report_name': report.source_dict[0][
                                                            'origin_filename'] if report.source_dict and len(
                                                            report.source_dict) > 0 else 'Неизвестный файл'}
    for report in tech_report:
        all_coordinates['Научно-технические отчёты'][report.id] = {'coordinates': report.coordinates_dict,
                                                                   'report_name': report.source_dict[0][
                                                                       'origin_filename'] if report.source_dict and len(
                                                                       report.source_dict) > 0 else 'Неизвестный файл'}
    return render(request, 'interactive_map.html', {'all_coordinates': all_coordinates})


def download_all_coordinates(request):
    if request.method == 'POST':
        acts = Act.objects.filter(is_processing=False)
        scientific_reports = ScientificReport.objects.filter(is_processing=False)
        tech_report = TechReport.objects.filter(is_processing=False)
        all_coordinates = {'Акты': {}, 'Научные отчёты': {}, 'Научно-технические отчёты': {}}
        coordinates_to_download = {}

        for act in acts:
            all_coordinates['Акты'][
                act.source_dict[0]['origin_filename']] = act.coordinates_dict  # TODO: Подобрать более удачный нейминг?
        for report in scientific_reports:
            all_coordinates['Научные отчёты'][report.source_dict[0]['origin_filename']] = report.coordinates_dict
        for report in tech_report:
            all_coordinates['Научно-технические отчёты'][report.source[0]['origin_filename']] = report.coordinates_dict

        for report_type, reports in all_coordinates.items():
            for report, groups in reports.items():
                for group, point in groups.items():
                    for point_name, coords in point.items():
                        for key in request.POST.keys():
                            if f'{report_type}-{report}-{group}-{point_name}' == key:
                                if report_type not in coordinates_to_download.keys():
                                    coordinates_to_download[report_type] = {}
                                if report not in coordinates_to_download[report_type].keys():
                                    coordinates_to_download[report_type][report] = {}
                                if group not in coordinates_to_download[report_type][report].keys():
                                    coordinates_to_download[report_type][report][group] = {}
                                coordinates_to_download[report_type][report][group][point_name] = coords

        if coordinates_to_download:
            kml = simplekml.Kml()
            catalog_style = simplekml.Style()
            catalog_style.iconstyle.color = simplekml.Color.blue
            photos_style = simplekml.Style()
            photos_style.iconstyle.color = simplekml.Color.green
            pits_style = simplekml.Style()
            pits_style.iconstyle.color = simplekml.Color.red
            current_style = current_group = None
            for report_type, reports in coordinates_to_download.items():
                report_type_folder = kml.newfolder(name=report_type)
                for report, groups in reports.items():
                    report_folder = report_type_folder.newfolder(name=report)
                    for group, point in groups.items():
                        system_check = True  # 'WGS-84' in group or 'WGS84' in group or 'WGS 84' in group or 'Шурф' in group
                        if 'фотофиксации' in group:
                            current_style = photos_style
                            photos_group = report_folder.newfolder(name=group)
                            current_group = photos_group
                        elif 'Каталог' in group:
                            current_style = catalog_style
                            catalog_group = report_folder.newfolder(name=group)
                            current_group = catalog_group
                        elif 'Шурфы' in group:
                            current_style = pits_style
                            pits_group = report_folder.newfolder(name=group)
                            current_group = pits_group
                        for point_name, coords in point.items():
                            if current_group and system_check:
                                photo_point = current_group.newpoint(name=str(point_name),
                                                                     coords=[
                                                                         (coords[1],
                                                                          coords[
                                                                              0])])  # TODO: менять их местами или нет?!
                                photo_point.style = current_style

            file_path = f'uploaded_files/{request.user.id}-all_coordinates.kml'
            kml.save(file_path)
            return redirect('/' + file_path)
        return JsonResponse({'response': f'There is no selected coordinates'})
    return JsonResponse({'response': f'Method {request.method} is not available for this URL'})


def acts_register(request):
    only_fields = [
        'id', 'user_id', 'date_uploaded', 'is_processing', 'year',
        'finish_date', 'type', 'name_number', 'place', 'customer',
        'area', 'expert', 'executioner', 'open_list', 'conclusion',
        'border_objects', 'source'
    ]
    view = get_register_view(request, Act, 'acts', public_only_fields=only_fields, private_only_fields=only_fields,
                             template_name='acts_register.html')
    return view


@login_required
def open_list_ocr(request):
    tasks_id = get_user_tasks(request.user.id, ('open_list',))
    view = upload_entity_view(request, tasks_id, 'open_list', UploadOpenListsForm, raw_open_lists_save,
                              process_open_lists,
                              error_handler_open_lists, 'open_list_ocr.html')
    return view


@login_required
def gpt_chat(request):
    user_id = request.user.id
    chats = Chat.objects.filter(user_id=user_id)
    for i in range(len(chats)):
        chats[i].messages = Message.objects.filter(chat_id=chats[i].id).order_by('sent_at')
    return render(request, 'gpt_chat.html', {'chats': chats})


@login_required
def create_gpt_chat(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        body_data = json.loads(body_unicode)
        chat = Chat(user_id=request.user.id, name=body_data['name'])
        chat.save()
        return JsonResponse({'chat_id': chat.id})


@login_required
def edit_gpt_chat(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        body_data = json.loads(body_unicode)
        chat = Chat.objects.get(id=body_data['chat_id'])
        chat.name = body_data['name']
        chat.save()
        return JsonResponse({'result': 'success'})


@login_required
def delete_gpt_chat(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        body_data = json.loads(body_unicode)
        chat_id = int(body_data['chat_id'])
        Message.objects.filter(chat_id=chat_id).delete()
        Chat.objects.get(id=chat_id).delete()
        return JsonResponse({'result': 'success'})


@login_required
def ask_gpt(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        body_data = json.loads(body_unicode)
        msg = body_data['messages'][1]['content']
        message_user = Message(chat_id=body_data['messages'][1]['chat_id'], sender='user', content=msg)
        message_user.save()
        answer = ask_question_with_context(msg)
        print(answer)
        message_ai = Message(chat_id=body_data['messages'][1]['chat_id'], sender='ai', content=answer)
        message_ai.save()
        return JsonResponse({'choices': [{'message': {'content': answer, 'message_id': message_ai.id}}]})


@login_required
def edit_chat_message(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        body_data = json.loads(body_unicode)
        message = Message.objects.get(id=body_data['message_id'])
        message.content = body_data['content']
        message.save()
        return JsonResponse({'result': 'success'})


@login_required
def delete_chat_message(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        body_data = json.loads(body_unicode)
        chat_id = int(body_data['chat_id'])
        message = Message.objects.filter(chat_id=chat_id).order_by('-sent_at').first()
        if message.sender == 'ai':
            message.delete()
            message = Message.objects.filter(chat_id=chat_id, sender='user').order_by('-sent_at').first()
        message.delete()
        return JsonResponse({'result': 'success'})


def user_register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  # Автоматически авторизуем пользователя после регистрации
            return redirect('profile')
        else:
            return render(request, 'register.html', {'error': 'Неверные учетные данные'})
    else:
        form = UserRegisterForm()
    return render(request, 'register.html', {'form': form})


def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('profile')
        else:
            return render(request, 'login.html', {'error': 'Неверные учетные данные'})
    return render(request, 'login.html')


@login_required
def custom_logout(request):
    logout(request)
    return redirect('index')


@login_required
def profile(request):
    return render(request, 'profile.html', {'user_to_show': request.user})


@login_required
def settings(request):
    if request.method == 'POST':
        user = request.user
        if 'avatar' in request.FILES.keys():
            user.avatar = request.FILES['avatar']
        user.first_name = request.POST['first_name']
        user.last_name = request.POST['last_name']
        user.username = request.POST['username']
        user.email = request.POST['email']
        password = request.POST['password']

        if password:
            user.set_password(password)  # Хешируйте новый пароль
            update_session_auth_hash(request, user)  # Убедитесь, что сеанс остается активным
        user.save()
        messages.success(request, 'Профиль успешно обновлен.')
        return redirect('profile')  # Перенаправление на страницу профиля

    return render(request, 'settings.html')


def open_lists_register(request):
    view = get_register_view(request, OpenLists, 'open_lists', template_name='open_lists_register.html')
    return view


def open_lists_register_download(request):
    table_path = "uploaded_files/Открытые листы/Открытые листы.xlsx"
    fields_mapping = {
        'Номер листа': 'number',
        'Держатель': 'holder',
        'Объект': 'object',
        'Работы': 'works',
        'Начало срока': 'start_date',
        'Конец срока': 'end_date'
    }
    df_existing = create_model_dataframe(OpenLists, fields_mapping)
    if df_existing is None:
        return redirect(open_lists_register)
    column_widths = {
        'A': 14,
        'B': 20,
        'C': 100,
        'D': 100,
        'E': 14,
        'F': 14
    }
    generate_excel_report(df_existing, table_path, column_widths)
    return redirect('/' + table_path)


def acts_register_download(request):
    table_path = "uploaded_files/Акты ГИКЭ/РЕЕСТР актов ГИКЭ.xlsx"
    fields_mapping = {
        'ГОД': 'year',
        'Дата окончания проведения ГИКЭ': 'finish_date',
        'Вид ГИКЭ': 'type',
        'Номер (если имеется) и наименование Акта ГИКЭ': 'name_number',
        'Место проведения экспертизы': 'place',
        'Заказчик работ (*если не указан, то заказчик экспертизы)': 'customer',
        'Площадь, протяжённость и/или др. параметры объекта': 'area',
        'Эксперт (физ. или юр. лицо)': 'expert',
        'Исполнитель полевых работ (юр. лицо)': 'executioner',
        'ОЛ': 'open_list',
        'Заключение. Выявленные объекты': 'conclusion',
        'Объекты расположенные в непосредственной близости. Для границ': 'border_objects'
    }
    df_existing = create_model_dataframe(Act, fields_mapping)
    if df_existing is None:
        return redirect(acts_register)
    column_widths = {
        'A': 6.86,
        'B': 10.14,
        'C': 10.14,
        'D': 66.43,
        'E': 24,
        'F': 26,
        'G': 20.71,
        'H': 18.43,
        'I': 24.71,
        'J': 21.29,
        'K': 26,
        'L': 27.29
    }
    generate_excel_report(df_existing, table_path, column_widths)
    return redirect('/' + table_path)


def scientific_reports_register_download(request):
    table_path = "uploaded_files/Научные отчёты/РЕЕСТР ПНО.xlsx"
    fields_mapping = {
        'Год написания отчёта': 'writing_date',
        'Название отчёта': 'name',
        'Организация': 'organization',
        'Автор': 'author',
        'Открытый лист': 'open_list',
        'Населённый пункт': 'place',
        'Исполнители': 'contractors',
        'Площадь': 'area_info'
    }
    df_existing = create_model_dataframe(ScientificReport, fields_mapping)
    if df_existing is None:
        return redirect(scientific_reports_register)
    column_widths = {
        'A': 24,
        'B': 24,
        'C': 24,
        'D': 24,
        'E': 24,
        'F': 26,
        'G': 20.71,
        'H': 18.43,
        'I': 24.71,
        'J': 21.29,
        'K': 26,
        'L': 27.29
    }
    generate_excel_report(df_existing, table_path, column_widths)
    return redirect('/' + table_path)


def tech_reports_register_download(request):
    table_path = "uploaded_files/Научно-технические отчёты/РЕЕСТР ПНТО.xlsx"
    fields_mapping = {
        'Год написания отчёта': 'writing_date',
        'Название отчёта': 'name',
        'Организация': 'organization',
        'Автор': 'author',
        'Открытый лист': 'open_list',
        'Населённый пункт': 'place',
        'Исполнители': 'contractors',
        'Площадь': 'area_info'
    }
    df_existing = create_model_dataframe(TechReport, fields_mapping)
    if df_existing is None:
        return redirect(tech_reports_register)
    column_widths = {
        'A': 24,
        'B': 24,
        'C': 24,
        'D': 24,
        'E': 24,
        'F': 26,
        'G': 20.71,
        'H': 18.43,
        'I': 24.71,
        'J': 21.29,
        'K': 26,
        'L': 27.29
    }
    generate_excel_report(df_existing, table_path, column_widths)
    return redirect("/" + table_path)


def scientific_reports_register(request):
    only_fields = [
        'id', 'user_id', 'date_uploaded', 'upload_source', 'is_processing',
        'name', 'organization', 'author', 'open_list', 'writing_date',
        'contractors', 'source', 'place', 'area_info', 'results', 'conclusion'
    ]
    view = get_register_view(request, ScientificReport, 'reports', public_only_fields=only_fields,
                             private_only_fields=only_fields, template_name='scientific_reports_register.html')
    return view


def tech_reports_register(request):
    only_fields = [
        'id', 'user_id', 'date_uploaded', 'upload_source', 'is_processing',
        'name', 'organization', 'author', 'open_list', 'writing_date',
        'contractors', 'source', 'place', 'area_info', 'results', 'conclusion'
    ]
    view = get_register_view(request, TechReport, 'reports', public_only_fields=only_fields,
                             private_only_fields=only_fields, template_name='tech_reports_register.html')
    return view


def users(request, pk):
    user = User.objects.get(id=pk)
    return render(request, 'profile.html', {'user_to_show': user})


def map(request, report_type, pk):
    report = None
    if report_type == 'account_card':
        report = ObjectAccountCard.objects.get(id=pk)
        report_name = report.origin_filename
    elif report_type == 'commercial_offer':
        report = CommercialOffers.objects.get(id=pk)
        report_name = report.origin_filename
    elif report_type == 'geo_object':
        report = GeoObject.objects.get(id=pk)
        report_name = report.origin_filename
    else:
        if report_type == 'act':
            report = Act.objects.get(id=pk)
        elif report_type == 'scientific_report':
            report = ScientificReport.objects.get(id=pk)
        elif report_type == 'tech_report':
            report = TechReport.objects.get(id=pk)
        report_name = report.source_dict[0]['origin_filename'] if report.source_dict and len(
            report.source_dict) > 0 else report.origin_filename if hasattr(report,
                                                                           'origin_filename') else 'Неизвестный файл'
    coordinates = report.coordinates_dict if report else {}
    matching_polygons = {'matching_polygons': get_geojson_polygons_sync(coordinates)}
    return render(request, 'interactive_map.html',
                  {'coordinates': coordinates, 'matching_polygons': matching_polygons,
                   'report_type': report_type, 'pk': pk, 'report_name': report_name})


def get_geojson_polygons(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            points = json.loads(data.get('points', []))
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Неверный формат данных'}, status=400)

        geojson_folder = os.path.join(os.getcwd(), 'uploaded_files/regions_polygons')
        geojson_data = {
            "type": "FeatureCollection",
            "features": []
        }

        for filename in os.listdir(geojson_folder):
            if filename.endswith('.geojson'):
                file_path = os.path.join(geojson_folder, filename)
                with open(file_path, 'r', encoding='utf-8') as file:
                    try:
                        data = json.load(file)
                        geojson_data['features'].extend(data['features'])
                    except json.JSONDecodeError:
                        return JsonResponse({'error': f'Ошибка при чтении файла {filename}'}, status=400)

        matching_polygons = {'Russia': [], 'Subject': [], 'Regions': []}
        for feature in geojson_data['features']:
            matching_polygons['Russia'].append(feature)

        for dirpath, dirnames, filenames in os.walk(geojson_folder):
            if 'Красноярский край' not in dirpath:
                continue
            for filename in filenames:
                if filename.endswith('.geojson'):
                    file_path = os.path.join(dirpath, filename)
                    with open(file_path, 'r', encoding='utf-8') as file:
                        try:
                            data = json.load(file)
                            for feature in data['features']:
                                polygon = shape(feature['geometry'])
                                for group, elements in points.items():
                                    for name, point_coords in elements.items():
                                        if isinstance(point_coords, list) and len(point_coords) == 2:
                                            point = Point([point_coords[1], point_coords[0]])
                                            if polygon.contains(point):
                                                if filename == 'Красноярский край.geojson':
                                                    matching_polygons['Subject'].append(feature)
                                                else:
                                                    matching_polygons['Regions'].append(feature)
                                                    break
                        except json.JSONDecodeError:
                            return JsonResponse({'error': f'Ошибка при чтении файла {filename}'}, status=400)

        if matching_polygons:
            return JsonResponse({'matching_polygons': matching_polygons}, status=200)
        else:
            return JsonResponse({'message': 'Нет совпадений с полигонами'}, status=404)

    return JsonResponse({'error': 'Метод не поддерживается'}, status=405)


def check_point_in_polygon(feature, point_coords):
    polygon = shape(feature.geojson['geometry'])
    point = Point([point_coords[1], point_coords[0]])
    return polygon.contains(point)


def get_geojson_polygons_sync(points):
    matching_polygons = {
        'Russia': [GeojsonData.objects.get(name='Россия').geojson],
        'Subject': [GeojsonData.objects.get(name='Красноярский край').geojson],
        'Regions': []
    }
    regions = GeojsonData.objects.exclude(name__in=('Россия', 'Красноярский край'))
    for feature in regions:
        polygon = shape(feature.geojson['geometry'])
        for group, elements in points.items():
            for name, point_coords in elements.items():
                if isinstance(point_coords, list) and len(point_coords) == 2:
                    point = Point([point_coords[1], point_coords[0]])
                    if polygon.contains(point):
                        matching_polygons['Regions'].append(feature.geojson)

    return matching_polygons


def download_coordinates(request, report_type, pk):
    if request.method == 'POST':
        report = None
        if report_type == 'act':
            report = Act.objects.get(id=pk)
        elif report_type == 'scientific_report':
            report = ScientificReport.objects.get(id=pk)
        elif report_type == 'tech_report':
            report = TechReport.objects.get(id=pk)
        elif report_type == 'account_card':
            report = ObjectAccountCard.objects.get(id=pk)
        elif report_type == 'commercial_offer':
            report = CommercialOffers.objects.get(id=pk)
        elif report_type == 'geo_object':
            report = GeoObject.objects.get(id=pk)
        coordinates = report.coordinates_dict if report else {}
        coordinates_to_download = {}
        print('request.POST.keys(): ' + str(request.POST.keys()))
        print('coordinates.items(): ' + str(coordinates.items()))

        for group, point in coordinates.items():
            for point_name, coords in point.items():
                if f'{group}-{point_name}' in request.POST.keys():
                    if group not in coordinates_to_download.keys():
                        coordinates_to_download[group] = {}
                    coordinates_to_download[group][point_name] = coords

        if coordinates_to_download:
            kml = simplekml.Kml()
            catalog_style = simplekml.Style()
            catalog_style.iconstyle.color = simplekml.Color.blue
            photos_style = simplekml.Style()
            photos_style.iconstyle.color = simplekml.Color.green
            pits_style = simplekml.Style()
            pits_style.iconstyle.color = simplekml.Color.red
            obj_center = simplekml.Style()
            obj_center.iconstyle.color = simplekml.Color.yellow
            current_style = current_group = None
            for group, point in coordinates_to_download.items():
                system_check = True  # 'WGS-84' in group or 'WGS84' in group or 'WGS 84' in group or 'Шурф' in group
                if 'фотофиксации' in group:
                    current_style = photos_style
                    photos_group = kml.newfolder(name=group)
                    current_group = photos_group
                elif 'Каталог' in group:
                    current_style = catalog_style
                    catalog_group = kml.newfolder(name=group)
                    current_group = catalog_group
                elif 'Шурфы' in group:
                    current_style = pits_style
                    pits_group = kml.newfolder(name=group)
                    current_group = pits_group
                elif 'Центр' in group:
                    current_style = obj_center
                    center_group = kml.newfolder(name=group)
                    current_group = center_group
                for point_name, coords in point.items():
                    if current_group and system_check:
                        photo_point = current_group.newpoint(name=str(point_name),
                                                             coords=[
                                                                 (coords[1],
                                                                  coords[0])])  # TODO: менять их местами или нет?!
                        photo_point.style = current_style

            file_path = f'uploaded_files/Координаты-{report_type}-{pk}/coordinates.kml'
            kml.save(file_path)
            return redirect('/' + file_path)
        return JsonResponse({'response': f'Coordinates to download not selected'})
    return JsonResponse({'response': f'Method {request.method} is not available for this URL'})


def acts(request, pk):
    act = Act.objects.get(id=pk)
    return render(request, 'act.html', {'report': act})


@login_required
@owner_or_admin_required(Act)
def acts_edit(request, pk):
    act = Act.objects.get(id=pk)
    if request.method == 'POST':
        fields = [
            'year',
            'finish_date',
            'type',
            'name_number',
            'place',
            'customer',
            'area',
            'expert',
            'executioner',
            'open_list',
            'conclusion',
            'border_objects'
        ]
        process_edit_form(request, act, fields)
        act.coordinates = process_coords_from_edit_page(request, act)
        act.supplement = process_supplement(request, act)

        act.save()
        messages.success(request, 'Акт успешно обновлен.')
        return redirect(f'/acts/{act.id}')  # Перенаправление на страницу профиля

    return render(request, 'act_edit.html', {'report': act})


@login_required
@owner_or_admin_required(Act)
def acts_delete(request, pk):
    act_instance = Act.objects.get(id=pk)
    act_instance.delete()
    return redirect(f'acts_register')


@login_required
def doc_reprocess(request, pk):
    if request.method == 'POST':
        report_type = None
        url = request.META.get('HTTP_REFERER')
        if 'act' in url:
            report_type = 'act'
        elif 'scientific' in url:
            report_type = 'scientific_report'
        elif 'tech' in url:
            report_type = 'tech_report'
        user = request.user
        tasks_id = get_user_tasks(user.id, ('act', 'scientific_report', 'tech_report'))
        form = UploadReportsForm()
        select_text = select_image = select_coord = False
        if 'select_text' in request.POST:
            select_text = True
        if 'select_image' in request.POST:
            select_image = True
        if 'select_coord' in request.POST:
            select_coord = True
        if report_type == 'act':
            task = process_acts.apply_async(([pk], user.id, select_text, select_image, select_coord),
                                            link_error=error_handler_acts.s())
        elif report_type == 'scientific_report':
            task = process_scientific_reports.apply_async(
                ([pk], user.id, select_text, select_image, select_coord),
                link_error=error_handler_scientific_reports.s())
        elif report_type == 'tech_report':
            task = process_tech_reports.apply_async(
                ([pk], user.id, select_text, select_image, select_coord),
                link_error=error_handler_tech_reports.s())
        else:
            return JsonResponse({'response': 'invalid doc type'})
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
    user_task = UserTasks.objects.get(task_id=task_id)
    user_task.delete()
    task = TaskResult.objects.get(task_id=task_id)
    task.delete()
    return JsonResponse({'response': 'deleted'})


def scientific_reports(request, pk):
    report = ScientificReport.objects.get(id=pk)
    return render(request, 'scientific_report.html', {'report': report})


@login_required
@owner_or_admin_required(ScientificReport)
def scientific_reports_edit(request, pk):
    report = ScientificReport.objects.get(id=pk)
    if request.method == 'POST':
        fields = [
            'name',
            'organization',
            'author',
            'open_list',
            'writing_date',
            'introduction',
            'contractors',
            'place',
            'area_info',
            'research_history',
            'results',
            'conclusion'
        ]
        process_edit_form(request, report, fields)
        report.coordinates = process_coords_from_edit_page(request, report)
        report.supplement = process_supplement(request, report)

        report.save()
        messages.success(request, 'Отчёт успешно обновлен.')
        return redirect(f'/scientific_reports/{report.id}')

    return render(request, 'scientific_report_edit.html', {'report': report})


@login_required
@owner_or_admin_required(ScientificReport)
def scientific_reports_delete(request, pk):
    report_instance = ScientificReport.objects.get(id=pk)
    report_instance.delete()
    return redirect(f'scientific_reports_register')


def tech_reports(request, pk):
    report = TechReport.objects.get(id=pk)
    return render(request, 'tech_report.html', {'report': report})


@login_required
@owner_or_admin_required(TechReport)
def tech_reports_edit(request, pk):
    report = TechReport.objects.get(id=pk)
    if request.method == 'POST':
        fields = [
            'name',
            'organization',
            'author',
            'open_list',
            'writing_date',
            'introduction',
            'contractors',
            'place',
            'area_info',
            'research_history',
            'results',
            'conclusion'
        ]
        process_edit_form(request, report, fields)
        report.coordinates = process_coords_from_edit_page(request, report)
        report.supplement = process_supplement(request, report)

        report.save()
        messages.success(request, 'Отчёт успешно обновлен.')
        return redirect(f'/tech_reports/{report.id}')

    return render(request, 'tech_report_edit.html', {'report': report})


@login_required
@owner_or_admin_required(TechReport)
def tech_reports_delete(request, pk):
    report_instance = TechReport.objects.get(id=pk)
    report_instance.delete()
    return redirect(f'tech_reports_register')


def open_lists(request, pk):
    open_list = OpenLists.objects.get(id=pk)
    return render(request, 'open_list.html', {'open_list': open_list})


@login_required
@owner_or_admin_required(OpenLists)
def open_lists_edit(request, pk):
    open_list = OpenLists.objects.get(id=pk)
    if request.method == 'POST':
        fields = [
            'number',
            'holder',
            'object',
            'works',
            'start_date',
            'end_date'
        ]
        process_edit_form(request, open_list, fields)
        open_list.save()
        messages.success(request, 'Открытый лист успешно обновлен.')
        return redirect(f'/open_lists/{open_list.id}')

    return render(request, 'open_list_edit.html', {'open_list': open_list})


@login_required
@owner_or_admin_required(OpenLists)
def open_lists_delete(request, pk):
    list_instance = OpenLists.objects.get(id=pk)
    list_instance.delete()
    return redirect(f'open_lists_register')


def archaeological_heritage_sites(request):
    is_processing, scan_task_id, active_scan_task = get_scan_task(
        'agregator.processing.external_sources.process_oan_list')

    if request.method == 'POST' and scan_task_id is None:
        scan_task = process_oan_list.delay()
        scan_task_id = scan_task.id
        is_processing = True
    oan = ArchaeologicalHeritageSite.objects.all()
    return render(request, 'archaeological_heritage_site_register.html',
                  {'oan': oan, 'is_processing': is_processing, 'scan_task_id': scan_task_id,
                   'active_scan_task': active_scan_task})


def identified_archaeological_heritage_sites(request):
    is_processing, scan_task_id, active_scan_task = get_scan_task(
        'agregator.processing.external_sources.process_voan_list')

    if request.method == 'POST' and scan_task_id is None:
        scan_task = process_voan_list.delay()
        scan_task_id = scan_task.id
        is_processing = True
    voan = IdentifiedArchaeologicalHeritageSite.objects.all()
    return render(request, 'identified_archaeological_heritage_site_register.html',
                  {'voan': voan, 'is_processing': is_processing, 'scan_task_id': scan_task_id,
                   'active_scan_task': active_scan_task})


def archaeological_heritage_site(request, pk):
    oan = ArchaeologicalHeritageSite.objects.get(id=pk)
    return render(request, 'archaeological_heritage_site.html', {'archaeological_heritage_site': oan})


def identified_archaeological_heritage_site(request, pk):
    voan = IdentifiedArchaeologicalHeritageSite.objects.get(id=pk)
    return render(request, 'identified_archaeological_heritage_site.html',
                  {'identified_archaeological_heritage_site': voan})


@login_required
@owner_or_admin_required(ArchaeologicalHeritageSite)
def archaeological_heritage_sites_edit(request, pk):
    oan = ArchaeologicalHeritageSite.objects.get(id=pk)
    if request.method == 'POST':
        fields = [
            'doc_name',
            'district',
            'document',
            'register_num',
            'is_excluded'
        ]
        process_edit_form(request, oan, fields)
        messages.success(request, 'Памятник успешно обновлен.')
        return redirect(f'/archaeological_heritage_sites/{oan.id}')

    return render(request, 'archaeological_heritage_site_edit.html', {'archaeological_heritage_site': oan})


@login_required
@owner_or_admin_required(IdentifiedArchaeologicalHeritageSite)
def identified_archaeological_heritage_sites_edit(request, pk):
    voan = IdentifiedArchaeologicalHeritageSite.objects.get(id=pk)
    if request.method == 'POST':
        fields = [
            'name',
            'address',
            'obj_info',
            'document',
            'is_excluded'
        ]
        process_edit_form(request, voan, fields)
        messages.success(request, 'Отчёт успешно обновлен.')
        return redirect(f'/identified_archaeological_heritage_sites/{voan.id}')

    return render(request, 'identified_archaeological_heritage_site_edit.html',
                  {'identified_archaeological_heritage_site': voan})


@login_required
@owner_or_admin_required(ArchaeologicalHeritageSite)
def archaeological_heritage_sites_delete(request, pk):
    oan = ArchaeologicalHeritageSite.objects.get(id=pk)
    oan.delete()
    return redirect(f'archaeological_heritage_sites')


@login_required
@owner_or_admin_required(IdentifiedArchaeologicalHeritageSite)
def identified_archaeological_heritage_sites_delete(request, pk):
    voan = IdentifiedArchaeologicalHeritageSite.objects.get(id=pk)
    voan.delete()
    return redirect(f'identified_archaeological_heritage_sites')


def archaeological_heritage_sites_download(request):
    current_lists = 'uploaded_files/Памятники/current_lists.txt'
    link = None
    with open(current_lists, 'r', encoding='utf-8') as file:
        for line in file.readlines():
            if 'list_oan - ' in line:
                link = line.replace('list_oan - ', '').strip()
    if link is None:
        return redirect(request.META.get('HTTP_REFERER', '/'))
    return redirect('/' + quote(link))


def identified_archaeological_heritage_sites_download(request):
    current_lists = 'uploaded_files/Памятники/current_lists.txt'
    link = None
    with open(current_lists, 'r', encoding='utf-8') as file:
        for line in file.readlines():
            if 'list_voan - ' in line:
                link = line.replace('list_voan - ', '').strip()
    if link is None:
        return redirect(request.META.get('HTTP_REFERER', '/'))
    return redirect('/' + quote(link))


def update_voan_list(request):
    external_voan_list_processing()
    return redirect(request.META.get('HTTP_REFERER', '/'))


def account_cards(request, pk):
    account_card = ObjectAccountCard.objects.get(id=pk)
    heritage = IdentifiedArchaeologicalHeritageSite.objects.filter(account_card__id=pk, name=account_card.name)
    if not heritage:
        heritage = ArchaeologicalHeritageSite.objects.filter(account_card__id=pk, doc_name=account_card.name)
        if heritage:
            account_card.heritage_url = '/archaeological_heritage_sites/'
    else:
        account_card.heritage_url = '/identified_archaeological_heritage_sites/'
    if heritage:
        account_card.heritage_url += str(heritage[0].id) + '/'
        account_card.heritage_source = heritage[0].source
    return render(request, 'account_card.html', {'account_card': account_card})


@login_required
@owner_or_admin_required(ObjectAccountCard)
def account_cards_edit(request, pk):
    account_card = ObjectAccountCard.objects.get(id=pk)
    if request.method == 'POST':
        fields = [
            'name',
            'creation_time',
            'address',
            'object_type',
            'general_classification',
            'description',
            'usage',
            'discovery_info'
        ]
        process_edit_form(request, account_card, fields)
        account_card.supplement = process_supplement(request, account_card)
        account_card.coordinates = process_coords_from_edit_page(request, account_card)

        account_card.save()
        messages.success(request, 'Учётная карта успешно обновлена.')
        return redirect(f'/account_cards/{account_card.id}')

    return render(request, 'account_card_edit.html', {'account_card': account_card})


@login_required
@owner_or_admin_required(ObjectAccountCard)
def account_cards_delete(request, pk):
    account_card_instance = ObjectAccountCard.objects.get(id=pk)
    account_card_instance.delete()
    return redirect(f'account_cards_register')


@login_required
def account_cards_upload(request):
    tasks_id = get_user_tasks(request.user.id, ('account_card',))
    view = upload_entity_view(request, tasks_id, 'account_card', UploadReportsForm, raw_account_cards_save,
                              process_account_cards,
                              error_handler_account_cards, 'account_cards_upload.html')
    return view


def account_cards_register_download(request):
    table_path = "uploaded_files/Учётные карты/РЕЕСТР Учётных карт.xlsx"
    fields_mapping = {
        'Наименование объекта': 'name',
        'Время создания (возникновения) объекта': 'creation_time',
        'Адрес (местонахождение) объекта': 'address',
        'Вид объекта': 'object_type',
        'Общая видовая принадлежность объекта': 'general_classification',
        'Общее описание объекта и вывод о его историко-культурной ценности': 'description',
        'Использование объекта культурного наследия или пользователь': 'usage',
        'Сведения о дате и обстоятельствах выявления (обнаружения) объекта': 'discovery_info',
        'Составитель учетной карты': 'compiler'
    }
    df_existing = create_model_dataframe(ObjectAccountCard, fields_mapping)
    if df_existing is None:
        return redirect(account_cards_register)
    column_widths = {
        'A': 24,
        'B': 24,
        'C': 50,
        'D': 16,
        'E': 18,
        'F': 62,
        'G': 20,
        'H': 28,
        'I': 25
    }
    generate_excel_report(df_existing, table_path, column_widths, height_title=80, height_cell=100)
    return redirect("/" + table_path)


def account_cards_register(request):
    only_fields = [
        'id', 'user_id', 'date_uploaded', 'upload_source', 'is_processing',
        'is_public', 'origin_filename', 'name', 'creation_time',
        'address', 'object_type', 'general_classification', 'description',
        'usage', 'discovery_info', 'source'
    ]
    view = get_register_view(request, ObjectAccountCard, 'account_cards', public_only_fields=only_fields,
                             private_only_fields=only_fields, template_name='account_cards_register.html')
    return view


@login_required
@owner_or_admin_required(CommercialOffers)
def commercial_offers_edit(request, pk):
    commercial_offer = CommercialOffers.objects.get(id=pk)
    commercial_offer.coordinates = commercial_offer.coordinates_dict
    if request.method == 'POST':
        commercial_offer.coordinates = process_coords_from_edit_page(request, commercial_offer)
        commercial_offer.save()
        messages.success(request, 'Коммерческое предложение успешно обновлено.')
        return redirect(f'/commercial_offers_edit/{commercial_offer.id}')

    return render(request, 'commercial_offer_edit.html',
                  {'commercial_offer': commercial_offer})


@login_required
@owner_or_admin_required(CommercialOffers)
def commercial_offers_delete(request, pk):
    commercial_offer_instance = CommercialOffers.objects.get(id=pk)
    commercial_offer_instance.delete()
    return redirect(f'commercial_offers_register')


@login_required
def commercial_offers_upload(request):
    tasks_id = get_user_tasks(request.user.id, ('commercial_offer',))
    view = upload_entity_view(request, tasks_id, 'commercial_offer', UploadCommercialOffersForm,
                              raw_commercial_offers_save,
                              process_commercial_offers,
                              error_handler_commercial_offers, 'commercial_offers_upload.html')
    return view


def commercial_offers_register(request):
    view = get_register_view(request, CommercialOffers, 'commercial_offers',
                             template_name='commercial_offers_register.html')
    return view


def download_commercial_offer_report(request, pk):
    commercial_offer = CommercialOffers.objects.get(id=pk)
    table_path = f"uploaded_files/Коммерческие предложения/{commercial_offer.id}_commercial_offer/Отчёт.xlsx"
    table_columns = ['Памятник', 'Дистанция до памятника (км)']
    account_cards = ObjectAccountCard.objects.all()
    if not account_cards:
        return redirect(commercial_offers_register)
    df_existing = None
    geo_objects = GeoObject.objects.filter(type='heritage')
    print('geo_objects' + str(geo_objects))
    account_cards = list(account_cards) + list(geo_objects)
    counter = 0
    for account_card in account_cards:
        table_columns_info = {i: '' for i in table_columns}
        print('TYPE: ' + str(type(account_card)))

        min_distance = None
        if account_card.coordinates_dict and commercial_offer.coordinates_dict:
            if type(account_card) != GeoObject:
                for ac_polygon in account_card.coordinates_dict.values():
                    if 'coordinate_system' not in ac_polygon.keys() or ac_polygon['coordinate_system'] == 'None':
                        continue
                    for co_polygon in commercial_offer.coordinates_dict.values():
                        if 'coordinate_system' not in co_polygon.keys() or co_polygon['coordinate_system'] == 'None':
                            continue
                        polygon1 = [[float(value[0]), float(value[1])] for key, value in co_polygon.items() if
                                    key not in ('coordinate_system', 'area')]
                        polygon2 = [[float(value[0]), float(value[1])] for key, value in ac_polygon.items() if
                                    key not in ('coordinate_system', 'area')]

                        if not (co_polygon['coordinate_system'] == ac_polygon['coordinate_system'] == 'wgs84'):
                            polygon1 = [[convert_to_wgs84(x[0], x[1], co_polygon['coordinate_system'])] for x in
                                        polygon1]
                            polygon2 = [[convert_to_wgs84(x[0], x[1], ac_polygon['coordinate_system'])] for x in
                                        polygon2]

                        if len(polygon1) > 2:
                            polygon1 = Polygon(polygon1)
                        elif len(polygon1) == 2:
                            polygon1 = LineString(polygon1)
                        elif len(polygon1) == 1:
                            polygon1 = Point(polygon1)

                        if len(polygon2) > 2:
                            polygon2 = Polygon(polygon2)
                        elif len(polygon2) == 2:
                            polygon2 = LineString(polygon2)
                        elif len(polygon2) == 1:
                            polygon2 = Point(polygon2)

                        point1, point2 = nearest_points(polygon1, polygon2)
                        geod = Geod(ellps="WGS84")
                        # print(str(polygon1) + ' HERE ' + str(polygon2))
                        # print(str(point1) + ' HERE ' + str(point2))
                        if not point1 or not point2:
                            continue
                        az12, az21, distance = geod.inv(point1.y, point1.x, point2.y, point2.x)
                        if min_distance is None or min_distance > distance:
                            min_distance = distance
            else:
                for ac_polygon in account_card.coordinates_dict.values():
                    for point_name, coords in ac_polygon.items():
                        print(str(counter) + '/' + str(len(ac_polygon.items())))
                        counter += 1
                        if 'coordinate_system' not in ac_polygon.keys() or ac_polygon[
                            'coordinate_system'] == 'None' or point_name == 'coordinate_system':
                            continue
                        for co_polygon in commercial_offer.coordinates_dict.values():
                            if 'coordinate_system' not in co_polygon.keys() or co_polygon[
                                'coordinate_system'] == 'None':
                                continue
                            polygon1 = [[float(value[0]), float(value[1])] for key, value in co_polygon.items() if
                                        key not in ('coordinate_system', 'area')]
                            polygon2 = [[float(value) for value in coords]]

                            if not (co_polygon['coordinate_system'] == ac_polygon['coordinate_system'] == 'wgs84'):
                                polygon1 = [[convert_to_wgs84(x[0], x[1], co_polygon['coordinate_system'])] for x in
                                            polygon1]
                                polygon2 = [[convert_to_wgs84(x[0], x[1], ac_polygon['coordinate_system'])] for x in
                                            polygon2]

                            if len(polygon1) > 2:
                                polygon1 = Polygon(polygon1)
                            elif len(polygon1) == 2:
                                polygon1 = LineString(polygon1)
                            elif len(polygon1) == 1:
                                polygon1 = Point(polygon1)

                            if len(polygon2) > 2:
                                polygon2 = Polygon(polygon2)
                            elif len(polygon2) == 2:
                                polygon2 = LineString(polygon2)
                            elif len(polygon2) == 1:
                                polygon2 = Point(polygon2)

                            point1, point2 = nearest_points(polygon1, polygon2)
                            geod = Geod(ellps="WGS84")
                            # print(str(polygon1) + ' HERE ' + str(polygon2))
                            # print(str(point1) + ' HERE ' + str(point2))
                            if not point1 or not point2:
                                continue
                            az12, az21, distance = geod.inv(point1.y, point1.x, point2.y, point2.x)
                            if min_distance is None or min_distance > distance:
                                min_distance = distance
                        table_columns_info['Памятник'] = point_name
                        table_columns_info['Дистанция до памятника (км)'] = distance / 1000
                        df_new = pd.DataFrame(table_columns_info, columns=table_columns_info.keys(), index=[0])
                        if df_existing is None:
                            df_existing = df_new
                        else:
                            df_existing = df_existing._append(df_new, ignore_index=True)

        if min_distance is not None and type(account_card) != GeoObject:
            table_columns_info['Памятник'] = account_card.name
            table_columns_info['Дистанция до памятника (км)'] = min_distance / 1000
            df_new = pd.DataFrame(table_columns_info, columns=table_columns_info.keys(), index=[0])
            if df_existing is None:
                df_existing = df_new
            else:
                df_existing = df_existing._append(df_new, ignore_index=True)
    if df_existing is None:
        return redirect(commercial_offers_register)
    df_existing = df_existing.sort_values(by='Дистанция до памятника (км)', ascending=True).reset_index(drop=True)
    column_widths = {
        'A': 100,
        'B': 40
    }
    generate_excel_report(df_existing, table_path, column_widths, height_title=15, height_cell=15)
    return redirect('/' + table_path)


@login_required
@owner_or_admin_required(GeoObject)
def geo_objects_edit(request, pk):
    geo_object = GeoObject.objects.get(id=pk)
    geo_object.coordinates = geo_object.coordinates_dict
    if request.method == 'POST':
        geo_object.coordinates = process_coords_from_edit_page(request, geo_object)
        geo_object.save()
        messages.success(request, 'Коммерческое предложение успешно обновлено.')
        return redirect(f'/geo_objects_edit/{geo_object.id}')

    return render(request, 'geo_object_edit.html',
                  {'geo_object': geo_object})


@login_required
@owner_or_admin_required(GeoObject)
def geo_objects_delete(request, pk):
    geo_object = GeoObject.objects.get(id=pk)
    geo_object.delete()
    return redirect(f'geo_objects_register')


@login_required
def geo_objects_upload(request):
    tasks_id = get_user_tasks(request.user.id, ('geo_object',))
    view = upload_entity_view(request, tasks_id, 'geo_object', UploadGeoObjectsForm,
                              raw_geo_objects_save,
                              process_geo_objects,
                              error_handler_geo_objects, 'geo_object_upload.html')
    return view


def geo_objects_register(request):
    view = get_register_view(request, GeoObject, 'geo_objects', template_name='geo_object_register.html')
    return view


class UserList(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class UserDetail(generics.RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer


class ActList(generics.ListAPIView):
    queryset = Act.objects.all()
    serializer_class = ActSerializer


class ActDetail(generics.RetrieveAPIView):
    queryset = Act.objects.all()
    serializer_class = ActSerializer


class ScientificReportList(generics.ListAPIView):
    queryset = ScientificReport.objects.all()
    serializer_class = ScientificReport


class ScientificReportDetail(generics.RetrieveAPIView):
    queryset = ScientificReport.objects.all()
    serializer_class = ScientificReportSerializer


class TechReportList(generics.ListAPIView):
    queryset = TechReport.objects.all()
    serializer_class = TechReport


class TechReportDetail(generics.RetrieveAPIView):
    queryset = TechReport.objects.all()
    serializer_class = TechReportSerializer


class OpenListsList(generics.ListAPIView):
    queryset = OpenLists.objects.all()
    serializer_class = OpenListsSerializer


class OpenListsDetail(generics.RetrieveAPIView):
    queryset = OpenLists.objects.all()
    serializer_class = OpenListsSerializer


class ObjectAccountCardList(generics.ListAPIView):
    queryset = ObjectAccountCard.objects.all()
    serializer_class = ObjectAccountCardSerializer


class ObjectAccountCardDetail(generics.RetrieveAPIView):
    queryset = ObjectAccountCard.objects.all()
    serializer_class = ObjectAccountCardSerializer


class ArchaeologicalHeritageSiteList(generics.ListAPIView):
    queryset = ArchaeologicalHeritageSite.objects.all()
    serializer_class = ArchaeologicalHeritageSiteSerializer


class ArchaeologicalHeritageSiteDetail(generics.RetrieveAPIView):
    queryset = ArchaeologicalHeritageSite.objects.all()
    serializer_class = ArchaeologicalHeritageSiteSerializer


class IdentifiedArchaeologicalHeritageSiteList(generics.ListAPIView):
    queryset = IdentifiedArchaeologicalHeritageSite.objects.all()
    serializer_class = IdentifiedArchaeologicalHeritageSiteSerializer


class IdentifiedArchaeologicalHeritageSiteDetail(generics.RetrieveAPIView):
    queryset = IdentifiedArchaeologicalHeritageSite.objects.all()
    serializer_class = IdentifiedArchaeologicalHeritageSiteSerializer


class CommercialOffersList(generics.ListAPIView):
    queryset = CommercialOffers.objects.all()
    serializer_class = CommercialOffersSerializer


class CommercialOffersDetail(generics.RetrieveAPIView):
    queryset = CommercialOffers.objects.all()
    serializer_class = CommercialOffersSerializer


class GeoObjectList(generics.ListAPIView):
    queryset = GeoObject.objects.all()
    serializer_class = GeoObjectSerializer


class GeoObjectDetail(generics.RetrieveAPIView):
    queryset = GeoObject.objects.all()
    serializer_class = GeoObjectSerializer


class GeojsonDataList(generics.ListAPIView):
    queryset = GeojsonData.objects.all()
    serializer_class = GeojsonDataSerializer


class GeojsonDataDetail(generics.RetrieveAPIView):
    queryset = GeojsonData.objects.all()
    serializer_class = GeojsonDataSerializer


class ChatList(generics.ListAPIView):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer


class ChatDetail(generics.RetrieveAPIView):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializer


class MessageList(generics.ListAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer


class MessageDetail(generics.RetrieveAPIView):
    queryset = Message.objects.all()
    serializer_class = MessageSerializer
