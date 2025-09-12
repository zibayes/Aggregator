import pytest
import json
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from agregator.models import (
    User, UserTasks, Act, ScientificReport, TechReport, OpenLists,
    ObjectAccountCard, ArchaeologicalHeritageSite, IdentifiedArchaeologicalHeritageSite,
    CommercialOffers, GeoObject, GeojsonData, Chat, Message
)
import os
import tempfile
from unittest.mock import patch, MagicMock

UserModel = get_user_model()


class TestUserModel:
    def test_user_creation(self, db):
        """Тест создания пользователя"""
        user = UserModel.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        assert user.username == 'testuser'
        assert user.email == 'test@example.com'
        assert user.check_password('testpass123')
        assert user.avatar.name == 'avatars/default.png'

    def test_user_str_method(self, db):
        """Тест строкового представления пользователя"""
        user = UserModel.objects.create_user(username='testuser')
        assert str(user) == 'testuser'

    def test_user_avatar_upload(self, db, test_image):
        """Тест загрузки аватара"""
        user = UserModel.objects.create_user(username='testuser')
        user.avatar = test_image
        user.save()

        assert user.avatar.name.startswith('avatars/')
        assert 'test_avatar' in user.avatar.name


class TestUserTasksModel:
    def test_user_tasks_creation(self, db, test_user):
        """Тест создания пользовательской задачи"""
        task = UserTasks.objects.create(
            user=test_user,
            task_id='test_task_123',
            files_type='pdf',
            upload_source={'source': 'test', 'files': ['file1.pdf']}
        )

        assert task.user == test_user
        assert task.task_id == 'test_task_123'
        assert task.files_type == 'pdf'
        assert task.upload_source_dict == {'source': 'test', 'files': ['file1.pdf']}

    def test_user_tasks_str_method(self, db, test_user):
        """Тест строкового представления задачи"""
        task = UserTasks.objects.create(user=test_user, task_id='test_task')
        assert str(task) == f"User task {task.id}"


class TestActModel:
    def test_act_creation(self, db, test_user):
        """Тест создания акта"""
        act = Act.objects.create(
            user=test_user,
            year='2023',
            finish_date='2023-12-31',
            type='test_type',
            name_number='123',
            place='Test place',
            customer='Test customer',
            area='Test area',
            expert='Test expert',
            executioner='Test executioner',
            open_list='12345',
            conclusion='Test conclusion',
            border_objects='Test objects',
            act='Test act',
            start_date='2023-01-01',
            exp_place='Test exp place',
            exp_customer='Test exp customer',
            exp_expert='Test exp expert',
            relationship='Test relationship',
            goal='Test goal',
            object='Test object',
            docs='Test docs',
            exp_info='Test info',
            exp_facts='Test facts',
            literature='Test literature',
            exp_conclusion='Test exp conclusion',
            source=[{'path': '/test/path', 'name': 'test.pdf'}],
            supplement={'key': 'value'},
            coordinates={'lat': 55.7558, 'lon': 37.6176}
        )

        assert act.user == test_user
        assert act.year == '2023'
        assert act.coordinates_dict == {'lat': 55.7558, 'lon': 37.6176}
        assert act.source_dict == [{'path': '/test/path', 'name': 'test.pdf'}]

    def test_act_str_method(self, db, test_user):
        """Тест строкового представления акта"""
        act = Act.objects.create(user=test_user, year='2023', name_number='123')
        assert str(act) == f"Act {act.id} by testuser"


class TestScientificReportModel:
    def test_scientific_report_creation(self, db, test_user):
        """Тест создания научного отчета"""
        report = ScientificReport.objects.create(
            user=test_user,
            name='Test Report',
            organization='Test Org',
            author='Test Author',
            open_list='12345',
            writing_date='2023',
            introduction='Test intro',
            contractors='Test contractors',
            place='Test place',
            area_info='Test area info',
            research_history='Test history',
            results='Test results',
            conclusion='Test conclusion',
            source=[{'path': '/test/path', 'name': 'test.pdf'}],
            content={'sections': ['1', '2']},
            supplement={'key': 'value'},
            coordinates={'lat': 55.7558, 'lon': 37.6176}
        )

        assert report.user == test_user
        assert report.name == 'Test Report'
        assert report.content_dict == {'sections': ['1', '2']}


