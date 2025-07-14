import math
import pandas as pd

def saveobject(self, request):
    newobject = self.save(commit=False)
    if str(request.user) != "AnonymousUser":
        newobject.user = request.user
    newobject.save()
    print(newobject.user)
    return newobject

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