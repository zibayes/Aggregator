import pytest
import json
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from unittest.mock import patch, MagicMock, mock_open
from django.core.files.uploadedfile import SimpleUploadedFile
from agregator.models import (
    TaskResult, Chat, Message
)


@pytest.mark.django_db
class TestLLMViews:
    def test_gpt_chat_view(self, client, test_user):
        """Тест страницы GPT чата"""
        client.force_login(test_user)

        # Создаем тестовый чат с сообщениями
        chat = Chat.objects.create(user=test_user, name="Тестовый чат")
        Message.objects.create(chat=chat, sender="user", content="Привет")
        Message.objects.create(chat=chat, sender="ai", content="Привет! Как дела?")

        response = client.get(reverse('gpt_chat'))
        assert response.status_code == 200
        assert 'gpt_chat.html' in [t.name for t in response.templates]

    def test_create_gpt_chat(self, client, test_user):
        """Тест создания нового чата"""
        client.force_login(test_user)

        response = client.post(reverse('create_gpt_chat'),
                               json.dumps({'name': 'Новый чат'}),
                               content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'chat_id' in data
        assert Chat.objects.filter(id=data['chat_id']).exists()

    @patch('agregator.views.ask_question_with_context')
    def test_ask_gpt(self, mock_ask, client, test_user):
        """Тест запроса к GPT"""
        client.force_login(test_user)

        chat = Chat.objects.create(user=test_user, name="Тестовый чат")
        mock_ask.return_value = "Это тестовый ответ"

        response = client.post(reverse('ask_gpt'), json.dumps({
            'messages': [
                {'role': 'system', 'content': 'You are helpful'},
                {'chat_id': chat.id, 'content': 'Тестовый вопрос'}
            ]
        }), content_type='application/json')

        assert response.status_code == 200
        data = json.loads(response.content)
        assert 'choices' in data
        assert Message.objects.filter(chat=chat).count() == 2
