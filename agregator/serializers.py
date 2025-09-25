from rest_framework import serializers

from .models import User, UserTasks, Act, ScientificReport, TechReport, OpenLists, ObjectAccountCard, \
    ArchaeologicalHeritageSite, IdentifiedArchaeologicalHeritageSite, CommercialOffers, GeoObject, GeojsonData, Chat, \
    Message


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'last_login', 'is_superuser',
                  'first_name', 'last_name', 'email', 'is_staff', 'is_active', 'date_joined']


class UserTasksSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserTasks
        fields = ['id', 'user', 'task_id', 'files_type', 'upload_source']


class ActSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = Act
        fields = ['id', 'user', 'supplement', 'year',
                  'finish_date', 'type', 'name_number', 'place', 'customer',
                  'area', 'expert', 'executioner', 'open_list', 'conclusion', 'border_objects',
                  'act', 'start_date', 'exp_place', 'exp_customer', 'relationship', 'goal',
                  'object', 'docs', 'exp_info', 'exp_facts', 'literature', 'exp_conclusion']


class ScientificReportSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = ScientificReport
        fields = ['id', 'user', 'supplement', 'name',
                  'organization', 'author', 'open_list',
                  'writing_date', 'introduction', 'contractors', 'place',
                  'area_info', 'research_history', 'results', 'conclusion']


class TechReportSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())

    class Meta:
        model = TechReport
        fields = ['id', 'user', 'supplement', 'name',
                  'organization', 'author', 'open_list',
                  'writing_date', 'introduction', 'contractors', 'place',
                  'area_info', 'research_history', 'results', 'conclusion']


class OpenListsSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpenLists
        fields = ['id', 'user', 'origin_filename', 'date_uploaded', 'upload_source', 'is_processing',
                  'is_public', 'number', 'holder', 'object', 'works', 'start_date', 'end_date', 'source']


class ObjectAccountCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = ObjectAccountCard
        fields = ['id', 'user', 'date_uploaded', 'upload_source', 'is_processing', 'is_public',
                  'origin_filename', 'name', 'creation_time', 'address', 'object_type',
                  'general_classification', 'description', 'usage', 'discovery_info', 'compiler',
                  'supplement', 'coordinates', 'source']


class ArchaeologicalHeritageSiteSerializer(serializers.ModelSerializer):
    doc_name = serializers.CharField(required=True, allow_blank=False)
    district = serializers.CharField(required=True, allow_blank=False)
    register_num = serializers.CharField(required=True, allow_blank=False)

    class Meta:
        model = ArchaeologicalHeritageSite
        fields = ['id', 'account_card', 'date_uploaded', 'doc_name', 'district', 'document',
                  'register_num', 'is_excluded']


class IdentifiedArchaeologicalHeritageSiteSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True, allow_blank=False)
    address = serializers.CharField(required=True, allow_blank=False)
    obj_info = serializers.CharField(required=True, allow_blank=False)

    class Meta:
        model = IdentifiedArchaeologicalHeritageSite
        fields = ['id', 'account_card', 'date_uploaded', 'name', 'address', 'obj_info',
                  'document', 'is_excluded']


class CommercialOffersSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommercialOffers
        fields = ['id', 'user', 'date_uploaded', 'upload_source', 'is_processing', 'is_public',
                  'origin_filename', 'coordinates', 'source']


class GeoObjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoObject
        fields = ['id', 'user', 'date_uploaded', 'upload_source', 'is_processing', 'is_public',
                  'origin_filename', 'name', 'type', 'coordinates', 'source']


class GeojsonDataSerializer(serializers.ModelSerializer):
    name = serializers.CharField(required=True, allow_blank=False)
    geojson = serializers.JSONField(required=True)

    class Meta:
        model = GeojsonData
        fields = ['id', 'name', 'geojson']


class ChatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = ['id', 'user', 'name', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.CharField()
    sender_name = serializers.CharField(source='sender.username', read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'chat', 'sender', 'sender_name', 'content', 'sent_at']

    def to_representation(self, instance):
        """Переопределяем представление для включения username"""
        representation = super().to_representation(instance)
        representation['sender'] = instance.sender
        return representation
