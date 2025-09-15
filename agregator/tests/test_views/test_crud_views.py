import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from agregator.models import Act, ScientificReport, TechReport, OpenLists, ObjectAccountCard, \
    ArchaeologicalHeritageSite, IdentifiedArchaeologicalHeritageSite, UserTasks
from django_celery_results.models import TaskResult
from unittest.mock import patch, MagicMock

User = get_user_model()


@pytest.mark.django_db
class TestActViews:

    def test_acts_list_view(self):
        """Тест списка актов"""
        client = Client()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.login(username='testuser', password='testpass123')

        # Создаем тестовый акт
        act = Act.objects.create(
            user=user,
            year='2023',
            name_number='test-123',
            is_processing=False,
            is_public=True,
        )

        response = client.get(reverse('acts_register'))

        assert response.status_code == 200
        assert 'test-123' in str(response.content.decode('utf-8'))

    def test_act_detail_view(self):
        """Тест детальной страницы акта"""
        client = Client()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.login(username='testuser', password='testpass123')

        act = Act.objects.create(
            user=user,
            year='2023',
            name_number='test-123'
        )

        response = client.get(reverse('acts', kwargs={'pk': act.id}))

        assert response.status_code == 200
        assert 'test-123' in str(response.content.decode('utf-8'))

    def test_act_edit_view_get(self):
        """Тест GET запроса редактирования акта"""
        client = Client()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.login(username='testuser', password='testpass123')

        act = Act.objects.create(
            user=user,
            year='2023',
            name_number='test-123'
        )

        response = client.get(reverse('acts_edit', kwargs={'pk': act.id}))

        assert response.status_code == 200
        assert 'Редактирование' in str(response.content.decode('utf-8'))

    def test_act_delete_view(self):
        """Тест удаления акта"""
        client = Client()
        user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        client.login(username='testuser', password='testpass123')

        act = Act.objects.create(
            user=user,
            year='2023',
            name_number='test-123'
        )

        response = client.get(reverse('acts_delete', kwargs={'pk': act.id}))

        assert response.status_code == 302
        assert not Act.objects.filter(id=act.id).exists()


@pytest.mark.django_db
class TestDocumentViews:
    def test_open_lists_register_download(self, client, test_user):
        """Тест скачивания реестра открытых листов"""
        client.force_login(test_user)
        OpenLists.objects.create(
            user=test_user,
            number="123",
            holder="Test Holder"
        )

        response = client.get(reverse('open_lists_register_download'))
        assert response.status_code == 302  # Проверка редиректа на файл

    @patch('agregator.views.get_scan_task')
    def test_archaeological_heritage_sites_view(self, mock_scan, client, test_user):
        """Тест списка археологических памятников"""
        mock_scan.return_value = (False, None, None)
        client.force_login(test_user)

        response = client.get(reverse('archaeological_heritage_sites'))
        assert response.status_code == 200


@pytest.mark.django_db
class TestErrorCases:
    def test_act_detail_not_found(self, client, test_user):
        """Тест 404 для несуществующего акта"""
        client.force_login(test_user)
        response = client.get(reverse('acts', kwargs={'pk': 999}))
        assert response.status_code == 404

    def test_map_with_invalid_type(self, client, test_user):
        """Тест карты с неверным типом документа"""
        client.force_login(test_user)
        response = client.get(reverse('map', kwargs={
            'report_type': 'invalid',
            'pk': 1
        }))
        assert response.status_code == 404


