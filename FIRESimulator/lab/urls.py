from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='lab_home'),
    path('<uuid:pk>/', views.scenario, name='lab_scenario'),
    path('<uuid:pk>/item/', views.save_item, name='lab_item_add'),
    path('<uuid:pk>/item/<int:item_pk>/', views.save_item, name='lab_item_edit'),
    path('<uuid:pk>/item/<int:item_pk>/delete/', views.delete_item, name='lab_item_delete'),
    path('<uuid:pk>/settings/', views.settings_view, name='lab_settings'),
    path('<uuid:pk>/allocate/', views.allocate, name='lab_allocate'),
]
