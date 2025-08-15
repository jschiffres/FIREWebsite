import math
import pandas as pd

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
        else:
            newsimulation.estimated_coastfire_age = 0
        
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
        
        #Set lumpsum payment fields equal to the list of amounts and ages within the request/form
        newsimulation.estimated_lumpsum_payment_amounts = request.POST.getlist('estimated_lumpsum_payment_amounts')
        newsimulation.estimated_lumpsum_payment_ages = request.POST.getlist('estimated_lumpsum_payment_ages')

        #Check that there are no duplicate lumpsum payment ages:
        if len(list(newsimulation.estimated_lumpsum_payment_ages)) != len(set(list(newsimulation.estimated_lumpsum_payment_ages))):
            return "Limit of one lump sum payment per year."
        
        #Check that all lumpsum payment ages are greater than or equal to the simulation's current age:
        if len(list(filter(lambda age: age < newsimulation.current_age, list(map(int, newsimulation.estimated_lumpsum_payment_ages))))) > 0:
            return "Lump sum payments must occur after or equal to your current age."
        
        #Check that all lumpsum payment ages are less than the simulation's estimated retirement age:
        if len(list(filter(lambda age: age >= newsimulation.estimated_retirement_age, list(map(int, newsimulation.estimated_lumpsum_payment_ages))))) > 0:
            return "Lump sum payments must occur before your estimated retirement age."
        
        newsimulation.current_asset_values = request.POST.getlist('current_asset_values')
        newsimulation.estimated_asset_value_growths = request.POST.getlist('estimated_asset_value_growths')

        #Save simulation w/ Commit and return simulation object
        newsimulation.save()
        return newsimulation
    
    except Exception as e:
        print(e)
        return "Error creating simulation, please try again."

def yearly_contribution_limits(current,step,years):
    limits = [current + (year * step) for year in range(0,years)]
    return limits

def yearly_contributions(years,savings,salaries,hsa_cont_limits,retirement_cont_limits,ira_cont_limits,employer_contribution,hsa_enrollment_opt_out):
    hsa_contributions = []
    ira_contributions = []
    retirement_contributions = []
    employer_retirement_contributions = []
    iba_contributions = []
    for year in range(0,years):
        employer_contribution_amount = math.floor(round(employer_contribution/100,3) * salaries[year])
        # IF SAVINGS IS LESS THAN 0: contribute nothing
        if savings[year] < 0:
            hsa_contributions.append(0)
            retirement_contributions.append(0)
            employer_retirement_contributions.append(0)
            ira_contributions.append(0)
            iba_contributions.append(0)
        # IF HSA ENROLLMENT HAS BEEN OPTED OUT: 
        if hsa_enrollment_opt_out:
            # IF SAVINGS IS GREATER THAN ALL CONTRIBUTION LIMITS (excluding HSA): max 401k, ira, then rest to iba
            if savings[year] >= retirement_cont_limits[year] + ira_cont_limits[year]:
                hsa_contributions.append(0)
                retirement_contributions.append(retirement_cont_limits[year])
                employer_retirement_contributions.append(employer_contribution_amount)
                ira_contributions.append(ira_cont_limits[year])
                iba_contributions.append(savings[year] - retirement_cont_limits[year] - ira_cont_limits[year])
            # IF SAVINGS IS GREATER 401K CONTRIBUTION LIMITS: max 401k, then rest to iba
            elif savings[year] >= retirement_cont_limits[year]:
                hsa_contributions.append(0)
                retirement_contributions.append(retirement_cont_limits[year])
                employer_retirement_contributions.append(employer_contribution_amount)
                ira_contributions.append(savings[year] - retirement_cont_limits[year])
                iba_contributions.append(0)
            # IF SAVINGS IS GREATER THAN EMPLOYER CONTRIBUTION MATCH: all to 401k
            elif savings[year] >= employer_contribution_amount:
                hsa_contributions.append(0)
                retirement_contributions.append(savings[year])
                employer_retirement_contributions.append(employer_contribution_amount)
                ira_contributions.append(0)
                iba_contributions.append(0)
            # IF SAVINGS IS LESS THAN EMPLOYER CONTRIBUTION MATCH: all to 401k
            else:
                hsa_contributions.append(0)
                if employer_contribution_amount > retirement_cont_limits[year]:
                    retirement_contributions.append(retirement_cont_limits[year])
                else:
                    retirement_contributions.append(savings[year])
                employer_retirement_contributions.append(savings[year])
                ira_contributions.append(0)
                iba_contributions.append(0)
        # IF HSA ENROLLMENT HAS NOT BEEN OPTED OUT
        else:
            # IF SAVINGS IS GREATER THAN ALL CONTRIBUTION LIMITS: max hsa, 401k, ira then rest to iba
            if savings[year] >= hsa_cont_limits[year] + retirement_cont_limits[year] + ira_cont_limits[year]:
                hsa_contributions.append(hsa_cont_limits[year])
                retirement_contributions.append(retirement_cont_limits[year])
                employer_retirement_contributions.append(employer_contribution_amount)
                ira_contributions.append(ira_cont_limits[year])
                iba_contributions.append(savings[year] - hsa_cont_limits[year] - retirement_cont_limits[year] - ira_cont_limits[year])
            # IF SAVINGS IS GREATER THAN HSA & 401K CONTRIBUTION LIMITS: max hsa, 401k then rest to ira
            elif savings[year] >= hsa_cont_limits[year] + retirement_cont_limits[year]:
                hsa_contributions.append(hsa_cont_limits[year])
                retirement_contributions.append(retirement_cont_limits[year])
                employer_retirement_contributions.append(employer_contribution_amount)
                ira_contributions.append(savings[year] - hsa_cont_limits[year] - retirement_cont_limits[year])
                iba_contributions.append(0)
            # IF SAVINGS IS GREATER THAN EMPLOYER CONTRIBUTION MATCH and HSA CONTRIBUTION LIMIT: max hsa then rest to 401k
            elif savings[year] >= employer_contribution_amount + hsa_cont_limits[year]:
                hsa_contributions.append(hsa_cont_limits[year])
                retirement_contributions.append(savings[year] - hsa_cont_limits[year])
                employer_retirement_contributions.append(employer_contribution_amount)
                ira_contributions.append(0)
                iba_contributions.append(0)
            # IF SAVINGS IS GREATER THAN EMPLOYER CONTRIBUTION MATCH: get 401k employer match then rest to hsa
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
            # IF SAVINGS IS LESS THAN EMPLOYER CONTRIBUTION MATCH: all to 401k
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