@pytest.mark.django_db
class TestEditForms:

    def test_process_edit_form_act(self, client, test_user):
        """Тест обработки формы редактирования акта"""
        client.force_login(test_user)

        act = Act.objects.create(
            user=test_user,
            year='2023',
            name_number='Тестовый акт',
            is_processing=False
        )

        # Данные для формы
        form_data = {
            'year': '2024',
            'name_number': 'Обновленный акт',
            'place': 'Москва',
            'customer': 'Заказчик',
            'area': '100 кв.м.',
            'expert': 'Эксперт',
            'executioner': 'Исполнитель',
            'open_list': '12345',
            'conclusion': 'Заключение',
            'border_objects': 'Объекты рядом'
        }

        response = client.post(reverse('acts_edit', kwargs={'pk': act.id}), form_data)

        assert response.status_code == 302
        act.refresh_from_db()
        assert act.year == '2024'
        assert act.name_number == 'Обновленный акт'
        assert act.place == 'Москва'

    def test_process_edit_form_scientific_report(self, client, test_user):
        """Тест обработки формы редактирования научного отчета"""
        client.force_login(test_user)

        report = ScientificReport.objects.create(
            user=test_user,
            name='Тестовый отчет',
            is_processing=False
        )

        form_data = {
            'name': 'Обновленный отчет',
            'organization': 'Организация',
            'author': 'Автор',
            'open_list': '12345',
            'writing_date': '2023',
            'introduction': 'Введение',
            'contractors': 'Исполнители',
            'place': 'Место',
            'area_info': 'Информация о площади',
            'research_history': 'История исследований',
            'results': 'Результаты',
            'conclusion': 'Заключение'
        }

        response = client.post(reverse('scientific_reports_edit', kwargs={'pk': report.id}), form_data)

        assert response.status_code == 302
        report.refresh_from_db()
        assert report.name == 'Обновленный отчет'
        assert report.organization == 'Организация'

    def test_process_supplement_with_images(self, client, test_user):
        """Тест обработки дополнений с изображениями"""
        client.force_login(test_user)

        act = Act.objects.create(
            user=test_user,
            year='2023',
            name_number='Тестовый акт',
            is_processing=False,
            supplement={
                'images': [
                    {'source': 'img1.jpg', 'label': 'Изображение 1'},
                    {'source': 'img2.jpg', 'label': 'Изображение 2'}
                ]
            }
        )

        # Имитируем POST запрос с обновленными labels
        with patch('agregator.views.process_supplement') as mock_process:
            mock_process.return_value = {
                'images': [
                    {'source': 'img1.jpg', 'label': 'Новая подпись 1'},
                    {'source': 'img2.jpg', 'label': 'Новая подпись 2'}
                ]
            }

            response = client.post(reverse('acts_edit', kwargs={'pk': act.id}), {
                'label-img1.jpg': 'Новая подпись 1',
                'label-img2.jpg': 'Новая подпись 2'
            })

            assert response.status_code == 302
            mock_process.assert_called_once()


@pytest.mark.django_db
class TestDeleteOperations:

    def test_act_delete(self, client, test_user):
        """Тест удаления акта"""
        client.force_login(test_user)

        act = Act.objects.create(
            user=test_user,
            year='2023',
            name_number='Акт для удаления',
            is_processing=False
        )
        act_id = act.id

        response = client.get(reverse('acts_delete', kwargs={'pk': act.id}))

        assert response.status_code == 302
        assert not Act.objects.filter(id=act_id).exists()

    def test_scientific_report_delete(self, client, test_user):
        """Тест удаления научного отчета"""
        client.force_login(test_user)

        report = ScientificReport.objects.create(
            user=test_user,
            name='Отчет для удаления',
            is_processing=False
        )
        report_id = report.id

        response = client.get(reverse('scientific_reports_delete', kwargs={'pk': report.id}))

        assert response.status_code == 302
        assert not ScientificReport.objects.filter(id=report_id).exists()

    def test_open_list_delete(self, client, test_user):
        """Тест удаления открытого листа"""
        client.force_login(test_user)

        open_list = OpenLists.objects.create(
            user=test_user,
            number='123',
            holder='Держатель',
            is_processing=False
        )
        open_list_id = open_list.id

        response = client.get(reverse('open_lists_delete', kwargs={'pk': open_list.id}))

        assert response.status_code == 302
        assert not OpenLists.objects.filter(id=open_list_id).exists()


@pytest.mark.django_db
class TestDetailViews:

    def test_act_detail_view(self, client, test_user):
        """Тест детального просмотра акта"""
        client.force_login(test_user)

        act = Act.objects.create(
            user=test_user,
            year='2023',
            name_number='Детальный акт',
            is_processing=False,
            source=[{'origin_filename': 'test.pdf'}]
        )

        response = client.get(reverse('acts', kwargs={'pk': act.id}))

        assert response.status_code == 200
        assert 'Детальный акт' in response.content.decode()

    def test_scientific_report_detail_view(self, client, test_user):
        """Тест детального просмотра научного отчета"""
        client.force_login(test_user)

        report = ScientificReport.objects.create(
            user=test_user,
            name='Детальный отчет',
            is_processing=False,
            source=[{'origin_filename': 'test.pdf'}]
        )

        response = client.get(reverse('scientific_reports', kwargs={'pk': report.id}))

        assert response.status_code == 200
        assert 'Детальный отчет' in response.content.decode()

    def test_archaeological_heritage_site_detail(self, client, test_user):
        """Тест детального просмотра объекта наследия"""
        client.force_login(test_user)

        oan = ArchaeologicalHeritageSite.objects.create(
            doc_name='Тестовый объект',
            district='Район',
            document='Документ',
            register_num='123'
        )

        response = client.get(reverse('archaeological_heritage_sites', kwargs={'pk': oan.id}))

        assert response.status_code == 200
        assert 'Тестовый объект' in response.content.decode()


