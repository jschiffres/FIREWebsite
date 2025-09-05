import math
import pandas as pd
from datetime import date
import json

def savesimulation(self, request):
    try:
        #Save simulation w/o Commit
        newsimulation = self.save(commit=False)

        #Check whether current age is not greater than retirement age:
        if newsimulation.current_age > newsimulation.estimated_retirement_age:
            return "Current age must be less than estimated retirement age."
        
        #Check whether Coast FIRE age was provided and if it is greater than current age but less than retirement age: 
        if request.POST.get('estimated_coastfire_age'):
            if int(request.POST.get('estimated_coastfire_age')) >= newsimulation.estimated_retirement_age or int(request.POST.get('estimated_coastfire_age')) <= newsimulation.current_age:
                return "Coast FIRE age must be less than estimated retirement age and greater than your current age."
            else:
                newsimulation.estimated_coastfire_age = request.POST.get('estimated_coastfire_age')
        
        #Set user equal to request user if logged in
        if str(request.user) != "AnonymousUser":
            newsimulation.user = request.user

        #If HSA investment has been opted out, set input variables = to 0 else set them equal to the form inputs
        if newsimulation.hsa_enrollment_opt_out:
            newsimulation.current_hsa_balance = 0
            newsimulation.current_hsa_yearly_contribution_limit = 0
            newsimulation.estimated_hsa_yearly_contribution_limit_step = 0
            newsimulation.esitmated_hsa_yearly_return = 0
        else:
            newsimulation.current_hsa_balance = request.POST.get('current_hsa_balance')
            newsimulation.current_hsa_yearly_contribution_limit = request.POST.get('current_hsa_yearly_contribution_limit')
            newsimulation.estimated_hsa_yearly_contribution_limit_step = request.POST.get('estimated_hsa_yearly_contribution_limit_step')
            newsimulation.esitmated_hsa_yearly_return = request.POST.get('esitmated_hsa_yearly_return')
        
        #Set lumpsum income/expense and fixed/vairable cost adjustment fields equal to the list of amounts and ages within the request/form
        newsimulation.lumpsum_income_names = request.POST.getlist('lumpsum_income_names')
        newsimulation.estimated_lumpsum_income_amounts = request.POST.getlist('estimated_lumpsum_income_amounts')
        newsimulation.estimated_lumpsum_income_ages = request.POST.getlist('estimated_lumpsum_income_ages')
        newsimulation.lumpsum_expense_names = request.POST.getlist('lumpsum_expense_names')
        newsimulation.estimated_lumpsum_expense_amounts = request.POST.getlist('estimated_lumpsum_expense_amounts')
        newsimulation.estimated_lumpsum_expense_ages = request.POST.getlist('estimated_lumpsum_expense_ages')
        newsimulation.fixed_cost_adjustment_names = request.POST.getlist('fixed_cost_adjustment_names')
        newsimulation.estimated_fixed_cost_adjustments = request.POST.getlist('estimated_fixed_cost_adjustments')
        newsimulation.estimated_fixed_cost_adjustment_ages = request.POST.getlist('estimated_fixed_cost_adjustment_ages')
        newsimulation.variable_cost_adjustment_names = request.POST.getlist('variable_cost_adjustment_names')
        newsimulation.estimated_variable_cost_adjustments = request.POST.getlist('estimated_variable_cost_adjustments')
        newsimulation.estimated_variable_cost_adjustment_ages = request.POST.getlist('estimated_variable_cost_adjustment_ages')

        #Check that there are no duplicate yearly entries within survey add-ons (lump sum payments, expense adjustments etc.):
        if len(list(newsimulation.estimated_lumpsum_income_ages)) != len(set(list(newsimulation.estimated_lumpsum_income_ages))) or len(list(newsimulation.estimated_lumpsum_expense_ages)) != len(set(list(newsimulation.estimated_lumpsum_expense_ages))) or len(list(newsimulation.estimated_fixed_cost_adjustment_ages)) != len(set(list(newsimulation.estimated_fixed_cost_adjustment_ages))) or len(list(newsimulation.estimated_variable_cost_adjustment_ages)) != len(set(list(newsimulation.estimated_variable_cost_adjustment_ages))):
            return "Limit of one one entry per year before retirement age."
        
        #Check that all entry ages are greater than or equal to the simulation's current age:
        if len(list(filter(lambda age: age < newsimulation.current_age, list(map(int, newsimulation.estimated_lumpsum_income_ages))))) > 0 or len(list(filter(lambda age: age < newsimulation.current_age, list(map(int, newsimulation.estimated_lumpsum_expense_ages))))) > 0 or len(list(filter(lambda age: age < newsimulation.current_age, list(map(int, newsimulation.estimated_fixed_cost_adjustment_ages))))) > 0 or len(list(filter(lambda age: age < newsimulation.current_age, list(map(int, newsimulation.estimated_variable_cost_adjustment_ages))))) > 0:
            return "Entries must occur after or equal to your current age."
        
        #Check that all entry ages are less than the simulation's estimated retirement age:
        if len(list(filter(lambda age: age >= newsimulation.estimated_retirement_age, list(map(int, newsimulation.estimated_lumpsum_income_ages))))) > 0 or len(list(filter(lambda age: age >= newsimulation.estimated_retirement_age, list(map(int, newsimulation.estimated_lumpsum_expense_ages))))) > 0 or len(list(filter(lambda age: age >= newsimulation.estimated_retirement_age, list(map(int, newsimulation.estimated_fixed_cost_adjustment_ages))))) > 0 or len(list(filter(lambda age: age >= newsimulation.estimated_retirement_age, list(map(int, newsimulation.estimated_variable_cost_adjustment_ages))))) > 0:
            return "Entries must occur before your estimated retirement age."
        
        #Set asset fields equal to the list of amounts and growths within the request/form
        newsimulation.asset_names = request.POST.getlist('asset_names')
        newsimulation.current_asset_values = request.POST.getlist('current_asset_values')
        newsimulation.estimated_asset_value_growths = request.POST.getlist('estimated_asset_value_growths')

        #Save simulation w/ Commit and return simulation object
        newsimulation.save()
        return newsimulation
    
    except Exception as e:
        print(e)
        return "Error creating simulation, please try again."

