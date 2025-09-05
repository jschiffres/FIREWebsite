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
from .functions import savesimulation, DFtoHTML, FIRE

import math
import pandas as pd
from datetime import date
import json

def landing(request):
    return render(request, 'FIRE/landing.html')

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
        return redirect('landing')

# SIMULATIONS: Display User's Simulations
def usersimulations(request):
    if request.user.is_authenticated:
        simulations = Simulation.objects.filter(user=request.user)
        return render(request, 'FIRE/usersimulations.html', {'simulations' : simulations})
    else:
        messages.warning(request, "You must be logged in to view your simulations.")
        return redirect('loginuser')

# SIMULATIONS: Run Simulation / Live Edit
def runsimulation(request, simulation_id):
    #TO DO:
    # update navbar
    # move retirement age to same row as coastfire age 
    # WHEN SOMEONE REMOVES ALL ASSETS/LUMPSUMS, IT BREAKS
    # POST RETIREMENT EXPENSE ADJUSTMENT
    # GAP YEARS YAY!, 
    # CHANGE SAVINGS/EXPENSES TO "N/A" DURING COASTFIRE YEARS   
    
    # Retrieve simulation object from Django model
    simulation = get_object_or_404(Simulation, pk=simulation_id)

    # Ensure simulation belongs to requesting user
    if simulation.user and request.user != simulation.user:
        return render(request, 'FIRE/newsimulation.html', {'form': SimulationForm(), 'error': "Not authorized to view simulation."})

    # If post request, update the simulation in the database by saving the form
    if request.method == "POST":
        form_save_error = False
        form = EditSimulationForm(request.POST, instance=simulation)
        try:
            form.save()
            print("here")
            print(request.POST.get("tableDetailedViewSwitch"))
            print("her2")
            if request.POST.get("tableDetailedViewSwitch"):
                toggle = True
            else:
                toggle = False
            if request.POST.get('estimated_coastfire_age'):
                if int(request.POST.get('estimated_coastfire_age')) >= simulation.estimated_retirement_age or int(request.POST.get('estimated_coastfire_age')) <= simulation.current_age:
                    return "Coast FIRE age must be less than estimated retirement age and greater than your current age."
                else:
                    simulation.estimated_coastfire_age = int(request.POST.get('estimated_coastfire_age'))
            else:
                simulation.estimated_coastfire_age = None
            simulation.lumpsum_income_names = request.POST.getlist('lumpsum_income_names')
            simulation.estimated_lumpsum_income_amounts = request.POST.getlist('estimated_lumpsum_income_amounts')
            simulation.estimated_lumpsum_income_ages = request.POST.getlist('estimated_lumpsum_income_ages')
            simulation.asset_names = request.POST.getlist('asset_names')
            simulation.current_asset_values = request.POST.getlist('current_asset_values')
            simulation.estimated_asset_value_growths = request.POST.getlist('estimated_asset_value_growths')            
        except Exception as e:
            print(e)
            form_save_error = True

    # If post or get request, exeucte simulation logic to generate data for firetable       
    try:
        # Initialize FIRE object
        FIREObject = FIRE(simulation)

        # Generate ages and years
        ages, years = FIREObject.personal_infos()

        # Calculate yearly amounts for income, expenses and savings
        total_income, salaries, bonuses, other_income, lump_sum_incomes = FIREObject.incomes()
        total_expenses, fixed_costs, variable_costs, health_insurance, lump_sum_expenses, taxes = FIREObject.expenses()
        savings = FIREObject.savings()

        # Caluclate yearly contribution limits for retirement accounts based on current limits, step and years until retirement
        hsa_cont_limits, ira_cont_limits, retirement_cont_limits = FIREObject.yearly_contribution_limits()

        # Calculate actual contributions based on yearly savings and contribution limit amounts
        hsa_contributions,retirement_contributions,employer_retirement_contributions,ira_contributions,iba_contributions = FIREObject.yearly_contributions()

        # Calculate investment account start and end balances based on current balances, contributions and estimated returns
        hsa_start, hsa_end, retirement_start, retirement_end, ira_start, ira_end, iba_start, iba_end = FIREObject.start_end_balances()

        # Calculate total asset values
        assets = FIREObject.assets()
    
        # Calculate net worth based on ending balances of each investment account
        net_worths, magic_numbers, drawdowns = FIREObject.fire_indicators()



        # Store all simulation data in a list of dictionaires
        simulation_data = FIREObject.simulation_data()

        # Once simulation data is finalized, update simulation within database with new final net worth number
        simulation.final_net_worth = (simulation_data[-1]['net_worth'])
        simulation.save()

        lump_sum_incomes = zip(simulation.lumpsum_income_names ,simulation.estimated_lumpsum_income_ages, simulation.estimated_lumpsum_income_amounts)
        assets = zip(simulation.asset_names ,simulation.current_asset_values, simulation.estimated_asset_value_growths)        

    # If simulation logic fails, return user to the new simulation screen with error message
    except Exception as e:
        print(e)
        #change to return redirect...?
        return render(request, 'FIRE/newsimulation.html', {'form': SimulationForm(), 'error': "Error generating simulation, please try again."})

    # If post reuqest only, return the partial HTML template 
    if request.method == "POST":
        if form_save_error:
            return render(request, 'FIRE/partials/firetable.html', {'toggle': toggle, 'simulation': simulation, "data": simulation_data, 'form' : form, 'ages': json.dumps(ages), 'net_worths': json.dumps(net_worths), 'magic_numbers': json.dumps(magic_numbers), 'total_income': json.dumps(total_income), 'total_expenses': json.dumps(total_expenses), 'savings': json.dumps(savings), 'lump_sum_incomes': lump_sum_incomes, 'assets': assets, 'error': "There was an error updating your simulation, please try again."})
        else:
           messages.success(request, f"{simulation.name} updated successfully!")
           return render(request, 'FIRE/partials/firetable.html', {'toggle': toggle, 'simulation': simulation, "data": simulation_data, 'form' : form, 'ages': json.dumps(ages), 'net_worths': json.dumps(net_worths), 'magic_numbers': json.dumps(magic_numbers), 'total_income': json.dumps(total_income), 'total_expenses': json.dumps(total_expenses), 'savings': json.dumps(savings), 'lump_sum_incomes': lump_sum_incomes, 'assets': assets}) 
    # If get request, return the whole runsimulation HTML template
    else:
        return render(request, "FIRE/runsimulation.html", {'toggle': True, "simulation": simulation, "data": simulation_data, 'form': EditSimulationForm(), 'ages': json.dumps(ages), 'net_worths': json.dumps(net_worths), 'magic_numbers': json.dumps(magic_numbers), 'total_income': json.dumps(total_income), 'total_expenses': json.dumps(total_expenses), 'savings': json.dumps(savings), 'lump_sum_incomes': lump_sum_incomes, 'assets': assets})

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

