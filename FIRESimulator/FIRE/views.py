from django.db.models import F
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db import IntegrityError
from django.http import HttpResponse

from .models import Simulation, Plan, Feedback
from .forms import SimulationForm, EditSimulationForm, CreateUserForm, FeedbackForm, PlanForm, EditPlanForm
from .functions import saveplan, FIRE, PlanObject
from .emails import welcome_email

import math
import json
import csv

# LANDING PAGE
def landing(request):
    return render(request, 'FIRE/landing.html')

# USER: Signup
def signupuser(request):
    if request.method == "GET":
        return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm()})
    else:
        if request.POST.get('password1') == request.POST.get('password2'):
            try:
                if 1 == 2:
                # if User.objects.filter(email=request.POST.get('email')).exists():
                    return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm(), 'error':'Email provided is already associated with an account.'})
                else:
                    user = User.objects.create_user(username=request.POST.get('username'), email=request.POST.get('email'), password=request.POST.get('password1')) 
                    user.save()
                    login(request, user)
                    messages.success(request, "User created successfully!")
                    welcome_email(user)
                    return redirect('userplans')
            except IntegrityError: 
                return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm(), 'error':'Username has already been taken.'})
        else:
            return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm(), 'error':'Passwords did not match.'})

# USER: Signup & Save Plan            
def signupsave(request, plan_id):
    if request.method == "GET":
        return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm()})
    else:
        if request.POST.get('password1') == request.POST.get('password2'):
            try:
                if 1 == 2:
                # if User.objects.filter(email=request.POST.get('email')).exists():
                    return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm(), 'error':'Email provided is already associated with an account.'})
                else:
                    user = User.objects.create_user(username=request.POST.get('username'), email=request.POST.get('email'), password=request.POST.get('password1')) 
                    user.save()
                    plan_id = request.path_info.split("/")[2]
                    plan = get_object_or_404(Plan, pk=plan_id)
                    plan.user = user
                    plan.save()
                    login(request, user)
                    messages.success(request, "User created successfully!")
                    welcome_email(user)
                    return redirect('userplans')
            except IntegrityError: 
                return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm(), 'error':'Username has already been taken.'})
        else:
            return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm(), 'error':'Passwords did not match.'})

# USER: Login
def loginuser(request):
    if request.method == "GET":
        if request.user.is_authenticated:
            return redirect('userplans')
        else:
            return render(request, 'FIRE/loginuser.html', {'form':AuthenticationForm()})
    else:
        user = authenticate(request, username=request.POST.get('username'), password=request.POST.get('password'))
        if user is None:
            return render(request, 'FIRE/loginuser.html', {'form':AuthenticationForm(), 'error': "Username and password did not match."})
        else:
            login(request, user)
            messages.success(request, "Logged in successfully!")
            return redirect('userplans')

# USER: Logout     
@login_required
def logoutuser(request):
    if request.method == "POST":
        logout(request)
        messages.success(request, "Logged out successfully!")
        return redirect('landing')
    else:
        return redirect('userplans')

# USER: Feedback    
def feedback(request):
    if request.method == "GET":
        if request.user.is_superuser: # just using request.user attributes
            feedback = Feedback.objects.all()
            return render(request, 'FIRE/feedback.html', {'form': FeedbackForm(), 'feedback': feedback})
        return render(request, 'FIRE/feedback.html', {'form': FeedbackForm()})
    else:
        form = FeedbackForm(request.POST)
        newfeedback = form.save(commit=False)
        if str(request.user) != "AnonymousUser":
            newfeedback.user = request.user
        newfeedback.save()
        messages.success(request, "Feedback submitted successfully!")
        return redirect('feedback')

# USER: Plans
def userplans(request):
    if request.user.is_authenticated:
        plans = Plan.objects.filter(user=request.user)
        return render(request, 'FIRE/userplans.html', {'plans' : plans})
    else:
        messages.warning(request, "You must be logged in to view your plans.")
        return redirect('loginuser')

