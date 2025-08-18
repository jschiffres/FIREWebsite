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
    #TO DO:
    # try centering vertically
    # fix scrollsby
    # POST RETIREMENT EXPENSE ADJUSTMENT
    # ASSETS - ADD NAME TOO
    # GAP YEARS YAY!, 
    # CHANGE SAVINGS/EXPENSES TO "N/A" DURING COASTFIRE YEARS  
    # ADJUSTMENTS IN EXPENSES (CHILD), 
    # LUMP SUM EXPENSES (HOUSE INCLUDE NAME OF EXPENSE ON TABLE),
    # LUMP SUM PAYMENTS (INCLUDE NAME ON TABLE) 
    # COASTFIRE, 
    # CHARTS, 
    # DOWNLOAD FIRETABLE, 
    # ADJUST FIRETABLE LAYOUT (FREEZE AND FORM/HEADERS)
    
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
            simulation.estimated_lumpsum_payment_amounts = request.POST.getlist('estimated_lumpsum_payment_amounts')
            simulation.estimated_lumpsum_payment_ages = request.POST.getlist('estimated_lumpsum_payment_ages')
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
        salaries, bonuses, other_income, lump_sum_payments = FIREObject.incomes()
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

        # Store all simulation data in a list of dictionaires
        simulation_data = FIREObject.simulation_data()

        # Once simulation data is finalized, update simulation within database with new final net worth number
        simulation.final_net_worth = (simulation_data[-1]['net_worth'])
        simulation.save()

        lump_sum_payments = zip(simulation.estimated_lumpsum_payment_ages, simulation.estimated_lumpsum_payment_amounts)

    # If simulation logic fails, return user to the new simulation screen with error message
    except Exception as e:
        print(e)
        #change to return redirect...?
        return render(request, 'FIRE/newsimulation.html', {'form': SimulationForm(), 'error': "Error generating simulation, please try again."})

    # If post reuqest only, return the partial HTML template 
    if request.method == "POST":
        if form_save_error:
            return render(request, 'FIRE/partials/firetable.html', {'simulation': simulation, "data": simulation_data, 'form' : form, 'ages': json.dumps(ages), 'net_worths': json.dumps(net_worths), 'lump_sum_payments': lump_sum_payments, 'error': "There was an error updating your simulation, please try again."})
        else:
           return render(request, 'FIRE/partials/firetable.html', {'simulation': simulation, "data": simulation_data, 'form' : form, 'ages': json.dumps(ages), 'net_worths': json.dumps(net_worths), 'lump_sum_payments': lump_sum_payments}) 
    # If get request, return the whole runsimulation HTML template
    else:
        return render(request, "FIRE/runsimulation.html", {"simulation": simulation, "data": simulation_data, 'form': EditSimulationForm(), 'ages': json.dumps(ages), 'net_worths': json.dumps(net_worths), 'lump_sum_payments': lump_sum_payments})

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