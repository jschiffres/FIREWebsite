from django.db.models import F
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db import IntegrityError
from django.http import HttpResponse, Http404
from django.views.decorators.http import require_POST
import uuid

from .models import Plan, Feedback
from .forms import CreateUserForm, FeedbackForm, PlanForm, EditPlanForm
from .engine import PlanObject
from .plan_input import saveplan
from .emails import welcome_email

import math
import csv

def _is_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False

def _can_access_plan(request, plan):
    # Unowned (anonymous) plans stay reachable by their unguessable UUID
    return plan.user is None or plan.user == request.user

def _create_account(request, plan=None):
    """Shared signup logic; returns (redirect_response, None) or (None, error_response)."""
    form = CreateUserForm(request.POST)
    template = 'FIRE/signupuser.html'
    if request.POST.get('password1') != request.POST.get('password2'):
        return None, render(request, template, {'form': form, 'error': 'Passwords did not match.'})
    email = (request.POST.get('email') or '').strip()
    if email and User.objects.filter(email__iexact=email).exists():
        return None, render(request, template, {'form': form, 'error': 'Email provided is already associated with an account.'})
    if not form.is_valid():
        errors = " ".join(e for errs in form.errors.values() for e in errs)
        return None, render(request, template, {'form': form, 'error': errors})
    try:
        user = form.save()
    except IntegrityError:
        return None, render(request, template, {'form': form, 'error': 'Username has already been taken.'})
    if plan is not None:
        plan.user = user
        plan.save()
    login(request, user)
    messages.success(request, "User created successfully!")
    welcome_email(user)
    return redirect('userplans'), None

# LANDING PAGE
def landing(request):
    return render(request, 'FIRE/landing.html')

# USER: Signup
def signupuser(request):
    if request.method == "GET":
        return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm()})
    response, error = _create_account(request)
    return response or error

# USER: Signup & Save Plan            
def signupsave(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    if plan.user is not None:
        messages.warning(request, "This plan already belongs to an account.")
        return redirect('loginuser')
    if request.method == "GET":
        return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm()})
    response, error = _create_account(request, plan)
    return response or error

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
        if not form.is_valid():
            messages.warning(request, "Please provide your feedback before submitting.")
            return redirect('feedback')
        newfeedback = form.save(commit=False)
        if request.user.is_authenticated:
            newfeedback.user = request.user
        newfeedback.save()
        messages.success(request, "Feedback submitted successfully!")
        return redirect('feedback')

def _summarize(plan):
    try:
        fi = PlanObject(plan).run()
    except Exception as e:
        print(f"summary failed for {plan.pk}: {e}")
        return None
    return fi

# USER: Plans
def userplans(request):
    if request.user.is_authenticated:
        plans = list(Plan.objects.filter(user=request.user).order_by('-created_at'))
        for plan in plans:
            fi = _summarize(plan)
            plan.fi_age = fi.fi_age if fi else "N/A"
            plan.funded_percent = fi.funded_percent if fi else None
        return render(request, 'FIRE/userplans.html', {'plans' : plans})
    else:
        messages.warning(request, "You must be logged in to view your plans.")
        return redirect('loginuser')

# PLANS: Compare (2-3 of the user's own plans)
@login_required
def compareplans(request):
    ids = request.GET.getlist('plans')
    plans = list(Plan.objects.filter(user=request.user, pk__in=[i for i in ids if _is_uuid(i)]))
    if not 2 <= len(plans) <= 3:
        messages.warning(request, "Select two or three plans to compare.")
        return redirect('userplans')

    rows, series = [], []
    max_age = max(plan.retirement_age for plan in plans)
    for plan in plans:
        fi = _summarize(plan)
        if fi is None:
            messages.warning(request, f"Could not generate {plan.plan_name}.")
            return redirect('userplans')
        rows.append({'plan': plan, 'fi': fi})
        series.append({
            'name': plan.plan_name,
            'points': [{'x': age, 'y': nw} for age, nw in zip(fi.ages, fi.net_worths)],
            'magic': [{'x': age, 'y': m} for age, m in zip(fi.ages, fi.magic_numbers)],
        })
    return render(request, 'FIRE/compareplans.html', {'rows': rows, 'compare_data': {'series': series, 'max_age': max_age}})

def _build_fiplan(plan):
    FIplan = PlanObject(plan).run()
    FIplan.update_final_net_worth()
    return FIplan

