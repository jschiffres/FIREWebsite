import json

from django.test import TestCase, override_settings
from django.urls import reverse

from . import simulation
from .models import Scenario

SC = {'age': 30, 'plan_to_age': 95, 'filing_status': 'single', 'state': 'NONE', 'seed': 1}


def inc(**kw):
    d = dict(id=1, kind='income', name='Job', amount=6000, frequency='monthly', growth_pct=2, bonus_pct=0,
             taxed=True, payroll_taxed=True, tax_deferred=False, start_age=None, end_mode='fi', end_age=None,
             account_type='', contribution_type='posttax', contribution_limit=None, fixed_growth=False,
             fixed_growth_pct=None, allocation_pct=0, savings_level='none', priority=0)
    d.update(kw)
    return d


class SimulationTests(TestCase):
    def test_empty(self):
        r = simulation.run(SC, [])
        self.assertEqual(r['status'], 'empty')
        self.assertIsNone(r['fi_age'])

    def test_saver_reaches_fi_and_sankey_balances(self):
        items = [inc(), inc(id=2, kind='expense', name='Rent', amount=2500, end_mode='life', growth_pct=2.5),
                 inc(id=3, kind='account', name='Brokerage', amount=50000, account_type='taxable',
                     allocation_pct=100)]
        r = simulation.run(SC, items)
        self.assertIsNotNone(r['fi_age'])
        self.assertGreater(r['fi_age'], 30)
        for links in r['sankey'][:3]:
            into = sum(v for a, b, v in links if b == 'Money in')
            out = sum(v for a, b, v in links if a == 'Money in')
            self.assertAlmostEqual(into, out, delta=10)

    def test_priority_fills_in_order_then_taxable_gets_rest(self):
        items = [inc(), inc(id=2,         kind='expense', name='Rent', amount=1500, end_mode='life'),
                 inc(id=3, kind='account', name='401k', amount=0, account_type='employer',
                     contribution_type='pretax', savings_level='max', priority=1),
                 inc(id=4, kind='account', name='IRA', amount=0, account_type='ira', contribution_type='posttax',
                     savings_level='max', priority=0),
                 inc(id=5, kind='account', name='Brokerage', amount=0, account_type='taxable', allocation_pct=50)]
        cf = simulation.cashflows(SC, items, 60)
        f = cf['factor'][0]
        self.assertAlmostEqual(cf['contrib'][4][0], 7000 * f)
        self.assertAlmostEqual(cf['contrib'][3][0], 23500 * f)
        left = cf['spendable'][0] - (7000 + 23500) * f
        self.assertAlmostEqual(cf['contrib'][5][0], max(left, 0), places=2)
        self.assertAlmostEqual(cf['free'][0], 0, places=1)

    def test_user_limit_is_not_inflated_in_first_year(self):
        items = [inc(), inc(id=3, kind='account', name='HSA', amount=0, account_type='hsa',
                            contribution_type='pretax', savings_level='max', contribution_limit=4500)]
        cf = simulation.cashflows(SC, items, 60)
        self.assertAlmostEqual(cf['contrib'][3][0], 4500)

    def test_start_at_fi_expense_only_after_fi(self):
        items = [inc(), inc(id=2, kind='expense', name='Insurance', amount=500, end_mode='life', start_at_fi=True)]
        cf = simulation.cashflows(SC, items, 40)
        ages = cf['ages']
        self.assertEqual(cf['expenses'][ages < 40].sum(), 0)
        self.assertGreater(cf['expenses'][ages == 40][0], 0)

    def test_run_chart_series_lengths(self):
        items = [inc(), inc(id=2, kind='expense', name='Life', amount=2000, end_mode='life')]
        r = simulation.run(SC, items)
        n = len(r['ages'])
        for key in ('income', 'expenses', 'taxes', 'savings_rate'):
            self.assertEqual(len(r[key]), n)
        self.assertTrue(r['retire_options'])
        self.assertTrue(all(0 <= o['success'] <= 100 for o in r['retire_options']))

    def test_no_savings_never_fi(self):
        items = [inc(), inc(id=2, kind='expense', name='Life', amount=6000, end_mode='life')]
        self.assertIsNone(simulation.run(SC, items)['fi_age'])