class TestTechReportModel:
    def test_tech_report_creation(self, db, test_user):
        """Тест создания техотчета"""
        report = TechReport.objects.create(
            user=test_user,
            name='Tech Report',
            organization='Tech Org',
            author='Tech Author',
            open_list='54321',
            writing_date='2023',
            introduction='Tech intro',
            contractors='Tech contractors',
            place='Tech place',
            area_info='Tech area info',
            research_history='Tech history',
            results='Tech results',
            conclusion='Tech conclusion'
        )

        assert report.organization == 'Tech Org'
        assert report.open_list == '54321'


class TestOpenListsModel:
    def test_open_lists_creation(self, db, test_user):
        """Тест создания открытого листа"""
        test_file = SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")

        open_list = OpenLists.objects.create(
            user=test_user,
            origin_filename='test.pdf',
            number='123',
            holder='Test Holder',
            object='Test Object',
            works='Test Works',
            start_date='2023-01-01',
            end_date='2023-12-31',
            source=test_file
        )

        assert open_list.user == test_user
        assert open_list.number == '123'
        assert open_list.source.name.startswith('Открытые листы/')


class TestObjectAccountCardModel:
    def test_account_card_creation(self, db, test_user):
        """Тест создания учетной карты"""
        card = ObjectAccountCard.objects.create(
            user=test_user,
            origin_filename='test.pdf',
            name='Test Object',
            creation_time='2023',
            address='Test Address',
            object_type='Test Type',
            general_classification='Test Classification',
            description='Test Description',
            usage='Test Usage',
            discovery_info='Test Discovery',
            compiler='Test Compiler',
            compile_date='2023-01-01',
            supplement={'key': 'value'},
            coordinates={'lat': 55.7558, 'lon': 37.6176},
            source='/test/path'
        )

        assert card.user == test_user
        assert card.name == 'Test Object'
        assert card.coordinates_dict == {'lat': 55.7558, 'lon': 37.6176}


class TestArchaeologicalHeritageSiteModel:
    def test_heritage_site_creation(self, db, test_user):
        """Тест создания объекта наследия"""
        account_card = ObjectAccountCard.objects.create(
            user=test_user,
            name='Test Card'
        )

        site = ArchaeologicalHeritageSite.objects.create(
            account_card=account_card,
            doc_name='Test Site',
            district='Test District',
            document='Test Document',
            register_num='123',
            source='/test/path',
            document_source=[{'path': '/test/path', 'name': 'test.pdf'}]
        )

        assert site.account_card == account_card
        assert site.doc_name == 'Test Site'
        assert site.register_num == '123'


class TestCommercialOffersModel:
    def test_commercial_offer_creation(self, db, test_user):
        """Тест создания коммерческого предложения"""
        offer = CommercialOffers.objects.create(
            user=test_user,
            origin_filename='test.pdf',
            coordinates={'lat': 55.7558, 'lon': 37.6176},
            source='/test/path'
        )

        assert offer.user == test_user
        assert offer.coordinates_dict == {'lat': 55.7558, 'lon': 37.6176}


class TestGeoObjectModel:
    def test_geo_object_creation(self, db, test_user):
        """Тест создания геообъекта"""
        geo_object = GeoObject.objects.create(
            user=test_user,
            origin_filename='test.pdf',
            name='Test Geo Object',
            type='Test Type',
            coordinates={'lat': 55.7558, 'lon': 37.6176},
            source='/test/path'
        )

        assert geo_object.user == test_user
        assert geo_object.name == 'Test Geo Object'
        assert geo_object.type == 'Test Type'


class TestGeojsonDataModel:
    def test_geojson_data_creation(self, db):
        """Тест создания геоданных"""
        geojson_data = GeojsonData.objects.create(
            name='Test GeoJSON',
            geojson={'type': 'FeatureCollection', 'features': []}
        )

        assert geojson_data.name == 'Test GeoJSON'
        assert geojson_data.geojson['type'] == 'FeatureCollection'


class TestChatModel:
    def test_chat_creation(self, db, test_user):
        """Тест создания чата"""
        chat = Chat.objects.create(
            user=test_user,
            name='Test Chat'
        )

        assert chat.user == test_user
        assert chat.name == 'Test Chat'


