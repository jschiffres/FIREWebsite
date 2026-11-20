from django import forms

from .models import Item

COMMON = ['name', 'amount']
FIELDS = {
    'income': COMMON + ['frequency', 'growth_pct', 'bonus_pct', 'taxed',     'payroll_taxed', 'start_age', 'start_at_fi', 'end_mode', 'end_age'],
        'expense': COMMON + ['frequency', 'growth_pct', 'tax_deferred', 'start_age', 'start_at_fi', 'end_mode', 'end_age'],
    'account': COMMON + ['account_type', 'contribution_type', 'contribution_limit', 'fixed_growth', 'fixed_growth_pct',
                         'employer_match_pct', 'linked_income'],
}


def item_form(kind, data, instance=None, scenario=None):
    class _Form(forms.ModelForm):
        class Meta:
            model = Item
            fields = FIELDS[kind]

        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            if 'linked_income' in self.fields:
                self.fields['linked_income'].queryset = Item.objects.filter(scenario=scenario, kind='income')
            if 'employer_match_pct' in self.fields:
                self.fields['employer_match_pct'].required = False

        def clean(self):
            d = super().clean()
            if scenario and kind != 'account':
                lo, hi = scenario.age + 1, scenario.plan_to_age - 1
                for f, label in (('start_age', 'Start'), ('end_age', 'End')):
                    v = d.get(f)
                    if v is not None and not lo <= v <= hi:
                        self.add_error(f, f'{label} age must be between {lo} and {hi}.')
            if kind == 'account':
                d['employer_match_pct'] = d.get('employer_match_pct') or 0
                if d.get('account_type') != 'employer':
                    d['employer_match_pct'], d['linked_income'] = 0, None
                elif d['employer_match_pct'] and not d.get('linked_income'):
                    self.add_error('linked_income', 'Choose which income the employer match is based on.')
            if d.get('amount') is not None and d['amount'] < 0:
                self.add_error('amount', 'Must be zero or more.')
            if kind != 'account':
                if d.get('start_at_fi'):
                    d['start_age'] = None
                    if d.get('end_mode') == 'fi':
                        self.add_error('end_mode', 'An item that starts at FI cannot also end at FI.')
                if d.get('end_mode') == 'age' and d.get('end_age') is None:
                    self.add_error('end_age', 'Enter an end age.')
                s, e = d.get('start_age'), d.get('end_age')
                if d.get('end_mode') == 'age' and s is not None and e is not None and e < s:
                    self.add_error('end_age', 'End age must be after the start age.')
            else:
                if not d.get('account_type'):
                    self.add_error('account_type', 'Choose an account type.')
                if d.get('fixed_growth') and d.get('fixed_growth_pct') is None:
                    self.add_error('fixed_growth_pct', 'Enter a growth rate.')
            return d

    return _Form(data, instance=instance)
