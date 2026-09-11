from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth import logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.shortcuts import render, redirect, get_object_or_404
from django_celery_results.models import TaskResult
from celery.result import AsyncResult
from pyproj import Geod
from rest_framework import generics
import logging

from agregator.models import User, Notification
from agregator.views import get_user_tasks

logger = logging.getLogger(__name__)


@login_required
def get_user_notifications(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:20]
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    data = [{
        'id': n.id,
        'title': n.title or '',
        'message': n.message or '',
        'url': n.url or '',
        'is_read': n.is_read,
        'created_at': n.created_at.strftime('%d.%m.%Y %H:%M'),
    } for n in notifications]
    return JsonResponse({'notifications': data, 'unread_count': unread_count})


@login_required
@require_POST
def delete_notification(request, notification_id):
    """Удаляет одно уведомление пользователя."""
    deleted, _ = Notification.objects.filter(
        id=notification_id, user=request.user
    ).delete()
    if deleted:
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False, 'error': 'not found'}, status=404)


@login_required
@require_POST
def delete_all_notifications(request):
    """Удаляет все уведомления пользователя."""
    Notification.objects.filter(user=request.user).delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    try:
        n = Notification.objects.get(id=notification_id, user=request.user)
        n.is_read = True
        n.save(update_fields=['is_read'])
        return JsonResponse({'ok': True})
    except Notification.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'not found'}, status=404)


@login_required
@require_POST
def mark_all_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'ok': True})


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
        admin = User.objects.filter(is_superuser=True)[0]
        # admin = User.objects.get(is_superuser=True)
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


def health_check(request):
    return JsonResponse({"status": "ok"})