class TestMessageModel:
    def test_message_creation(self, db, test_user):
        """Тест создания сообщения"""
        chat = Chat.objects.create(user=test_user, name='Test Chat')
        message = Message.objects.create(
            chat=chat,
            sender='user',
            content='Test message content'
        )

        assert message.chat == chat
        assert message.sender == 'user'
        assert message.content == 'Test message content'
        assert str(message) == f"Сообщение от user в чате Test Chat"


@pytest.mark.django_db
def test_model_properties():
    """Тест свойств моделей с JSON-полями"""
    user = UserModel.objects.create_user(username='testuser')

    # Test Act properties
    act = Act.objects.create(
        user=user,
        year='2023',
        name_number='123',
        source='[{"path": "/test", "name": "test.pdf"}]',
        supplement='{"key": "value"}',
        coordinates='{"lat": 55.7558, "lon": 37.6176}'
    )

    assert isinstance(act.source_dict, list)
    assert isinstance(act.supplement_dict, dict)
    assert isinstance(act.coordinates_dict, dict)

    # Test UserTasks properties
    task = UserTasks.objects.create(
        user=user,
        task_id='test',
        files_type='pdf',
        upload_source='{"source": "test"}'
    )

    assert isinstance(task.upload_source_dict, dict)


class TestEdgeCasesAndMissingCoverage:
    """Тесты для непокрытых участков кода"""

    def test_user_save_with_existing_avatar(self, db, test_user, test_image):
        """Тест сохранения пользователя с существующим аватаром (строки 25-36)"""
        # Сначала сохраняем с аватаром
        test_user.avatar = test_image
        test_user.save()

        # Затем сохраняем с новым аватаром (должен удалить старый)
        new_image = SimpleUploadedFile("new_avatar.jpg", b"new_content", content_type="image/jpeg")
        test_user.avatar = new_image
        test_user.save()

        assert test_user.avatar.name.startswith('avatars/')

    def test_user_delete_with_default_avatar(self, db):
        """Тест удаления пользователя с аватаром по умолчанию (строки 73-74)"""
        user = UserModel.objects.create_user(username='default_avatar_user')
        user_id = user.id
        user.delete()

        assert not UserModel.objects.filter(id=user_id).exists()

    def test_user_tasks_save_with_dict_upload_source(self, db, test_user):
        """Тест сохранения UserTasks с dict вместо JSON (строки 80-82)"""
        task = UserTasks(
            user=test_user,
            task_id='test_task',
            files_type='pdf',
            upload_source={'test': 'dict'}
        )
        task.save()

        assert task.upload_source_dict == {'test': 'dict'}

    def test_act_delete_without_source(self, db, test_user):
        """Тест удаления акта без source (строки 164-168)"""
        act = Act.objects.create(
            user=test_user,
            year='2023',
            name_number='123'
        )
        act_id = act.id
        act.delete()

        assert not Act.objects.filter(id=act_id).exists()

    def test_act_delete_with_string_source(self, db, test_user):
        """Тест удаления акта с source как строкой (строки 172)"""
        act = Act.objects.create(
            user=test_user,
            year='2023',
            name_number='123',
            source='[{"path": "/test/path"}]'
        )
        act_id = act.id
        act.delete()

        assert not Act.objects.filter(id=act_id).exists()

    def test_act_save_with_dict_data(self, db, test_user):
        """Тест сохранения акта с dict данными (строки 214, 230-234, 238)"""
        act = Act(
            user=test_user,
            year='2023',
            name_number='123',
            upload_source={'test': 'dict'},
            source={'test': 'dict'},
            supplement={'test': 'dict'},
            coordinates={'test': 'dict'}
        )
        act.save()

        assert isinstance(act.upload_source, str)
        assert isinstance(act.source, str)
        assert isinstance(act.supplement, str)
        assert isinstance(act.coordinates, str)

    def test_scientific_report_save_and_delete(self, db, test_user):
        """Тест ScientificReport с разными сценариями (строки 246, 254, 284, 300-304, 308)"""
        # Сохранение с dict данными
        report = ScientificReport(
            user=test_user,
            name='Test Report',
            upload_source={'test': 'dict'},
            source={'test': 'dict'},
            supplement={'test': 'dict'},
            content={'test': 'dict'},
            coordinates={'test': 'dict'}
        )
        report.save()

        # Удаление без source
        report_id = report.id
        report.delete()
        assert not ScientificReport.objects.filter(id=report_id).exists()

        # Удаление с source как строкой
        report2 = ScientificReport.objects.create(
            user=test_user,
            name='Test Report 2',
            source='[{"path": "/test/path"}]'
        )
        report2_id = report2.id
        report2.delete()
        assert not ScientificReport.objects.filter(id=report2_id).exists()

    def test_tech_report_save_with_dict_data(self, db, test_user):
        """Тест TechReport с dict данными (строки 316, 320, 324)"""
        report = TechReport(
            user=test_user,
            name='Tech Report',
            upload_source={'test': 'dict'},
            source={'test': 'dict'},
            supplement={'test': 'dict'},
            content={'test': 'dict'},
            coordinates={'test': 'dict'}
        )
        report.save()

        assert isinstance(report.upload_source, str)
        assert isinstance(report.source, str)

    def test_open_lists_save_with_dict_upload_source(self, db, test_user):
        """Тест OpenLists с dict upload_source (строки 346, 358-360, 364)"""
        test_file = SimpleUploadedFile("test.pdf", b"file_content", content_type="application/pdf")

        open_list = OpenLists(
            user=test_user,
            origin_filename='test.pdf',
            number='123',
            upload_source={'test': 'dict'},
            source=test_file
        )
        open_list.save()

        assert isinstance(open_list.upload_source, str)

    def test_object_account_card_save_and_delete(self, db, test_user):
        """Тест ObjectAccountCard с разными сценариями (строки 391, 405-407, 411, 415)"""
        # Сохранение с dict данными
        card = ObjectAccountCard(
            user=test_user,
            origin_filename='test.pdf',
            name='Test Card',
            upload_source={'test': 'dict'},
            supplement={'test': 'dict'},
            coordinates={'test': 'dict'}
        )
        card.save()

        # Удаление без source
        card_id = card.id
        card.delete()
        assert not ObjectAccountCard.objects.filter(id=card_id).exists()

    def test_archaeological_heritage_site_save(self, db, test_user):
        """Тест ArchaeologicalHeritageSite с dict document_source (строки 440, 447-454, 458)"""
        account_card = ObjectAccountCard.objects.create(
            user=test_user,
            name='Test Card'
        )

        site = ArchaeologicalHeritageSite(
            account_card=account_card,
            doc_name='Test Site',
            document_source={'test': 'dict'}
        )
        site.save()

        assert isinstance(site.document_source, str)

    def test_identified_heritage_site_save(self, db, test_user):
        """Тест IdentifiedArchaeologicalHeritageSite с dict document_source (строки 479, 482-483, 486-493, 497)"""
        account_card = ObjectAccountCard.objects.create(
            user=test_user,
            name='Test Card'
        )

        site = IdentifiedArchaeologicalHeritageSite(
            account_card=account_card,
            name='Test Site',
            document_source={'test': 'dict'}
        )
        site.save()

        assert isinstance(site.document_source, str)

    def test_commercial_offers_save_with_dict_data(self, db, test_user):
        """Тест CommercialOffers с dict данными (строки 513, 526-528, 532)"""
        offer = CommercialOffers(
            user=test_user,
            origin_filename='test.pdf',
            upload_source={'test': 'dict'},
            coordinates={'test': 'dict'}
        )
        offer.save()

        assert isinstance(offer.upload_source, str)
        assert isinstance(offer.coordinates, str)

    def test_geo_object_save_with_dict_data(self, db, test_user):
        """Тест GeoObject с dict данными (строки 559, 567-569, 573, 577)"""
        geo_object = GeoObject(
            user=test_user,
            origin_filename='test.pdf',
            upload_source={'test': 'dict'},
            coordinates={'test': 'dict'}
        )
        geo_object.save()

        assert isinstance(geo_object.upload_source, str)
        assert isinstance(geo_object.coordinates, str)

    def test_user_avatar_replacement_logic(self, db):
        """Тестируем только логику условия удаления аватара"""
        from agregator.models import User

        user = User(username='test')
        user.avatar = None

        # Тест 1: Нет старого аватара
        result = user._should_delete_old_avatar(None)
        assert result is False

        # Тест 2: Старый аватар - дефолтный
        class MockAvatar:
            name = 'avatars/default.png'

        result = user._should_delete_old_avatar(MockAvatar())
        assert result is False

        # Тест 3: Старый и новый аватар одинаковые
        class MockAvatar:
            name = 'avatars/custom.jpg'

        user.avatar = MockAvatar()
        result = user._should_delete_old_avatar(MockAvatar())
        assert result is False

        # Тест 4: Должен удалить - разные не-дефолтные аватары
        class OldAvatar:
            name = 'avatars/old.jpg'

        class NewAvatar:
            name = 'avatars/new.jpg'

        user.avatar = NewAvatar()
        result = user._should_delete_old_avatar(OldAvatar())
        assert result is True

    @patch('agregator.models.shutil.rmtree')
    @patch('agregator.models.os.path.isdir')
    @patch('agregator.models.os.path.isfile')
    def test_delete_files_function(self, mock_isfile, mock_isdir, mock_rmtree, db):
        """Тест функции delete_files (строки 590, 604)"""
        mock_isfile.return_value = True
        mock_isdir.return_value = True

        # Тестируем с Windows путем
        from agregator.models import delete_files
        delete_files(r'C:\test\file.txt')

        # Тестируем с Unix путем
        delete_files('/test/file.txt')

        assert mock_rmtree.called


