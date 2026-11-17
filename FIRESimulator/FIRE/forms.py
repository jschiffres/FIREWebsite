from django.forms import ModelForm
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordResetForm
from django import forms
from django.contrib.auth.models import User
from .models import Feedback, Plan


class AnyUserPasswordResetForm(PasswordResetForm):
    """Also emails Google-only accounts (unusable password) so they can set a first password."""

    def get_users(self, email):
        return (u for u in User.objects.filter(email__iexact=email, is_active=True))


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
	CATEGORIES = ['Bug Report', 'Feature Request', 'Content Accuracy', 'Performance Issue', 'Account Issue', 'Other']
	category = forms.ChoiceField(choices=[('', 'Select a category')] + [(c, c) for c in CATEGORIES])
	feedback = forms.CharField(max_length=5000, widget=forms.Textarea)
	reply_email = forms.EmailField(required=False)
	website = forms.CharField(required=False)  # honeypot, real users leave it empty

	class Meta:
		model = Feedback
		fields = ['feedback',
			'category']
		
class EditPlanForm(ModelForm):
	class Meta:
		model = Plan
		fields = ['current_age', 'retirement_age']