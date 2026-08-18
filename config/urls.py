
"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from core.views import custom_admin_login

urlpatterns = [
    path("management-portal-x99/login/", custom_admin_login, name='admin_login_custom'),
    path("management-portal-x99/", admin.site.urls),
    path("ledger/", include("ledger.urls")),
    path("expenses/", include("expenses.urls")),
    path("trips/", include("trips.urls")),
    path('login/', include('authentication.urls')),
    path('', include('core.urls')),
]