# PLANS: Run
def runplan(request, plan_id):
    # Retrieve plan object from Django model
    plan = get_object_or_404(Plan, pk=plan_id)

    # Ensure simulation belongs to requesting user
    if plan.user and request.user != plan.user:
        return render(request, 'FIRE/newplan.html', {'form': PlanForm(), 'error': "Not authorized to view simulation."})

    error_status = False
    # If post request, update the simulation in the database by saving the form
    if request.method == "POST":
        form = EditPlanForm(request.POST, instance=plan)
        try:
            updatedplan = saveplan(form, request, dashboard_edit=True)
            if type(updatedplan) == str:
                error_status = True
                error = updatedplan        
        except Exception as e:
            print(f"Error updating: {e}")
            error_status = True
            error = f"Error updaing {plan.plan_name}."

    try:
        # Initialize FIplan object
        FIplan = PlanObject(plan)

        # Execute FIplan methods to create necessary attributes
        FIplan.personal_infos()
        FIplan.incomes()
        FIplan.expenses()
        FIplan.savings()
        FIplan.yearly_contribution_limits()
        FIplan.yearly_contributions()
        FIplan.start_end_amounts()
        FIplan.fi_indicators()
        FIplan.template_data()
        FIplan.update_final_net_worth()
        sankey = FIplan.sankey_chart()

    # If plan logic fails, return user to the new plan screen with error message
    except Exception as e:
        print(f"Error generating: {e}")
        error_status = True
        error = f"Error generating {plan.plan_name}."
    
    # If post request only, return the partial HTML template 
    if request.method == "POST":
        if error_status:
            return render(request, 'FIRE/partials/plandashboard.html', {'plan': plan, 'FIplan': FIplan, 'form' : form, 'error': error})
        else:
            messages.success(request, f"{plan.plan_name} updated successfully!")
            return render(request, 'FIRE/partials/plandashboard.html', {'plan': plan, 'FIplan': FIplan, 'form' : form, 'sankey_chart': sankey})
    # If get request, return the whole HTML template
    else:
        if error_status:
            return render(request, "FIRE/runplan.html", {'plan': plan, 'FIplan': FIplan, 'form': EditPlanForm(), 'error': error})
        else:
            return render(request, "FIRE/runplan.html", {'plan': plan, 'FIplan': FIplan, 'form': EditPlanForm(), 'sankey_chart': sankey})

# PLANS: Create New
def newplan(request):

    if request.method == "GET":
        return render(request, 'FIRE/newplan.html', {'form': PlanForm()})
    else:
        try:
            form = PlanForm(request.POST)
            newplan = saveplan(form, request)
            if type(newplan) == str:
                return render(request, 'FIRE/newplan.html', {'form': form, 'error': newplan})
            id = newplan.id
            return redirect(f'/plan/{id}')
        except Exception as e:
            print(e)
            return render(request, 'FIRE/newplan.html', {'form': form, 'error': "Error saving plan, please try again."})

# PLANS: Edit  
@login_required
def editplan(request, plan_id):
    plan = get_object_or_404(Simulation, pk=plan_id)
    if request.method == "GET":
        form = SimulationForm(instance=plan)
        return render(request, 'FIRE/editsimulation.html', {'simulation': plan, 'form' : form})
    else:
        try:   
            form = SimulationForm(request.POST, instance=plan)
            newsim = saveplan(form, request)
            if type(newsim) == str:
                return render(request, 'FIRE/editsimulation.html', {'simulation': plan, 'form': form, 'error': newsim})
            id = newsim.id
            return redirect(f'/firesimulation/{id}')
        except Exception as e:
            return render(request, 'FIRE/newplan.html', {'simulation': plan, 'form': form, 'error': "Error creating simulation, please try again"})

