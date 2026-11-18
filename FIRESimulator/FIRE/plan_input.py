"""Parsing and validation of plan survey / dashboard form submissions."""
from . import taxes
from .engine import CURRENT_AGE, RETIREMENT_AGE
from .models import user_is_premium


class PlanInputError(ValueError):
    """Raised with a user-facing message when submitted plan data is invalid."""


def _to_int(value):
    return int(float(value))


def _field(request, name, index, cast, label):
    values = request.POST.getlist(name)
    try:
        return cast(values[index])
    except (IndexError, ValueError, TypeError):
        raise PlanInputError(f"Please enter a valid value for {label}.")


def _single(request, name, cast, label):
    return _field(request, name, 0, cast, label)


def _check_range(value, low, high, label):
    if not low <= value <= high:
        raise PlanInputError(f"{label} must be between {low} and {high}.")


def _parse_ages(request):
    try:
        current_age = int(request.POST.get('current_age'))
        retirement_age = int(request.POST.get('retirement_age'))
    except (TypeError, ValueError):
        raise PlanInputError("Invalid age provided.")
    if not 1 <= current_age <= 100 or not 1 <= retirement_age <= 101:
        raise PlanInputError("Ages must be between 1 and 100.")

    if retirement_age <= current_age:
        raise PlanInputError("Retirement age must be greater than current age.")
    return current_age, retirement_age


def _parse_recurring_ages(request, prefix, idx, label, current_age, retirement_age):
    last_age = retirement_age - 1
    raw_start = request.POST.getlist(f'{prefix}_start_age')
    raw_stop = request.POST.getlist(f'{prefix}_stop_age')
    try:
        start = current_age if raw_start[idx] == CURRENT_AGE else int(raw_start[idx])
        stop = last_age if raw_stop[idx] == RETIREMENT_AGE else int(raw_stop[idx])
    except (IndexError, ValueError):
        raise PlanInputError(f"Please select valid start and stop ages for {label}.")
    if not current_age <= start <= last_age:
        raise PlanInputError(f"{label}: start age must be between {current_age} and {last_age}.")
    if not current_age <= stop <= last_age:
        raise PlanInputError(f"{label}: stop age must be between {current_age} and {last_age}.")
    if start > stop:
        raise PlanInputError(f"{label}: start age can not be after stop age.")
    return (
        CURRENT_AGE if start == current_age else start,
        RETIREMENT_AGE if stop == last_age else stop,
    )


def _parse_incomes(request, current_age, retirement_age):
    names = request.POST.getlist('income_name')
    categories = request.POST.getlist('income_category')
    if not names:
        raise PlanInputError("No incomes provided.")

    counters = {'Salary': 0, 'Recurring': 0, 'One-time': 0}
    incomes = []
    for category, name in zip(categories, names):
        if category not in counters:
            raise PlanInputError("Invalid income category.")
        idx = counters[category]
        counters[category] += 1
        label = f"Income '{name}'"
        income = {'income_category': category, 'income_name': name}

        if category == 'One-time':
            income['amount'] = _field(request, 'one_time_income_amount', idx, _to_int, f"{label} amount")
            income['age'] = _field(request, 'one_time_income_age', idx, int, f"{label} age")
            income['tax_rate'] = _field(request, 'one_time_income_tax_rate', idx, float, f"{label} tax rate")
            if not current_age <= income['age'] < retirement_age:
                raise PlanInputError(f"{label}: age must be between {current_age} and {retirement_age - 1}.")
        else:
            prefix = 'salary' if category == 'Salary' else 'recurring_income'
            income['starting_amount'] = _field(request, f'{prefix}_starting_amount', idx, _to_int, f"{label} starting amount")
            income['yearly_change'] = _field(request, f'{prefix}_yearly_change', idx, float, f"{label} yearly change")
            if category == 'Salary':
                income['bonus_rate'] = _field(request, 'salary_bonus_rate', idx, float, f"{label} bonus rate")
                _check_range(income['bonus_rate'], 0, 1000, f"{label} bonus rate")
            income['tax_rate'] = _field(request, f'{prefix}_tax_rate', idx, float, f"{label} tax rate")
            income['tax_rate_change'] = _field(request, f'{prefix}_tax_rate_change', idx, float, f"{label} tax rate change")
            income['start_age'], income['stop_age'] = _parse_recurring_ages(
                request, prefix, idx, label, current_age, retirement_age)
            _check_range(income['yearly_change'], -100, 100, f"{label} yearly change")

        if income.get('starting_amount', income.get('amount', 0)) < 0:
            raise PlanInputError(f"{label}: amount can not be negative.")
        _check_range(income['tax_rate'], 0, 100, f"{label} tax rate")
        incomes.append(income)
    return incomes


