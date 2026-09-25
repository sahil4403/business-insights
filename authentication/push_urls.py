from django.urls import path

from . import views

app_name = 'push'

urlpatterns = [
    path('vapid-key/', views.push_vapid_key, name='vapid_key'),
    path('subscribe/', views.push_subscribe, name='subscribe'),
    path('test/', views.push_test, name='test'),
]
