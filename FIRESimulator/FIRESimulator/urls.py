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
from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView
from django.contrib.staticfiles.storage import staticfiles_storage
from FIRE import views
from FIRE.ratelimit import ratelimit
from FIRE.forms import AnyUserPasswordResetForm

handler404 = "FIRE.views.not_found"
handler500 = "FIRE.views.server_error"

urlpatterns = [
    #PASSWORD: Reset, Change
    path("password-reset/", ratelimit('pwreset', 5, 3600)(auth_views.PasswordResetView.as_view(
        form_class=AnyUserPasswordResetForm,
        template_name="FIRE/account/password_reset_form.html",
        email_template_name="FIRE/account/password_reset_email.txt",
        html_email_template_name="emails/password_reset.html",
        subject_template_name="FIRE/account/password_reset_subject.txt",
        success_url=reverse_lazy("password_reset_done"))), name="password_reset"),
    path("password-reset/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="FIRE/account/password_reset_done.html"), name="password_reset_done"),
    path("password-reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="FIRE/account/password_reset_confirm.html",
        success_url=reverse_lazy("password_reset_complete")), name="password_reset_confirm"),
    path("password-reset/complete/", auth_views.PasswordResetCompleteView.as_view(
        template_name="FIRE/account/password_reset_complete.html"), name="password_reset_complete"),
    path("password-change/", auth_views.PasswordChangeView.as_view(
        template_name="FIRE/account/password_change_form.html",
        success_url=reverse_lazy("password_change_done")), name="password_change"),
    path("password-change/done/", auth_views.PasswordChangeDoneView.as_view(
        template_name="FIRE/account/password_change_done.html"), name="password_change_done"),

    #USER: Sign-up, Sign-up Save, Logout, Login, Plans, Feedback
    path("signup/check-email/", views.check_email, name="check_email"),
    path("signup/", views.signupuser, name="signupuser"),
    path("signup/<str:plan_id>", views.signupsave, name="signupsave"),
    path('logout/', views.logoutuser, name='logoutuser'),
    path('login/', views.loginuser, name='loginuser'),
    path("verify-email/<str:token>/", views.verify_email, name="verify_email"),
    path("verify-email/", views.resend_verification, name="resend_verification"),
    path("auth/google/", views.google_login, name="google_login"),
    path("auth/google/callback/", views.google_callback, name="google_callback"),
    path("myplans/", views.userplans, name="userplans"),
    path("account/", views.myaccount, name="myaccount"),
    path("privacy/", views.privacy, name="privacy"),
    path("terms/", views.terms, name="terms"),
    path("faq/", views.faq, name="faq"),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path("favicon.ico", RedirectView.as_view(url=staticfiles_storage.url("favicon.svg"), permanent=True)),
    path("sitemap.xml", views.sitemap_xml, name="sitemap_xml"),
    path("billing/checkout/", views.start_checkout, name="start_checkout"),
    path("billing/portal/", views.billing_portal, name="billing_portal"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    path('feedback/', views.feedback, name='feedback'),

    #PLAN: New, Run, Download, Copy, Delete
    path("new/", views.newplan, name="newplan"),
    path("new/template/", views.templateplan, name="templateplan"),
    path("plan/<str:plan_id>", views.runplan, name="runplan"),
    path("downloadplan/<str:plan_id>", views.downloadplan, name="downloadplan"),
    path("downloadpdf/<str:plan_id>", views.downloadpdf, name="downloadpdf"),
    path("copyplan/<str:plan_id>", views.copyplan, name="copyplan"),
    path("compare/", views.compareplans, name="compareplans"),
    path("plan/<str:plan_id>/whatif/", views.whatif, name="whatif"),
    path("plan/<str:plan_id>/withdrawal/", views.withdrawal, name="withdrawal"),
    path("about/", views.about, name="about"),
    path("renameplan/<str:plan_id>", views.renameplan, name="renameplan"),
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
]
