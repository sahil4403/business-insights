from django.urls import path

from .views import all_vehicle_documents, vehicle_documents

app_name = 'vehicles'

urlpatterns = [
    path(
        'documents/',
        all_vehicle_documents,
        name='all_documents',
    ),

    path(
        '<int:vehicle_id>/documents/',
        vehicle_documents,
        name='documents',
    ),
]
