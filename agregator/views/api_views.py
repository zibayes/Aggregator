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

from agregator.models import User
from agregator.views import get_user_tasks


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