# PLANS: Delete        
@login_required
def deleteplan(request, plan_id):
    # Retrieve plan object from Django model
    plan = get_object_or_404(Plan, pk=plan_id) 

    # Delete plan
    try:
        plan.delete()
        messages.success(request, f"{plan.plan_name} deleted successfully!")
        return redirect('userplans')
    except Exception as e:
        messages.warning(request, f"Error deleting {plan.plan_name}.")
        return redirect('userplans')
    
# PLANS: Copy
@login_required
def copyplan(request, plan_id):
    # Retrieve plan object from Django model
    plan = get_object_or_404(Plan, id=plan_id)

    try:
        # Set pk and id to none
        plan.pk = None
        plan.id = None

        # Rename plan name and save to model
        plan_name = plan.plan_name
        plan.plan_name = str(plan_name) + " (copy)"
        plan.save()

        # Return user's plans
        messages.success(request, f"{plan_name} copied successfully!")
        return redirect('userplans')
    except Exception as e:
        messages.warning(request, f"Error copying {plan.plan_name}.")
        return redirect('userplans')


# PLANS: Download
@login_required
def downloadplan(request, plan_id):
    # Retrieve plan object from Django model
    plan = get_object_or_404(Plan, id=plan_id)

    try:
      # Initialize FIplan object
        FIplan = PlanObject(plan)

        # Execute FIplan methods to create necessary attributes
        FIplan.personal_infos()
        FIplan.incomes()
        FIplan.expenses()
        FIplan.savings()
        FIplan.yearly_contribution_limits()
        FIplan.yearly_contributions()
        FIplan.start_end_amounts()
        FIplan.fi_indicators()
        FIplan.template_data()
        FIplan.update_final_net_worth()

        # Set up response object for return of csv file
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="plan_{plan_id}.csv"'

        # Set up writer object to store plan data
        writer = csv.writer(response)

        # Create header row based on plan entires
        header_row = ['Age', 'Year']

        for income in FIplan.incomes:
            if income['income_category'] == "Salary":
                header_row.extend([income['income_name'] + ': Gross', income['income_name'] + ': Bonus', income['income_name'] + ': Tax', income['income_name'] + ': Net'])
            else:
                header_row.extend([income['income_name'] + ': Gross', income['income_name'] + ': Tax', income['income_name'] + ': Net'])
        
        for expense in FIplan.expenses:
            header_row.extend([expense['expense_name']])
        
        header_row.extend(['Savings'])
        
        for account in FIplan.accounts:
            if account['saving_category'] == "ESRP":
                header_row.extend([account['saving_name'] + ": Start", account['saving_name'] + ": Cont. Limit", account['saving_name'] + ": Cont. Amount", account['saving_name'] + ": Employer Cont. Amount", account['saving_name'] + ": End"])
            elif account['saving_category'] == "HSA" or account['saving_category'] == "IRA":
                header_row.extend([account['saving_name'] + ": Start", account['saving_name'] + ": Cont. Limit", account['saving_name'] + ": Cont. Amount", account['saving_name'] + ": End"])
            else:
                header_row.extend([account['saving_name'] + ": Start", account['saving_name'] + ": Cont. Amount", account['saving_name'] + ": End",])
        
        header_row.extend(['Net Worth', 'Magic Number', 'Withdraw Rate'])
        
        # Write header row
        writer.writerow(header_row)

        # Write data rows
        for row in FIplan.plan_data:
            writer.writerow(row)

        # Return csv response
        return response
    except Exception as e:
        messages.warning(request, f"Error downloading {plan.plan_name}.")
        return redirect('userplans')
    

# HTMX: Add Section
def create_incomes_section(request):
    return render(request, 'FIRE/partials/section_incomes.html')

# HTMX: Add Section
def create_expenses_section(request):
    return render(request, 'FIRE/partials/section_expenses.html')

# HTMX: Add Section
def create_savings_section(request):
    return render(request, 'FIRE/partials/section_savings.html')

# HTMX: Add New Entry
def create_income(request):
    entry_count = int(request.GET.get("entry_count"))+1
    return render(request, 'FIRE/partials/new_income.html', {'entry_count': entry_count})

