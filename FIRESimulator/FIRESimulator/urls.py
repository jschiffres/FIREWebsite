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
    #USER: Sign-up, Sign-up Save, Logout, Login, Plans, Feedback
    path("signup/", views.signupuser, name="signupuser"),
    path("signup/<str:plan_id>", views.signupsave, name="signupsave"),
    path('logout/', views.logoutuser, name='logoutuser'),
    path('login/', views.loginuser, name='loginuser'),
    path("myplans/", views.userplans, name="userplans"),
    path('feedback/', views.feedback, name='feedback'),

    #PLAN: New, Run, Edit, Download, Copy, Delete
    path("new/", views.newplan, name="newplan"),
    path("plan/<str:plan_id>", views.runplan, name="runplan"),
    path("editplan/<str:plan_id>", views.editplan, name="editplan"),
    path("downloadplan/<str:plan_id>", views.downloadplan, name="downloadplan"),
    path("copyplan/<str:plan_id>", views.copyplan, name="copyplan"),
    path("deleteplan/<str:plan_id>", views.deleteplan, name="deleteplan"),

    #HTMX: Section, Entry, Fields, Tables
    path('newincome/', views.create_income, name="create-income"),
    path('incomefields/', views.income_fields, name="income-fields"),
    path('incometable/', views.income_table, name="income-table"),
    path('incomes/', views.create_incomes_section, name="create-incomes-section"),
    path('newexpense/', views.create_expense, name="create-expense"),
    path('expensefields/', views.expense_fields, name="expense-fields"),
    path('expensetable/', views.expense_table, name="expense-table"),
    path('expenses/', views.create_expenses_section, name="create-expenses-section"),
    path('newsaving/', views.create_saving, name="create-saving"),
    path('savingfields/', views.saving_fields, name="saving-fields"),
    path('savingsmethod/', views.savings_method, name="savings-method"),
    path('savings/', views.create_savings_section, name="create-savings-section"),

    #Admin, Landing
    path("admin/", admin.site.urls),
    path("", views.landing, name="landing"),

    # To Delete
    path("firesimulation/<str:simulation_id>", views.runsimulation, name="runsimulation"),
    path('newlumpsumincome/', views.create_lumpsum_income, name="create-lumpsum-income"),
    path('newlumpsumexpense/', views.create_lumpsum_expense, name="create-lumpsum-expense"),
    path('newasset/', views.create_asset, name="create-asset"),
    path('newfixedcostadjustment/', views.create_fixedcost_adjustment, name="create-fixedcost-adjustment"),
    path('newvariablecostadjustment/', views.create_variablecost_adjustment, name="create-variablecost-adjustment"),
    path('hsaoptin/', views.hsa_opt_in, name="hsa-opt-in"),
    path('coastfireoptin/', views.coastfire_opt_in, name="coastfire-opt-in"),
]
