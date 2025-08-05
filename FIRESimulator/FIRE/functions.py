import math
import pandas as pd

def savesimulation(self, request, create=True):
    newsimulation = self.save(commit=False)
    if newsimulation.current_age > newsimulation.estimated_retirement_age:
        return "Current age must be less than estimated retirement age."
    try:
        if str(request.user) != "AnonymousUser":
            newsimulation.user = request.user
        # if create == True:
            # newsimulation.estimated_salary_raise=round(newsimulation.estimated_salary_raise/100,3)
            # newsimulation.estimated_bonus=round(newsimulation.estimated_bonus/100,3)
            # newsimulation.estimated_other_income_increase=round(newsimulation.estimated_other_income_increase/100,3)
            # newsimulation.estimated_fixed_costs_inflation=round(newsimulation.estimated_fixed_costs_inflation/100,3)
            # newsimulation.estimated_cost_of_living_inflation=round(newsimulation.estimated_cost_of_living_inflation/100,3)
            # newsimulation.estimated_tax_rate=round(newsimulation.estimated_tax_rate/100,3)
            # newsimulation.estimated_health_insurance_inflation=round(newsimulation.estimated_health_insurance_inflation/100,3)
            # newsimulation.esitmated_hsa_yearly_return=round(newsimulation.esitmated_hsa_yearly_return/100,3)
            # newsimulation.current_401k_employer_contribution=round(newsimulation.current_401k_employer_contribution/100,3)
            # newsimulation.esitmated_401k_yearly_return=round(newsimulation.esitmated_401k_yearly_return/100,3)
            # newsimulation.esitmated_ira_yearly_return=round(newsimulation.esitmated_ira_yearly_return/100,3)
            # newsimulation.esitmated_iba_yearly_return=round(newsimulation.esitmated_iba_yearly_return/100,3)
        newsimulation.save()
        return newsimulation
    except Exception as e:
        return "Error creating simulation, please try again."

def yearly_contribution_limits(current,step,years):
    limits = [current + (year * step) for year in range(0,years)]
    return limits

def yearly_contributions(years,savings,salaries,hsa_cont_limits,retirement_cont_limits,ira_cont_limits,employer_contribution,hsa_enrollment):
    hsa_contributions = []
    ira_contributions = []
    retirement_contributions = []
    employer_retirement_contributions = []
    iba_contributions = []
    for year in range(0,years):
        employer_contribution_amount = math.floor(round(employer_contribution/100,3) * salaries[year])
        # IF SAVINGS IS LESS THAN 0
        if savings[year] < 0:
            hsa_contributions.append(0)
            retirement_contributions.append(0)
            employer_retirement_contributions.append(0)
            ira_contributions.append(0)
            iba_contributions.append(0)
        # IF SAVINGS IS GREATER THAN ALL CONTRIBUTION LIMITS
        elif savings[year] >= hsa_cont_limits[year] + retirement_cont_limits[year] + ira_cont_limits[year]:
            hsa_contributions.append(hsa_cont_limits[year])
            retirement_contributions.append(retirement_cont_limits[year])
            employer_retirement_contributions.append(employer_contribution_amount)
            ira_contributions.append(ira_cont_limits[year])
            iba_contributions.append(savings[year] - hsa_cont_limits[year] - retirement_cont_limits[year] - ira_cont_limits[year])
        #IF SAVINGS IS GREATER THAN HSA & 401K CONTRIBUTION LIMITS
        elif savings[year] >= hsa_cont_limits[year] + retirement_cont_limits[year]:
            hsa_contributions.append(hsa_cont_limits[year])
            retirement_contributions.append(retirement_cont_limits[year])
            employer_retirement_contributions.append(employer_contribution_amount)
            ira_contributions.append(savings[year] - hsa_cont_limits[year] - retirement_cont_limits[year])
            iba_contributions.append(0)
        #IF SAVINGS IS GREATER THAN EMPLOYER CONTRIBUTION MATCH and HSA CONTRIBUTION LIMIT
        elif savings[year] >= employer_contribution_amount + hsa_cont_limits[year]:
            hsa_contributions.append(hsa_cont_limits[year])
            retirement_contributions.append(savings[year] - hsa_cont_limits[year])
            employer_retirement_contributions.append(employer_contribution_amount)
            ira_contributions.append(0)
            iba_contributions.append(0)
        #IF SAVINGS IS GREATER THAN EMPLOYER CONTRIBUTION MATCH
        elif savings[year] > employer_contribution_amount:
            hsa_contributions.append(savings[year] - employer_contribution_amount)
            if employer_contribution_amount > retirement_cont_limits[year]:
                retirement_contributions.append(retirement_cont_limits[year])
            else:
                retirement_contributions.append(employer_contribution_amount)
            employer_retirement_contributions.append(employer_contribution_amount)
            ira_contributions.append(0)
            iba_contributions.append(0)
        else:
        #IF SAVINGS IS LESS THAN EMPLOYER CONTRIBUTION MATCH
            hsa_contributions.append(0)
            if employer_contribution_amount > retirement_cont_limits[year]:
                retirement_contributions.append(retirement_cont_limits[year])
            else:
                retirement_contributions.append(savings[year])
            employer_retirement_contributions.append(savings[year])
            ira_contributions.append(0)
            iba_contributions.append(0)

    return hsa_contributions,retirement_contributions,employer_retirement_contributions,ira_contributions,iba_contributions

def start_end_balances(current_balance,years,contributions_list,yearly_return,employer_contributions_list=[]):
    yearly_return = round(yearly_return/100,3)
    start_list = [current_balance]
    end_list = []
    for year in range(0,years):
        if employer_contributions_list == []:
            end_list.append(math.floor((start_list[year] + contributions_list[year]) * (1 + yearly_return)))
        else:
            end_list.append(math.floor((start_list[year] + contributions_list[year] + employer_contributions_list[year]) * (1 + yearly_return)))
        if year != years - 1:
            start_list.append(math.floor(end_list[year]))
    return start_list,end_list

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