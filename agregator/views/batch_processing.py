import os
import json
import logging
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator

from agregator.processing.batch_processing import scan_and_prepare_batch, create_act_from_existing_file
from agregator.processing.acts_processing import process_acts, error_handler_acts
from agregator.models import UserTasks

logger = logging.getLogger(__name__)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def batch_processing_dashboard(request):
    """Дашборд пакетной обработки"""
    context = {
        'default_directories': {
            'acts': 'uploaded_files/Акты ГИКЭ',
            'scientific_reports': 'uploaded_files/Научные отчёты',
            'tech_reports': 'uploaded_files/Научно-технические отчёты'
        }
    }
    return render(request, 'batch_processing_dashboard.html', context)


@login_required
@csrf_exempt
@user_passes_test(lambda u: u.is_superuser)
def scan_directory(request):
    """Сканирует директорию и возвращает список файлов с проверкой дубликатов"""
    logger.info("=== SCAN DIRECTORY CALLED ===")

    if request.method == 'POST':
        try:
            directory = request.POST.get('directory', '').strip()
            file_type = request.POST.get('file_type', 'act')
            page = int(request.POST.get('page', 1))
            limit = int(request.POST.get('limit', 1000))  # Лимит файлов для сканирования

            logger.info(f"Directory: {directory}, File type: {file_type}, Page: {page}")

            if not directory:
                logger.error("Directory not provided")
                return JsonResponse({'error': 'Не указана директория'}, status=400)

            if not os.path.exists(directory):
                logger.error(f"Directory does not exist: {directory}")
                return JsonResponse({'error': 'Директория не существует'}, status=400)

            # Сканируем и проверяем файлы
            scan_result = scan_and_prepare_batch(directory, file_type, request.user, limit=limit)
            files = scan_result['files']

            # Пагинация
            paginator = Paginator(files, 100)  # 100 файлов на страницу
            page_obj = paginator.get_page(page)

            response_data = {
                'files': list(page_obj),
                'total_count': scan_result['total_scanned'],
                'new_files': scan_result['new_files_count'],
                'existing_files': scan_result['existing_files_count'],
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'current_page': page,
                'total_pages': paginator.num_pages,
                'page_size': 100
            }

            logger.info(
                f"Scan completed: {scan_result['total_scanned']} files scanned, {scan_result['new_files_count']} new files")
            return JsonResponse(response_data)

        except Exception as e:
            logger.error(f"Error scanning directory: {e}", exc_info=True)
            return JsonResponse({'error': f'Ошибка при сканировании: {str(e)}'}, status=500)

    return JsonResponse({'error': 'Метод не разрешен'}, status=405)


@login_required
@user_passes_test(lambda u: u.is_superuser)
@csrf_exempt
def process_batch_files(request):
    """Запускает пакетную обработку выбранных файлов"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            file_paths = data.get('file_paths', [])
            file_type = data.get('file_type', 'act')
            select_text = data.get('select_text', True)
            select_image = data.get('select_image', True)
            select_coord = data.get('select_coord', True)
            is_public = data.get('is_public', True)

            logger.info(f"Processing batch: {len(file_paths)} files, type: {file_type}")

            if not file_paths:
                return JsonResponse({'error': 'Не выбраны файлы для обработки'}, status=400)

            # Маппинг функций создания и обработки
            creation_functions = {
                'act': create_act_from_existing_file,
            }

            processing_tasks = {
                'act': process_acts,
            }

            creation_func = creation_functions.get(file_type)
            processing_task = processing_tasks.get(file_type)

            if not creation_func or not processing_task:
                return JsonResponse({'error': f'Обработка типа {file_type} не реализована'}, status=400)

            # Создаем записи в БД для выбранных файлов
            created_ids = []
            errors = []

            for file_path in file_paths:
                file_info = {
                    'path': file_path,
                    'name': os.path.basename(file_path)
                }

                try:
                    record_id = creation_func(file_info, request.user, is_public)
                    if record_id:
                        created_ids.append(record_id)
                        logger.info(f"Successfully created record {record_id} for {file_path}")
                    else:
                        errors.append(f"Не удалось создать запись для {file_path} (возможно, дубликат)")
                except Exception as e:
                    error_msg = f"Ошибка при создании записи для {file_path}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg, exc_info=True)

            if not created_ids:
                error_message = 'Не удалось создать ни одной записи. ' + ' '.join(errors[:3])
                return JsonResponse({'error': error_message}, status=400)

            # Запускаем обработку
            task = processing_task.apply_async(
                (created_ids, request.user.id, select_text, select_image, select_coord),
                link_error=error_handler_acts.s()
            )

            # Сохраняем информацию о задаче
            user_task = UserTasks(
                user_id=request.user.id,
                task_id=task.task_id,
                files_type=file_type,
                upload_source={'source': 'Пакетная загрузка из файловой системы'}
            )
            user_task.save()

            response_data = {
                'success': True,
                'task_id': task.task_id,
                'processed_count': len(created_ids),
                'message': f'Запущена обработка {len(created_ids)} файлов',
                'warnings': errors if errors else None
            }

            logger.info(f"Batch processing started: {len(created_ids)} files, task: {task.task_id}")
            return JsonResponse(response_data)

        except Exception as e:
            logger.error(f"Ошибка при пакетной обработке: {e}", exc_info=True)
            return JsonResponse({'error': f'Ошибка при обработке: {str(e)}'}, status=500)

    return JsonResponse({'error': 'Метод не разрешен'}, status=405)
