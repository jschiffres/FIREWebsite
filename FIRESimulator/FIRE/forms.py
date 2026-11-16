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
	"""Email + password signup; the internal username is generated from the email."""
	email = forms.EmailField(required=True)
	class Meta:
		model = User
		fields = ['email', 'password1', 'password2']

	def save(self, commit=True):
		from .auth_flows import unique_username
		user = super().save(commit=False)
		user.email = self.cleaned_data['email']
		user.username = unique_username(user.email)
		if commit:
			user.save()
		return user
		
class FeedbackForm(ModelForm):
	class Meta:
		model = Feedback
		fields = ['feedback',
			'category']
		
class EditPlanForm(ModelForm):
	class Meta:
		model = Plan
		fields = ['current_age', 'retirement_age']