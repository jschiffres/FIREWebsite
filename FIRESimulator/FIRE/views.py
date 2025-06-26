from django.db.models import F
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .models import Simulation

import math
import pandas as pd 

# Create your views here.
def index(request):
    return HttpResponse("Hello, world. You're at the FIRE index.")

def yearly_amounts(current,percentage,years,derived=False):
    incrementing_list = []
    if derived == True:
        current = current * percentage
    for num in range(0,years):
        if num != 0:
            new_amount = incrementing_list[num-1] * (1+percentage)
            incrementing_list.append(math.floor(new_amount))
        else:
            incrementing_list.append(math.floor(current))
    return incrementing_list

def yearly_contribution_limits(start,increment_amount,years):
    limits = []
    limits.append(start)
    for num in range(0,years-1):
        limits.append(limits[num] + increment_amount)
    return limits

def yearly_contributions(years,savings,hsa_cont_limits,retirement_cont_limits,ira_cont_limits):
    hsa_contributions = []
    ira_contributions = []
    retirement_contributions = []
    iba_contributions = []
    for num in range(0,years):
        if savings[num] < 0:
            hsa_contributions.append(0)
            retirement_contributions.append(0)
            ira_contributions.append(0)
            iba_contributions.append(0)
        if savings[num] > hsa_cont_limits[num] + retirement_cont_limits[num] + ira_cont_limits[num]:
            hsa_contributions.append(hsa_cont_limits[num])
            retirement_contributions.append(retirement_cont_limits[num])
            ira_contributions.append(ira_cont_limits[num])
            iba_contributions.append(savings[num] - hsa_cont_limits[num] - retirement_cont_limits[num] - ira_cont_limits[num])
        elif savings[num] > hsa_cont_limits[num] + retirement_cont_limits[num]:
            hsa_contributions.append(hsa_cont_limits[num])
            retirement_contributions.append(retirement_cont_limits[num])
            ira_contributions.append(savings[num] - hsa_cont_limits[num] - retirement_cont_limits[num])
            iba_contributions.append(0)
        elif savings[num] > hsa_cont_limits[num]:
            hsa_contributions.append(hsa_cont_limits[num])
            retirement_contributions.append(savings[num] - hsa_cont_limits[num])
            ira_contributions.append(0)
            iba_contributions.append(0)
        else:
            hsa_contributions.append(savings[num])
            retirement_contributions.append(0)
            ira_contributions.append(0)
            iba_contributions.append(0)

    return hsa_contributions,retirement_contributions,ira_contributions,iba_contributions

def start_end_balances(current_balance,years,contributions_list,salaries_list,yearly_return,employer_contribution=0):
    start_list = [current_balance]
    end_list = []
    for num in range(0,years):
        end_list.append(math.floor((start_list[num] + contributions_list[num] + (salaries_list[num] * employer_contribution)) * (1+yearly_return)))
        if num != years - 1:
            start_list.append(math.floor(end_list[num]))
    return start_list,end_list

def firesimulation(request, simulation_id):
    simulation = get_object_or_404(Simulation, pk=simulation_id)
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
    df = df.to_html()
    return render(request, "FIRE/firesimulation.html", {"salaries": salaries, "df": df})