from django.contrib import admin
from .models import Simulation, Plan, Feedback

admin.site.register(Simulation)
admin.site.register(Plan)
admin.site.register(Feedback)