# HTMX: Add New Entry
def create_expense(request):
    entry_count = int(request.GET.get("entry_count"))+1
    return render(request, 'FIRE/partials/new_expense.html', {'entry_count': entry_count})

#HTMX: Savings Method
def savings_method(request):
    if request.GET.get('saving_option') == 'Simple':
        return render(request, 'FIRE/partials/savings_method_simple.html')
    elif request.GET.get('saving_option') == 'Recommended':
        return render(request, 'FIRE/partials/savings_method_recommended.html')
    elif request.GET.get('saving_option') == 'Custom':
        print("Here")
        return render(request, 'FIRE/partials/savings_method_custom.html')
    else:
        return render(request, 'FIRE/partials/none.html')

# HTMX: Add New Entry
def create_saving(request):
    entry_count = int(request.GET.get("entry_count"))
    esrp_count = int(request.GET.get("esrp_count"))
    hsa_count = int(request.GET.get("hsa_count"))
    ira_count = int(request.GET.get("ira_count"))
    tba_count = int(request.GET.get("tba_count"))
    if entry_count < 4:
        return render(request, 'FIRE/partials/new_saving.html', {'entry_count': entry_count, 'esrp_count': esrp_count, 'hsa_count': hsa_count, 'ira_count': ira_count, 'tba_count': tba_count})
    else:
        return render(request, 'FIRE/partials/none.html')

# HTMX: Add Category Fields
def income_fields(request):
    category = request.GET.get("income_category")
    salary_count = request.GET.get("salary_count")
    recurring_income_count = request.GET.get("recurring_income_count")
    one_time_income_count = request.GET.get("one_time_income_count")
    ages = [num for num in range(int(request.GET.get("min_age")),int(request.GET.get("max_age")))]
    if category == "Salary":
        ages[0] = "Current Age"
        ages[-1] = "Target Retirement Age"
        return render(request, 'FIRE/partials/fields_income_salary.html', {'ages' : ages, 'salary_count' : salary_count})
    elif category == "Recurring":
        ages[0] = "Current Age"
        ages[-1] = "Target Retirement Age"
        return render(request, 'FIRE/partials/fields_income_recurring.html', {'ages' : ages, 'recurring_income_count' : recurring_income_count})
    elif category == "One-time":
        return render(request, 'FIRE/partials/fields_income_one_time.html', {'ages' : ages, 'one_time_income_count' : one_time_income_count})
    else:
        return render(request, 'FIRE/partials/fields_income_none.html')

# HTMX: Add Category Fields    
def expense_fields(request):
    category = request.GET.get("expense_category")
    recurring_expense_count = request.GET.get("recurring_expense_count")
    one_time_expense_count = request.GET.get("one_time_expense_count")
    ages = [num for num in range(int(request.GET.get("min_age")),int(request.GET.get("max_age")))]
    if category == "Recurring":
        ages[0] = "Current Age"
        ages[-1] = "Target Retirement Age"
        return render(request, 'FIRE/partials/fields_expenses_recurring.html', {'ages' : ages, 'recurring_expense_count' : recurring_expense_count})
    elif category == "One-time":
        return render(request, 'FIRE/partials/fields_expenses_one_time.html', {'ages' : ages, 'one_time_expense_count' : one_time_expense_count})
    else:
        return render(request, 'FIRE/partials/fields_expenses_none.html')

