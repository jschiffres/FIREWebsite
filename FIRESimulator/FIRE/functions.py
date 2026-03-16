import math
import plotly.graph_objects as go
from datetime import date

def saveplan(self, request, dashboard_edit = False):
    try:
        current_age = int(request.POST.get('current_age'))
        retirement_age = int(request.POST.get('retirement_age'))
    except Exception as e:
        print(f"Error in Ages 1: {e}")
        return "Invalid age provided."
    
    try:
        if not request.POST.get('plan_name'):
            if dashboard_edit == False:
                return "Please provide a name for this plan."

        if request.POST.get('coast_fire_age'):
            coast_fire_age = int(request.POST.get('coast_fire_age'))
            if retirement_age <= coast_fire_age:
                return "Retirement age must be greater than Coast FIRE age."
            if current_age >= coast_fire_age:
                return "Current age must be less than Coast FIRE age."
            if current_age > 100 or current_age <= 0 or retirement_age > 101 or retirement_age <= 0 or coast_fire_age > 101 or coast_fire_age <= 0:
                return "Ages must be greater than 0 and less than 100."
        else:
            if retirement_age <= current_age:
                return "Retirement age must be greater than current age."
            if current_age > 100 or current_age <= 0 or retirement_age > 101 or retirement_age <= 0:
                return "Ages must be greater than 0 and less than 100."
                
    except Exception as e:
        print(f"Error in Ages 2: {e}")
        return "Invalid age provided."

    try:
        #Incomes
        income_names = request.POST.getlist('income_name')
        income_categories = request.POST.getlist('income_category')

        if income_names:
            if "Salary" in income_categories:
                salary_starting_amounts = request.POST.getlist('salary_starting_amount')
                salary_yearly_changes = request.POST.getlist('salary_yearly_change')
                salary_bonus_rates = request.POST.getlist('salary_bonus_rate')
                salary_tax_rates = request.POST.getlist('salary_tax_rate')
                salary_tax_rate_changes = request.POST.getlist('salary_tax_rate_change')
                salary_start_ages = request.POST.getlist('salary_start_age')
                salary_stop_ages = request.POST.getlist('salary_stop_age')
                for age in salary_start_ages:
                    if age != "Current Age":
                        if int(age) < current_age:
                            return "Salary start age can not be less than current age."
                        if int(age) >= retirement_age:
                            return "Salary start age can not be greater than or equal to retirement age."
                for age in salary_stop_ages:
                    if age != "Target Retirement Age":
                        if int(age) < current_age:
                            return "Salary stop age can not be less than current age."
                        if int(age) >= retirement_age:
                            return "Salary stop age can not be greater than or equal to retirement age."

            if "Recurring" in income_categories:
                recurring_income_starting_amounts = request.POST.getlist('recurring_income_starting_amount')
                recurring_income_yearly_changes = request.POST.getlist('recurring_income_yearly_change')
                recurring_income_tax_rates = request.POST.getlist('recurring_income_tax_rate')
                recurring_income_tax_rate_changes = request.POST.getlist('recurring_income_tax_rate_change')
                recurring_income_start_ages = request.POST.getlist('recurring_income_start_age')
                recurring_income_stop_ages = request.POST.getlist('recurring_income_stop_age')
                for age in recurring_income_start_ages:
                    if age != "Current Age":
                        if int(age) < current_age:
                            return "Recurring income start age can not be less than current age."
                        if int(age) >= retirement_age:
                            return "Recurring income start age can not be greater than or equal to retirement age."
                for age in recurring_income_stop_ages:
                    if age != "Target Retirement Age":
                        if int(age) < current_age:
                            return "Recurring income stop age can not be less than current age."
                        if int(age) >= retirement_age:
                            return "Recurring income stop age can not be greater than or equal to retirement age."

            if "One-time" in income_categories:
                one_time_income_amounts = request.POST.getlist('one_time_income_amount')
                one_time_income_ages = request.POST.getlist('one_time_income_age')
                one_time_income_tax_rates = request.POST.getlist('one_time_income_tax_rate')
                if len([age for age in one_time_income_ages if int(age) < current_age]) != 0:
                    return "One-time income age can not be less than current age."
                if len([age for age in one_time_income_ages if int(age) > retirement_age]) != 0:
                    return "One-time income age can not be greater than or equal to retirement age."

            incomes = []
            salary_idx = 0
            recurring_income_idx = 0
            one_time_income_idx = 0
            for category, name in zip(income_categories, income_names):
                income = {'income_category': category, 'income_name': name}
                if category == "Salary":
                    income['starting_amount'] = int(salary_starting_amounts[salary_idx])
                    income['yearly_change'] = float(salary_yearly_changes[salary_idx])
                    income['bonus_rate'] = float(salary_bonus_rates[salary_idx])
                    income['tax_rate'] = float(salary_tax_rates[salary_idx])
                    income['tax_rate_change'] = float(salary_tax_rate_changes[salary_idx])
                    if salary_start_ages[salary_idx] =="Current Age":
                        income['start_age'] = salary_start_ages[salary_idx]
                    elif int(salary_start_ages[salary_idx]) == current_age:
                        income['start_age'] = "Current Age"
                    else:
                        income['start_age'] = int(salary_start_ages[salary_idx])
                    if salary_stop_ages[salary_idx] =="Target Retirement Age":
                        income['stop_age'] = salary_stop_ages[salary_idx]
                    elif int(salary_stop_ages[salary_idx]) == retirement_age-1:
                        income['stop_age'] = "Target Retirement Age"
                    else:
                        income['stop_age'] = int(salary_stop_ages[salary_idx])
                    incomes.append(income)
                    salary_idx += 1

                elif category == "Recurring":
                    income['starting_amount'] = int(recurring_income_starting_amounts[recurring_income_idx])
                    income['yearly_change'] = float(recurring_income_yearly_changes[recurring_income_idx])
                    income['tax_rate'] = float(recurring_income_tax_rates[recurring_income_idx])
                    income['tax_rate_change'] = float(recurring_income_tax_rate_changes[recurring_income_idx])
                    if recurring_income_start_ages[recurring_income_idx] =="Current Age":
                        income['start_age'] = recurring_income_start_ages[recurring_income_idx]
                    elif int(recurring_income_start_ages[recurring_income_idx]) == current_age:
                        income['start_age'] = "Current Age"
                    else:
                        income['start_age'] = int(recurring_income_start_ages[recurring_income_idx])
                    if recurring_income_stop_ages[recurring_income_idx] =="Target Retirement Age":
                        income['stop_age'] = recurring_income_stop_ages[recurring_income_idx]
                    elif int(recurring_income_stop_ages[recurring_income_idx]) == retirement_age-1:
                        income['stop_age'] = "Target Retirement Age"
                    else:
                        income['stop_age'] = int(recurring_income_stop_ages[recurring_income_idx])
                    incomes.append(income)
                    recurring_income_idx += 1

                elif category == "One-time":
                    income['amount'] = int(one_time_income_amounts[one_time_income_idx])
                    income['age'] = int(one_time_income_ages[one_time_income_idx])
                    income['tax_rate'] = float(one_time_income_tax_rates[one_time_income_idx])
                    incomes.append(income)
                    one_time_income_idx += 1
                else:
                    return "Invalid income category."
                
            # print(incomes)
        
        else:
            return "No incomes provided."
        
    except Exception as e:
        print(f"Error in Incomes: {e}")
        return "Invalid income input provided."
    
    try:
        #Expenses
        expense_names = request.POST.getlist('expense_name')
        expense_categories = request.POST.getlist('expense_category')

        if expense_names:
            if "Recurring" in expense_categories:
                recurring_expense_starting_amounts = request.POST.getlist('recurring_expense_starting_amount')
                recurring_expense_yearly_changes = request.POST.getlist('recurring_expense_yearly_change')
                recurring_expense_start_ages = request.POST.getlist('recurring_expense_start_age')
                recurring_expense_stop_ages = request.POST.getlist('recurring_expense_stop_age')
                for age in recurring_expense_start_ages:
                    if age != "Current Age":
                        if int(age) < current_age:
                            return "Salary start age can not be less than current age."
                        if int(age) >= retirement_age:
                            return "Salary start age can not be greater than or equal to retirement age."
                for age in recurring_expense_stop_ages:
                    if age != "Target Retirement Age":
                        if int(age) < current_age:
                            return "Salary stop age can not be less than current age."
                        if int(age) >= retirement_age:
                            return "Salary stop age can not be greater than or equal to retirement age."

            if "One-time" in expense_categories:
                one_time_expense_amounts = request.POST.getlist('one_time_expense_amount')
                one_time_expense_ages = request.POST.getlist('one_time_expense_age')
                if len([age for age in one_time_expense_ages if int(age) < current_age]) != 0:
                    return "One-time expense age can not be less than current age."
                if len([age for age in one_time_expense_ages if int(age) > retirement_age]) != 0:
                    return "One-time expense age can not be greater than or equal to retirement age."

            expenses = []

            recurring_expense_idx = 0
            one_time_expense_idx = 0

            for category, name in zip(expense_categories, expense_names):
                expense = {'expense_category': category, 'expense_name': name}
                if category == "Recurring":
                    expense['starting_amount'] = int(recurring_expense_starting_amounts[recurring_expense_idx])
                    expense['yearly_change'] = float(recurring_expense_yearly_changes[recurring_expense_idx])
                    if recurring_expense_start_ages[recurring_expense_idx] =="Current Age":
                        expense['start_age'] = recurring_expense_start_ages[recurring_expense_idx]
                    elif int(recurring_expense_start_ages[recurring_expense_idx]) == current_age:
                        expense['start_age'] = "Current Age"
                    else:
                        expense['start_age'] = int(recurring_expense_start_ages[recurring_expense_idx])
                    if recurring_expense_stop_ages[recurring_expense_idx] =="Target Retirement Age":
                        expense['stop_age'] = recurring_expense_stop_ages[recurring_expense_idx]
                    elif int(recurring_expense_stop_ages[recurring_expense_idx]) == retirement_age-1:
                        expense['stop_age'] = "Target Retirement Age"
                    else:
                        expense['stop_age'] = int(recurring_expense_stop_ages[recurring_expense_idx])
                    expenses.append(expense)
                    recurring_expense_idx += 1

                elif category == "One-time":
                    expense['amount'] = int(one_time_expense_amounts[one_time_expense_idx])
                    expense['age'] = int(one_time_expense_ages[one_time_expense_idx])
                    expenses.append(expense)
                    one_time_expense_idx += 1

                else:
                    return "Invalid expense category."
                
            # print(expenses)
        else:
            return "No expenses provided"
        
    except Exception as e:
        print(f"Error in Expenses: {e}")
        return "Invalid expense input provided."
        
    try:
        saving_option = request.POST.get('saving_option')
        print(saving_option)
        savings = [saving_option]
        if saving_option == 'Simple':
            simple_net_worth = int(request.POST.get('simple_net_worth'))
            simple_yearly_growth = float(request.POST.get('simple_yearly_growth'))
            savings.append({'simple_net_worth': simple_net_worth, 'simple_yearly_growth': simple_yearly_growth})
        else:
            #Savings
            saving_names = request.POST.getlist('saving_name')
            saving_categories = request.POST.getlist('saving_category')

            if saving_names:
                if "ESRP" in saving_categories:
                    esrp_current_values = request.POST.get('esrp_current_value')
                    esrp_yearly_growths = request.POST.get('esrp_yearly_growth')
                    esrp_contribution_rates = request.POST.get('esrp_contribution_rate')
                    esrp_contribution_limit = request.POST.get('esrp_contribution_limit')
                    esrp_contribution_limit_steps = request.POST.get('esrp_contribution_limit_step')
                    
                if "HSA" in saving_categories:
                    hsa_current_values = request.POST.get('hsa_current_value')
                    hsa_yearly_growths = request.POST.get('hsa_yearly_growth')
                    hsa_contribution_limit = request.POST.get('hsa_contribution_limit')
                    hsa_contribution_limit_steps = request.POST.get('hsa_contribution_limit_step')

                if "IRA" in saving_categories:
                    ira_current_values = request.POST.get('ira_current_value')
                    ira_yearly_growths = request.POST.get('ira_yearly_growth')
                    ira_contribution_limit = request.POST.get('ira_contribution_limit')
                    ira_contribution_limit_steps = request.POST.get('ira_contribution_limit_step')
                    
                if "TBA" in saving_categories:
                    tba_current_values = request.POST.get('tba_current_value')
                    tba_yearly_growths = request.POST.get('tba_yearly_growth')

                for category, name in zip(saving_categories, saving_names):
                    saving = {'saving_category': category, 'saving_name': name}
                    if category == "ESRP":
                        saving['current_value'] = int(esrp_current_values)
                        saving['yearly_growth'] = float(esrp_yearly_growths)
                        saving['employer_contribution_rate'] = float(esrp_contribution_rates)
                        saving['contribution_limit'] = int(esrp_contribution_limit)
                        saving['contribution_limit_step'] = int(esrp_contribution_limit_steps)
                        savings.append(saving)

                    elif category == "HSA":
                        saving['current_value'] = int(hsa_current_values)
                        saving['yearly_growth'] = float(hsa_yearly_growths)
                        saving['contribution_limit'] = int(hsa_contribution_limit)
                        saving['contribution_limit_step'] = int(hsa_contribution_limit_steps)
                        savings.append(saving)
                    
                    elif category == "IRA":
                        saving['current_value'] = int(ira_current_values)
                        saving['yearly_growth'] = float(ira_yearly_growths)
                        saving['contribution_limit'] = int(ira_contribution_limit)
                        saving['contribution_limit_step'] = int(ira_contribution_limit_steps)
                        savings.append(saving)

                    elif category == "TBA":
                        saving['current_value'] = int(tba_current_values)
                        saving['yearly_growth'] = float(tba_yearly_growths)
                        savings.append(saving)

                    else:
                        return "Invalid saving category."
                    
            else:
                return "No savings provided."
        
        # print(savings)
            
    except Exception as e:
        print(f"Error in Savings: {e}")
        return "Invalid saving input provided."  
    
    try:
        plan = self.save(commit=False)
        if request.POST.get('coast_fire_age'):
            plan.coast_fire_age = coast_fire_age
        else:
            plan.coast_fire_age = None  
        if str(request.user) != "AnonymousUser":
            plan.user = request.user
        plan.incomes = incomes
        plan.expenses = expenses
        plan.savings = savings
        plan.save()
        return plan
    except Exception as e:
        print(f"Error Saving: {e}")
        return "Error saving plan, please try again."
    
