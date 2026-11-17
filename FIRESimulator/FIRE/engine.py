"""Financial-independence projection engine.

PlanObject turns a saved ``Plan`` (current/retirement age plus JSON incomes,
expenses and savings) into year-by-year projections. The stored plan is never
mutated: all computed series live on the PlanObject.
"""
import copy
import math
import random
from datetime import date

import plotly.graph_objects as go

CURRENT_AGE = "Current Age"
RETIREMENT_AGE = "Target Retirement Age"
SAFE_WITHDRAWAL_MULTIPLE = 25


def pct(value):
    return float(value) / 100.0


def money(value):
    value = int(value)
    return f"-${abs(value):,}" if value < 0 else f"${value:,}"


def sum_series(series, length):
    """Element-wise sum of equally long lists; zeros when there is nothing to add."""
    return [sum(values) for values in zip(*series)] if series else [0] * length


SCENARIO_RETURN_SHIFT = 2.0
MONTE_CARLO_TRIALS = 400
MONTE_CARLO_VOLATILITY = 10.0
MAX_DEFAULT_RETIREMENT_RETURN = 6.0


class PlanObject:
    def __init__(self, plan, return_delta=0.0, extra_savings=0):
        """``return_delta`` (percentage points) and ``extra_savings`` ($/year while working)
        support what-if projections without touching the stored plan."""
        self.plan = plan
        self.return_delta = float(return_delta)
        self.extra_savings = int(extra_savings)
        self.years_until_retirement = plan.retirement_age - plan.current_age
        if self.years_until_retirement < 1:
            raise ValueError("Retirement age must be greater than current age.")
        # Contributions always continue until retirement; Coast FI age is computed, not chosen
        self.years_until_coast_fire = self.years_until_retirement
        # Work on copies so computed series are never persisted back to the plan
        self.incomes = copy.deepcopy(plan.incomes or [])
        self.expenses = copy.deepcopy(plan.expenses or [])
        self.accounts = copy.deepcopy(plan.savings or ['Simple'])

    def run(self):
        self.personal_infos()
        self.compute_incomes()
        self.compute_expenses()
        self.compute_savings()
        self.compute_contribution_limits()
        self.compute_contributions()
        self.compute_balances()
        self.fi_indicators()
        self.template_data()
        return self

    # ------------------------------------------------------------------ basics
    def personal_infos(self):
        n = self.years_until_retirement
        self.ages = [self.plan.current_age + year for year in range(n)]
        self.ages_display = list(self.ages)
        self.ages_display[0] = CURRENT_AGE
        self.ages_display[-1] = RETIREMENT_AGE
        self.years = [date.today().year + year for year in range(n)]

    def _resolve_age(self, value):
        if value == CURRENT_AGE:
            return self.plan.current_age
        if value == RETIREMENT_AGE:
            return self.plan.retirement_age - 1
        return int(value)

    def _recurring_series(self, entry):
        """Gross amounts and tax-rate (percent) per projected age for a recurring entry."""
        start = self._resolve_age(entry['start_age'])
        stop = self._resolve_age(entry['stop_age'])
        entry['start_age_num'] = start
        entry['stop_age_num'] = stop
        amounts = {}
        tax_rates = {}
        for step, age in enumerate(range(start, stop + 1)):
            amounts[age] = math.floor(entry['starting_amount'] * (1 + pct(entry['yearly_change'])) ** step)
            if 'tax_rate' in entry:
                tax_rates[age] = entry['tax_rate'] + step * entry.get('tax_rate_change', 0)
        gross = [amounts.get(age, 0) for age in self.ages]
        rates = [min(max(tax_rates.get(age, 0), 0), 100) for age in self.ages]
        return gross, rates

    # ----------------------------------------------------------------- incomes
    def compute_incomes(self):
        n = self.years_until_retirement
        gross_all, bonuses, taxes, nets = [], [], [], []
        salary, recurring, one_time = [], [], []
        counts = {'Salary': 0, 'Recurring': 0, 'One-time': 0}

        for income in self.incomes:
            category = income['income_category']
            income['category_index'] = counts[category]
            counts[category] += 1

            if category == 'One-time':
                rate = min(max(income['tax_rate'], 0), 100)
                income['gross_amounts'] = [income['amount'] if age == income['age'] else 0 for age in self.ages]
                income['tax_amounts'] = [math.floor(g * pct(rate)) for g in income['gross_amounts']]
                one_time.append(income['gross_amounts'])
            else:
                gross, rates = self._recurring_series(income)
                income['gross_amounts'] = gross
                income['tax_rates'] = rates
                if category == 'Salary':
                    income['bonus_amounts'] = [math.floor(g * pct(income['bonus_rate'])) for g in gross]
                    taxable = [g + b for g, b in zip(gross, income['bonus_amounts'])]
                    salary.append(gross)
                    bonuses.append(income['bonus_amounts'])
                    gross_all.append(income['bonus_amounts'])
                else:
                    taxable = gross
                    recurring.append(gross)
                income['tax_amounts'] = [math.floor(t * pct(r)) for t, r in zip(taxable, rates)]
                income['net_amounts'] = [t - x for t, x in zip(taxable, income['tax_amounts'])]

            if category == 'One-time':
                income['net_amounts'] = [g - x for g, x in zip(income['gross_amounts'], income['tax_amounts'])]
            gross_all.append(income['gross_amounts'])
            taxes.append(income['tax_amounts'])
            nets.append(income['net_amounts'])

        self.total_salary_income = sum_series(salary, n)
        self.total_recurring_income = sum_series(recurring, n)
        self.total_one_time_income = sum_series(one_time, n)
        self.total_gross_income = sum_series(gross_all, n)
        self.total_bonuses = sum_series(bonuses, n)
        self.total_taxes = sum_series(taxes, n)
        self.total_net_income = sum_series(nets, n)

    # ---------------------------------------------------------------- expenses
    def compute_expenses(self):
        n = self.years_until_retirement
        every, recurring, one_time = [], [], []
        counts = {'Recurring': 0, 'One-time': 0}

        for expense in self.expenses:
            category = expense['expense_category']
            expense['category_index'] = counts[category]
            counts[category] += 1
            if category == 'Recurring':
                expense['amounts'], _ = self._recurring_series(expense)
                recurring.append(expense['amounts'])
            else:
                expense['amounts'] = [expense['amount'] if age == expense['age'] else 0 for age in self.ages]
                one_time.append(expense['amounts'])
            every.append(expense['amounts'])

        self.total_expenses = sum_series(every, n)
        self.total_recurring_expenses = sum_series(recurring, n)
        self.total_one_time_expenses = sum_series(one_time, n)

    def compute_savings(self):
        self.total_savings = [
            self.total_net_income[year] - self.total_expenses[year] + self.extra_savings
            if year < self.years_until_coast_fire else 0
            for year in range(self.years_until_retirement)
        ]

    # ---------------------------------------------------------------- accounts
    @property
    def is_simple(self):
        return self.accounts[0] == 'Simple'

    def _account(self, category):
        return next((a for a in self.accounts[1:] if a['saving_category'] == category), None)

    def compute_contribution_limits(self):
        if self.is_simple:
            return
        for account in self.accounts[1:]:
            if account['saving_category'] != 'TBA':
                account['contribution_limits'] = [
                    account['contribution_limit'] + year * account['contribution_limit_step']
                    for year in range(self.years_until_retirement)
                ]

    def compute_contributions(self):
        n = self.years_until_retirement
        self.unallocated_savings = [0] * n

        if self.is_simple:
            self.accounts[1]['contribution_amounts'] = list(self.total_savings)
            return

        esrp, hsa, ira, tba = (self._account(c) for c in ('ESRP', 'HSA', 'IRA', 'TBA'))
        employee = {id(a): [0] * n for a in self.accounts[1:]}
        employer = [0] * n

        for year in range(n):
            savings = self.total_savings[year]

            if savings < 0:
                # Shortfall years are withdrawn from the first available account
                for account in (tba, ira, esrp, hsa):
                    if account is not None:
                        employee[id(account)][year] = savings
                        break
                continue

            remaining = savings
            esrp_amount = 0
            if esrp is not None:
                # Employer contributes dollar-for-dollar up to rate% of salary, so fill the match first
                match_target = math.floor(pct(esrp['employer_contribution_rate']) * self.total_salary_income[year])
                esrp_amount = min(remaining, match_target, esrp['contribution_limits'][year])
                employer[year] = esrp_amount
                remaining -= esrp_amount
            if hsa is not None:
                amount = min(remaining, hsa['contribution_limits'][year])
                employee[id(hsa)][year] = amount
                remaining -= amount
            if esrp is not None:
                extra = min(remaining, esrp['contribution_limits'][year] - esrp_amount)
                employee[id(esrp)][year] = esrp_amount + extra
                remaining -= extra
            if ira is not None:
                amount = min(remaining, ira['contribution_limits'][year])
                employee[id(ira)][year] = amount
                remaining -= amount
            if tba is not None:
                employee[id(tba)][year] = remaining
                remaining = 0
            self.unallocated_savings[year] = remaining

        for account in self.accounts[1:]:
            account['contribution_amounts'] = employee[id(account)]
            if account['saving_category'] == 'ESRP':
                account['employer_contribution_amounts'] = employer

        def series(account):
            return employee[id(account)] if account is not None else [0] * n

        self.hsa_contribution_amounts = series(hsa)
        self.esrp_contribution_amounts = series(esrp)
        self.esrp_employer_contribution_amounts = employer if esrp is not None else [0] * n
        self.ira_contribution_amounts = series(ira)
        self.tba_contribution_amounts = series(tba)

    def compute_balances(self):
        n = self.years_until_retirement
        for account in self.accounts[1:]:
            if self.is_simple:
                opening, growth = account['simple_net_worth'], account['simple_yearly_growth']
            else:
                opening, growth = account['current_value'], account['yearly_growth']
            employer = account.get('employer_contribution_amounts', [0] * n)
            start, end = [], []
            balance = opening
            for year in range(n):
                start.append(balance)
                balance = math.floor(
                    (balance + account['contribution_amounts'][year] + employer[year])
                    * (1 + pct(growth + self.return_delta))
                )
                end.append(balance)
            account['start_amounts'] = start
            account['end_amounts'] = end

    def _net_worth_path(self, growth_fn):
        """Net worth per year when each year's return is ``growth_fn(base_growth_pct, year)`` percent."""
        n = self.years_until_retirement
        totals = [0] * n
        for account in self.accounts[1:]:
            if self.is_simple:
                balance, base = account['simple_net_worth'], account['simple_yearly_growth']
            else:
                balance, base = account['current_value'], account['yearly_growth']
            employer = account.get('employer_contribution_amounts', [0] * n)
            for year in range(n):
                balance = math.floor(
                    (balance + account['contribution_amounts'][year] + employer[year])
                    * (1 + pct(growth_fn(base, year)))
                )
                totals[year] += balance
        return totals

    def scenario_bands(self):
        """Conservative/optimistic return scenarios plus a seeded Monte Carlo range."""
        shift = SCENARIO_RETURN_SHIFT
        conservative = self._net_worth_path(lambda base, year: base + self.return_delta - shift)
        optimistic = self._net_worth_path(lambda base, year: base + self.return_delta + shift)

        rng = random.Random(str(self.plan.pk))
        n = self.years_until_retirement
        paths = []
        for _ in range(MONTE_CARLO_TRIALS):
            shocks = [rng.gauss(0, MONTE_CARLO_VOLATILITY) for _ in range(n)]
            paths.append(self._net_worth_path(lambda base, year: base + self.return_delta + shocks[year]))

        def percentile(values, q):
            ordered = sorted(values)
            return ordered[min(len(ordered) - 1, int(q * len(ordered)))]

        target = self.magic_numbers[-1]
        hits = sum(1 for path in paths if path[-1] >= target) if target > 0 else None
        return {
            'conservative': conservative,
            'optimistic': optimistic,
            'p10': [percentile([p[y] for p in paths], 0.10) for y in range(n)],
            'p50': [percentile([p[y] for p in paths], 0.50) for y in range(n)],
            'p90': [percentile([p[y] for p in paths], 0.90) for y in range(n)],
            'success_probability': None if hits is None else round(hits / len(paths) * 100),
            'shift': shift,
            'volatility': MONTE_CARLO_VOLATILITY,
        }

    def compute_coast_fi_age(self):
        """Earliest age at which stopping all contributions still lets each account's growth
        carry the balance to the Magic Number at retirement. "N/A" if never."""
        n = self.years_until_retirement
        target = self.magic_numbers[-1]
        if target <= 0:
            return "N/A"
        for index in range(n):
            remaining = n - 1 - index
            total = 0
            for account in self.accounts[1:]:
                growth = account['simple_yearly_growth'] if self.is_simple else account['yearly_growth']
                total += account['end_amounts'][index] * (1 + pct(growth + self.return_delta)) ** remaining
            if total >= target:
                return self.ages[index]
        return "N/A"

    # -------------------------------------------------------------- indicators
    def fi_indicators(self):
        n = self.years_until_retirement
        self.net_worths = sum_series([a['end_amounts'] for a in self.accounts[1:]], n)
        self.magic_numbers = [expenses * SAFE_WITHDRAWAL_MULTIPLE for expenses in self.total_recurring_expenses]
        self.drawdowns = [
            round(self.total_recurring_expenses[year] / self.net_worths[year] * 100, 2) if self.net_worths[year] > 0 else None
            for year in range(n)
        ]

        self.fi_age = "N/A"
        for index, (net_worth, magic) in enumerate(zip(self.net_worths, self.magic_numbers)):
            if magic > 0 and net_worth >= magic:
                self.fi_age = self.ages[index]
                break

        self.coast_fi_age = self.compute_coast_fi_age()
        self.coast_fi_years_away = self.coast_fi_age - self.plan.current_age if isinstance(self.coast_fi_age, int) else None

        self.net_worths_last = money(self.net_worths[-1])
        self.magic_numbers_last = money(self.magic_numbers[-1])
        self.drawdowns_last = "N/A" if self.drawdowns[-1] is None else f"{self.drawdowns[-1]}%"

        # Dashboard summary
        projected, target = self.net_worths[-1], self.magic_numbers[-1]
        working_years = [y for y in range(n) if y < self.years_until_coast_fire and self.total_net_income[y] > 0]
        savings_rate = (
            sum(self.total_savings[y] / self.total_net_income[y] for y in working_years) / len(working_years) * 100
            if working_years else 0
        )
        self.fi_reached = target > 0 and projected >= target
        self.funded_percent = round(projected / target * 100) if target > 0 else 0
        self.funded_gap = projected - target
        self.funded_gap_display = money(abs(self.funded_gap))
        self.average_savings_rate = round(savings_rate, 1)
        self.fi_years_away = self.fi_age - self.plan.current_age if isinstance(self.fi_age, int) else None
        self.unallocated_total = sum(self.unallocated_savings)
        self.has_shortfall_years = any(s < 0 for s in self.total_savings)

    def chart_data(self):
        accounts = [
            {'name': a.get('saving_name', 'Savings'), 'end_amounts': a['end_amounts']}
            for a in self.accounts[1:]
        ]
        return {
            'ages': self.ages,
            'net_worths': self.net_worths,
            'magic_numbers': self.magic_numbers,
            'income': self.total_net_income,
            'expenses': self.total_expenses,
            'savings': self.total_savings,
            'fi_age': self.fi_age if isinstance(self.fi_age, int) else None,
            'retirement_age': self.ages[-1],
            'coast_fi_age': self.coast_fi_age if isinstance(self.coast_fi_age, int) else None,
            'accounts': accounts,
            'scenarios': self.scenario_bands(),
        }

    def withdrawal_data(self, end_age=95, inflation=2.5, annual_return=None, spending_percent=100):
        """Retirement-phase projection: spend down the portfolio from retirement to ``end_age``.

        Spending starts at the plan's final-year recurring expenses (scaled by ``spending_percent``)
        and grows with ``inflation``. Returns are fixed for the main path and randomised for the
        Monte Carlo survival odds."""
        n = self.years_until_retirement
        start_age = self.plan.current_age + n
        end_age = int(max(end_age, start_age + 1))
        years = end_age - start_age
        portfolio = self.net_worths[-1]
        blended = 0.0
        if portfolio > 0:
            blended = sum(
                a['end_amounts'][-1] * (a['simple_yearly_growth'] if self.is_simple else a['yearly_growth'])
                for a in self.accounts[1:]
            ) / portfolio + self.return_delta
        default_return = round(min(max(blended, 0.0), MAX_DEFAULT_RETIREMENT_RETURN), 1)
        annual_return = default_return if annual_return is None else float(annual_return)
        first_year_spending = self.total_recurring_expenses[-1] * (1 + pct(inflation)) * spending_percent / 100

        def simulate(returns):
            balance, path, spend_path = portfolio, [], []
            depleted_age = None
            for year in range(years):
                spend = first_year_spending * (1 + pct(inflation)) ** year
                balance = (balance - spend) * (1 + pct(returns[year])) if balance > 0 else 0
                if balance <= 0 and depleted_age is None:
                    depleted_age = start_age + year
                    balance = 0
                path.append(round(balance))
                spend_path.append(round(spend))
            return path, spend_path, depleted_age

        flat = [annual_return] * years
        path, spending, depleted_age = simulate(flat)

        rng = random.Random(f"{self.plan.pk}-withdrawal")
        trials = [simulate([annual_return + rng.gauss(0, MONTE_CARLO_VOLATILITY) for _ in range(years)]) for _ in range(MONTE_CARLO_TRIALS)]

        def percentile(year, q):
            ordered = sorted(t[0][year] for t in trials)
            return ordered[min(len(ordered) - 1, int(q * len(ordered)))]

        survived = sum(1 for t in trials if t[2] is None)
        return {
            'ages': [start_age + year for year in range(years)],
            'balances': path,
            'spending': spending,
            'p10': [percentile(y, 0.10) for y in range(years)],
            'p50': [percentile(y, 0.50) for y in range(years)],
            'p90': [percentile(y, 0.90) for y in range(years)],
            'start_age': start_age,
            'end_age': end_age,
            'starting_portfolio': portfolio,
            'starting_portfolio_display': money(portfolio),
            'first_year_spending': round(first_year_spending),
            'first_year_spending_display': money(first_year_spending),
            'initial_withdrawal_rate': round(first_year_spending / portfolio * 100, 1) if portfolio > 0 else None,
            'depleted_age': depleted_age,
            'ending_balance_display': money(path[-1]) if path else money(portfolio),
            'success_probability': round(survived / len(trials) * 100),
            'default_return': default_return,
            'return': annual_return,
            'inflation': float(inflation),
            'volatility': MONTE_CARLO_VOLATILITY,
        }

    def whatif_data(self):
        """Light-weight payload for the what-if sliders."""
        return {
            'ages': self.ages,
            'net_worths': self.net_worths,
            'magic_numbers': self.magic_numbers,
            'fi_age': self.fi_age if isinstance(self.fi_age, int) else None,
            'coast_fi_age': self.coast_fi_age if isinstance(self.coast_fi_age, int) else None,
            'net_worth_display': self.net_worths_last,
            'magic_number_display': self.magic_numbers_last,
            'funded_percent': self.funded_percent,
            'fi_reached': self.fi_reached,
        }

    # ------------------------------------------------------------ table / csv
    def template_data(self):
        plan_data = []
        for year in range(self.years_until_retirement):
            row = [self.ages[year], self.years[year]]

            for income in self.incomes:
                row.append(money(income['gross_amounts'][year]))
                if income['income_category'] == 'Salary':
                    row.append(money(income['bonus_amounts'][year]))
                row.append(money(income['tax_amounts'][year]))
                row.append(money(income['net_amounts'][year]))

            for expense in self.expenses:
                row.append(money(expense['amounts'][year]))

            row.append(money(self.total_savings[year]))

            for account in self.accounts[1:]:
                category = account.get('saving_category')
                row.append(money(account['start_amounts'][year]))
                if category in ('ESRP', 'HSA', 'IRA'):
                    row.append(money(account['contribution_limits'][year]))
                row.append(money(account['contribution_amounts'][year]))
                if category == 'ESRP':
                    row.append(money(account['employer_contribution_amounts'][year]))
                row.append(money(account['end_amounts'][year]))

            row.append(money(self.net_worths[year]))
            row.append(money(self.magic_numbers[year]))
            row.append("N/A" if self.drawdowns[year] is None else f"{self.drawdowns[year]}%")
            plan_data.append(row)
        self.plan_data = plan_data

    def update_final_net_worth(self):
        self.plan.final_net_worth = self.net_worths_last
        self.plan.save(update_fields=['final_net_worth'])

    # ------------------------------------------------------------------ sankey
    def sankey_chart(self):
        labels, node_colors = [], []
        sources, targets, values, link_colors = [], [], [], []

        def node(label, color):
            labels.append(label)
            node_colors.append(color)
            return len(labels) - 1

        def link(source, target, value, color):
            if value > 0:
                sources.append(source)
                targets.append(target)
                values.append(value)
                link_colors.append(color)

        income_color, expense_color, saving_color = "#285C53", "#EC652B", "#4F378A"
        total_income = node("Total Income", income_color)

        for label, series in (
            ("Salary", self.total_salary_income),
            ("Bonuses", self.total_bonuses),
            ("Recurring", self.total_recurring_income),
            ("One-time", self.total_one_time_income),
        ):
            if sum(series) > 0:
                link(node(label, income_color), total_income, sum(series), "#DFF5F1")

        link(total_income, node("Taxes", expense_color), sum(self.total_taxes), "#FFEDDD")

        expenses = node("Total Expenses", expense_color)
        link(total_income, expenses, sum(self.total_expenses), "#FFEDDD")
        for label, series in (("Recurring", self.total_recurring_expenses), ("One-time", self.total_one_time_expenses)):
            if sum(series) > 0:
                link(expenses, node(label, expense_color), sum(series), "#FFEDDD")

        savings = node("Total Savings", saving_color)
        link(total_income, savings, sum(s for s in self.total_savings if s > 0), "#EDE6F8")

        if self.is_simple:
            link(savings, node("Investments", saving_color), sum(c for c in self.accounts[1]['contribution_amounts'] if c > 0), "#EDE6F8")
        else:
            esrp_node = None
            for label, series in (
                ("HSA", self.hsa_contribution_amounts),
                ("IRA", self.ira_contribution_amounts),
                ("TBA", self.tba_contribution_amounts),
                ("401k/403b", self.esrp_contribution_amounts),
            ):
                total = sum(v for v in series if v > 0)
                if total > 0:
                    account_node = node(label, saving_color)
                    link(savings, account_node, total, "#EDE6F8")
                    if label == "401k/403b":
                        esrp_node = account_node
            employer_total = sum(self.esrp_employer_contribution_amounts)
            if employer_total > 0 and esrp_node is not None:
                link(node("Employer Contribution", saving_color), esrp_node, employer_total, "#EDE6F8")

        fig = go.Figure(data=[go.Sankey(
            node=dict(pad=15, thickness=20, line=dict(color="black", width=0.5), label=labels, color=node_colors),
            link=dict(source=sources, target=targets, value=values, color=link_colors),
        )])
        fig.update_layout(
            title={
                "text": f"Total Cash Flow: {self.plan.current_age} to {self.plan.retirement_age - 1}",
                "font": {'color': '#777980', 'family': 'Inter', 'size': 16, 'style': 'normal', 'weight': 500},
            },
            title_x=0.05,
            paper_bgcolor="#FCFBF9",
            plot_bgcolor="#FCFBF9",
            font=dict(family="Inter", size=16, color="black"),
        )
        return fig.to_html(full_html=True)