def _parse_expenses(request, current_age, retirement_age):
    names = request.POST.getlist('expense_name')
    categories = request.POST.getlist('expense_category')
    if not names:
        raise PlanInputError("No expenses provided.")

    counters = {'Recurring': 0, 'One-time': 0}
    expenses = []
    for category, name in zip(categories, names):
        if category not in counters:
            raise PlanInputError("Invalid expense category.")
        idx = counters[category]
        counters[category] += 1
        label = f"Expense '{name}'"
        expense = {'expense_category': category, 'expense_name': name}

        if category == 'One-time':
            expense['amount'] = _field(request, 'one_time_expense_amount', idx, _to_int, f"{label} amount")
            expense['age'] = _field(request, 'one_time_expense_age', idx, int, f"{label} age")
            if not current_age <= expense['age'] < retirement_age:
                raise PlanInputError(f"{label}: age must be between {current_age} and {retirement_age - 1}.")
        else:
            expense['starting_amount'] = _field(request, 'recurring_expense_starting_amount', idx, _to_int, f"{label} starting amount")
            expense['yearly_change'] = _field(request, 'recurring_expense_yearly_change', idx, float, f"{label} yearly change")
            expense['start_age'], expense['stop_age'] = _parse_recurring_ages(
                request, 'recurring_expense', idx, label, current_age, retirement_age)
            _check_range(expense['yearly_change'], -100, 100, f"{label} yearly change")

        if expense.get('starting_amount', expense.get('amount', 0)) < 0:
            raise PlanInputError(f"{label}: amount can not be negative.")
        expenses.append(expense)
    return expenses


MAX_CUSTOM_ACCOUNTS = 8
ALLOCATION_MODES = ('limit', 'fixed', 'percent', 'match', 'none')
UNLIMITED_CATEGORIES = ('TBA', 'HYSA')


def _by_position(request, name, position, default):
    values = request.POST.getlist(name)
    return values[position] if position < len(values) else default


def _parse_custom_settings(request, position, category, label):
    """Per-account allocation rule for Custom plans (missing values use defaults)."""
    mode = _by_position(request, 'allocation_mode', position, 'limit')
    if mode not in ALLOCATION_MODES or (mode == 'match' and category != 'ESRP'):
        raise PlanInputError(f"{label}: invalid allocation method.")
    try:
        value = float(_by_position(request, 'allocation_value', position, 0) or 0)
    except ValueError:
        raise PlanInputError(f"{label}: please enter a valid allocation amount.")
    if mode == 'fixed':
        _check_range(value, 0, 10000000, f"{label} yearly amount")
        value = int(value)
    elif mode == 'percent':
        _check_range(value, 0, 100, f"{label} percent of savings")
    else:
        value = 0
    return {'allocation_mode': mode, 'allocation_value': value}


