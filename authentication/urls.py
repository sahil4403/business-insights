from django.urls import path

from .views import (
    UserLoginView,
    UserLogoutView,
)


app_name = 'authentication'


urlpatterns = [

    path(
        '',
        UserLoginView.as_view(),
        name='login',
    ),

    path(
        'logout/',
        UserLogoutView.as_view(),
        name='logout',
    ),

]