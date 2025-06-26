from django.urls import path

from . import views

app_name = "FIRE"
urlpatterns = [
    path("", views.index, name="index"),
    path("firesimulation/<int:simulation_id>", views.firesimulation, name="firesimulation"),
]