# PLANS: Run
def runplan(request, plan_id):
    # Retrieve plan object from Django model
    plan = get_object_or_404(Plan, pk=plan_id)

    # Ensure plan belongs to requesting user
    if not _can_access_plan(request, plan):
        messages.warning(request, "You are not authorized to view that plan.")
        return redirect('userplans' if request.user.is_authenticated else 'loginuser')

    error = None
    form = None
    # If post request, update the plan in the database by saving the form
    if request.method == "POST":
        form = EditPlanForm(request.POST, instance=plan)
        try:
            updatedplan = saveplan(form, request, dashboard_edit=True)
            if isinstance(updatedplan, str):
                error = updatedplan
                plan.refresh_from_db()
        except Exception as e:
            print(f"Error updating: {e}")
            error = f"Error updating {plan.plan_name}."
            plan.refresh_from_db()

    FIplan = None
    sankey = None
    try:
        FIplan = _build_fiplan(plan)
        sankey = FIplan.sankey_chart()
    except Exception as e:
        print(f"Error generating: {e}")
        error = error or f"Error generating {plan.plan_name}."

    if FIplan is None:
        messages.warning(request, error)
        return render(request, 'FIRE/newplan.html', {'form': PlanForm(), 'error': error})

    context = {'plan': plan, 'FIplan': FIplan, 'sankey_chart': sankey, 'chart_data': FIplan.chart_data()}
    if error:
        context['error'] = error
    if request.method == "POST":
        context['form'] = form
        if not error:
            messages.success(request, f"{plan.plan_name} updated successfully!")
        return render(request, 'FIRE/partials/plandashboard.html', context)
    context['form'] = EditPlanForm()
    return render(request, "FIRE/runplan.html", context)

# PLANS: Create New
def newplan(request):

    if request.method == "GET":
        return render(request, 'FIRE/newplan.html', {'form': PlanForm()})
    form = PlanForm(request.POST)
    try:
        newplan = saveplan(form, request)
        if isinstance(newplan, str):
            return render(request, 'FIRE/newplan.html', {'form': form, 'error': newplan})
        return redirect('runplan', plan_id=newplan.id)
    except Exception as e:
        print(e)
        return render(request, 'FIRE/newplan.html', {'form': form, 'error': "Error saving plan, please try again."})

def _owned_plan(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    if plan.user != request.user:
        raise Http404("Plan not found.")
    return plan

# PLANS: Delete        
@login_required
@require_POST
def deleteplan(request, plan_id):
    plan = _owned_plan(request, plan_id)
    name = plan.plan_name
    try:
        plan.delete()
        messages.success(request, f"{name} deleted successfully!")
    except Exception as e:
        messages.warning(request, f"Error deleting {name}.")
    return redirect('userplans')
    
# PLANS: Copy
@login_required
def copyplan(request, plan_id):
    plan = _owned_plan(request, plan_id)
    plan_name = plan.plan_name

    try:
        plan.pk = None
        plan.id = uuid.uuid4()
        plan._state.adding = True
        plan.plan_name = f"{plan_name} (copy)"[:50]
        plan.save()
        messages.success(request, f"{plan_name} copied successfully!")
    except Exception as e:
        print(f"copyplan: {e}")
        messages.warning(request, f"Error copying {plan_name}.")
    return redirect('userplans')


# PLANS: Download
def downloadplan(request, plan_id):
    # Retrieve plan object from Django model
    plan = get_object_or_404(Plan, id=plan_id)
    if not _can_access_plan(request, plan):
        raise Http404("Plan not found.")

    try:
        FIplan = _build_fiplan(plan)

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
        
        for account in FIplan.accounts[1:]:
            category = account.get('saving_category')
            name = account.get('saving_name', 'Investments')
            if category == "ESRP":
                header_row.extend([name + ": Start", name + ": Cont. Limit", name + ": Cont. Amount", name + ": Employer Cont. Amount", name + ": End"])
            elif category in ("HSA", "IRA"):
                header_row.extend([name + ": Start", name + ": Cont. Limit", name + ": Cont. Amount", name + ": End"])
            else:
                header_row.extend([name + ": Start", name + ": Cont. Amount", name + ": End"])
        
        header_row.extend(['Net Worth', 'Magic Number', 'Withdraw Rate'])
        
        # Write header row
        writer.writerow(header_row)

        # Write data rows
        for row in FIplan.plan_data:
            writer.writerow(row)

        # Return csv response
        return response
    except Exception as e:
        print(f"downloadplan: {e}")
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

