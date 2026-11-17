from django.contrib import admin
from .models import Plan, Feedback, Profile

admin.site.register(Profile)

admin.site.register(Plan)
admin.site.register(Feedback)
