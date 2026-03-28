from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, UserTasks, Act, ScientificReport, TechReport, OpenLists,
    ObjectAccountCard, ArchaeologicalHeritageSite, IdentifiedArchaeologicalHeritageSite,
    CommercialOffers, GeoObject, GeojsonData, Chat, Message
)
from agregator.kodexplorer_users_sync import update_kod_user, delete_kod_user


class CustomUserAdmin(UserAdmin):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        # Принудительная синхронизация при ЛЮБОМ сохранении
        print(f"🔧 АДМИНКА: Сохранение пользователя {obj.username}")
        update_kod_user(obj)

    def delete_model(self, request, obj):
        print(f"🔧 АДМИНКА: Удаление пользователя {obj.username}")
        delete_kod_user(obj.username)
        super().delete_model(request, obj)


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, CustomUserAdmin)


@admin.register(UserTasks)
class UserTasksAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'task_id', 'files_type')
    search_fields = ('task_id', 'files_type', 'user__username')


@admin.register(Act)
class ActAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'year', 'name_number', 'date_uploaded', 'is_processing', 'is_public')
    list_filter = ('is_processing', 'is_public')
    search_fields = ('name_number', 'user__username')


@admin.register(ScientificReport)
class ScientificReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'organization', 'date_uploaded', 'is_processing', 'is_public')
    list_filter = ('is_processing', 'is_public')
    search_fields = ('name', 'organization', 'user__username')


@admin.register(TechReport)
class TechReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'organization', 'date_uploaded', 'is_processing', 'is_public')
    list_filter = ('is_processing', 'is_public')
    search_fields = ('name', 'organization', 'user__username')


@admin.register(OpenLists)
class OpenListsAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'origin_filename', 'date_uploaded', 'is_processing', 'is_public')
    list_filter = ('is_processing', 'is_public')
    search_fields = ('origin_filename', 'user__username')


@admin.register(ObjectAccountCard)
class ObjectAccountCardAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'name', 'date_uploaded', 'is_processing', 'is_public')
    list_filter = ('is_processing', 'is_public')
    search_fields = ('name', 'origin_filename', 'user__username')


@admin.register(ArchaeologicalHeritageSite)
class ArchaeologicalHeritageSiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'doc_name', 'district', 'date_uploaded', 'is_excluded')
    list_filter = ('is_excluded',)
    search_fields = ('doc_name', 'district')


@admin.register(IdentifiedArchaeologicalHeritageSite)
class IdentifiedArchaeologicalHeritageSiteAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'address', 'date_uploaded', 'is_excluded')
    list_filter = ('is_excluded',)
    search_fields = ('name', 'address')


@admin.register(CommercialOffers)
class CommercialOffersAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'origin_filename', 'date_uploaded', 'is_processing', 'is_public')
    list_filter = ('is_processing', 'is_public')
    search_fields = ('origin_filename', 'user__username')


@admin.register(GeoObject)
class GeoObjectAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'type', 'user', 'date_uploaded', 'is_processing', 'is_public')
    list_filter = ('is_processing', 'is_public')
    search_fields = ('name', 'type', 'user__username')


@admin.register(GeojsonData)
class GeojsonDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'user', 'created_at')
    search_fields = ('name', 'user__username')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat', 'sender', 'sent_at')
    search_fields = ('sender', 'chat__name')
