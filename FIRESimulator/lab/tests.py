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
