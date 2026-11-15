from django.forms import ModelForm
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django import forms
from django.contrib.auth.models import User
from .models import Feedback, Plan

class PlanForm(ModelForm):
	class Meta:
		model = Plan
		fields = ['plan_name' ,'current_age', 'retirement_age']

class CreateUserForm(UserCreationForm):
	email = forms.EmailField(required=True)
	class Meta:
		model = User
		fields = ['username', 'email', 'password1', 'password2']
		
class FeedbackForm(ModelForm):
	class Meta:
		model = Feedback
		fields = ['feedback',
			'category']
		
class EditPlanForm(ModelForm):
	class Meta:
		model = Plan
		fields = ['current_age', 'retirement_age']