class FIRE:
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
            year_dict['fixed_cost'] = '${:,}'.format(self.fixed_costs[year])
            year_dict['variable_cost'] = '${:,}'.format(self.variable_costs[year])
            year_dict['health_insurance'] = '${:,}'.format(self.health_insurance[year])
            year_dict['lump_sum_expense'] = '${:,}'.format(self.lump_sum_expenses[year])
            year_dict['tax'] = '${:,}'.format(self.taxes[year])
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
            simulation_data.append(year_dict)

        self.simulation_data = simulation_data

        return simulation_data









def DFtoHTML(df):
    HTMLdf = df.to_html(index=False)
    edit1 = HTMLdf.replace('dataframe','table table-striped table-hover')
    edit2 = edit1.replace('thead','thead class="table-dark"')
    edit3 = edit2.replace('''<th>SALARY</th>
      <th>BONUS</th>
      <th>OTHER INCOME</th>
      <th>BILLS</th>
      <th>COST OF LIVING</th>
      <th>TAXES</th>
      <th>HEALTH INSURANCE</th>
      <th>SAVINGS</th>
      <th>HSA START</th>
      <th>HSA CONTRIBUTION LIMIT</th>
      <th>HSA CONTRIBUTIONS</th>
      <th>HSA END</th>
      <th>401K START</th>
      <th>401K CONTRIBUTION LIMIT</th>
      <th>401K CONTRIBUTIONS</th>
      <th>401K END</th>
      <th>IRA START</th>
      <th>IRA CONTRIBUTION LIMIT</th>
      <th>IRA CONTRIBUTIONS</th>
      <th>IRA END</th>
      <th>INDIVIDUAL START</th>
      <th>INDIVIDUAL CONTRIBUTIONS</th>
      <th>INDIVIDUAL END</th>
      <th>NET WORTH</th>''','''<th style="white-space:nowrap;" class="table-success">SALARY</th>
      <th style="white-space:nowrap;" class="table-success">BONUS</th>
      <th style="white-space:nowrap;" class="table-success">OTHER INCOME</th>
      <th style="white-space:nowrap;" class="table-danger">BILLS</th>
      <th style="white-space:nowrap;" class="table-danger">COST OF LIVING</th>
      <th style="white-space:nowrap;" class="table-danger">TAXES</th>
      <th style="white-space:nowrap;" class="table-danger">HEALTH INSURANCE</th>
      <th style="white-space:nowrap;" class="table-success">SAVINGS</th>
      <th style="white-space:nowrap;">HSA START</th>
      <th style="white-space:nowrap;" class="table-secondary">HSA CONTRIBUTION LIMIT</th>
      <th style="white-space:nowrap;" class="table-info">HSA CONTRIBUTIONS</th>
      <th style="white-space:nowrap;" class="table-success">HSA END</th>
      <th style="white-space:nowrap;">401K START</th>
      <th style="white-space:nowrap;" class="table-secondary">401K CONTRIBUTION LIMIT</th>
      <th style="white-space:nowrap;" class="table-info">401K CONTRIBUTIONS</th>
      <th style="white-space:nowrap;" class="table-success">401K END</th>
      <th style="white-space:nowrap;">IRA START</th>
      <th style="white-space:nowrap;" class="table-secondary">IRA CONTRIBUTION LIMIT</th>
      <th style="white-space:nowrap;" class="table-info">IRA CONTRIBUTIONS</th>
      <th style="white-space:nowrap;" class="table-success">IRA END</th>
      <th style="white-space:nowrap;">INDIVIDUAL START</th>
      <th style="white-space:nowrap;" class="table-info">INDIVIDUAL CONTRIBUTIONS</th>
      <th style="white-space:nowrap;" class="table-success">INDIVIDUAL END</th>
      <th style="white-space:nowrap;">NET WORTH</th>''')
    final = edit3.replace('tr style="text-align: right;"','tr style="text-align: center;"')
    # print(final)
    return final