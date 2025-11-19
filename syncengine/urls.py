"""
URL configuration for syncengine app
"""
from django.urls import path
from . import views

app_name = 'syncengine'

urlpatterns = [
    path('webhook/cloud', views.webhook_cloud, name='webhook_cloud'),
    path('webhook/local', views.webhook_local, name='webhook_local'),
    path('health', views.health, name='health'),
    path('status', views.status, name='status'),
]