# HTMX: Add Section
def create_incomes_section(request):
    return render(request, 'FIRE/partials/section_incomes.html')

# HTMX: Add Section
def create_expenses_section(request):
    return render(request, 'FIRE/partials/section_expenses.html')

# HTMX: Add Section
def create_savings_section(request):
    return render(request, 'FIRE/partials/section_savings.html')

# HTMX: Add New Lumpsum Input
def create_lumpsum_income(request):
    max_age = int(request.GET.get("max_age")) - 1
    min_age = int(request.GET.get("min_age"))
    return render(request, 'FIRE/partials/lumpsumincome.html', {'max_age' : max_age, 'min_age' : min_age})

# HTMX: Add New Lumpsum Input
def create_lumpsum_expense(request):
    max_age = int(request.GET.get("max_age")) - 1
    min_age = int(request.GET.get("min_age"))
    return render(request, 'FIRE/partials/lumpsumexpense.html', {'max_age' : max_age, 'min_age' : min_age})

# HTMX: Add New Asset Input
def create_asset(request):
    return render(request, 'FIRE/partials/asset.html')

# HTMX: Add New Expense Adjustment Input
def create_fixedcost_adjustment(request):
    max_age = int(request.GET.get("max_age")) - 1
    min_age = int(request.GET.get("min_age")) + 1
    return render(request, 'FIRE/partials/adjustment_fixedcosts.html', {'max_age' : max_age, 'min_age' : min_age})

