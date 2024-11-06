from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('deconstructor/', views.deconstructor, name='deconstructor'),
    path('constructor/', views.constructor, name='constructor'),
    path('interactive_map/', views.interactive_map, name='interactive_map'),
    path('demonstrator/', views.demonstrator, name='demonstrator'),
]