class TestJsonConversionMethods:
    """Тесты для функций to_json и from_json"""

    def test_to_json_with_string(self):
        """Тест to_json со строкой"""
        from agregator.models import to_json
        result = to_json("already string")
        assert result == "already string"

    def test_to_json_with_none(self):
        """Тест to_json с None"""
        from agregator.models import to_json
        result = to_json(None)
        assert result is None

    def test_to_json_with_dict(self):
        """Тест to_json с dict"""
        from agregator.models import to_json
        result = to_json({"test": "value"})
        assert result == '{"test": "value"}'

    def test_to_json_with_list(self):
        """Тест to_json с list"""
        from agregator.models import to_json
        result = to_json(["item1", "item2"])
        assert result == '["item1", "item2"]'

    def test_from_json_with_dict(self):
        """Тест from_json с dict"""
        from agregator.models import from_json
        result = from_json('{"test": "value"}')
        assert result == {"test": "value"}

    def test_from_json_with_list(self):
        """Тест from_json с list"""
        from agregator.models import from_json
        result = from_json('["item1", "item2"]')
        assert result == ["item1", "item2"]

    def test_from_json_with_string(self):
        """Тест from_json со строкой"""
        from agregator.models import from_json
        result = from_json("plain string")
        assert result == "plain string"

    def test_from_json_with_none(self):
        """Тест from_json с None"""
        from agregator.models import from_json
        result = from_json(None)
        assert result is None


