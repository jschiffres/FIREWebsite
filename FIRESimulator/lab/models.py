import uuid

from django.conf import settings
from django.db import models


class Scenario(models.Model):
    FILING = [('single', 'Single'), ('married', 'Married filing jointly')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Null for anonymous scenarios, which stay reachable by their link until a signed-in user claims them.
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE,
                              related_name='lab_scenarios')
    name = models.CharField(max_length=60, default='My scenario')
    age = models.PositiveSmallIntegerField()
    plan_to_age = models.PositiveSmallIntegerField(default=95)
    filing_status = models.CharField(max_length=10, choices=FILING, default='single')
    state = models.CharField(max_length=4, default='NONE')
    created = models.DateTimeField(auto_now_add=True)


class Item(models.Model):
    INCOME, EXPENSE, ACCOUNT = 'income', 'expense', 'account'
    KINDS = [(INCOME, 'Income'), (EXPENSE, 'Expense'), (ACCOUNT, 'Account')]
    FREQUENCIES = [('weekly', 'Weekly'), ('biweekly', 'Bi-weekly'), ('bimonthly', 'Twice a month'),
                   ('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('biannual', 'Twice a year'),
                   ('yearly', 'Yearly')]
    END_MODES = [('fi', 'Until FI'), ('age', 'Specific age'), ('life', 'For life')]
    ACCOUNT_TYPES = [('cash', 'Cash / savings'), ('employer', 'Employer retirement (401k, 403b, 457b, TSP)'),
                     ('ira', 'Individual retirement (IRA)'), ('hsa', 'Health savings (HSA)'),
                     ('taxable', 'Taxable investment'), ('education', 'Education savings (529)'),
                     ('alt', 'Alternative (crypto, private equity)')]
    CONTRIBUTION_TYPES = [('pretax', 'Pre-tax'), ('posttax', 'Post-tax'), ('none', 'N/A'), ('dormant', 'Dormant')]

    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name='items')
    kind = models.CharField(max_length=8, choices=KINDS)
    name = models.CharField(max_length=60)
    # Income/expense: amount per period. Account: current balance.
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    frequency = models.CharField(max_length=10, choices=FREQUENCIES, default='monthly')
    # Income: annual raise. Expense: annual inflation.
    growth_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    bonus_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    taxed = models.BooleanField(default=True)
    payroll_taxed = models.BooleanField(default=True)
    tax_deferred = models.BooleanField(default=False)
    start_age = models.PositiveSmallIntegerField(null=True, blank=True)
    start_at_fi = models.BooleanField(default=False)
    end_mode = models.CharField(max_length=4, choices=END_MODES, default='life')
    end_age = models.PositiveSmallIntegerField(null=True, blank=True)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES, blank=True)
    contribution_type = models.CharField(max_length=8, choices=CONTRIBUTION_TYPES, default='posttax')
    contribution_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    fixed_growth = models.BooleanField(default=False)
    fixed_growth_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    allocation_pct = models.PositiveSmallIntegerField(default=0)
    employer_match_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    savings_level = models.CharField(max_length=5, default='none',
                                     choices=[('none', 'None'), ('match', 'Up to employer match'), ('max', 'Up to max')])
    priority = models.PositiveIntegerField(default=0)
    linked_income = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created', 'id']
