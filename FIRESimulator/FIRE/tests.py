from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from django.test import client as _test_client

from .engine import PlanObject, money
from .models import Plan

# Django 4.2's test client copies template contexts, which breaks on Python 3.14+.
# These tests don't inspect response.context, so skip that bookkeeping.
_test_client.store_rendered_templates = lambda *args, **kwargs: None


def make_plan(savings, current_age=30, retirement_age=35, coast_fire_age=None, salary=100000, expense=40000):
    return SimpleNamespace(
        current_age=current_age,
        retirement_age=retirement_age,
        coast_fire_age=coast_fire_age,
        incomes=[{
            'income_category': 'Salary', 'income_name': 'Job', 'starting_amount': salary, 'yearly_change': 0.0,
            'bonus_rate': 0.0, 'tax_rate': 20.0, 'tax_rate_change': 0.0,
            'start_age': 'Current Age', 'stop_age': 'Target Retirement Age',
        }],
        expenses=[{
            'expense_category': 'Recurring', 'expense_name': 'Living', 'starting_amount': expense,
            'yearly_change': 0.0, 'start_age': 'Current Age', 'stop_age': 'Target Retirement Age',
        }],
        savings=savings,
    )


ESRP = {'saving_category': 'ESRP', 'saving_name': '401k', 'current_value': 0, 'yearly_growth': 0.0,
        'employer_contribution_rate': 5.0, 'contribution_limit': 10000, 'contribution_limit_step': 0}
HSA = {'saving_category': 'HSA', 'saving_name': 'HSA', 'current_value': 0, 'yearly_growth': 0.0,
       'contribution_limit': 4000, 'contribution_limit_step': 0}
TBA = {'saving_category': 'TBA', 'saving_name': 'Brokerage', 'current_value': 0, 'yearly_growth': 0.0}


class EngineTests(TestCase):
    def test_simple_plan_projects_net_worth(self):
        plan = make_plan(['Simple', {'simple_net_worth': 1000, 'simple_yearly_growth': 0.0}])
        fi = PlanObject(plan).run()
        self.assertEqual(fi.total_savings, [40000] * 5)
        self.assertEqual(fi.net_worths[-1], 1000 + 5 * 40000)
        self.assertEqual(fi.magic_numbers[-1], 40000 * 25)

    def test_employer_match_not_double_counted(self):
        fi = PlanObject(make_plan(['Custom', dict(ESRP), dict(HSA), dict(TBA)])).run()
        esrp = fi.accounts[1]
        self.assertEqual(esrp['employer_contribution_amounts'], [5000] * 5)
        self.assertEqual(esrp['contribution_amounts'], [10000] * 5)
        self.assertEqual(fi.accounts[2]['contribution_amounts'], [4000] * 5)
        self.assertEqual(fi.accounts[3]['contribution_amounts'], [26000] * 5)
        self.assertEqual(fi.unallocated_total, 0)

    def test_unallocated_savings_reported(self):
        fi = PlanObject(make_plan(['Custom', dict(ESRP)])).run()
        self.assertEqual(fi.unallocated_savings, [30000] * 5)

    def test_plan_is_not_mutated(self):
        plan = make_plan(['Simple', {'simple_net_worth': 0, 'simple_yearly_growth': 5.0}])
        PlanObject(plan).run()
        self.assertNotIn('gross_amounts', plan.incomes[0])

    def test_money_negative(self):
        self.assertEqual(money(-1500), '-$1,500')


def survey_post(**overrides):
    data = {
        'plan_name': 'My Plan', 'current_age': '30', 'retirement_age': '35',
        'income_name': ['Job'], 'income_category': ['Salary'],
        'salary_starting_amount': ['100000'], 'salary_yearly_change': ['3'], 'salary_bonus_rate': ['0'],
        'salary_tax_rate': ['20'], 'salary_tax_rate_change': ['0'],
        'salary_start_age': ['Current Age'], 'salary_stop_age': ['Target Retirement Age'],
        'expense_name': ['Living'], 'expense_category': ['Recurring'],
        'recurring_expense_starting_amount': ['40000'], 'recurring_expense_yearly_change': ['2'],
        'recurring_expense_start_age': ['Current Age'], 'recurring_expense_stop_age': ['Target Retirement Age'],
        'saving_option': 'Simple', 'simple_net_worth': '1000', 'simple_yearly_growth': '6',
    }
    data.update(overrides)
    return data


class SurveyAndPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'pw-12345-xyz')
        self.other = User.objects.create_user('other', 'other@example.com', 'pw-12345-xyz')

    def create_plan(self):
        response = self.client.post(reverse('newplan'), survey_post())
        self.assertEqual(response.status_code, 302)
        return Plan.objects.latest('created_at')

    def test_survey_creates_plan_and_dashboard_renders(self):
        plan = self.create_plan()
        response = self.client.get(reverse('runplan', args=[plan.id]))
        self.assertEqual(response.status_code, 200)

    def test_survey_validation(self):
        for field, value in {'retirement_age': '30', 'salary_tax_rate': ['150'], 'simple_net_worth': 'abc'}.items():
            response = self.client.post(reverse('newplan'), survey_post(**{field: value}))
            self.assertEqual(response.status_code, 200, field)
        self.assertEqual(Plan.objects.count(), 0)

    def test_csv_download(self):
        plan = self.create_plan()
        response = self.client.get(reverse('downloadplan', args=[plan.id]))
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_other_users_cannot_touch_owned_plan(self):
        self.client.force_login(self.owner)
        plan = self.create_plan()
        self.client.logout()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(reverse('deleteplan', args=[plan.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse('downloadplan', args=[plan.id])).status_code, 404)
        self.assertTrue(Plan.objects.filter(pk=plan.pk).exists())

    def test_signup_rejects_duplicate_email(self):
        response = self.client.post(reverse('signupuser'), {
            'username': 'dupe', 'email': 'OWNER@example.com', 'password1': 'Str0ng-pass-99', 'password2': 'Str0ng-pass-99'})
        self.assertEqual(User.objects.filter(username='dupe').count(), 0)
        self.assertEqual(response.status_code, 200)

    def test_dashboard_embeds_chart_json_and_lists_show_fi_age(self):
        self.client.force_login(self.owner)
        plan = self.create_plan()
        page = self.client.get(reverse('runplan', args=[plan.id])).content.decode()
        self.assertIn('id="plan-chart-data"', page)
        self.assertNotIn('data-networths', page)
        self.assertContains(self.client.get(reverse('userplans')), 'FI Age')

    def test_compare_plans_requires_own_plans(self):
        self.client.force_login(self.owner)
        first, second = self.create_plan(), self.create_plan()
        ok = self.client.get(reverse('compareplans'), {'plans': [first.id, second.id]})
        self.assertEqual(ok.status_code, 200)
        self.assertContains(ok, 'compare-data')
        self.client.logout()
        self.client.force_login(self.other)
        denied = self.client.get(reverse('compareplans'), {'plans': [first.id, second.id]})
        self.assertEqual(denied.status_code, 302)
        self.assertEqual(self.client.get(reverse('compareplans'), {'plans': ['nope', first.id]}).status_code, 302)

