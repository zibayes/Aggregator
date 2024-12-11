from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'items', views.ItemViewSet)

urlpatterns = [
    path('', views.index, name='index'),
    path('deconstructor/', views.deconstructor, name='deconstructor'),
    path('constructor/', views.constructor, name='constructor'),
    path('interactive_map/', views.interactive_map, name='interactive_map'),
    path('demonstrator/', views.demonstrator, name='demonstrator'),
    path('api/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]