class PlanObject:
    # Function: __init__
    def __init__(self, plan):
        try:
            self.plan = plan
            self.years_until_retirement = self.plan.retirement_age - self.plan.current_age
            if self.plan.coast_fire_age:
                self.years_until_coast_fire = self.plan.coast_fire_age - self.plan.current_age
            else:
                self.years_until_coast_fire = self.plan.retirement_age - self.plan.current_age
        except Exception as e:
            print(f"init: {e}")

    # Function: Personal Infos
    def personal_infos(self):
        
        try:
            # Ages
            ages = [self.plan.current_age + year for year in range(0,self.years_until_retirement)]
            self.ages = ages
            ages_display = [self.plan.current_age + year for year in range(0,self.years_until_retirement)]
            ages_display[0] = "Current Age"
            ages_display[-1] = "Target Retirement Age"
            self.ages_display = ages_display
            # Years
            years = [date.today().year + year for year in range(0,self.years_until_retirement)]
            self.years = years
            # Range
            data_iter = [num for num in range(0,self.years_until_retirement)]
            self.data_iter = data_iter
        except Exception as e:
            print(f"personal_infos: {e}")
    
    def incomes(self):

        try:
            self.incomes = self.plan.incomes
            total_gross_income = []
            total_bonuses = []
            total_taxes = []
            total_net_income = []
            total_salary_income = []
            total_recurring_income = []
            total_one_time_income = []
            salary_count = 0
            recurring_count = 0
            one_time_count = 0

            for income in self.incomes:
                #Salary
                if income['income_category'] == 'Salary':
                    income['category_index'] = salary_count
                    salary_count += 1
                    if income['start_age'] == "Current Age":
                        income['start_age_num'] = self.plan.current_age
                    else:
                        income['start_age_num'] = int(income['start_age'])
                    if income['stop_age'] == "Target Retirement Age":
                        income['stop_age_num'] = self.plan.retirement_age - 1
                    else:
                        income['stop_age_num'] = int(income['stop_age'])
                    income_age_range = [age for age in range(income['start_age_num'],income['stop_age_num']+1)]
                    gross_amounts = [math.floor(income['starting_amount'] * ((1 + round(income['yearly_change']/100,3)) ** year)) for year in range(0,len(income_age_range))]
                    gross_amounts_dict = dict(zip(income_age_range, gross_amounts))
                    income['gross_amounts'] = [gross_amounts_dict[age] if age in gross_amounts_dict else 0 for age in self.ages]
                    income['bonus_amounts'] = [math.floor(income['gross_amounts'][year] * round(income['bonus_rate']/100,3)) for year in range(0,self.years_until_retirement)]
                    tax_rates = [round(((income['tax_rate']) + (year * income['tax_rate_change'])),3) for year in range(0,len(income_age_range))]
                    tax_rates_dict = dict(zip(income_age_range,tax_rates))
                    income['tax_rates'] = [tax_rates_dict[age] if age in tax_rates_dict else 0 for age in self.ages]
                    income['tax_amounts'] = [math.floor((income['gross_amounts'][year] + income['bonus_amounts'][year]) * round(income['tax_rates'][year]/100,3)) for year in range(0,self.years_until_retirement)]
                    income['net_amounts'] = [math.floor(income['gross_amounts'][year] + income['bonus_amounts'][year] - income['tax_amounts'][year]) for year in range(0,self.years_until_retirement)]
                    total_salary_income.append(income['gross_amounts'])
                    total_gross_income.append(income['gross_amounts'])
                    total_gross_income.append(income['bonus_amounts'])
                    total_bonuses.append(income['bonus_amounts'])
                    total_taxes.append(income['tax_amounts'])
                    total_net_income.append(income['net_amounts'])
                #Recurring
                elif income['income_category'] == 'Recurring':
                    income['category_index'] = recurring_count
                    recurring_count += 1
                    if income['start_age'] == "Current Age":
                        income['start_age_num'] = self.plan.current_age
                    else:
                        income['start_age_num'] = int(income['start_age'])
                    if income['stop_age'] == "Target Retirement Age":
                        income['stop_age_num'] = self.plan.retirement_age - 1
                    else:
                        income['stop_age_num'] = int(income['stop_age'])
                    income_age_range = [age for age in range(income['start_age_num'],income['stop_age_num']+1)]
                    gross_amounts = [math.floor(income['starting_amount'] * ((1 + round(income['yearly_change']/100,3)) ** year)) for year in range(0,len(income_age_range))]
                    gross_amounts_dict = dict(zip(income_age_range, gross_amounts))
                    income['gross_amounts'] = [gross_amounts_dict[age] if age in gross_amounts_dict else 0 for age in self.ages]
                    tax_rates = [round(((income['tax_rate']) + (year * income['tax_rate_change'])),3) for year in range(0,len(income_age_range))]
                    tax_rates_dict = dict(zip(income_age_range,tax_rates))
                    income['tax_rates'] = [tax_rates_dict[age] if age in tax_rates_dict else 0 for age in self.ages]
                    income['tax_amounts'] = [math.floor((income['gross_amounts'][year]) * round(income['tax_rates'][year]/100,3)) for year in range(0,self.years_until_retirement)]
                    income['net_amounts'] = [math.floor(income['gross_amounts'][year] - income['tax_amounts'][year]) for year in range(0,self.years_until_retirement)]
                    total_recurring_income.append(income['gross_amounts'])
                    total_gross_income.append(income['gross_amounts'])
                    total_taxes.append(income['tax_amounts'])
                    total_net_income.append(income['net_amounts'])
                #One-time
                else:
                    income['category_index'] = one_time_count
                    one_time_count += 1
                    income['gross_amounts'] = [income['amount'] if age is income['age'] else 0 for age in self.ages]
                    income['tax_amounts'] = [math.floor(income['gross_amounts'][year] * round(income['tax_rate']/100,3)) for year in range(0,self.years_until_retirement)]
                    income['net_amounts'] = income['net_amounts'] = [math.floor(income['gross_amounts'][year] - income['tax_amounts'][year]) for year in range(0,self.years_until_retirement)]
                    total_one_time_income.append(income['gross_amounts'])
                    total_gross_income.append(income['gross_amounts'])
                    total_taxes.append(income['tax_amounts'])
                    total_net_income.append(income['net_amounts'])
            
            #Totals
            self.total_salary_income = [sum(amount) for amount in zip(*total_salary_income)]
            self.total_recurring_income = [sum(amount) for amount in zip(*total_recurring_income)]
            self.total_one_time_income = [sum(amount) for amount in zip(*total_one_time_income)]
            self.total_gross_income = [sum(amount) for amount in zip(*total_gross_income)]
            self.total_bonuses = [sum(amount) for amount in zip(*total_bonuses)]
            self.total_taxes = [sum(amount) for amount in zip(*total_taxes)]
            self.total_net_income = [sum(amount) for amount in zip(*total_net_income)] 
        except Exception as e:
            print(f"incomes: {e}")
        
    def expenses(self):

        try:
            self.expenses = self.plan.expenses
            total_expenses = []
            total_recurring_expenses = []
            total_one_time_expenses = []
            recurring_count = 0
            one_time_count = 0

            for expense in self.expenses:
                #Recurring
                if expense['expense_category'] == 'Recurring':
                    expense['category_index'] = recurring_count
                    recurring_count += 1
                    if expense['start_age'] == "Current Age":
                        expense['start_age_num'] = self.plan.current_age
                    else:
                        expense['start_age_num'] = int(expense['start_age'])
                    if expense['stop_age'] == "Target Retirement Age":
                        expense['stop_age_num'] = self.plan.retirement_age - 1
                    else:
                        expense['stop_age_num'] = int(expense['stop_age'])
                    expense_age_range = [age for age in range(expense['start_age_num'],expense['stop_age_num']+1)]
                    expense_amounts = [math.floor(expense['starting_amount'] * ((1 + round(expense['yearly_change']/100,3)) ** year)) for year in range(0,len(expense_age_range))]
                    expense_amounts_dict = dict(zip(expense_age_range, expense_amounts))
                    expense['amounts'] = [expense_amounts_dict[age] if age in expense_amounts_dict else 0 for age in self.ages]
                    total_expenses.append(expense['amounts'])
                    total_recurring_expenses.append(expense['amounts'])
                #One-time
                else:
                    expense['category_index'] = one_time_count
                    one_time_count += 1
                    expense['amounts'] = [expense['amount'] if age is expense['age'] else 0 for age in self.ages]
                    total_expenses.append(expense['amounts'])
                    total_one_time_expenses.append(expense['amounts'])

                #Totals
                self.total_expenses = [sum(amount) for amount in zip(*total_expenses)]
                self.total_recurring_expenses = [sum(amount) for amount in zip(*total_recurring_expenses)]
                self.total_one_time_expenses = [sum(amount) for amount in zip(*total_one_time_expenses)]
        except Exception as e:
            print(f"expenses: {e}")

    def savings(self):
        try:
            self.total_savings = [self.total_net_income[year] - self.total_expenses[year] if year < self.years_until_coast_fire else 0 for year in range(0,self.years_until_retirement)]
        except Exception as e:
            print(f"savings: {e}")

    def yearly_contribution_limits(self):
        
        try:
            self.accounts = self.plan.savings

            if self.accounts[0] != 'Simple':
                for account in self.accounts[1:]:
                    if account['saving_category'] != 'TBA':
                        account['contribution_limits'] = [account['contribution_limit'] + (year * account['contribution_limit_step']) for year in range(0,self.years_until_retirement)]
        except Exception as e:
            print(f"yearly_contribution_limits: {e}")
    
    def yearly_contributions(self):

        try:
            if self.accounts[0] == 'Simple':
                self.accounts[1]['contribution_amounts'] = self.total_savings
            else:
                #1. Create list of account types within self.accounts
                account_types = [account['saving_category'] for account in self.accounts[1:]]

                #2. Pull out from self.accounts the account dictionaries for HSA, ESRP and IRA types (it is ok if they do not exist)
                hsa = [account for account in self.accounts[1:] if account['saving_category'] == 'HSA']
                esrp = [account for account in self.accounts[1:] if account['saving_category'] == 'ESRP']
                ira = [account for account in self.accounts[1:] if account['saving_category'] == 'IRA']

                #3. Create blank lists to store contribution amounts for each account type
                hsa_contribution_amounts = []
                esrp_contribution_amounts = []
                esrp_employer_contribution_amounts = []
                ira_contribution_amounts = []
                tba_contribution_amounts = []

                #4. Loop through each year:
                for year in range(0,self.years_until_retirement):

                    #4a. Define maximum amount of savings to allocate
                    saving_amount = self.total_savings[year]
                    if saving_amount > 0:
                        #4b. ESRP Employer Contributions
                        if 'ESRP' in account_types:
                            employer_contribution_amount = math.floor(round(esrp[0]['employer_contribution_rate']/100,3) * self.total_salary_income[year])
                            if saving_amount >= employer_contribution_amount:
                                esrp_employer_contribution_amounts.append(employer_contribution_amount)
                                esrp_contribution_amounts.append(employer_contribution_amount)
                                saving_amount -= employer_contribution_amount
                            elif saving_amount > 0:
                                esrp_employer_contribution_amounts.append(saving_amount)
                                esrp_contribution_amounts.append(saving_amount)
                                saving_amount -= saving_amount
                            else:
                                esrp_employer_contribution_amounts.append(saving_amount)
                                esrp_contribution_amounts.append(0)
                        #4c. HSA Contributions
                        if 'HSA' in account_types:
                            if saving_amount >= hsa[0]['contribution_limits'][year]:
                                hsa_contribution_amounts.append(hsa[0]['contribution_limits'][year])
                                saving_amount -= hsa[0]['contribution_limits'][year]
                            elif saving_amount > 0:
                                hsa_contribution_amounts.append(saving_amount)
                                saving_amount -= saving_amount
                            else:
                                hsa_contribution_amounts.append(0)
                        #4d. ESRP Contributions
                        if 'ESRP' in account_types:
                            if saving_amount >= esrp[0]['contribution_limits'][year]:
                                esrp_contribution_amounts[year] = esrp[0]['contribution_limits'][year]
                                saving_amount -= esrp[0]['contribution_limits'][year] - employer_contribution_amount
                            elif saving_amount > 0:
                                esrp_contribution_amounts[year] += saving_amount
                                saving_amount -= saving_amount
                            else:
                                esrp_contribution_amounts[year] = esrp_contribution_amounts[year]
                        #4e. IRA Contributions
                        if 'IRA' in account_types:
                            if saving_amount >= ira[0]['contribution_limits'][year]:
                                ira_contribution_amounts.append(ira[0]['contribution_limits'][year])
                                saving_amount -= ira[0]['contribution_limits'][year]
                            elif saving_amount > 0:
                                ira_contribution_amounts.append(saving_amount)
                                saving_amount -= saving_amount
                            else:
                                ira_contribution_amounts.append(0)
                        #4f. TBA Contributions
                        if 'TBA' in account_types:
                            if saving_amount > 0:
                                tba_contribution_amounts.append(saving_amount)
                                saving_amount -= saving_amount
                            else:
                                tba_contribution_amounts.append(0)
                    else:
                        if 'TBA' in account_types:
                            tba_contribution_amounts.append(saving_amount)
                            hsa_contribution_amounts.append(0)
                            esrp_contribution_amounts.append(0)
                            esrp_employer_contribution_amounts.append(0)
                            ira_contribution_amounts.append(0)


                #5. Append contribution_amount lists defined in step 3 to their corresponding account dictionary within self.accounts
                for account in self.accounts[1:]:
                    if account['saving_category'] == "HSA":
                        account['contribution_amounts'] = hsa_contribution_amounts
                    if account['saving_category'] == "ESRP":
                        account['contribution_amounts'] = esrp_contribution_amounts
                        account['employer_contribution_amounts'] = esrp_employer_contribution_amounts
                    if account['saving_category'] == "IRA":
                        account['contribution_amounts'] = ira_contribution_amounts
                    if account['saving_category'] == "TBA":
                        account['contribution_amounts'] = tba_contribution_amounts
                
                self.hsa_contribution_amounts = hsa_contribution_amounts
                self.esrp_contribution_amounts = esrp_contribution_amounts
                self.esrp_employer_contribution_amounts = esrp_employer_contribution_amounts
                self.ira_contribution_amounts = ira_contribution_amounts
                self.tba_contribution_amounts = tba_contribution_amounts

        except Exception as e:
            print(f"yearly_contributions: {e}")

    def start_end_amounts(self):
        try:
            if self.accounts[0] == 'Simple':
                start_amounts = [self.accounts[1]['simple_net_worth']]
                end_amounts = []
                for year in range(0,self.years_until_retirement):
                    end_amounts.append(math.floor((start_amounts[year] + self.accounts[1]['contribution_amounts'][year]) * (1 + round(self.accounts[1]['simple_yearly_growth']/100,3))))

                    if year != self.years_until_retirement - 1:
                        start_amounts.append(math.floor(end_amounts[year]))
                
                self.accounts[1]['start_amounts'] = start_amounts
                self.accounts[1]['end_amounts'] = end_amounts
            else:
                for account in self.accounts[1:]:
                    if account['saving_category'] != "ESRP":
                        start_amounts= [account['current_value']]
                        end_amounts = []
                        for year in range(0,self.years_until_retirement):
                            end_amounts.append(math.floor((start_amounts[year] + account['contribution_amounts'][year]) * (1 + round(account['yearly_growth']/100,3))))

                            if year != self.years_until_retirement - 1:
                                start_amounts.append(math.floor(end_amounts[year]))
                        
                        account['start_amounts'] = start_amounts
                        account['end_amounts'] = end_amounts
                
                    else:
                        start_amounts= [account['current_value']]
                        end_amounts = []
                        for year in range(0,self.years_until_retirement):
                            end_amounts.append(math.floor((start_amounts[year] + account['contribution_amounts'][year] + account['employer_contribution_amounts'][year]) * (1 + round(account['yearly_growth']/100,3))))

                            if year != self.years_until_retirement - 1:
                                start_amounts.append(math.floor(end_amounts[year]))
                                
                        account['start_amounts'] = start_amounts
                        account['end_amounts'] = end_amounts
        except Exception as e:
            print(f"start_end_amounts: {e}")
    
    def fi_indicators(self):
        
        try:
            #Net Worths
            net_worths = []
            if self.accounts[0] == 'Simple':
                self.net_worths = self.accounts[1]['end_amounts']
                self.net_worths_last = '${:,}'.format(self.accounts[1]['end_amounts'][-1])
            else:
                for account in self.accounts[1:]:
                    net_worths.append(account['end_amounts'])
                self.net_worths = [sum(amount) for amount in zip(*net_worths)]
                self.net_worths_last = '${:,}'.format(self.net_worths[-1])

            # Magic Numbers
            self.magic_numbers = [(self.total_recurring_expenses[year] * 25) for year in range(0,self.years_until_retirement)]
            self.magic_numbers_last = '${:,}'.format(self.magic_numbers[-1])

            # Drawdowns
            self.drawdowns = [round((self.total_expenses[year] / self.net_worths[year]) * 100,2) for year in range(0,self.years_until_retirement)]
            self.drawdowns_last = str(self.drawdowns[-1]) + "%"

            # FI Age
            for index, (a,b) in enumerate(zip(self.net_worths,self.magic_numbers)):
                if a > b:
                    self.fi_age = self.ages[index]
                    break
                else:
                    self.fi_age = "N/A"
        except Exception as e:
            print(f"fi_indicators: {e}")

    def template_data(self):

        try:
            plan_data = []
            for year in range(0,self.years_until_retirement):
                year_data = []
                
                year_data.append(self.ages[year])

                year_data.append(self.years[year])

                for income in self.incomes:
                    if income['income_category'] == 'Salary':
                        year_data.append('${:,}'.format(income['gross_amounts'][year]))
                        year_data.append('${:,}'.format(income['bonus_amounts'][year]))
                        year_data.append('${:,}'.format(income['tax_amounts'][year]))
                        year_data.append('${:,}'.format(income['net_amounts'][year]))
                    else:
                        year_data.append('${:,}'.format(income['gross_amounts'][year]))
                        year_data.append('${:,}'.format(income['tax_amounts'][year]))
                        year_data.append('${:,}'.format(income['net_amounts'][year]))

                for expense in self.expenses:
                    year_data.append('${:,}'.format(expense['amounts'][year]))

                year_data.append('${:,}'.format(self.total_savings[year]))

                if self.accounts[0] == 'Simple':
                    year_data.append('${:,}'.format(self.accounts[1]['start_amounts'][year]))
                    year_data.append('${:,}'.format(self.accounts[1]['contribution_amounts'][year]))
                    year_data.append('${:,}'.format(self.accounts[1]['end_amounts'][year]))
                else:
                    for account in self.accounts[1:]:
                        if account['saving_category'] == 'ESRP':
                            year_data.append('${:,}'.format(account['start_amounts'][year]))
                            year_data.append('${:,}'.format(account['contribution_limits'][year]))
                            year_data.append('${:,}'.format(account['contribution_amounts'][year]))
                            year_data.append('${:,}'.format(account['employer_contribution_amounts'][year]))
                            year_data.append('${:,}'.format(account['end_amounts'][year]))
                        elif account['saving_category'] == 'IRA' or account['saving_category'] == 'HSA':
                            year_data.append('${:,}'.format(account['start_amounts'][year]))
                            year_data.append('${:,}'.format(account['contribution_limits'][year]))
                            year_data.append('${:,}'.format(account['contribution_amounts'][year]))
                            year_data.append('${:,}'.format(account['end_amounts'][year]))
                        else:
                            year_data.append('${:,}'.format(account['start_amounts'][year]))
                            year_data.append('${:,}'.format(account['contribution_amounts'][year]))
                            year_data.append('${:,}'.format(account['end_amounts'][year]))

                year_data.append('${:,}'.format(self.net_worths[year]))
                year_data.append('${:,}'.format(self.magic_numbers[year]))
                year_data.append(str(self.drawdowns[year]) + '%')

                plan_data.append(year_data)
            
            self.plan_data = plan_data
        except Exception as e:
            print(f"teamplate_data: {e}")

    def update_final_net_worth(self):
        try:
            self.plan.final_net_worth = self.net_worths_last
            self.plan.save()
        except Exception as e:
            print(f"update_final_net_worth: {e}")

    def sankey_chart(self):

        # Values for each flow (use sum for the plan period)
        income_sum = sum(self.total_gross_income)
        salary_sum = sum(self.total_salary_income)
        bonus_sum = sum(self.total_bonuses)
        recurring_income_sum = sum(self.total_recurring_income)
        one_time_income_sum = sum(self.total_one_time_income)

        expenses_sum = sum(self.total_expenses)
        recurring_expenses_sum = sum(self.total_recurring_expenses)
        one_time_expenses_sum = sum(self.total_one_time_expenses)
        tax_sum = sum(self.total_taxes)

        savings_sum = sum(self.total_savings)
        hsa_sum = sum(self.hsa_contribution_amounts)
        retirement_sum = sum(self.esrp_contribution_amounts)
        ira_sum = sum(self.ira_contribution_amounts)
        tba_sum = sum(self.tba_contribution_amounts)
        employer_sum = sum(self.esrp_employer_contribution_amounts)

        labels = []
        values = []
        sources = []
        targets = []

        labels.append("Total Income")
        income_counter = 0
        if salary_sum:
            labels.append("Salary")
            values.append(salary_sum)
            income_counter += 1
            sources.append(income_counter)
            targets.append(0)
        if bonus_sum:
            labels.append("Bonuses")
            values.append(bonus_sum)
            income_counter += 1
            sources.append(income_counter)
            targets.append(0)
        if recurring_income_sum:
            labels.append("Recurring")
            values.append(recurring_income_sum)
            income_counter += 1
            sources.append(income_counter)
            targets.append(0)
        if one_time_income_sum:
            labels.append("One-time")
            values.append(one_time_income_sum)
            income_counter += 1
            sources.append(income_counter)
            targets.append(0)

        sources.extend([0, 0, 0])
        labels.append("Taxes")
        values.append(tax_sum)
        targets.append(income_counter + 1)
        
        labels.append("Total Expenses")
        values.append(expenses_sum)
        targets.append(income_counter + 2)
        expense_counter = 0
        if recurring_expenses_sum:
            labels.append("Recurring")
            values.append(recurring_expenses_sum)
            expense_counter += 1
            sources.append(income_counter + 2)
            targets.append(income_counter + 2 + expense_counter)
        if one_time_expenses_sum:
            labels.append("One-time")
            values.append(one_time_expenses_sum)
            expense_counter += 1
            sources.append(income_counter + 2)
            targets.append(income_counter + 2 + expense_counter)

        targets.insert(len(targets)-expense_counter, income_counter + 2 + expense_counter + 1)

        labels.append("Total Savings")
        values.insert(len(targets)-expense_counter-1, savings_sum)
        saving_counter = 0
        if hsa_sum:
            labels.append("HSA")
            values.append(hsa_sum)
            saving_counter += 1
            sources.append(income_counter + 2 + expense_counter + 1)
            targets.append(income_counter + 2 + expense_counter + saving_counter + 1)
        if ira_sum:
            labels.append("IRA")
            values.append(ira_sum)
            saving_counter += 1
            sources.append(income_counter + 2 + expense_counter + 1)
            targets.append(income_counter + 2 + expense_counter + saving_counter + 1)
        if tba_sum:
            labels.append("TBA")
            values.append(tba_sum)
            saving_counter += 1
            sources.append(income_counter + 2 + expense_counter + 1)
            targets.append(income_counter + 2 + expense_counter + saving_counter + 1)
        if retirement_sum:
            labels.append("401k/403b")
            values.append(retirement_sum)
            saving_counter += 1
            sources.append(income_counter + 2 + expense_counter + 1)
            targets.append(income_counter + 2 + expense_counter + saving_counter + 1)
        if employer_sum:
            labels.append("Employer Contribution")
            values.append(employer_sum)
            saving_counter += 1
            sources.append(income_counter + 2 + expense_counter + saving_counter + 1)
            targets.append(income_counter + 2 + expense_counter + saving_counter)

        # Create Sankey Chart
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
                color=["#DFF5F1"]*income_counter + ["#FFEDDD"]*2 + ["#EDE6F8"]+ ["#FFEDDD"]*expense_counter + ["#EDE6F8"]*saving_counter
            ),
        )])
        fig.update_layout(
            title = {
                "text": f"Total Cash Flow: {self.plan.current_age} to {self.plan.retirement_age - 1}",
                "font": {
                    'color': '#777980',
                    'family': 'Inter',
                    'size': 16,
                    'style': 'normal',
                    'weight': 500,
                },
            },
            title_x=0.05,
            paper_bgcolor="#FCFBF9",
            plot_bgcolor="#FCFBF9",
            font=dict(
                family = "Inter",
                size = 16,
                color = "black"
            )
        )
        fig.update_traces(
            node_color=["#285C53"]*(1+income_counter) + ["#EC652B"]*(2+expense_counter) + ["#4F378A"]*(1+saving_counter)
        )

        return fig.to_html(full_html=True)

