from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()

urlpatterns = [
    path('', views.index, name='index'),
    path('deconstructor/', views.deconstructor, name='deconstructor'),
    path('external_sources/', views.external_sources, name='external_sources'),
    path('constructor/', views.constructor, name='constructor'),
    path('interactive_map/', views.interactive_map, name='interactive_map'),
    path('demonstrator/', views.demonstrator, name='demonstrator'),
    path('processing_status/', views.processing_status, name='processing_status'),
    path('open_list_ocr/', views.open_list_ocr, name='open_list_ocr'),
    path('open_lists_register/', views.open_lists_register, name='open_lists_register'),
    path('gpt_chat/', views.gpt_chat, name='gpt_chat'),
    path('ask_gpt/', views.ask_gpt, name='ask_gpt'),
    path('register/', views.user_register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('settings/', views.settings, name='settings'),
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]