class ViewTests(TestCase):
    def setUp(self):
        self.sc = Scenario.objects.create(age=30)

    def post(self, name, body, **kw):
        return self.client.post(reverse(name, kwargs={'pk': self.sc.pk, **kw}), json.dumps(body),
                                content_type='application/json')

    def test_flow(self):
        r = self.client.post(reverse('lab_home'), {'age': 35})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get(reverse('lab_scenario', args=[self.sc.pk])).status_code, 200)
        r = self.post('lab_item_add', {'kind': 'income', 'name': 'Job', 'amount': '5000', 'frequency': 'monthly',
                                       'growth_pct': '2', 'bonus_pct': '0', 'taxed': True, 'payroll_taxed': True,
                                       'end_mode': 'fi'})
        self.assertEqual(r.status_code, 200)
        item = r.json()['items'][0]
        r = self.post('lab_item_edit', {'name': 'Job 2', 'amount': '6000', 'frequency': 'monthly', 'growth_pct': '2',
                                        'bonus_pct': '0', 'end_mode': 'age', 'end_age': '40'}, item_pk=item['id'])
        self.assertEqual(r.json()['items'][0]['name'], 'Job 2')
        r = self.post('lab_item_add', {'kind': 'income', 'name': 'x', 'amount': '1', 'frequency': 'monthly',
                                       'growth_pct': '0', 'bonus_pct': '0', 'end_mode': 'age'})
        self.assertEqual(r.status_code, 400)
        r = self.post('lab_item_delete', {}, item_pk=item['id'])
        self.assertEqual(r.json()['items'], [])

    def test_age_bounds_and_employer_match(self):
        base = {'kind': 'income', 'name': 'Job', 'amount': '5000', 'frequency': 'biannual', 'growth_pct': '0',
                'bonus_pct': '0', 'end_mode': 'age'}
        for extra in ({'start_age': 30, 'end_age': 40}, {'end_age': 95}, {'start_age': 40, 'end_age': 35}):
            self.assertEqual(self.post('lab_item_add', {**base, **extra}).status_code, 400, extra)
        r = self.post('lab_item_add', {**base, 'start_age': 31, 'end_age': 94})
        self.assertEqual(r.status_code, 200)
        income_id = r.json()['items'][0]['id']
        acct = {'kind': 'account', 'name': '401k', 'amount': '0', 'account_type': 'employer',
                'contribution_type': 'pretax', 'employer_match_pct': '5'}
        self.assertEqual(self.post('lab_item_add', acct).status_code, 400)
        r = self.post('lab_item_add', {**acct, 'linked_income': income_id})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['items'][1]['linked_income'], income_id)

    @override_settings(LAB_ENABLED=False)
    def test_disabled_404(self):
        self.assertEqual(self.client.get(reverse('lab_home')).status_code, 404)


class OwnershipAndPremiumTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import User
        from FIRE.models import Profile
        self.User, self.Profile = User, Profile
        self.u = User.objects.create_user('a', 'a@example.com', 'pw-12345-xyz')
        self.o = User.objects.create_user('b', 'b@example.com', 'pw-12345-xyz')

    def premium(self, user):
        self.Profile.objects.update_or_create(user=user, defaults={'is_premium': True, 'email_verified': True})

    def test_owner_only_access(self):
        sc = Scenario.objects.create(age=30, owner=self.u)
        self.client.force_login(self.o)
        self.assertEqual(self.client.get(reverse('lab_scenario', args=[sc.pk])).status_code, 404)
        self.client.force_login(self.u)
        self.assertEqual(self.client.get(reverse('lab_scenario', args=[sc.pk])).status_code, 200)

    def test_free_limit_and_premium(self):
        self.client.force_login(self.u)
        for _ in range(2):
            self.assertEqual(self.client.post(reverse('lab_home'), {'age': 30}).status_code, 302)
        r = self.client.post(reverse('lab_home'), {'age': 30})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.u.lab_scenarios.count(), 2)
        self.premium(self.u)
        self.assertEqual(self.client.post(reverse('lab_home'), {'age': 30}).status_code, 302)

    def test_claim_session_scenario_on_login(self):
        self.client.post(reverse('lab_home'), {'age': 33})
        sc = Scenario.objects.get()
        self.assertIsNone(sc.owner)
        self.client.force_login(self.u)
        self.assertEqual(self.client.get(reverse('lab_mine')).status_code, 200)
        sc.refresh_from_db()
        self.assertEqual(sc.owner, self.u)

    def test_mine_requires_login(self):
        self.assertEqual(self.client.get(reverse('lab_mine')).status_code, 302)

    def test_extras_stripped_for_free(self):
        sc = Scenario.objects.create(age=30, owner=self.u)
        self.client.force_login(self.u)
        body = json.dumps({'kind': 'income', 'name': 'Job', 'amount': '9000', 'frequency': 'monthly',
                           'growth_pct': '0', 'bonus_pct': '0', 'taxed': True, 'payroll_taxed': True, 'end_mode': 'fi'})
        r = self.client.post(reverse('lab_item_add', args=[sc.pk]), body, content_type='application/json')
        res = r.json()['results']
        self.assertEqual(res['retire_options'], [])
        self.assertEqual(res['acct_bal'], {})

    def test_exports_gated(self):
        sc = Scenario.objects.create(age=30, owner=self.u)
        self.client.force_login(self.u)
        for name in ('lab_export_csv', 'lab_export_pdf'):
            self.assertEqual(self.client.get(reverse(name, args=[sc.pk])).status_code, 302)
        self.premium(self.u)
        from .models import Item
        Item.objects.create(scenario=sc, kind='income', name='Job', amount=9000, frequency='monthly')
        Item.objects.create(scenario=sc, kind='expense', name='Rent', amount=2000, frequency='monthly')
        r = self.client.get(reverse('lab_export_csv', args=[sc.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Job', r.content)
        r = self.client.get(reverse('lab_export_pdf', args=[sc.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))

class AutoBrokerageTests(TestCase):
    def test_leftover_savings_are_invested_without_taxable_account(self):
        from .models import Item  # noqa: F401
        items = [inc(id=1, amount=150000), {**inc(id=2), 'kind': 'expense', 'amount': 40000, 'end_mode': 'life',
                                            'name': 'Rent'}]
        r = simulation.run(SC, items)
        self.assertEqual(r['unallocated_now'], 0)
        self.assertTrue(any('automatic taxable brokerage' in n for n in r['notes']))

    def test_one_off_income_does_not_zero_magic_number(self):
        items = [inc(id=1, amount=100000), {**inc(id=2), 'kind': 'expense', 'amount': 40000, 'end_mode': 'life',
                                            'name': 'Rent'},
                 {**inc(id=3), 'name': 'Gift', 'amount': 500000, 'start_age': 40, 'end_mode': 'age', 'end_age': 40}]
        r = simulation.run(SC, items)
        self.assertTrue(all(m > 0 for m in r['magic']))

class WithdrawalTests(TestCase):
    def test_pretax_withdrawals_are_fully_funded_and_magic_is_25x(self):
        items = [inc(id=1, name='Salary', amount=75000, frequency='yearly', growth_pct=5, end_mode='fi'),
                 inc(id=2, name='Bills', amount=62000, frequency='yearly', kind='expense', growth_pct=2.5, end_mode='life'),
                 inc(id=3, name='401k', amount=75000, kind='account', account_type='employer', contribution_type='pretax', savings_level='max'),
                 inc(id=4, name='Inv', amount=50000, kind='account', account_type='taxable', contribution_type='posttax', allocation_pct=100)]
        r = simulation.run(SC, items)
        self.assertEqual(r['magic'][0], 62000 * 25)
        self.assertLessEqual(r['fi_age'], 72)

class RefundConvergenceTests(TestCase):
    def test_max_401k_leaves_nothing_unallocated_when_savings_below_limit(self):
        for expense in (52000, 55000, 57000):
            items = [inc(id=1, name='Salary', amount=75000, frequency='yearly', growth_pct=5, end_mode='fi'),
                     inc(id=2, name='Bills', amount=expense, frequency='yearly', kind='expense', end_mode='life'),
                     inc(id=3, name='401k', amount=0, kind='account', account_type='employer',
                         contribution_type='pretax', savings_level='max')]
            r = simulation.run(SC, items)
            self.assertEqual(r['unallocated_now'], 0, expense)