class FIRE:
    # Function: __init__
    def __init__(self, simulation):
        self.simulation = simulation
        self.years_until_retirement = self.simulation.estimated_retirement_age - self.simulation.current_age
        if self.simulation.estimated_coastfire_age:
            self.years_until_coast_fire = self.simulation.estimated_coastfire_age - self.simulation.current_age
        else:
            self.years_until_coast_fire = self.simulation.estimated_retirement_age - self.simulation.current_age

    # Function: Personal Infos
    def personal_infos(self):
        
        # Ages
        ages = [self.simulation.current_age + year for year in range(0,self.years_until_retirement)]
        self.ages = ages
        # Years
        years = [date.today().year + year for year in range(0,self.years_until_retirement)]
        self.years = years

        # Return
        return ages, years

    # Function: Incomes
    def incomes(self):

        # Salaries
        salaries = [math.floor(self.simulation.current_yearly_salary * ((1 + round(self.simulation.estimated_salary_raise/100,3)) ** year)) for year in range(0,self.years_until_retirement)]
        self.salaries = salaries
        # Bonuses
        bonuses = [math.floor(salaries[year] * round(self.simulation.estimated_bonus/100,3)) for year in range(0,self.years_until_retirement)]
        self.bonuses = bonuses
        # Other Income
        other_income = [math.floor(self.simulation.current_yearly_other_income * ((1 + round(self.simulation.estimated_other_income_increase/100,3)) ** year)) for year in range(0,self.years_until_retirement)]
        self.other_income = other_income
        # Lump Sum Payments
        lump_sum_incomes_dict = dict(zip(list(map(int, self.simulation.estimated_lumpsum_income_ages)), list(map(int, self.simulation.estimated_lumpsum_income_amounts))))
        lump_sum_incomes = [lump_sum_incomes_dict[age] if age in lump_sum_incomes_dict else 0 for age in [self.simulation.current_age + year for year in range(0,self.years_until_retirement)]]
        self.lump_sum_incomes = lump_sum_incomes

        # Total Income
        total_income = [salaries[year] + bonuses[year] + other_income[year] + lump_sum_incomes[year] for year in range(0,self.years_until_retirement)]
        self.total_income = total_income

        # Return
        return total_income, salaries, bonuses, other_income, lump_sum_incomes
    
    # Function: Expenses
    def expenses(self):

        # Fixed Costs
        fixed_cost_adjustments_dict = dict(zip(list(map(int, self.simulation.estimated_fixed_cost_adjustment_ages)), list(map(float, self.simulation.estimated_fixed_cost_adjustments))))
        fixed_costs = [self.simulation.current_yearly_fixed_costs]
        idx = 0
        for age in [self.simulation.current_age + year for year in range(1,self.years_until_retirement)]:
            if age in fixed_cost_adjustments_dict:
                fixed_costs.append(math.floor(fixed_costs[idx] * (1+round(self.simulation.estimated_fixed_costs_inflation/100,3)+round(fixed_cost_adjustments_dict[age]/100,3))))
                idx += 1
            else:
                fixed_costs.append(math.floor(fixed_costs[idx] * (1+round(self.simulation.estimated_fixed_costs_inflation/100,3))))
                idx += 1
        self.fixed_costs = fixed_costs
        #Variable Costs
        variable_cost_adjustments_dict = dict(zip(list(map(int, self.simulation.estimated_variable_cost_adjustment_ages)), list(map(float, self.simulation.estimated_variable_cost_adjustments))))
        variable_costs = [self.simulation.current_yearly_variable_costs]
        idx = 0
        for age in [self.simulation.current_age + year for year in range(1,self.years_until_retirement)]:
            if age in variable_cost_adjustments_dict:
                variable_costs.append(math.floor(variable_costs[idx] * (1+round(self.simulation.estimated_variable_costs_inflation/100,3)+round(variable_cost_adjustments_dict[age]/100,3))))
                idx += 1
            else:
                variable_costs.append(math.floor(variable_costs[idx] * (1+round(self.simulation.estimated_variable_costs_inflation/100,3))))
                idx += 1
        self.variable_costs = variable_costs
        # Health Insurance
        health_insurance = [math.floor(self.simulation.current_yearly_health_insurance_cost * ((1 + round(self.simulation.estimated_health_insurance_inflation/100,3)) ** year)) for year in range(0,self.years_until_retirement)]
        self.health_insurance = health_insurance
        # Lump Sum Expenses
        lump_sum_expenses_dict = dict(zip(list(map(int, self.simulation.estimated_lumpsum_expense_ages)), list(map(int, self.simulation.estimated_lumpsum_expense_amounts))))
        lump_sum_expenses = [lump_sum_expenses_dict[age] if age in lump_sum_expenses_dict else 0 for age in [self.simulation.current_age + year for year in range(0,self.years_until_retirement)]]
        self.lump_sum_expenses = lump_sum_expenses    
        # Taxes
        tax_rates = [round(((self.simulation.estimated_tax_rate) + (year * self.simulation.estimated_tax_rate_step))/100,3) for year in range(0,self.years_until_retirement)]
        taxes = [math.floor((self.salaries[year] + self.bonuses[year] + self.other_income[year] + self.lump_sum_incomes[year]) * tax_rates[year]) for year in range(0,self.years_until_retirement)]
        self.taxes = taxes

        # Total Expenses
        total_expenses = [fixed_costs[year] + variable_costs[year] + health_insurance[year] + lump_sum_expenses[year] + taxes[year] for year in range(0,self.years_until_retirement)]
        self.total_expenses = total_expenses

        # Return
        return total_expenses, fixed_costs, variable_costs, health_insurance, lump_sum_expenses, taxes
    
    # Function: Savings
    def savings(self):
        #incorporate impact of a negative savings year - see contributions function for more details
        savings = [math.floor(self.salaries[year] + self.bonuses[year] + self.other_income[year] + self.lump_sum_incomes[year] - self.fixed_costs[year] - self.variable_costs[year] - self.health_insurance[year] - self.lump_sum_expenses[year] - self.taxes[year]) if year < self.years_until_coast_fire else 0 for year in range(0,self.years_until_retirement)]
        self.savings = savings

        # Return
        return savings
    
    # Function: Yearly Contribution Limits
    def yearly_contribution_limits(self):

        # HSA
        hsa_cont_limits = [self.simulation.current_hsa_yearly_contribution_limit + (year * self.simulation.estimated_hsa_yearly_contribution_limit_step) for year in range(0,self.years_until_retirement)]
        self.hsa_cont_limits = hsa_cont_limits
        # IRA
        ira_cont_limits = [self.simulation.current_ira_yearly_contribution_limit + (year * self.simulation.estimated_ira_yearly_contribution_limit_step) for year in range(0,self.years_until_retirement)]
        self.ira_cont_limits = ira_cont_limits
        # 401k/403b
        retirement_cont_limits = [self.simulation.current_401k_yearly_contribution_limit + (year * self.simulation.estimated_401k_yearly_contribution_limit_step) for year in range(0,self.years_until_retirement)]
        self.retirement_cont_limits = retirement_cont_limits

        # Return
        return hsa_cont_limits, ira_cont_limits, retirement_cont_limits
    
    # Function: Yearly Contributions
    def yearly_contributions(self):

        hsa_contributions = []
        ira_contributions = []
        retirement_contributions = []
        employer_retirement_contributions = []
        iba_contributions = []
        for year in range(0,self.years_until_retirement):
            employer_contribution_amount = math.floor(round(self.simulation.current_401k_employer_contribution/100,3) * self.salaries[year])
            # IF SAVINGS IS LESS THAN 0: contribute nothing - update to withdrawals later
            if self.savings[year] < 0:
                hsa_contributions.append(0)
                retirement_contributions.append(0)
                employer_retirement_contributions.append(0)
                ira_contributions.append(0)
                iba_contributions.append(0)
            # IF HSA ENROLLMENT HAS BEEN OPTED OUT: 
            if self.simulation.hsa_enrollment_opt_out:
                # IF SAVINGS IS GREATER THAN ALL CONTRIBUTION LIMITS (excluding HSA): max 401k, ira, then rest to iba
                if self.savings[year] >= self.retirement_cont_limits[year] + self.ira_cont_limits[year]:
                    hsa_contributions.append(0)
                    retirement_contributions.append(self.retirement_cont_limits[year])
                    employer_retirement_contributions.append(employer_contribution_amount)
                    ira_contributions.append(self.ira_cont_limits[year])
                    iba_contributions.append(self.savings[year] - self.retirement_cont_limits[year] - self.ira_cont_limits[year])
                # IF SAVINGS IS GREATER 401K CONTRIBUTION LIMITS: max 401k, then rest to iba
                elif self.savings[year] >= self.retirement_cont_limits[year]:
                    hsa_contributions.append(0)
                    retirement_contributions.append(self.retirement_cont_limits[year])
                    employer_retirement_contributions.append(employer_contribution_amount)
                    ira_contributions.append(self.savings[year] - self.retirement_cont_limits[year])
                    iba_contributions.append(0)
                # IF SAVINGS IS GREATER THAN EMPLOYER CONTRIBUTION MATCH: all to 401k
                elif self.savings[year] >= employer_contribution_amount:
                    hsa_contributions.append(0)
                    retirement_contributions.append(self.savings[year])
                    employer_retirement_contributions.append(employer_contribution_amount)
                    ira_contributions.append(0)
                    iba_contributions.append(0)
                # IF SAVINGS IS LESS THAN EMPLOYER CONTRIBUTION MATCH: all to 401k
                else:
                    hsa_contributions.append(0)
                    if employer_contribution_amount > self.retirement_cont_limits[year]:
                        retirement_contributions.append(self.retirement_cont_limits[year])
                    else:
                        retirement_contributions.append(self.savings[year])
                    employer_retirement_contributions.append(self.savings[year])
                    ira_contributions.append(0)
                    iba_contributions.append(0)
            # IF HSA ENROLLMENT HAS NOT BEEN OPTED OUT
            else:
                # IF SAVINGS IS GREATER THAN ALL CONTRIBUTION LIMITS: max hsa, 401k, ira then rest to iba
                if self.savings[year] >= self.hsa_cont_limits[year] + self.retirement_cont_limits[year] + self.ira_cont_limits[year]:
                    hsa_contributions.append(self.hsa_cont_limits[year])
                    retirement_contributions.append(self.retirement_cont_limits[year])
                    employer_retirement_contributions.append(employer_contribution_amount)
                    ira_contributions.append(self.ira_cont_limits[year])
                    iba_contributions.append(self.savings[year] - self.hsa_cont_limits[year] - self.retirement_cont_limits[year] - self.ira_cont_limits[year])
                # IF SAVINGS IS GREATER THAN HSA & 401K CONTRIBUTION LIMITS: max hsa, 401k then rest to ira
                elif self.savings[year] >= self.hsa_cont_limits[year] + self.retirement_cont_limits[year]:
                    hsa_contributions.append(self.hsa_cont_limits[year])
                    retirement_contributions.append(self.retirement_cont_limits[year])
                    employer_retirement_contributions.append(employer_contribution_amount)
                    ira_contributions.append(self.savings[year] - self.hsa_cont_limits[year] - self.retirement_cont_limits[year])
                    iba_contributions.append(0)
                # IF SAVINGS IS GREATER THAN EMPLOYER CONTRIBUTION MATCH and HSA CONTRIBUTION LIMIT: max hsa then rest to 401k
                elif self.savings[year] >= employer_contribution_amount + self.hsa_cont_limits[year]:
                    hsa_contributions.append(self.hsa_cont_limits[year])
                    retirement_contributions.append(self.savings[year] - self.hsa_cont_limits[year])
                    employer_retirement_contributions.append(employer_contribution_amount)
                    ira_contributions.append(0)
                    iba_contributions.append(0)
                # IF SAVINGS IS GREATER THAN EMPLOYER CONTRIBUTION MATCH: get 401k employer match then rest to hsa
                elif self.savings[year] > employer_contribution_amount:
                    hsa_contributions.append(self.savings[year] - employer_contribution_amount)
                    if employer_contribution_amount > self.retirement_cont_limits[year]:
                        retirement_contributions.append(self.retirement_cont_limits[year])
                    else:
                        retirement_contributions.append(employer_contribution_amount)
                    employer_retirement_contributions.append(employer_contribution_amount)
                    ira_contributions.append(0)
                    iba_contributions.append(0)
                else:
                # IF SAVINGS IS LESS THAN EMPLOYER CONTRIBUTION MATCH: all to 401k
                    hsa_contributions.append(0)
                    if employer_contribution_amount > self.retirement_cont_limits[year]:
                        retirement_contributions.append(self.retirement_cont_limits[year])
                    else:
                        retirement_contributions.append(self.savings[year])
                    employer_retirement_contributions.append(self.savings[year])
                    ira_contributions.append(0)
                    iba_contributions.append(0)
        
        self.hsa_contributions = hsa_contributions
        self.ira_contributions = ira_contributions
        self.retirement_contributions = retirement_contributions
        self.employer_retirement_contributions = employer_retirement_contributions
        self.iba_contributions = iba_contributions

        # Return
        return hsa_contributions,retirement_contributions,employer_retirement_contributions,ira_contributions,iba_contributions

    # Function: Start and End Investment Account Balances
    def start_end_balances(self):
        hsa_start = [self.simulation.current_hsa_balance]
        hsa_end = []
        retirement_start = [self.simulation.current_401k_balance]
        retirement_end = []
        ira_start = [self.simulation.current_ira_balance]
        ira_end = []
        iba_start = [self.simulation.current_ira_balance]
        iba_end = []

        for year in range(0,self.years_until_retirement):

            hsa_end.append(math.floor((hsa_start[year] + self.hsa_contributions[year]) * (1 + round(self.simulation.esitmated_hsa_yearly_return/100,3))))
            retirement_end.append(math.floor((retirement_start[year] + self.retirement_contributions[year] + self.employer_retirement_contributions[year]) * (1 + round(self.simulation.esitmated_401k_yearly_return/100,3))))
            ira_end.append(math.floor((ira_start[year] + self.ira_contributions[year]) * (1 + round(self.simulation.esitmated_ira_yearly_return/100,3))))
            iba_end.append(math.floor((iba_start[year] + self.iba_contributions[year]) * (1 + round(self.simulation.esitmated_iba_yearly_return/100,3))))

            if year != self.years_until_retirement - 1:
                hsa_start.append(math.floor(hsa_end[year]))
                retirement_start.append(math.floor(retirement_end[year]))
                ira_start.append(math.floor(ira_end[year]))
                iba_start.append(math.floor(iba_end[year]))

        self.hsa_start = hsa_start
        self.hsa_end = hsa_end
        self.retirement_start = retirement_start
        self.retirement_end = retirement_end
        self.ira_start = ira_start
        self.ira_end = ira_end
        self.iba_start = iba_start
        self.iba_end = iba_end

        # Return
        return hsa_start, hsa_end, retirement_start, retirement_end, ira_start, ira_end, iba_start, iba_end
    
    # Function: Asset Values
    def assets(self):
        assets = []
        if self.simulation.current_asset_values:
            for idx, asset_value in enumerate(self.simulation.current_asset_values):
                asset_value_list = [math.floor(int(asset_value) * ((1 + round(float(self.simulation.estimated_asset_value_growths[idx])/100,3)) ** year)) for year in range(0,self.years_until_retirement)]
                assets.append(asset_value_list)
            assets = [sum(asset) for asset in zip(*assets)]
        else:
            assets = [0 for year in range(0,self.years_until_retirement)]

        self.assets = assets

        return assets
    
    # Function: FIRE Indicators
    def fire_indicators(self):

        #Net Worths
        net_worths = [math.floor(self.hsa_end[year] + self.retirement_end[year] + self.ira_end[year] + self.iba_end[year] + self.assets[year]) for year in range(0,self.years_until_retirement)]
        self.net_worths = net_worths
        # Magic Numbers
        magic_numbers = [(self.variable_costs[year] + self.fixed_costs[year] + self.health_insurance[year]) * 25 for year in range(0,self.years_until_retirement)]
        self.magic_numbers = magic_numbers
        # Drawdowns
        drawdowns = [str(round(((self.variable_costs[year] + self.fixed_costs[year] + self.health_insurance[year]) / self.net_worths[year]) * 100,2)) + "%" for year in range(0,self.years_until_retirement)]
        self.drawdowns = drawdowns

        # Return
        return net_worths, magic_numbers, drawdowns
    
    # Function: Simulation Data Function
    def simulation_data(self):
        simulation_data = []
        for year in range(0,self.years_until_retirement):
            year_dict = {}
            year_dict['year'] = self.years[year]
            year_dict['age'] = self.ages[year]
            year_dict['salary'] = '${:,}'.format(self.salaries[year])
            year_dict['bonus'] = '${:,}'.format(self.bonuses[year])
            year_dict['other_income'] = '${:,}'.format(self.other_income[year])
            year_dict['lump_sum_income'] = '${:,}'.format(self.lump_sum_incomes[year])
            year_dict['total_income'] = '${:,}'.format(self.total_income[year])
            year_dict['fixed_cost'] = '${:,}'.format(self.fixed_costs[year])
            year_dict['variable_cost'] = '${:,}'.format(self.variable_costs[year])
            year_dict['health_insurance'] = '${:,}'.format(self.health_insurance[year])
            year_dict['lump_sum_expense'] = '${:,}'.format(self.lump_sum_expenses[year])
            year_dict['tax'] = '${:,}'.format(self.taxes[year])
            year_dict['total_expense'] = '${:,}'.format(self.total_expenses[year])
            year_dict['saving'] = '${:,}'.format(self.savings[year])
            year_dict['hsa_start'] = '${:,}'.format(self.hsa_start[year])
            year_dict['hsa_cont_limit'] = '${:,}'.format(self.hsa_cont_limits[year])
            year_dict['hsa_contribution'] = '${:,}'.format(self.hsa_contributions[year])
            year_dict['hsa_end'] = '${:,}'.format(self.hsa_end[year])
            year_dict['retirement_start'] = '${:,}'.format(self.retirement_start[year])
            year_dict['retirement_cont_limit'] = '${:,}'.format(self.retirement_cont_limits[year])
            year_dict['retirement_contribution'] = '${:,}'.format(self.retirement_contributions[year])
            year_dict['employer_retirement_contribution'] = '${:,}'.format(self.employer_retirement_contributions[year])
            year_dict['retirement_end'] = '${:,}'.format(self.retirement_end[year])
            year_dict['ira_start'] = '${:,}'.format(self.ira_start[year])
            year_dict['ira_cont_limit'] = '${:,}'.format(self.ira_cont_limits[year])
            year_dict['ira_contribution'] = '${:,}'.format(self.ira_contributions[year])
            year_dict['ira_end'] = '${:,}'.format(self.ira_end[year])
            year_dict['iba_start'] = '${:,}'.format(self.iba_start[year])
            year_dict['iba_contribution'] = '${:,}'.format(self.iba_contributions[year])
            year_dict['iba_end'] = '${:,}'.format(self.iba_end[year])
            year_dict['asset_value'] = '${:,}'.format(self.assets[year])
            year_dict['net_worth'] = '${:,}'.format(self.net_worths[year])
            year_dict['magic_number'] = '${:,}'.format(self.magic_numbers[year])
            year_dict['drawdown'] = self.drawdowns[year]
            year_dict['drawdown_int'] = float(self.drawdowns[year][:-1])
            simulation_data.append(year_dict)

        self.simulation_data = simulation_data

        return simulation_data
    
    def zip_objects(self):
        lump_sum_incomes = zip(self.simulation.lumpsum_income_names, self.simulation.estimated_lumpsum_income_ages, self.simulation.estimated_lumpsum_income_amounts)
        lump_sum_expenses = zip(self.simulation.lumpsum_expense_names, self.simulation.estimated_lumpsum_expense_ages, self.simulation.estimated_lumpsum_expense_amounts)
        variable_cost_adjustments = zip(self.simulation.variable_cost_adjustment_names, self.simulation.estimated_variable_cost_adjustment_ages, self.simulation.estimated_variable_cost_adjustments)
        fixed_cost_adjustments = zip(self.simulation.fixed_cost_adjustment_names, self.simulation.estimated_fixed_cost_adjustment_ages, self.simulation.estimated_fixed_cost_adjustments)
        assets = zip(self.simulation.asset_names, self.simulation.current_asset_values, self.simulation.estimated_asset_value_growths)

        return lump_sum_incomes, lump_sum_expenses, variable_cost_adjustments, fixed_cost_adjustments, assets
    
    def financial_independence_age(self):
        x = 0
        for net_worth in self.net_worths:
            if net_worth > self.magic_numbers[x]:
                return self.ages[x]
            else:
                x += 1
        return "N/A"
            
