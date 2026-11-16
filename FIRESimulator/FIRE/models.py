from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
import uuid

class Feedback(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    category = models.CharField(max_length=30, null=True)
    feedback = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    status = models.CharField(max_length=25, null=True)
    response = models.TextField(null=True)


class Plan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan_name = models.CharField(max_length=50)
    user = user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    current_age = models.PositiveSmallIntegerField(validators=[MaxValueValidator(100), MinValueValidator(1)])
    retirement_age = models.PositiveSmallIntegerField(validators=[MaxValueValidator(101), MinValueValidator(2)])
    incomes = models.JSONField(null=True)
    expenses = models.JSONField(null=True)
    savings = models.JSONField(null=True)
    final_net_worth = models.CharField(max_length=25, null=True)
