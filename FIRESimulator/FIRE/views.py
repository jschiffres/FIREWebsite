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
from .functions import savesimulation, FIRE

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
        # Run Simulation:
            # test all data entry possibilities/combos
            # test sim save and generate fail redirect/message
        # Logic:
            # POST RETIREMENT EXPENSE ADJUSTMENT
            # GAP YEARS YAY!, 
        # Edit Simulation:
            # update template
        # Account view
            # add logic to delete acocunt/ change username / password
            # forget password logic
        # Questionnaire:
            # add language for accordians
            # add better transitions and a progress bar
        # Landing:
            # Make perfect

    
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
            updatedsim = savesimulation(form, request)
            if type(updatedsim) == str:
                form_save_error = True
            if request.POST.get("tableDetailedViewSwitch"):
                toggle = True
            else:
                toggle = False         
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

        # Create zipped lists of lump sums, adjustments and assets for use in template
        lump_sum_income, lump_sum_expense_zip, variable_cost_adjustments, fixed_cost_adjustments, assets = FIREObject.zip_objects()

        financial_independence_age = FIREObject.financial_independence_age()

        # Once simulation data is finalized, update simulation within database with new final net worth number
        simulation.final_net_worth = (simulation_data[-1]['net_worth'])
        simulation.save()

        import plotly.graph_objects as go

        # Prepare Sankey data
        labels = [
            "Total Income", "Salary", "Bonuses", "Other Income", "Lump Sum Income",
            "Total Expenses", "Fixed Costs", "Variable Costs", "Health Insurances", "Lump Sum Expenses", "Taxes",
            "Total Savings", "HSA", "401k/403b", "IRA", "TBA", "Employer"
        ]

        # Sources and targets for Sankey diagram
        sources = [
            1, 2, 3, 4,
            0, 0,
            5, 5, 5, 5, 5,
            11, 11, 11, 11,
            16
        ]

        targets = [
            0, 0, 0, 0,
            5, 11,
            6, 7, 8, 9, 10,
            12, 13, 14, 15,
            13
        ]

        # Values for each flow (use sum for the simulation period)
        income_sum = sum(total_income)
        salary_sum = sum(salaries)
        bonus_sum = sum(bonuses)
        other_income_sum = sum(other_income)
        lump_sum_income_sum = sum(lump_sum_incomes)

        expenses_sum = sum(total_expenses)
        fixed_cost_sum = sum(fixed_costs)
        variable_cost_sum = sum(variable_costs)
        health_insurance_sum = sum(health_insurance)
        lump_sum_expense_sum = sum(lump_sum_expenses)
        tax_sum = sum(taxes)

        savings_sum = sum(savings)
        hsa_sum = sum(hsa_contributions)
        retirement_sum = sum(retirement_contributions)
        ira_sum = sum(ira_contributions)
        iba_sum = sum(iba_contributions)
        employer_sum = sum(employer_retirement_contributions)

        values = [
            salary_sum, bonus_sum, other_income_sum, lump_sum_income_sum, # Income splits
            expenses_sum, savings_sum,
            fixed_cost_sum, variable_cost_sum, health_insurance_sum, lump_sum_expense_sum, tax_sum, # Expense splits
            hsa_sum, retirement_sum, ira_sum, iba_sum, employer_sum # Income to Savings
        ]

        # Create Sankey chart
        fig = go.Figure(data=[go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color="black", width=0.5),
                label=labels,
            ),
            link=dict(
                source=sources,
                target=targets,
                value=values,
                color=["#94c9a9"]*4 + ["#D5573B"]+ ["#777DA7"]+ ["#D5573B"]*5 + ["#777DA7"]*5
            ),
        )])
        fig.update_layout(
            title = {
                "text": "Total Cash Flow Sankey Diagram",
                "font": {
                    "family": "Montserrat",
                    "size": 16,
                    "color": "black"
                }
            },
            paper_bgcolor="#F7F4EF",
            plot_bgcolor="#F7F4EF",
            font=dict(
                family = "Montserrat",
                size = 16,
                color = "black"
            )
        )
        fig.update_traces(
            node_color=["#50a772"]*5 + ["#af3d23"]*6 + ["#3c4379"]*5
        )

        sankey_html = fig.to_html(full_html=True)

    # If simulation logic fails, return user to the new simulation screen with error message
    except Exception as e:
        print(e)
        #change to return redirect...?
        return render(request, 'FIRE/newsimulation.html', {'form': SimulationForm(), 'error': "Error generating simulation, please try again."})

    # If post reuqest only, return the partial HTML template 
    if request.method == "POST":
        if form_save_error:
            return render(request, 'FIRE/partials/firetable.html', {'toggle': toggle, 'simulation': simulation, "data": simulation_data, 'form' : form, 'ages': json.dumps(ages), 'net_worths': json.dumps(net_worths), 'magic_numbers': json.dumps(magic_numbers), 'total_income': json.dumps(total_income), 'total_expenses': json.dumps(total_expenses), 'savings': json.dumps(savings), 'hsa_end': json.dumps(hsa_end), 'retirement_end': json.dumps(retirement_end), 'ira_end': json.dumps(ira_end), 'iba_end': json.dumps(iba_end), 'lump_sum_incomes': lump_sum_income, 'lump_sum_expenses': lump_sum_expense_zip, 'variable_cost_adjustments': variable_cost_adjustments, 'fixed_cost_adjustments': fixed_cost_adjustments, 'assets': assets, 'sankey': sankey_html, 'financial_independence_age': financial_independence_age, 'error': "There was an error updating your simulation, please try again."})
        else:
           messages.success(request, f"{simulation.name} updated successfully!")
           return render(request, 'FIRE/partials/firetable.html', {'toggle': toggle, 'simulation': simulation, "data": simulation_data, 'form' : form, 'ages': json.dumps(ages), 'net_worths': json.dumps(net_worths), 'magic_numbers': json.dumps(magic_numbers), 'total_income': json.dumps(total_income), 'total_expenses': json.dumps(total_expenses), 'savings': json.dumps(savings), 'hsa_end': json.dumps(hsa_end), 'retirement_end': json.dumps(retirement_end), 'ira_end': json.dumps(ira_end), 'iba_end': json.dumps(iba_end), 'lump_sum_incomes': lump_sum_income, 'lump_sum_expenses': lump_sum_expense_zip, 'variable_cost_adjustments': variable_cost_adjustments, 'fixed_cost_adjustments': fixed_cost_adjustments, 'assets': assets, 'sankey': sankey_html, 'financial_independence_age': financial_independence_age}) 
    # If get request, return the whole runsimulation HTML template
    else:
        return render(request, "FIRE/runsimulation.html", {'toggle': True, "simulation": simulation, "data": simulation_data, 'form': EditSimulationForm(), 'ages': json.dumps(ages), 'net_worths': json.dumps(net_worths), 'magic_numbers': json.dumps(magic_numbers), 'total_income': json.dumps(total_income), 'total_expenses': json.dumps(total_expenses), 'savings': json.dumps(savings), 'hsa_end': json.dumps(hsa_end), 'retirement_end': json.dumps(retirement_end), 'ira_end': json.dumps(ira_end), 'iba_end': json.dumps(iba_end), 'lump_sum_incomes': lump_sum_income, 'lump_sum_expenses': lump_sum_expense_zip, 'variable_cost_adjustments': variable_cost_adjustments, 'fixed_cost_adjustments': fixed_cost_adjustments, 'assets': assets, 'sankey': sankey_html, 'financial_independence_age': financial_independence_age})

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
    current_hsa_balance = int(request.GET.get("current_hsa_balance"))
    esitmated_hsa_yearly_return = float(request.GET.get("esitmated_hsa_yearly_return"))
    current_hsa_yearly_contribution_limit = int(request.GET.get("current_hsa_yearly_contribution_limit"))
    estimated_hsa_yearly_contribution_limit_step = int(request.GET.get("estimated_hsa_yearly_contribution_limit_step"))
    return render(request, 'FIRE/partials/opt_in_hsa.html', {'current_hsa_balance': current_hsa_balance, 'esitmated_hsa_yearly_return': esitmated_hsa_yearly_return, 'current_hsa_yearly_contribution_limit': current_hsa_yearly_contribution_limit, 'estimated_hsa_yearly_contribution_limit_step': estimated_hsa_yearly_contribution_limit_step})

# HTMX: Include Coast FIRE input fields
def coastfire_opt_in(request):
    max_age = int(request.GET.get("max_age")) - 1
    min_age = int(request.GET.get("min_age")) + 1
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