class TestRemainingCoverage:
    """Тесты для оставшихся непокрытых строк"""

    def test_user_save_with_same_avatar(self, db, test_user, test_image):
        """Тест сохранения с тем же аватаром (строки 34-35)"""
        test_user.avatar = test_image
        test_user.save()

        # Сохраняем again без изменения аватара
        test_user.save()

        # Не должно быть ошибок
        assert test_user.pk is not None

    def test_user_delete_without_avatar(self, db):
        """Тест удаления пользователя без аватара (строки 60-61, 69)"""
        user = UserModel.objects.create_user(username='no_avatar_user')
        user_id = user.id
        user.delete()

        assert not UserModel.objects.filter(id=user_id).exists()

    def test_act_save_with_none_data(self, db, test_user):
        """Тест акта с None данными (строки 98)"""
        act = Act.objects.create(
            user=test_user,
            year='2023',
            name_number='123',
            upload_source=None,
            source=None,
            supplement=None,
            coordinates=None
        )

        assert act.upload_source_dict is None
        assert act.source_dict is None

    @patch('agregator.models.delete_files')
    def test_act_delete_with_dict_source(self, mock_delete_files, db, test_user):
        """Тест удаления акта с source как dict (строки 193)"""
        act = Act.objects.create(
            user=test_user,
            year='2023',
            name_number='123',
            source=[{'path': '/test/path', 'name': 'test.pdf'}]
        )
        act_id = act.id
        act.delete()

        assert not Act.objects.filter(id=act_id).exists()
        assert mock_delete_files.called

    def test_scientific_report_with_empty_data(self, db, test_user):
        """Тест ScientificReport с пустыми данными (строки 256, 264, 272)"""
        report = ScientificReport.objects.create(
            user=test_user,
            name='Test Report',
            source=[],
            content={},
            supplement=None,
            coordinates=None
        )

        assert report.source_dict == []
        assert report.content_dict == {}

    def test_tech_report_properties_with_none(self, db, test_user):
        """Тест свойств TechReport с None (строки 318-319, 323, 331, 335, 339)"""
        report = TechReport.objects.create(
            user=test_user,
            name='Test Report',
            upload_source=None,
            source=None,
            supplement=None,
            content=None,
            coordinates=None
        )

        assert report.upload_source_dict is None
        assert report.source_dict is None
        assert report.supplement_dict is None
        assert report.content_dict is None
        assert report.coordinates_dict is None

    @patch('agregator.models.delete_files')
    def test_open_lists_delete_without_file(self, mock_delete_files, db, test_user):
        """Тест удаления OpenLists без файла (строки 361, 373-375, 379)"""
        open_list = OpenLists.objects.create(
            user=test_user,
            origin_filename='test.pdf',
            number='123'
        )
        open_list_id = open_list.id
        open_list.delete()

        assert not OpenLists.objects.filter(id=open_list_id).exists()
        assert not mock_delete_files.called

    def test_account_card_with_none_data(self, db, test_user):
        """Тест ObjectAccountCard с None данными (строки 406, 421, 426, 430)"""
        card = ObjectAccountCard.objects.create(
            user=test_user,
            origin_filename='test.pdf',
            name='Test Card',
            upload_source=None,
            supplement=None,
            coordinates=None,
            source=None
        )

        assert card.upload_source_dict is None
        assert card.supplement_dict is None
        assert card.coordinates_dict is None

    @patch('agregator.models.delete_files')
    def test_archaeological_site_delete_with_string_source(self, mock_delete_files, db, test_user):
        """Тест удаления ArchaeologicalHeritageSite с source как строкой (строки 462-466)"""
        account_card = ObjectAccountCard.objects.create(user=test_user, name='Test Card')
        site = ArchaeologicalHeritageSite.objects.create(
            account_card=account_card,
            doc_name='Test Site',
            document_source='[{"path": "/test/path"}]',
            source='/test/path'
        )
        site_id = site.id
        site.delete()

        assert not ArchaeologicalHeritageSite.objects.filter(id=site_id).exists()
        assert mock_delete_files.call_count == 2  # document_source и source

    @patch('agregator.models.delete_files')
    def test_identified_site_delete_with_string_source(self, mock_delete_files, db, test_user):
        """Тест удаления IdentifiedArchaeologicalHeritageSite с source как строкой (строки 498-502)"""
        account_card = ObjectAccountCard.objects.create(user=test_user, name='Test Card')
        site = IdentifiedArchaeologicalHeritageSite.objects.create(
            account_card=account_card,
            name='Test Site',
            document_source='[{"path": "/test/path"}]',
            source='/test/path'
        )
        site_id = site.id
        site.delete()

        assert not IdentifiedArchaeologicalHeritageSite.objects.filter(id=site_id).exists()
        assert mock_delete_files.call_count == 2

    def test_commercial_offers_with_none_data(self, db, test_user):
        """Тест CommercialOffers с None данными (строки 522, 535-537, 541)"""
        offer = CommercialOffers.objects.create(
            user=test_user,
            origin_filename='test.pdf',
            upload_source=None,
            coordinates=None,
            source=None
        )

        assert offer.upload_source_dict is None
        assert offer.coordinates_dict is None

    def test_geo_object_with_none_data(self, db, test_user):
        """Тест GeoObject с None данными (строки 568, 576-578, 582, 586)"""
        geo_object = GeoObject.objects.create(
            user=test_user,
            origin_filename='test.pdf',
            upload_source=None,
            coordinates=None,
            source=None
        )

        assert geo_object.upload_source_dict is None
        assert geo_object.coordinates_dict is None

    @patch('agregator.models.os.path.isfile', return_value=False)
    def test_delete_files_with_nonexistent_file(self, mock_isfile, db):
        """Тест delete_files с несуществующим файлом (строки 599, 613)"""
        from agregator.models import delete_files

        # Не должно быть ошибок при несуществующем файле
        delete_files('/nonexistent/path.txt')

        assert mock_isfile.called