# HTMX: Add Category Fields
def saving_fields(request):
    category = request.GET.get("saving_category")
    ages = [num for num in range(int(request.GET.get("min_age")),int(request.GET.get("max_age")))]
    if category == "ESRP":        
        if int(request.GET.get("esrp_count")) == 0:
            return render(request, 'FIRE/partials/fields_savings_esrp.html', {'ages' : ages})
        else:
            return render(request, 'FIRE/partials/fields_savings_none.html')
    elif category == "IRA":
        if int(request.GET.get("ira_count")) == 0:
            return render(request, 'FIRE/partials/fields_savings_ira.html', {'ages' : ages})
        else:
            return render(request, 'FIRE/partials/fields_savings_none.html')
    elif category == "HSA":
        if int(request.GET.get("hsa_count")) == 0:
            return render(request, 'FIRE/partials/fields_savings_hsa.html', {'ages' : ages})
        else:
            return render(request, 'FIRE/partials/fields_savings_none.html')
    elif category == "TBA":
        if int(request.GET.get("tba_count")) == 0:
            return render(request, 'FIRE/partials/fields_savings_tba.html', {'ages' : ages})
        else:
            return render(request, 'FIRE/partials/fields_savings_none.html')
    else:
        return render(request, 'FIRE/partials/fields_savings_none.html')

# HTMX: Add Entry Table    
def income_table(request):
    if request.GET.get('income_category') == "None":
        return render(request, 'FIRE/partials/table_none.html')
    
    try:
        min_age = int(request.GET.get("min_age"))
        max_age = int(request.GET.get("max_age"))
        ages = [age for age in range(min_age,max_age)]

        if request.GET.get('income_category') == "One-time":
            amount = int(request.GET.get("amount"))
            lump_sum_age = int(request.GET.get("age"))
            tax_rate = float(request.GET.get("tax_rate"))

            data = []
            year_dict = {}
            year_dict['age'] = lump_sum_age
            year_dict['gross_amount'] = '${:,}'.format(amount)
            year_dict['tax_amount'] = '${:,}'.format(math.floor(amount * round(tax_rate/100,3)))
            year_dict['net_amount'] = '${:,}'.format(amount - math.floor(amount * round(tax_rate/100,3)))
            data.append(year_dict)
            return render(request, 'FIRE/partials/table_income_one_time.html', {'data': data})
        
        else:
            starting_amount = int(request.GET.get("starting_amount"))
            yearly_change = float(request.GET.get("yearly_change"))
            tax_rate = float(request.GET.get("tax_rate"))
            tax_rate_change = float(request.GET.get("tax_rate_change"))
            start_age = request.GET.get("start_age")
            if start_age == "Current Age":
                start_age = min_age
            else:
                start_age = int(start_age)
            stop_age = request.GET.get("stop_age")
            if stop_age == "Target Retirement Age":
                stop_age = max_age-1
            else:
                stop_age = int(stop_age)
            income_age_range = [age for age in range(start_age,stop_age+1)]
            gross_amounts = [math.floor(starting_amount * ((1 + round(yearly_change/100,3)) ** year)) for year in range(0,len(income_age_range))]
            gross_amounts_dict = dict(zip(income_age_range, gross_amounts))
            gross_amounts = [gross_amounts_dict[age] if age in gross_amounts_dict else 0 for age in ages]
            tax_rates = [round(((tax_rate) + (year * tax_rate_change)),3) for year in range(0,len(income_age_range))]
            tax_rates_dict = dict(zip(income_age_range,tax_rates))
            tax_rates = [tax_rates_dict[age] if age in tax_rates_dict else 0 for age in ages]

            if request.GET.get('income_category') == "Salary":
                bonus_rate = float(request.GET.get("bonus_rate"))
                bonus_amounts = [math.floor(gross_amounts[year] * round(bonus_rate/100,3)) for year in range(0,len(ages))]
                tax_amounts = [math.floor((gross_amounts[year] + bonus_amounts[year]) * round(tax_rates[year]/100,3)) for year in range(0,len(ages))]
                net_amounts = [math.floor(gross_amounts[year] + bonus_amounts[year] - tax_amounts[year]) for year in range(0,len(ages))]
                
                data = []
                for age in range(0,len(ages)):
                    year_dict = {}
                    year_dict['age'] = ages[age]
                    year_dict['gross_amount'] = '${:,}'.format(gross_amounts[age])
                    year_dict['bonus_amount'] = '${:,}'.format(bonus_amounts[age])
                    year_dict['tax_amount'] = '${:,}'.format(tax_amounts[age])
                    year_dict['net_amount'] = '${:,}'.format(net_amounts[age])
                    data.append(year_dict)
                return render(request, 'FIRE/partials/table_income_salary.html', {'data': data})
            
            else: 
                tax_amounts = [math.floor((gross_amounts[year]) * round(tax_rates[year]/100,3)) for year in range(0,len(ages))]
                net_amounts = [math.floor(gross_amounts[year] - tax_amounts[year]) for year in range(0,len(ages))]
                
                data = []
                for age in range(0,len(ages)):
                    year_dict = {}
                    year_dict['age'] = ages[age]
                    year_dict['gross_amount'] = '${:,}'.format(gross_amounts[age])
                    year_dict['tax_amount'] = '${:,}'.format(tax_amounts[age])
                    year_dict['net_amount'] = '${:,}'.format(net_amounts[age])
                    data.append(year_dict)
                return render(request, 'FIRE/partials/table_income_recurring.html', {'data': data})
    except Exception as e:
        print(f"Income Table: {e}")
        return render(request, 'FIRE/partials/table_none.html')

