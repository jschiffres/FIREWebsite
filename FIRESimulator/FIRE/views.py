from django.db.models import F
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db import IntegrityError

from .models import Simulation
from .forms import SimulationForm, EditSimulationForm, CreateUserForm
from .functions import savesimulation, yearly_contribution_limits,start_end_balances, yearly_contributions, DFtoHTML

import math
import pandas as pd
from datetime import date
import json

# AUTHENTICATION: Signup
def signupuser(request):
    if request.method == "GET":
        return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm()})
    else:
        if request.POST.get('password1') == request.POST.get('password2'):
            try:
                if User.objects.filter(email=request.POST.get('email')).exists():
                    return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm(), 'error':'Email provided is already associated with an account.'})
                else:
                    user = User.objects.create_user(username=request.POST.get('username'), email=request.POST.get('email'), password=request.POST.get('password1')) 
                    user.save()
                    login(request, user)
                    messages.success(request, "User created successfully!")
                    return redirect('usersimulations')
            except IntegrityError: 
                return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm(), 'error':'Username has already been taken.'})
        else:
            return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm(), 'error':'Passwords did not match.'})

# AUTHENTICATION: Signup & Save Simulation            
def signupsave(request, simulation_id):
    if request.method == "GET":
        return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm()})
    else:
        if request.POST.get('password1') == request.POST.get('password2'):
            try:
                if User.objects.filter(email=request.POST.get('email')).exists():
                    return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm(), 'error':'Email provided is already associated with an account.'})
                else:
                    user = User.objects.create_user(username=request.POST.get('username'), email=request.POST.get('email'), password=request.POST.get('password1')) 
                    user.save()
                    simulation_id = request.path_info.split("/")[2]
                    simulation = get_object_or_404(Simulation, pk=simulation_id)
                    simulation.user = user
                    simulation.save()
                    login(request, user)
                    messages.success(request, "User created successfully!")
                    return redirect('usersimulations')
            except IntegrityError: 
                return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm(), 'error':'Username has already been taken.'})
        else:
            return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm(), 'error':'Passwords did not match.'})

# AUTHENTICATION: Login
def loginuser(request):
    if request.method == "GET":
        return render(request, 'FIRE/loginuser.html', {'form':AuthenticationForm()})
    else:
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user is None:
            return render(request, 'FIRE/loginuser.html', {'form':AuthenticationForm(), 'error': "Username and password did not match."})
        else:
            login(request, user)
            messages.success(request, "Logged in successfully!")
            return redirect('usersimulations')

# AUTHENTICATION: Logout     
@login_required
def logoutuser(request):
    if request.method == "POST":
        logout(request)
        messages.success(request, "Logged out successfully!")
        return redirect('newsimulation')

# SIMULATIONS: Display User's Simulations
def usersimulations(request):
    if request.user.is_authenticated:
        simulations = Simulation.objects.filter(user=request.user)
        return render(request, 'FIRE/usersimulations.html', {'simulations' : simulations})
    else:
        return redirect('loginuser')

