from django.urls import path

from .views import vehicle_documents

app_name = 'vehicles'

urlpatterns = [
    path(
        '<int:vehicle_id>/documents/',
        vehicle_documents,
        name='documents',
    ),
]
