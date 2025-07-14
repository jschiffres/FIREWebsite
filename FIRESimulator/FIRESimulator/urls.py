"""
URL configuration for FIRESimulator project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from FIRE import views

urlpatterns = [
    path("signup/", views.signupuser, name="signupuser"),
    path("signup/<str:simulation_id>", views.signupsave, name="signupsave"),
    path('logout/', views.logoutuser, name='logoutuser'),
    path('login/', views.loginuser, name='loginuser'),
    path("firesimulation/<str:simulation_id>", views.firesimulation, name="firesimulation"),
    path("editsimulation/<str:simulation_id>", views.editsimulation, name="editsimulation"),
    path("", views.newsimulation, name="newsimulation"),
    path("mysimulations/", views.usersimulations, name="usersimulations"),
    path("admin/", admin.site.urls),
]
