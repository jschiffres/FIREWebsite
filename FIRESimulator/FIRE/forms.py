from django.forms import ModelForm
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django import forms
from django.contrib.auth.models import User
from .models import Simulation

class SimulationForm(ModelForm):
	class Meta:
		model = Simulation
		fields = ['name',
		'current_age',
                'estimated_retirement_age',
                'current_yearly_salary',
                'estimated_salary_raise',
                'estimated_bonus',
                'current_yearly_other_income',
                'estimated_other_income_increase',
                'current_yearly_fixed_costs',
                'estimated_fixed_costs_inflation',
                'current_yearly_variable_costs',
                'estimated_variable_costs_inflation',
                'current_yearly_health_insurance_cost',
                'estimated_health_insurance_inflation',
                'estimated_tax_rate',
		'estimated_tax_rate_step',
		'hsa_enrollment_opt_out',
                # 'current_hsa_balance',
                # 'current_hsa_yearly_contribution_limit',
		# 'estimated_hsa_yearly_contribution_limit_step',
                # 'esitmated_hsa_yearly_return', 
                'current_401k_balance', 
                'current_401k_yearly_contribution_limit',
		'estimated_401k_yearly_contribution_limit_step',
                'current_401k_employer_contribution', 
                'esitmated_401k_yearly_return', 
                'current_ira_balance', 
                'current_ira_yearly_contribution_limit',
		'estimated_ira_yearly_contribution_limit_step', 
                'esitmated_ira_yearly_return', 
                'current_iba_balance', 
                'esitmated_iba_yearly_return']
		
class EditSimulationForm(ModelForm):
	class Meta:
		model = Simulation
		fields = ['estimated_retirement_age',
                'estimated_salary_raise',
                'estimated_bonus',
                'current_yearly_other_income',
                'estimated_other_income_increase',
                'estimated_fixed_costs_inflation',
                'estimated_variable_costs_inflation',
	        'estimated_health_insurance_inflation',
                'estimated_tax_rate',
                'estimated_tax_rate_step',
		'current_hsa_balance',
                'current_hsa_yearly_contribution_limit',
		'estimated_hsa_yearly_contribution_limit_step',
                'esitmated_hsa_yearly_return',
                'current_401k_balance',
                'current_401k_yearly_contribution_limit',
		'estimated_401k_yearly_contribution_limit_step',
	        'current_401k_employer_contribution',
                'esitmated_401k_yearly_return',
                'current_ira_balance',
                'current_ira_yearly_contribution_limit',
		'estimated_ira_yearly_contribution_limit_step',
		'esitmated_ira_yearly_return',
                'current_iba_balance',
                'esitmated_iba_yearly_return']
				
class CreateUserForm(UserCreationForm):
	email = forms.EmailField(required=True)
	class Meta:
		model = User
		fields = ['username', 'email', 'password1', 'password2']