# SIMULATIONS: Run Simulation / Live Edit
def runsimulation(request, simulation_id):
    #TO DO: ASSETS (house etc.), INCREASE IN EXPENSES (CHILD), LUMP SUM EXPENSES (HOUSE), COASTFIRE, CHARTS, DOWNLOAD FIRETABLE, ADJUST FIRETABLE LAYOUT (FREEZE AND FORM/HEADERS)

    # Retrieve simulation object from model
    simulation = get_object_or_404(Simulation, pk=simulation_id) 

    # Ensure simulation belongs to requesting user
    if request.user.is_authenticated and request.user != simulation.user:
        return render(request, 'FIRE/newsimulation.html', {'form': SimulationForm(), 'error': "Not authorized to view simulation."})

    # If post request, update the simulation in the database by saving the form
    if request.method == "POST":
        form_save_error = False
        form = EditSimulationForm(request.POST, instance=simulation)
        try:
            form.save()
        except Exception as e:
            form_save_error = True

    # If post or get request, exeucte simulation logic to generate data for firetable       
    try:
        # Input variableS - years_until_retirement & years_until_coast_fire
        years_until_retirement = simulation.estimated_retirement_age - simulation.current_age

        if simulation.estimated_coastfire_age != 0:
            years_until_coast_fire = simulation.estimated_coastfire_age - simulation.current_age
        else:
            years_until_coast_fire = simulation.estimated_retirement_age - simulation.current_age

        # Calculate yearly amounts for income, expenses and savings
        salaries = [math.floor(simulation.current_yearly_salary * ((1 + round(simulation.estimated_salary_raise/100,3)) ** year)) for year in range(0,years_until_retirement)]
        bonuses = [math.floor(salaries[year] * round(simulation.estimated_bonus/100,3)) for year in range(0,years_until_retirement)]
        other_income = [math.floor(simulation.current_yearly_other_income * ((1 + round(simulation.estimated_other_income_increase/100,3)) ** year)) for year in range(0,years_until_retirement)]
        lump_sum_payments_dict = dict(zip(simulation.estimated_lumpsum_payment_ages, list(map(int, simulation.estimated_lumpsum_payment_amounts))))
        lump_sum_payment_amounts = []
        for age in [str(simulation.current_age + year) for year in range(0,years_until_retirement)]:
            if age in lump_sum_payments_dict:
                lump_sum_payment_amounts.append(lump_sum_payments_dict[age])
            else:
                lump_sum_payment_amounts.append(0)
        fixed_costs = [math.floor(simulation.current_yearly_fixed_costs * ((1 + round(simulation.estimated_fixed_costs_inflation/100,3)) ** year)) for year in range(0,years_until_retirement)]
        cost_of_living = [math.floor(simulation.current_yearly_cost_of_living * ((1 + round(simulation.estimated_cost_of_living_inflation/100,3)) ** year)) for year in range(0,years_until_retirement)]
        health_insurance = [math.floor(simulation.current_yearly_health_insurance_cost * ((1 + round(simulation.estimated_health_insurance_inflation/100,3)) ** year)) for year in range(0,years_until_retirement)]
        taxes = [math.floor((salaries[year] + bonuses[year] + other_income[year] + lump_sum_payment_amounts[year]) * round(simulation.estimated_tax_rate/100,3)) for year in range(0,years_until_retirement)]
        savings = [math.floor(salaries[year] + bonuses[year] + other_income[year] + lump_sum_payment_amounts[year] - fixed_costs[year] - cost_of_living[year] - health_insurance[year] - taxes[year]) if year < years_until_coast_fire else 0 for year in range(0,years_until_retirement)]

        # Caluclate yearly contribution limits for retirement accounts based on current limits, step and years until retirement
        hsa_cont_limits = yearly_contribution_limits(simulation.current_hsa_yearly_contribution_limit,simulation.estimated_hsa_yearly_contribution_limit_step,years_until_retirement)
        ira_cont_limits = yearly_contribution_limits(simulation.current_ira_yearly_contribution_limit,simulation.estimated_ira_yearly_contribution_limit_step,years_until_retirement)
        retirement_cont_limits = yearly_contribution_limits(simulation.current_401k_yearly_contribution_limit,simulation.estimated_401k_yearly_contribution_limit_step,years_until_retirement)

        # Calculate actual contributions based on yearly savings and contribution limit amounts
        hsa_contributions,retirement_contributions,employer_retirement_contributions,ira_contributions,iba_contributions = yearly_contributions(years_until_retirement,savings,salaries,hsa_cont_limits,retirement_cont_limits,ira_cont_limits,simulation.current_401k_employer_contribution,simulation.hsa_enrollment_opt_out)

        # Calculate investment account start and end balances based on current balances, contributions and estimated returns
        ira_start,ira_end = start_end_balances(simulation.current_ira_balance,years_until_retirement,ira_contributions,simulation.esitmated_ira_yearly_return)
        retirement_start,retirement_end = start_end_balances(simulation.current_401k_balance,years_until_retirement,retirement_contributions,simulation.esitmated_401k_yearly_return,employer_retirement_contributions)
        hsa_start,hsa_end = start_end_balances(simulation.current_hsa_balance,years_until_retirement,hsa_contributions,simulation.esitmated_hsa_yearly_return)
        iba_start,iba_end = start_end_balances(simulation.current_iba_balance,years_until_retirement,iba_contributions,simulation.esitmated_iba_yearly_return)

        # Calculate total asset values
        assets = []
        if simulation.current_asset_values:
            for idx, asset_value in enumerate(simulation.current_asset_values):
                asset_value_list = [math.floor(int(asset_value) * ((1 + round(int(simulation.estimated_asset_value_growths[idx])/100,3)) ** year)) for year in range(0,years_until_retirement)]
                assets.append(asset_value_list)
            assets = [sum(asset) for asset in zip(*assets)]
        else:
            assets = [0 for year in range(0,years_until_retirement)]
        
        # Calculate net worth based on ending balances of each investment account
        net_worth = [math.floor(hsa_end[year] + retirement_end[year] + ira_end[year] + iba_end[year] + assets[year]) for year in range(0,years_until_retirement)]

        # Store all simulation data in a list of dictionaires
        data = []
        for year in range(0,years_until_retirement):
            year_dict = {}
            year_dict['year'] = year+date.today().year
            year_dict['age'] = year+simulation.current_age
            year_dict['salary'] = '${:,}'.format(salaries[year])
            year_dict['bonus'] = '${:,}'.format(bonuses[year])
            year_dict['other_income'] = '${:,}'.format(other_income[year])
            year_dict['lump_sum_payment_amounts'] = '${:,}'.format(lump_sum_payment_amounts[year])
            year_dict['fixed_costs'] = '${:,}'.format(fixed_costs[year])
            year_dict['cost_of_living'] = '${:,}'.format(cost_of_living[year])
            year_dict['health_insurance'] = '${:,}'.format(health_insurance[year])
            year_dict['taxes'] = '${:,}'.format(taxes[year])
            year_dict['savings'] = '${:,}'.format(savings[year])
            year_dict['hsa_start'] = '${:,}'.format(hsa_start[year])
            year_dict['hsa_cont_limits'] = '${:,}'.format(hsa_cont_limits[year])
            year_dict['hsa_contributions'] = '${:,}'.format(hsa_contributions[year])
            year_dict['hsa_end'] = '${:,}'.format(hsa_end[year])
            year_dict['retirement_start'] = '${:,}'.format(retirement_start[year])
            year_dict['retirement_cont_limits'] = '${:,}'.format(retirement_cont_limits[year])
            year_dict['retirement_contributions'] = '${:,}'.format(retirement_contributions[year])
            year_dict['employer_retirement_contributions'] = '${:,}'.format(employer_retirement_contributions[year])
            year_dict['retirement_end'] = '${:,}'.format(retirement_end[year])
            year_dict['ira_start'] = '${:,}'.format(ira_start[year])
            year_dict['ira_cont_limits'] = '${:,}'.format(ira_cont_limits[year])
            year_dict['ira_contributions'] = '${:,}'.format(ira_contributions[year])
            year_dict['ira_end'] = '${:,}'.format(ira_end[year])
            year_dict['iba_start'] = '${:,}'.format(iba_start[year])
            year_dict['iba_contributions'] = '${:,}'.format(iba_contributions[year])
            year_dict['iba_end'] = '${:,}'.format(iba_end[year])
            year_dict['assets_value'] = '${:,}'.format(assets[year])
            year_dict['net_worth'] = '${:,}'.format(net_worth[year])
            year_dict['magic_number'] = '${:,}'.format((cost_of_living[year] + fixed_costs[year] + health_insurance[year]) * 25)
            year_dict['drawdown'] = str(round(((cost_of_living[year] + fixed_costs[year] + health_insurance[year]) / net_worth[year]) * 100,2)) + "%"
            data.append(year_dict)

        # Once simulation data is finalized, update simulation within database with new final net worth number
        simulation.final_net_worth = (data[-1]['net_worth'])
        simulation.save()

    # If simulation logic fails, return user to the new simulation screen with error message
    except Exception as e:
        return render(request, 'FIRE/newsimulation.html', {'form': SimulationForm(), 'error': "Error generating simulation, please try again."})

    # If post reuqest only, return the partial HTML template 
    if request.method == "POST":
        if form_save_error:
            return render(request, 'FIRE/partials/firetable.html', {'simulation': simulation, "data": data, 'form' : form, 'ages': json.dumps([(simulation.current_age + year) for year in range(0,years_until_retirement)]), 'net_worth': json.dumps(net_worth), 'error': "There was an error updating your simulation, please try again."})
        else:
           return render(request, 'FIRE/partials/firetable.html', {'simulation': simulation, "data": data, 'form' : form, 'ages': json.dumps([(simulation.current_age + year) for year in range(0,years_until_retirement)]), 'net_worth': json.dumps(net_worth)}) 
    # If get request, return the whole runsimulation HTML template
    else:
        return render(request, "FIRE/runsimulation.html", {"simulation": simulation, "data": data, 'form': EditSimulationForm(), 'ages': json.dumps([(simulation.current_age + year) for year in range(0,years_until_retirement)]), 'net_worth': json.dumps(net_worth)})

