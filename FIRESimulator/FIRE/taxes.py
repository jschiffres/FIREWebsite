"""Simplified US tax estimates used when a plan has automatic taxes turned on.

Figures are 2025 US federal law (standard deduction, ordinary-income brackets,
Social Security and Medicare payroll taxes) and are indexed forward for inflation.
State tax is a flat approximate effective rate on income. Itemized deductions,
credits, capital gains and pre-tax retirement contributions are not modeled, so
results are estimates for planning only.
"""
import math
from datetime import date

BASE_YEAR = 2025
# Brackets, the deduction and the Social Security wage base grow by this much each year
INDEXING_RATE = 0.025

FILING_STATUSES = {
    'single': 'Single',
    'married': 'Married filing jointly',
}

# (upper bound of bracket, rate); None marks the top bracket
FEDERAL = {
    'single': {
        'deduction': 15750,
        'brackets': [(11925, 0.10), (48475, 0.12), (103350, 0.22), (197300, 0.24),
                     (250525, 0.32), (626350, 0.35), (None, 0.37)],
        'medicare_threshold': 200000,
    },
    'married': {
        'deduction': 31500,
        'brackets': [(23850, 0.10), (96950, 0.12), (206700, 0.22), (394600, 0.24),
                     (501050, 0.32), (751600, 0.35), (None, 0.37)],
        'medicare_threshold': 250000,
    },
}

SOCIAL_SECURITY_RATE = 0.062
SOCIAL_SECURITY_WAGE_BASE = 176100
MEDICARE_RATE = 0.0145
ADDITIONAL_MEDICARE_RATE = 0.009

# Approximate effective state income tax rate (percent of income)
NO_STATE = 'NONE'
STATE_RATES = {
    'AL': ('Alabama', 4.0), 'AK': ('Alaska', 0.0), 'AZ': ('Arizona', 2.5), 'AR': ('Arkansas', 3.9),
    'CA': ('California', 5.0), 'CO': ('Colorado', 4.4), 'CT': ('Connecticut', 4.5), 'DE': ('Delaware', 5.0),
    'DC': ('District of Columbia', 6.0), 'FL': ('Florida', 0.0), 'GA': ('Georgia', 5.2), 'HI': ('Hawaii', 6.0),
    'ID': ('Idaho', 5.3), 'IL': ('Illinois', 4.95), 'IN': ('Indiana', 3.0), 'IA': ('Iowa', 3.8),
    'KS': ('Kansas', 5.0), 'KY': ('Kentucky', 4.0), 'LA': ('Louisiana', 3.0), 'ME': ('Maine', 5.5),
    'MD': ('Maryland', 5.0), 'MA': ('Massachusetts', 5.0), 'MI': ('Michigan', 4.25), 'MN': ('Minnesota', 5.5),
    'MS': ('Mississippi', 4.0), 'MO': ('Missouri', 4.5), 'MT': ('Montana', 5.0), 'NE': ('Nebraska', 4.5),
    'NV': ('Nevada', 0.0), 'NH': ('New Hampshire', 0.0), 'NJ': ('New Jersey', 4.5), 'NM': ('New Mexico', 4.0),
    'NY': ('New York', 5.5), 'NC': ('North Carolina', 4.25), 'ND': ('North Dakota', 1.5), 'OH': ('Ohio', 3.0),
    'OK': ('Oklahoma', 4.0), 'OR': ('Oregon', 7.0), 'PA': ('Pennsylvania', 3.07), 'RI': ('Rhode Island', 4.5),
    'SC': ('South Carolina', 5.0), 'SD': ('South Dakota', 0.0), 'TN': ('Tennessee', 0.0), 'TX': ('Texas', 0.0),
    'UT': ('Utah', 4.55), 'VT': ('Vermont', 5.5), 'VA': ('Virginia', 5.0), 'WA': ('Washington', 0.0),
    'WV': ('West Virginia', 4.0), 'WI': ('Wisconsin', 4.5), 'WY': ('Wyoming', 0.0),
}

DEFAULT_SETTINGS = {'mode': 'auto', 'filing_status': 'single', 'state': NO_STATE}


def state_choices():
    return [(code, name) for code, (name, _rate) in STATE_RATES.items()]


def state_rate(state):
    """State rate as a percentage; unknown codes (and "no state") are 0."""
    return STATE_RATES.get(state, ('', 0.0))[1]


def index_factor(step):
    """Inflation factor for the projection year ``step`` (0 = this year)."""
    return (1 + INDEXING_RATE) ** (max(0, date.today().year - BASE_YEAR) + step)


def federal_income_tax(income, status, factor=1.0):
    """Federal income tax on ordinary income after the standard deduction."""
    rules = FEDERAL[status]
    taxable = max(0.0, income - rules['deduction'] * factor)
    tax, lower = 0.0, 0.0
    for upper, rate in rules['brackets']:
        top = math.inf if upper is None else upper * factor
        if taxable > lower:
            tax += (min(taxable, top) - lower) * rate
        lower = top
    return tax


def social_security_tax(wages, factor=1.0):
    return min(wages, SOCIAL_SECURITY_WAGE_BASE * factor) * SOCIAL_SECURITY_RATE


def medicare_tax(wages):
    return wages * MEDICARE_RATE


def additional_medicare_tax(total_wages, status):
    return max(0.0, total_wages - FEDERAL[status]['medicare_threshold']) * ADDITIONAL_MEDICARE_RATE