def _parse_savings(request, allow_custom=False):
    option = request.POST.get('saving_option')
    if option == 'Custom' and not allow_custom:
        raise PlanInputError("The Custom savings method is a Premium feature. Please choose Simple or Recommended.")
    if option == 'Simple':
        net_worth = _single(request, 'simple_net_worth', _to_int, "current net worth")
        growth = _single(request, 'simple_yearly_growth', float, "yearly growth")
        if net_worth < 0:
            raise PlanInputError("Current net worth can not be negative.")
        _check_range(growth, -50, 50, "Yearly growth")
        return [option, {'simple_net_worth': net_worth, 'simple_yearly_growth': growth}]

    names = request.POST.getlist('saving_name')
    categories = request.POST.getlist('saving_category')
    custom = option == 'Custom'
    if not names:
        raise PlanInputError("No savings provided.")
    if custom and len(names) > MAX_CUSTOM_ACCOUNTS:
        raise PlanInputError(f"You can add up to {MAX_CUSTOM_ACCOUNTS} accounts.")
    if not custom and len(set(categories)) != len(categories):
        raise PlanInputError("Each savings account type can only be added once.")

    savings = [option]
    seen = {}
    for position, (category, name) in enumerate(zip(categories, names)):
        if category not in ('ESRP', 'HSA', 'IRA', 'TBA') + (('HYSA',) if custom else ()):
            raise PlanInputError("Invalid saving category.")
        prefix = category.lower()
        # Custom plans can hold several accounts of one type; fields are matched by order within the type
        index = seen.get(category, 0)
        seen[category] = index + 1
        label = f"Account '{name}'"
        saving = {'saving_category': category, 'saving_name': name}
        saving['current_value'] = _field(request, f'{prefix}_current_value', index, _to_int, f"{label} current value")
        saving['yearly_growth'] = _field(request, f'{prefix}_yearly_growth', index, float, f"{label} yearly growth")
        if saving['current_value'] < 0:
            raise PlanInputError(f"{label}: current value can not be negative.")
        _check_range(saving['yearly_growth'], -50, 50, f"{label} yearly growth")
        if category == 'ESRP':
            saving['employer_contribution_rate'] = _field(request, 'esrp_contribution_rate', index, float, f"{label} employer contribution")
            _check_range(saving['employer_contribution_rate'], 0, 100, f"{label} employer contribution")
        if category not in UNLIMITED_CATEGORIES:
            saving['contribution_limit'] = _field(request, f'{prefix}_contribution_limit', index, _to_int, f"{label} contribution limit")
            saving['contribution_limit_step'] = _field(request, f'{prefix}_contribution_limit_step', index, _to_int, f"{label} limit increase")
            if saving['contribution_limit'] < 0:
                raise PlanInputError(f"{label}: contribution limit can not be negative.")
        if custom:
            saving.update(_parse_custom_settings(request, position, category, label))
        savings.append(saving)
    if option == 'Recommended':
        order = ['ESRP', 'HSA', 'IRA', 'TBA']
        savings[1:] = sorted(savings[1:], key=lambda s: order.index(s['saving_category']))
    return savings


def _parse_tax_settings(request):
    """Automatic tax estimates are opt-in per submission; otherwise manual rates apply."""
    if request.POST.get('tax_mode') != 'auto':
        return {'mode': 'manual'}
    status = request.POST.get('tax_filing_status', 'single')
    state = request.POST.get('tax_state', taxes.NO_STATE)
    if status not in taxes.FILING_STATUSES:
        raise PlanInputError("Invalid filing status.")
    if state != taxes.NO_STATE and state not in taxes.STATE_RATES:
        raise PlanInputError("Invalid state.")
    return {'mode': 'auto', 'filing_status': status, 'state': state}


def saveplan(form, request, dashboard_edit=False):
    """Validate the submitted plan and save it. Returns the Plan, or an error message string."""
    try:
        if not request.POST.get('plan_name') and not dashboard_edit:
            return "Please provide a name for this plan."
        current_age, retirement_age = _parse_ages(request)
        incomes = _parse_incomes(request, current_age, retirement_age)
        tax_settings = _parse_tax_settings(request)
        expenses = _parse_expenses(request, current_age, retirement_age)
        existing = getattr(form.instance, 'savings', None) or []
        allow_custom = user_is_premium(request.user) or (bool(existing) and existing[0] == 'Custom')
        savings = _parse_savings(request, allow_custom)
    except PlanInputError as error:
        return str(error)

    try:
        if not form.is_valid():
            return " ".join(error for errors in form.errors.values() for error in errors)
        plan = form.save(commit=False)
        if request.user.is_authenticated:
            plan.user = request.user
        plan.incomes = incomes
        plan.tax_settings = tax_settings
        plan.expenses = expenses
        plan.savings = savings
        plan.save()
        return plan
    except Exception as e:
        print(f"Error Saving: {e}")
        return "Error saving plan, please try again."