# SIMULATIONS: Create New
def newsimulation(request):
    if request.method == "GET":
        return render(request, 'FIRE/newsimulation.html', {'form': SimulationForm()})
    else:
        try:
            form = SimulationForm(request.POST)
            newsim = savesimulation(form, request)
            if type(newsim) == str:
                return render(request, 'FIRE/newsimulation.html', {'form': form, 'error': newsim})
            id = newsim.id
            return redirect(f'/firesimulation/{id}')
        except Exception as e:
            print(e)
            return render(request, 'FIRE/newsimulation.html', {'form': form, 'error': "Error saving simulation, please try again."})

#SIMULATIONS: Edit Simulation  
@login_required
def editsimulation(request, simulation_id):
    simulation = get_object_or_404(Simulation, pk=simulation_id)
    if request.method == "GET":
        form = SimulationForm(instance=simulation)
        return render(request, 'FIRE/editsimulation.html', {'simulation': simulation, 'form' : form})
    else:
        try:   
            form = SimulationForm(request.POST, instance=simulation)
            newsim = savesimulation(form, request)
            if type(newsim) == str:
                return render(request, 'FIRE/editsimulation.html', {'simulation': simulation, 'form': form, 'error': newsim})
            id = newsim.id
            return redirect(f'/firesimulation/{id}')
        except Exception as e:
            return render(request, 'FIRE/newsimulation.html', {'simulation': simulation, 'form': form, 'error': "Error creating simulation, please try again"})

