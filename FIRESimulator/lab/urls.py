from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='lab_home'),
    path('<uuid:pk>/', views.scenario, name='lab_scenario'),
    path('mine/', views.mine, name='lab_mine'),
    path('<uuid:pk>/rename/', views.rename, name='lab_rename'),
    path('<uuid:pk>/remove/', views.remove, name='lab_remove'),
    path('<uuid:pk>/export.csv', views.export_csv, name='lab_export_csv'),
    path('<uuid:pk>/export.pdf', views.export_pdf, name='lab_export_pdf'),
    path('<uuid:pk>/item/', views.save_item, name='lab_item_add'),
    path('<uuid:pk>/item/<int:item_pk>/', views.save_item, name='lab_item_edit'),
    path('<uuid:pk>/item/<int:item_pk>/delete/', views.delete_item, name='lab_item_delete'),
    path('<uuid:pk>/settings/', views.settings_view, name='lab_settings'),
    path('<uuid:pk>/allocate/', views.allocate, name='lab_allocate'),
]
