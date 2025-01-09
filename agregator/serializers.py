from rest_framework import serializers, viewsets
from .models import User, Act, ScientificReport, TechReport


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'last_login', 'is_superuser',
                  'first_name', 'last_name', 'email', 'is_staff', 'is_active', 'date_joined']


class ActSerializer(serializers.ModelSerializer):
    class Meta:
        model = Act
        fields = ['id', 'user_id', 'supplement_id', 'year',
                  'finish_date', 'type', 'name_number', 'place', 'customer',
                  'area', 'expert', 'executioner', 'open_list', 'conclusion', 'border_objects',
                  'act', 'start_date', 'exp_place', 'exp_customer', 'relationship', 'goal',
                  'object', 'docs', 'exp_info', 'exp_facts', 'literature', 'exp_conclusion']


class ScientificReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScientificReport
        fields = ['id', 'user_id', 'supplement_id', 'name',
                  'organization', 'author', 'open_list',
                  'writing_date', 'introduction', 'contractors', 'place',
                  'area_info', 'research_history', 'results', 'conclusion']


class TechReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = TechReport
        fields = ['id', 'user_id', 'supplement_id', 'name',
                  'organization', 'author', 'open_list',
                  'writing_date', 'introduction', 'contractors', 'place',
                  'area_info', 'research_history', 'results', 'conclusion']
