import json

import pandas as pd
import simplekml
from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth import login, authenticate
from django.contrib.auth import logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django_celery_results.models import TaskResult
from pyproj import Geod
from rest_framework import generics
from shapely.geometry import Polygon, LineString
from shapely.geometry import shape, Point
from shapely.ops import nearest_points

from agregator.llm.ask import ask_question_with_context
from agregator.models import Chat, Message


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
    return HttpResponse("Метод не поддерживается", status=405)


@login_required
def edit_gpt_chat(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        body_data = json.loads(body_unicode)
        chat = get_object_or_404(Chat, id=body_data['chat_id'])
        chat.name = body_data['name']
        chat.save()
        return JsonResponse({'result': 'success'})
    return HttpResponse("Метод не поддерживается", status=405)


@login_required
def delete_gpt_chat(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        body_data = json.loads(body_unicode)
        chat_id = int(body_data['chat_id'])
        Message.objects.filter(chat_id=chat_id).delete()
        get_object_or_404(Chat, id=chat_id).delete()
        return JsonResponse({'result': 'success'})
    return HttpResponse("Метод не поддерживается", status=405)


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
    return HttpResponse("Метод не поддерживается", status=405)


@login_required
def edit_chat_message(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        body_data = json.loads(body_unicode)
        message = get_object_or_404(Message, id=body_data['message_id'])
        message.content = body_data['content']
        message.save()
        return JsonResponse({'result': 'success'})
    return HttpResponse("Метод не поддерживается", status=405)


@login_required
def delete_chat_message(request):
    if request.method == 'POST':
        body_unicode = request.body.decode('utf-8')
        body_data = json.loads(body_unicode)
        chat_id = int(body_data['chat_id'])
        message = get_object_or_404(Message, chat_id=chat_id).order_by('-sent_at').first()
        if message.sender == 'ai':
            message.delete()
            message = Message.objects.filter(chat_id=chat_id, sender='user').order_by('-sent_at').first()
        message.delete()
        return JsonResponse({'result': 'success'})
    return HttpResponse("Метод не поддерживается", status=405)