# HTMX: Add Entry Table 
def expense_table(request):
    if request.GET.get('expense_category') == "None":
        return render(request, 'FIRE/partials/table_none.html')
    min_age = int(request.GET.get("min_age"))
    max_age = int(request.GET.get("max_age"))
    ages = [age for age in range(min_age,max_age)]

    if request.GET.get('expense_category') == "One-time":
        amount = int(request.GET.get("amount"))
        lump_sum_age = int(request.GET.get("age"))

        data = []
        year_dict = {}
        year_dict['age'] = lump_sum_age
        year_dict['amount'] = '${:,}'.format(amount)
        data.append(year_dict)
        return render(request, 'FIRE/partials/table_expense_one_time.html', {'data': data})
    
    else:
        starting_amount = int(request.GET.get("starting_amount"))
        yearly_change = float(request.GET.get("yearly_change"))
        start_age = request.GET.get("start_age")
        if start_age == "Current Age":
            start_age = min_age
        else:
            start_age = int(start_age)
        stop_age = request.GET.get("stop_age")
        if stop_age == "Target Retirement Age":
            stop_age = max_age-1
        else:
            stop_age = int(stop_age)

        expense_age_range = [age for age in range(start_age,stop_age+1)]
        amounts = [math.floor(starting_amount * ((1 + round(yearly_change/100,3)) ** year)) for year in range(0,len(expense_age_range))]
        amounts_dict = dict(zip(expense_age_range, amounts))
        amounts = [amounts_dict[age] if age in amounts_dict else 0 for age in ages]
            
        data = []
        for age in range(0,len(ages)):
            year_dict = {}
            year_dict['age'] = ages[age]
            year_dict['amount'] = '${:,}'.format(amounts[age])
            data.append(year_dict)
        return render(request, 'FIRE/partials/table_expense_recurring.html', {'data': data})
    
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
        #Compare functionality between two plans
        #discard current plan if user in the middle modal "are you sure you want to leave?"

    # Retrieve simulation object from Django model
    simulation = get_object_or_404(Simulation, pk=simulation_id)

    # Ensure simulation belongs to requesting user
    if simulation.user and request.user != simulation.user:
        return render(request, 'FIRE/newplan.html', {'form': SimulationForm(), 'error': "Not authorized to view simulation."})

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
            "Total Expenses", "Fixed Costs", "Variable Costs", "Health Insurance", "Lump Sum Expenses", "Taxes",
            "Total Savings", "HSA", "401k/403b", "IRA", "TBA", "Employer Contribution"
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
                color=["#B9FC72"]*4 + ["#F5BDFB"]+ ["#63D8EA"]+ ["#FBE3FD"]*5 + ["#97E4F1"]*5
            ),
        )])
        fig.update_layout(
            title = {
                "text": "Total Cash Flow Sankey Diagram",
                "font": {
                    "family": "Montserrat",
                    "size": 24,
                    "color": "black"
                },
            },
            title_x=0.5,
            paper_bgcolor="#F7F4EF",
            plot_bgcolor="#F7F4EF",
            font=dict(
                family = "Montserrat",
                size = 16,
                color = "black"
            )
        )
        fig.update_traces(
            node_color=["#285C53"]*5 + ["#E13335"]*6 + ["#4A09B5"]*6
        )

        sankey_html = fig.to_html(full_html=True)

    # If simulation logic fails, return user to the new simulation screen with error message
    except Exception as e:
        print(e)
        #change to return redirect...?
        return render(request, 'FIRE/newplan.html', {'form': SimulationForm(), 'error': "Error generating simulation, please try again."})

    # If post reuqest only, return the partial HTML template 
    if request.method == "POST":
        if form_save_error:
            return render(request, 'FIRE/partials/firetable.html', {'toggle': toggle, 'simulation': simulation, "data": simulation_data, 'form' : form, 'ages': json.dumps(ages), 'net_worths': json.dumps(net_worths), 'magic_numbers': json.dumps(magic_numbers), 'total_income': json.dumps(total_income), 'total_expenses': json.dumps(total_expenses), 'savings': json.dumps(savings), 'hsa_end': json.dumps(hsa_end), 'retirement_end': json.dumps(retirement_end), 'ira_end': json.dumps(ira_end), 'iba_end': json.dumps(iba_end), 'lump_sum_incomes': lump_sum_income, 'lump_sum_expenses': lump_sum_expense_zip, 'variable_cost_adjustments': variable_cost_adjustments, 'fixed_cost_adjustments': fixed_cost_adjustments, 'assets': assets, 'sankey': sankey_html, 'financial_independence_age': financial_independence_age, 'error': updatedsim})
        else:
           messages.success(request, f"{simulation.name} updated successfully!")
           return render(request, 'FIRE/partials/firetable.html', {'toggle': toggle, 'simulation': simulation, "data": simulation_data, 'form' : form, 'ages': json.dumps(ages), 'net_worths': json.dumps(net_worths), 'magic_numbers': json.dumps(magic_numbers), 'total_income': json.dumps(total_income), 'total_expenses': json.dumps(total_expenses), 'savings': json.dumps(savings), 'hsa_end': json.dumps(hsa_end), 'retirement_end': json.dumps(retirement_end), 'ira_end': json.dumps(ira_end), 'iba_end': json.dumps(iba_end), 'lump_sum_incomes': lump_sum_income, 'lump_sum_expenses': lump_sum_expense_zip, 'variable_cost_adjustments': variable_cost_adjustments, 'fixed_cost_adjustments': fixed_cost_adjustments, 'assets': assets, 'sankey': sankey_html, 'financial_independence_age': financial_independence_age}) 
    # If get request, return the whole runsimulation HTML template
    else:
        return render(request, "FIRE/runsimulation.html", {'toggle': True, "simulation": simulation, "data": simulation_data, 'form': EditSimulationForm(), 'ages': json.dumps(ages), 'net_worths': json.dumps(net_worths), 'magic_numbers': json.dumps(magic_numbers), 'total_income': json.dumps(total_income), 'total_expenses': json.dumps(total_expenses), 'savings': json.dumps(savings), 'hsa_end': json.dumps(hsa_end), 'retirement_end': json.dumps(retirement_end), 'ira_end': json.dumps(ira_end), 'iba_end': json.dumps(iba_end), 'lump_sum_incomes': lump_sum_income, 'lump_sum_expenses': lump_sum_expense_zip, 'variable_cost_adjustments': variable_cost_adjustments, 'fixed_cost_adjustments': fixed_cost_adjustments, 'assets': assets, 'sankey': sankey_html, 'financial_independence_age': financial_independence_age})
    
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