@pytest.mark.django_db
class TestFileUploadViews:

    @patch('agregator.views.raw_account_cards_save')
    @patch('agregator.views.process_account_cards.apply_async')
    def test_account_cards_upload(self, mock_apply, mock_save, client, test_user):
        """Тест загрузки учетных карт"""
        client.force_login(test_user)

        mock_save.return_value = [1]
        mock_task = MagicMock()
        mock_task.task_id = 'test-task-123'
        mock_apply.return_value = mock_task

        with patch('agregator.views.UserTasks.objects.create'):
            # Имитируем загрузку файла
            test_file = SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")

            response = client.post(reverse('account_cards_upload'), {
                'files': [test_file],
                'storage_type': 'private'
            })

        assert response.status_code == 200
        mock_save.assert_called_once()
        mock_apply.assert_called_once()

    @patch('agregator.views.raw_commercial_offers_save')
    @patch('agregator.views.process_commercial_offers.apply_async')
    def test_commercial_offers_upload(self, mock_apply, mock_save, client, test_user):
        """Тест загрузки коммерческих предложений"""
        client.force_login(test_user)

        mock_save.return_value = [1]
        mock_task = MagicMock()
        mock_task.task_id = 'test-task-456'
        mock_apply.return_value = mock_task

        with patch('agregator.views.UserTasks.objects.create'):
            test_file = SimpleUploadedFile("offer.pdf", b"file_content", content_type="application/pdf")

            response = client.post(reverse('commercial_offers_upload'), {
                'files': [test_file],
                'storage_type': 'private'
            })

        assert response.status_code == 200
        mock_save.assert_called_once()
        mock_apply.assert_called_once()


@pytest.mark.django_db
class TestErrorHandling:

    def test_doc_reprocess_invalid_type(self, client, test_user):
        """Тест повторной обработки с неверным типом документа"""
        client.force_login(test_user)

        response = client.post(reverse('doc_reprocess', kwargs={'pk': 999}), {
            'select_text': 'on'
        })

        # Должен вернуть ошибку 404
        assert response.status_code == 404

    def test_map_invalid_report_type(self, client, test_user):
        """Тест карты с неверным типом отчета"""
        client.force_login(test_user)

        response = client.get(reverse('map', kwargs={
            'report_type': 'invalid_type',
            'pk': 1
        }))

        assert response.status_code == 404

    def test_download_coordinates_invalid_type(self, client, test_user):
        """Тест скачивания координатов неверного типа"""
        client.force_login(test_user)

        response = client.post(reverse('download_coordinates', kwargs={
            'report_type': 'invalid_type',
            'pk': 1
        }))

        assert response.status_code == 404


@pytest.mark.django_db
class TestUserTasksViews:
    def test_get_user_tasks_reports(self, client, test_user):
        """Тест получения задач по отчетам пользователя"""
        client.force_login(test_user)
        # Создаем тестовую задачу
        task = TaskResult.objects.create(
            task_id='test-task-1',
            status='SUCCESS'
        )
        UserTasks.objects.create(
            user=test_user,
            task_id=task.task_id,
            files_type='act',
            upload_source={'source': 'Пользовательский файл'}
        )

        response = client.get(reverse('get_user_tasks_reports'))
        assert response.status_code == 200
        assert 'test-task-1' in response.json()['tasks_id']

    def test_get_user_tasks_external_admin(self, client, admin_user):
        """Тест получения внешних задач для администратора"""
        client.force_login(admin_user)
        task = TaskResult.objects.create(
            task_id='test-task-ext',
            status='SUCCESS'
        )
        UserTasks.objects.create(
            user=admin_user,
            task_id=task.task_id,
            files_type='act',
            upload_source={'source': 'Внешний источник'}
        )

        response = client.get(reverse('get_user_tasks_external'))
        assert response.status_code == 200
        assert 'test-task-ext' in response.json()['tasks_id']