# HTMX: Add New Expense Adjustment Input
def create_variablecost_adjustment(request):
    max_age = int(request.GET.get("max_age")) - 1
    min_age = int(request.GET.get("min_age")) + 1
    return render(request, 'FIRE/partials/adjustment_variablecosts.html', {'max_age' : max_age, 'min_age' : min_age})

# HTMX: Include HSA input fields
def hsa_opt_in(request):
    return render(request, 'FIRE/partials/opt_in_hsa.html')

# HTMX: Include Coast FIRE input fields
def coastfire_opt_in(request):
    max_age = int(request.GET.get("max_age")) - 1
    min_age = int(request.GET.get("min_age")) + 1
    print(min_age)
    return render(request, 'FIRE/partials/opt_in_coastfire.html', {'max_age' : max_age, 'min_age' : min_age})

import csv
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

@login_required
def downloadsimulation(request, simulation_id):
    # Fetch your simulation and data as you do in your template
    simulation = get_object_or_404(Simulation, id=simulation_id)

    try:
        # Initialize FIRE object
        FIREObject = FIRE(simulation)

        # Generate ages and years
        ages, years = FIREObject.personal_infos()

        # Calculate yearly amounts for income, expenses and savings
        salaries, bonuses, other_income, lump_sum_incomes = FIREObject.incomes()
        fixed_costs, variable_costs, health_insurance, lump_sum_expenses, taxes = FIREObject.expenses()
        savings = FIREObject.savings()

        # Caluclate yearly contribution limits for retirement accounts based on current limits, step and years until retirement
        hsa_cont_limits, ira_cont_limits, retirement_cont_limits = FIREObject.yearly_contribution_limits()

        # Calculate actual contributions based on yearly savings and contribution limit amounts
        hsa_contributions,retirement_contributions,employer_retirement_contributions,ira_contributions,iba_contributions = FIREObject.yearly_contributions()

        # Calculate investment account start and end balances based on current balances, contributions and estimated returns
        hsa_start, hsa_end, retirement_start, retirement_end, ira_start, ira_end, iba_start, iba_end = FIREObject.start_end_balances()

        # Calculate total asset values
        assets = FIREObject.assets()
    
        # Calculate net worth based on ending balances of each investment account
        net_worths, magic_numbers, drawdowns = FIREObject.fire_indicators()

    except Exception as e:
        print(e)
        return redirect('runsimulation', simulation_id=simulation_id)


    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="simulation_{simulation_id}.csv"'

    writer = csv.writer(response)
    # Write header row
    writer.writerow([
        'AGE', 'YEAR', 
        'SALARY', 'BONUS', 'OTHER INCOME', 'LUMP SUM INCOME',
        'FIXED COST', 'VARIABLE COST', 'HEALTH INSURANCE', 'LUMP SUM EXPENSE',
        'TAX', 'SAVING', 
        'HSA START', 'HSA CONT LIMIT', 'HSA CONTRIBUTION', 'HSA END',
        'RETIREMENT START', 'RETIREMENT CONT LIMIT', 'RETIREMENT CONTRIBUTION','EMPLOYER RETIREMENT CONTRIBUTION', 'RETIREMENT END', 
        'IRA START', 'IRA CONT LIMIT', 'IRA CONTRIBUTION', 'IRA END', 
        'IBA START', 'IBA CONTRIBUTION', 'IBA END', 
        'ASSET VALUE', 'NET WORTH', 'MAGIC NUMBER', 'DRAWDOWN'
    ])
    # Write data rows
    for year in range(len(ages)):
        writer.writerow([
            ages[year], years[year],
            salaries[year], bonuses[year], other_income[year], lump_sum_incomes[year],
            fixed_costs[year], variable_costs[year], health_insurance[year], lump_sum_expenses[year],
            taxes[year], savings[year],
            hsa_start[year], hsa_cont_limits[year], hsa_contributions[year], hsa_end[year],
            retirement_start[year], retirement_cont_limits[year], retirement_contributions[year], employer_retirement_contributions[year], retirement_end[year],
            ira_start[year], ira_cont_limits[year], ira_contributions[year], ira_end[year],
            iba_start[year], iba_contributions[year], iba_end[year],
            assets[year], net_worths[year], magic_numbers[year], drawdowns[year]
        ])
    return response
    
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