#SIMULATIONS: Delete Simulation        
@login_required
def deletesimulation(request, simulation_id):
    simulation = get_object_or_404(Simulation, pk=simulation_id, user=request.user) 
    if request.method == "POST":
        simulation.delete()
        messages.success(request, f"{simulation.name} deleted successfully!")
        return redirect('usersimulations')

# HTMX: Add New Lumpsum Input
def create_lumpsum(request):
    return render(request, 'FIRE/partials/lumpsum.html')

# HTMX: Add New Asset Input
def create_asset(request):
    return render(request, 'FIRE/partials/asset.html')

# HTMX: Add New Asset Input
def create_fixedcost_adjustment(request):
    return render(request, 'FIRE/partials/fixedcostadjustment.html')

# HTMX: Include HSA input fields
def hsa_opt_in(request):
    return render(request, 'FIRE/partials/hsa.html')

# HTMX: Include Coast FIRE input fields
def coastfire_opt_in(request):
    return render(request, 'FIRE/partials/coastfire.html')
    
# # Create dictionary for dataframe containing the yealry amounts, contribution limits, contributions and start/end balances 
# simulation_data = {'AGE': [year+simulation.current_age for year in range(0,years_until_retirement)],
#     'SALARY': salaries, 
#     'BONUS': bonuses, 
#     'OTHER INCOME': other_income, 
#     'BILLS': fixed_costs, 
#     'COST OF LIVING': cost_of_living,
#     'TAXES': taxes,
#     'HEALTH INSURANCE': health_insurance,
#     'SAVINGS': savings, 
#     'HSA START': hsa_start, 
#     'HSA CONTRIBUTION LIMIT': hsa_cont_limits, 
#     'HSA CONTRIBUTIONS': hsa_contributions, 
#     'HSA END': hsa_end, 
#     '401K START': retirement_start, 
#     '401K CONTRIBUTION LIMIT': retirement_cont_limits,
#     '401K CONTRIBUTIONS': retirement_contributions, 
#     '401K END': retirement_end,
#     'IRA START': ira_start, 
#     'IRA CONTRIBUTION LIMIT': ira_cont_limits,
#     'IRA CONTRIBUTIONS': ira_contributions, 
#     'IRA END': ira_end, 
#     'INDIVIDUAL START': iba_start, 
#     'INDIVIDUAL CONTRIBUTIONS': iba_contributions,  
#     'INDIVIDUAL END': iba_end, 
#     'NET WORTH': net_worth}

# # Create and return cleaned up html dataframe to /firesimulation template
# simulation_df = pd.DataFrame(simulation_data)
# for column in list(simulation_df.columns):
#    if column != "AGE":
#        simulation_df[column] = simulation_df[column].apply(lambda x : "${:,}".format(x)) 
# simulation_df = DFtoHTML(simulation_df)