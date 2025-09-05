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
    #Authentication: signup, signup + save, logout, login
    path("signup/", views.signupuser, name="signupuser"),
    path("signup/<str:simulation_id>", views.signupsave, name="signupsave"),
    path('logout/', views.logoutuser, name='logoutuser'),
    path('login/', views.loginuser, name='loginuser'),

    #Simulation: new, run, edit, delete, user's
    path("", views.landing, name="landing"),
    path("new/", views.newsimulation, name="newsimulation"),
    path("firesimulation/<str:simulation_id>", views.runsimulation, name="runsimulation"),
    path("editsimulation/<str:simulation_id>", views.editsimulation, name="editsimulation"),
    path("downloadsimulation/<str:simulation_id>", views.downloadsimulation, name="downloadsimulation"),
    path("deletesimulation/<str:simulation_id>", views.deletesimulation, name="deletesimulation"),
    path("mysimulations/", views.usersimulations, name="usersimulations"),

    #HTMX:
    path('incomes/', views.create_incomes_section, name="create-incomes-section"),
    path('expenses/', views.create_expenses_section, name="create-expenses-section"),
    path('savings/', views.create_savings_section, name="create-savings-section"),
    path('newlumpsumincome/', views.create_lumpsum_income, name="create-lumpsum-income"),
    path('newlumpsumexpense/', views.create_lumpsum_expense, name="create-lumpsum-expense"),
    path('newasset/', views.create_asset, name="create-asset"),
    path('newfixedcostadjustment/', views.create_fixedcost_adjustment, name="create-fixedcost-adjustment"),
    path('newvariablecostadjustment/', views.create_variablecost_adjustment, name="create-variablecost-adjustment"),
    path('hsaoptin/', views.hsa_opt_in, name="hsa-opt-in"),
    path('coastfireoptin/', views.coastfire_opt_in, name="coastfire-opt-in"),

    #Admin
    path("admin/", admin.site.urls),
]
