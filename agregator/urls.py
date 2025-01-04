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
    path('acts_register/', views.acts_register, name='acts_register'),
    path('acts_register_download/', views.acts_register_download, name='acts_register_download'),
    path('processing_status/', views.processing_status, name='processing_status'),
    path('open_list_ocr/', views.open_list_ocr, name='open_list_ocr'),
    path('open_lists_register/', views.open_lists_register, name='open_lists_register'),
    path('open_lists_register_download/', views.open_lists_register_download, name='open_lists_register_download'),
    path('scientific_reports_register/', views.scientific_reports_register, name='scientific_reports_register'),
    path('gpt_chat/', views.gpt_chat, name='gpt_chat'),
    path('ask_gpt/', views.ask_gpt, name='ask_gpt'),
    path('register/', views.user_register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('settings/', views.settings, name='settings'),

    path('users/<int:pk>/', views.users, name='users'),
    path('acts/<int:pk>/', views.acts, name='acts'),
    path('acts_edit/<int:pk>/', views.acts_edit, name='acts_edit'),
    path('acts_delete/<int:pk>/', views.acts_delete, name='acts_delete'),
    path('scientific_reports/<int:pk>/', views.scientific_reports, name='scientific_reports'),
    path('scientific_reports_edit/<int:pk>/', views.scientific_reports_edit, name='scientific_reports_edit'),
    path('scientific_reports_delete/<int:pk>/', views.scientific_reports_delete, name='scientific_reports_delete'),
    path('open_lists/<int:pk>/', views.open_lists, name='open_lists'),
    path('open_lists_edit/<int:pk>/', views.open_lists_edit, name='open_lists_edit'),
    path('open_lists_delete/<int:pk>/', views.open_lists_delete, name='open_lists_delete'),

    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    path('api/users/', views.UserList.as_view()),
    path('api/users/<int:pk>/', views.UserDetail.as_view()),
    path('api/acts/', views.ActList.as_view()),
    path('api/acts/<int:pk>/', views.ActDetail.as_view()),
    path('api/scientific_reports/', views.ScientificReportList.as_view()),
    path('api/scientific_reports/<int:pk>/', views.ScientificReportDetail.as_view()),
    path('api/tech_reports/', views.TechReportList.as_view()),
    path('api/tech_reports/<int:pk>/', views.TechReportDetail.as_view()),
    path('api/supplements/', views.SupplementList.as_view()),
    path('api/supplements/<int:pk>/', views.SupplementDetail.as_view()),
]
