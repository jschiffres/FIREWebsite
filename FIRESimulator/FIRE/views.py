from django.db.models import F
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db import IntegrityError

from .models import Simulation
from .forms import SimulationForm, CreateUserForm
from .functions import saveobject, yearly_contribution_limits, yearly_amounts,start_end_balances, yearly_contributions, DFtoHTML

import math
import pandas as pd 

# Create your views here.

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

def loginuser(request):
    if request.method == "GET":
        return render(request, 'FIRE/loginuser.html', {'form':AuthenticationForm()})
    else:
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user is None:
            return render(request, 'FIRE/loginuser.html', {'form':AuthenticationForm(), 'error':"Username and password did not match."})
        else:
            login(request, user)
            messages.success(request, "Logged in successfully!")
            return redirect('usersimulations')
        
@login_required
def logoutuser(request):
    if request.method == "POST":
        logout(request)
        messages.success(request, "Logged out successfully!")
        return redirect('newsimulation')

def usersimulations(request):
    if request.user.is_authenticated:
        simulations = Simulation.objects.filter(user=request.user)
        return render(request, 'FIRE/usersimulations.html', {'simulations' : simulations})
    else:
        print("redirecting")
        return redirect('loginuser')

def firesimulation(request, simulation_id):
    # print(request.path_info.split("/")[2])
    simulation = get_object_or_404(Simulation, pk=simulation_id)
    if request.user.is_authenticated and request.user != simulation.user:
            return redirect('/newsimulation')
    years_until_retirement = simulation.estimated_retirement_age - simulation.current_age
    salaries = yearly_amounts(simulation.current_yearly_salary,simulation.estimated_salary_raise,years_until_retirement)
    bonuses = yearly_amounts(simulation.current_yearly_salary,simulation.estimated_salary_raise,years_until_retirement,derived=True)
    other_income = yearly_amounts(simulation.current_yearly_other_income,simulation.estimated_other_income_increase,years_until_retirement)
    fixed_costs = yearly_amounts(simulation.current_yearly_fixed_costs,simulation.estimated_fixed_costs_inflation,years_until_retirement)
    cost_of_living = yearly_amounts(simulation.current_yearly_cost_of_living,simulation.estimated_cost_of_living_inflation,years_until_retirement)
    health_insurance = yearly_amounts(simulation.current_yearly_health_insurance_cost,simulation.estimated_health_insurance_inflation,years_until_retirement)
    taxes = []
    for num in range(0,years_until_retirement):
        tax = (salaries[num] + bonuses[num] + other_income[num]) * simulation.estimated_tax_rate
        taxes.append(math.floor(tax))
    savings = []
    for num in range(0,years_until_retirement):
        save = salaries[num] + bonuses[num] + other_income[num] - fixed_costs[num] - cost_of_living[num] - health_insurance[num] - taxes[num]
        savings.append(math.floor(save))
    hsa_cont_limits = yearly_contribution_limits(simulation.current_hsa_yearly_contribution_limit,100,years_until_retirement)
    ira_cont_limits = yearly_contribution_limits(simulation.current_ira_yearly_contribution_limit,150,years_until_retirement)
    retirement_cont_limits = yearly_contribution_limits(simulation.current_401k_yearly_contribution_limit,250,years_until_retirement)
    hsa_contributions,retirement_contributions,ira_contributions,iba_contributions = yearly_contributions(years_until_retirement,savings,hsa_cont_limits,retirement_cont_limits,ira_cont_limits)
    ira_start,ira_end = start_end_balances(simulation.current_ira_balance,years_until_retirement,ira_contributions,salaries,simulation.esitmated_ira_yearly_return)
    retirement_start,retirement_end = start_end_balances(simulation.current_401k_balance,years_until_retirement,retirement_contributions,salaries,simulation.esitmated_401k_yearly_return,simulation.current_401k_employer_contribution)
    hsa_start,hsa_end = start_end_balances(simulation.current_hsa_balance,years_until_retirement,hsa_contributions,salaries,simulation.esitmated_hsa_yearly_return)
    iba_start,iba_end = start_end_balances(simulation.current_iba_balance,years_until_retirement,iba_contributions,salaries,simulation.esitmated_iba_yearly_return)
    net_worth = []
    for num in range(0,years_until_retirement):
        worth = hsa_end[num] + retirement_end[num] + ira_end[num] + iba_end[num]
        net_worth.append(math.floor(worth))
    dict = {'SALARY': salaries, 
        'BONUS': bonuses, 
        'OTHER INCOME': other_income, 
        'BILLS': fixed_costs, 
        'COST OF LIVING': cost_of_living,
        'TAXES': taxes,
        'HEALTH INSURANCE': health_insurance,
        'SAVINGS': savings, 
        'HSA START': hsa_start, 
        'HSA CONTRIBUTION LIMIT': hsa_cont_limits, 
        'HSA CONTRIBUTIONS': hsa_contributions, 
        'HSA END': hsa_end, 
        '401K START': retirement_start, 
        '401K CONTRIBUTION LIMIT': retirement_cont_limits,
        '401K CONTRIBUTIONS': retirement_contributions, 
        '401K END': retirement_end,
        'IRA START': ira_start, 
        'IRA CONTRIBUTION LIMIT': ira_cont_limits,
        'IRA CONTRIBUTIONS': ira_contributions, 
        'IRA END': ira_end, 
        'INDIVIDUAL START': iba_start, 
        'INDIVIDUAL CONTRIBUTIONS': iba_contributions,  
        'INDIVIDUAL END': iba_end, 
        'NET WORTH': net_worth} 
   
    
    df = pd.DataFrame(dict)
    for column in list(df.columns):
       df[column] = df[column].apply(lambda x : "${:,}".format(x)) 
    df = DFtoHTML(df)
    return render(request, "FIRE/firesimulation.html", {"salaries": salaries, "df": df, "simulation": simulation})

def newsimulation(request):
    if request.method == "GET":
        return render(request, 'FIRE/newsimulation.html', {'form': SimulationForm()})
    else:
        # try:
        form = SimulationForm(request.POST)
        newsim = saveobject(form, request)
        id = newsim.id
            # newplaylist.user = request.user
            # ''' Spotify API Logic '''
            # playlistDF = URLtoDF(form['url'].value())
            # newplaylist.playlistHTML = DFtoHTML(playlistDF)
            # newplaylist.songs = len(playlistDF)
            # newplaylist.save()
            # messages.success(request, f"{newplaylist.name} imported successfully!")
        return redirect(f'/firesimulation/{id}')
        # except (spotipy.SpotifyException, ValueError):
            # return render(request, 'TopsListGenerator/importplaylist.html', {'form':PlaylistForm(), 'error': 'Sptofiy playlist URL not recongnized, please try again.'})

@login_required
def editsimulation(request, simulation_id):
    simulation = get_object_or_404(Simulation, pk=simulation_id)
    if request.method == "GET":
        form = SimulationForm(instance=simulation)
        return render(request, 'FIRE/editsimulation.html', {'simulation' : simulation, 'form' : form})
    else:
        # try:
        form = SimulationForm(request.POST, instance=simulation)
        newsim = saveobject(form, request)
        id = newsim.id
        # messages.success(request, f"{editedplaylist.name} info updated successfully!")
        return redirect(f'/firesimulation/{id}')
        # except (spotipy.SpotifyException, ValueError):
        #     return render(request, 'TopsListGenerator/editplaylist.html', {'playlist' : playlist, 'form' : form,'error' : 'Sptofiy playlist URL not recongnized, please try again.'})