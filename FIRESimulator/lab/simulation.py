"""Monte Carlo financial-independence simulation for the single-page planner.

Items are plain dicts (see views.serialize_item). All money is nominal. Contributions and withdrawals
happen at the start of each year, then investments grow for the year.
"""
import numpy as np

from FIRE import taxes

FREQ = {'weekly': 52, 'biweekly': 26, 'bimonthly': 24, 'monthly': 12, 'quarterly': 4, 'biannual': 2, 'yearly': 1}

WITHDRAWAL_RATE = 0.04          # the 4% rule behind the magic number
GENERAL_INFLATION = 0.025       # used only to show "today's dollars"
SUCCESS_THRESHOLD = 0.85        # share of simulated lifetimes that must stay funded to plan age
CAP_GAINS_EFFECTIVE = 0.075     # 15% long-term rate on an assumed 50% gain share
N_SEARCH, N_FINAL = 300, 1000

# Account type -> (mean nominal return, volatility, correlation with the market)
MARKET = {
    'cash': (0.03, 0.01, 0.0),
    'employer': (0.07, 0.15, 0.9),
    'ira': (0.07, 0.15, 0.9),
    'hsa': (0.06, 0.12, 0.8),
    'taxable': (0.07, 0.16, 0.9),
    'education': (0.06, 0.12, 0.8),
    'alt': (0.08, 0.30, 0.5),
}
# Default annual contribution limits (today's dollars, indexed over time)
LIMITS = {'employer': 23500, 'ira': 7000, 'hsa': 4300}
CONTRIBUTABLE = ('pretax', 'posttax')


def section(acct):
    """'adv' (tax-advantaged, has a contribution limit), 'taxable' (takes the remaining savings) or 'dormant'."""
    if acct['kind'] != 'account':
        return None
    if acct['contribution_type'] not in CONTRIBUTABLE:
        return 'dormant'
    if acct['account_type'] in LIMITS or acct['contribution_limit'] is not None:
        return 'adv'
    return 'taxable'


_FED_CURVES = {}


def _fed_curve(status):
    """Tax is piecewise linear in taxable income, so one interpolation replaces a loop over brackets."""
    if status not in _FED_CURVES:
        xs, ys, lower, tax = [0.0], [0.0], 0.0, 0.0
        last_rate = 0.0
        for upper, rate in taxes.FEDERAL[status]['brackets']:
            last_rate = rate
            if upper is None:
                break
            tax += (upper - lower) * rate
            xs.append(float(upper))
            ys.append(tax)
            lower = upper
        _FED_CURVES[status] = (np.array(xs), np.array(ys), last_rate)
    return _FED_CURVES[status]


def _fed(income, status, factor):
    rules = taxes.FEDERAL[status]
    xs, ys, top_rate = _fed_curve(status)
    taxable = np.maximum(0.0, income - rules['deduction'] * factor) / factor
    tax = np.interp(taxable, xs, ys) + np.maximum(0.0, taxable - xs[-1]) * top_rate
    return tax * factor

def _payroll(wages, status, factor):
    ss = np.minimum(wages, taxes.SOCIAL_SECURITY_WAGE_BASE * factor) * taxes.SOCIAL_SECURITY_RATE
    medicare = wages * taxes.MEDICARE_RATE
    extra = np.maximum(0.0, wages - taxes.FEDERAL[status]['medicare_threshold']) * taxes.ADDITIONAL_MEDICARE_RATE
    return ss + medicare + extra


def _treatment(acct):
    """How withdrawals are taxed: 'free', 'cg' (capital gains) or 'ordinary' (traditional retirement)."""
    kind = acct['account_type']
    if kind in ('cash', 'hsa', 'education'):
        return 'free'
    if kind in ('taxable', 'alt'):
        return 'cg'
    return 'free' if acct['contribution_type'] == 'posttax' else 'ordinary'


def _priority(acct):
    base = {'cash': 0, 'taxable': 1, 'alt': 2, 'employer': 3, 'ira': 3, 'hsa': 5}[acct['account_type']]
    if _treatment(acct) == 'free' and base == 3:
        base = 4
    return base + (0.5 if acct['contribution_type'] == 'dormant' else 0)


def _mask(item, ages, a0, plan_age, fi_age):
    start = a0 if item['start_age'] is None else max(item['start_age'], a0)
    if item.get('start_at_fi'):
        start = fi_age
    if item['end_mode'] == 'fi':
        end = fi_age - 1
    elif item['end_mode'] == 'age' and item['end_age'] is not None:
        end = item['end_age']
    else:
        end = plan_age
    return (ages >= start) & (ages <= end)


def _annual(item, ages, a0):
    base = item['amount'] * FREQ[item['frequency']]
    if item['kind'] == 'income':
        base *= 1 + item['bonus_pct'] / 100
    return base * (1 + item['growth_pct'] / 100) ** (ages - a0)


def cashflows(sc, items, fi_age):
    a0, plan = sc['age'], sc['plan_to_age']
    ages = np.arange(a0, plan + 1)
    T = len(ages)
    factor = np.array([taxes.index_factor(t) for t in range(T)])
    status = sc['filing_status']
    srate = taxes.state_rate(sc['state']) / 100

    zeros = lambda: np.zeros(T)
    wages, other_taxed, untaxed, nonwork = zeros(), zeros(), zeros(), zeros()
    expenses, deferred = zeros(), zeros()
    inc_rows, exp_rows = [], []
    for it in items:
        if it['kind'] not in ('income', 'expense'):
            continue
        arr = _annual(it, ages, a0) * _mask(it, ages, a0, plan, fi_age)
        if it['kind'] == 'income':
            inc_rows.append((it, arr))
            if not it['taxed']:
                untaxed += arr
            elif it['payroll_taxed']:
                wages += arr
            else:
                other_taxed += arr
            if it['end_mode'] != 'fi':
                nonwork += arr
        else:
            exp_rows.append((it, arr))
            expenses += arr
            if it['tax_deferred']:
                deferred += arr

    taxable_base = np.maximum(0.0, wages + other_taxed - deferred)
    payroll = _payroll(np.maximum(0.0, wages - deferred), status, factor)
    tax_base = _fed(taxable_base, status, factor) + srate * taxable_base + payroll
    net_before = wages + other_taxed + untaxed - tax_base - expenses
    base_surplus = np.maximum(0.0, net_before)

    inc_by_id = {it['id']: arr for it, arr in inc_rows}
    employer = {}
    for it in items:
        if it['kind'] == 'account' and it.get('employer_match_pct') and it.get('linked_income') in inc_by_id:
            employer[it['id']] = inc_by_id[it['linked_income']] * it['employer_match_pct'] / 100

    contrib, pretax_total = {}, zeros()
    remaining = base_surplus.copy()

    def limit_of(it):
        return it['contribution_limit'] if it['contribution_limit'] is not None else LIMITS.get(it['account_type'])

    def cap(it):
        # A limit the user typed is in this year's dollars; built-in limits are base-year figures.
        lim = limit_of(it)
        if lim is None:
            return None
        return lim * (factor / factor[0] if it['contribution_limit'] is not None else factor)

    def put(it, c):
        nonlocal pretax_total, remaining
        c = np.minimum(c, remaining)
        remaining = remaining - c
        contrib[it['id']] = c
        if it['contribution_type'] == 'pretax':
            pretax_total = pretax_total + c

    adv = sorted((i for i in items if section(i) == 'adv'), key=lambda i: (i['priority'], i['id']))
    taxable_accts = [i for i in items if section(i) == 'taxable']
    pct_sum = sum(i['allocation_pct'] for i in taxable_accts)

    def share(it):
        # Taxable accounts always split the whole remainder; no percentages means an equal split.
        return it['allocation_pct'] / pct_sum if pct_sum > 0 else 1 / len(taxable_accts)

    refund = zeros()
    for _ in range(60):
        # Pre-tax contributions lower the tax bill, and that refund is also cash to allocate.
        contrib, pretax_total, remaining = {}, zeros(), base_surplus + refund
        spendable = remaining.copy()
        for it in adv:
            level, limit = it['savings_level'], cap(it)
            if level == 'match':
                c = employer.get(it['id'], zeros()).copy()
            elif level == 'max':
                c = np.full(T, np.inf)
            else:
                continue
            if limit is not None:
                c = np.minimum(c, limit)
            put(it, c)
        pool = remaining.copy()
        for it in taxable_accts:
            c = pool * share(it)
            limit = cap(it)
            if limit is not None:
                c = np.minimum(c, limit)
            put(it, c)
        pretax_total = np.minimum(pretax_total, taxable_base)
        after = np.maximum(0.0, taxable_base - pretax_total)
        tax_after = _fed(after, status, factor) + srate * after + payroll
        new_refund = np.where(net_before > 0, tax_base - tax_after, 0.0)
        if np.allclose(new_refund, refund, atol=0.001, rtol=0):
            refund = new_refund
            break
        refund = new_refund
    free = net_before - sum(contrib.values(), zeros()) + (tax_base - tax_after)

    return {
        'employer': employer,
        'ages': ages, 'factor': factor, 'status': status, 'srate': srate,
        'inc_rows': inc_rows, 'exp_rows': exp_rows, 'expenses': expenses, 'nonwork': nonwork,
        'taxable_base': taxable_base, 'contrib': contrib, 'free': free, 'base_surplus': base_surplus,
        'spendable': spendable,
        'tax_fed': _fed(after, status, factor), 'tax_state': srate * after, 'tax_payroll': payroll,
        'income_total': wages + other_taxed + untaxed,
    }


def simulate(sc, items, fi_age, n, seed, detail=False):
    cf = cashflows(sc, items, fi_age)
    T = len(cf['ages'])
    rng = np.random.default_rng(seed)
    accounts = [it for it in items if it['kind'] == 'account']
    bal = {a['id']: np.full(n, float(a['amount'])) for a in accounts}
    unalloc = np.zeros(n)
    market = rng.standard_normal((T, n))
    idio = {a['id']: rng.standard_normal((T, n)) for a in accounts}
    order = sorted((a for a in accounts if a['account_type'] != 'education'), key=_priority)

    growth = {}
    for a in accounts:
        if a['fixed_growth'] and a['fixed_growth_pct'] is not None:
            growth[a['id']] = np.full((T, n), a['fixed_growth_pct'] / 100)
            continue
        mean, vol, rho = MARKET[a['account_type']]
        sig = np.sqrt(np.log(1 + (vol / (1 + mean)) ** 2))
        z = rho * market + np.sqrt(1 - rho ** 2) * idio[a['id']]
        growth[a['id']] = np.exp(np.log(1 + mean) - sig ** 2 / 2 + sig * z) - 1

    nw = np.zeros((T, n))
    ruined = np.zeros(n, dtype=bool)
    wd = {a['id']: np.zeros((T, n)) for a in accounts}
    ab = {a['id']: np.zeros((3, T)) for a in accounts}
    wd_tax, shortfall, cash_used = np.zeros((T, n)), np.zeros((T, n)), np.zeros((T, n))
    status, srate = cf['status'], cf['srate']

    for t in range(T):
        nw[t] = unalloc + sum(bal.values()) if bal else unalloc
        if detail:
            for aid, b in bal.items():
                ab[aid][:, t] = np.percentile(b, [10, 50, 90])
        for aid, c in cf['contrib'].items():
            bal[aid] = bal[aid] + c[t]
        for aid, e in cf['employer'].items():
            bal[aid] = bal[aid] + e[t]
        free = cf['free'][t]
        f = cf['factor'][t]
        if free > 0:
            unalloc = unalloc + free
        elif free < 0:
            need = np.full(n, -free)
            take = np.minimum(unalloc, need)
            if detail:
                cash_used[t] = take
            unalloc, need = unalloc - take, need - take
            ordinary = np.full(n, cf['taxable_base'][t])
            for a in order:
                if not need.any():
                    break
                b, kind = bal[a['id']], _treatment(a)
                if kind == 'free':
                    g, tax = np.minimum(b, need), 0.0
                    net = g
                elif kind == 'cg':
                    g = np.minimum(b, need / (1 - CAP_GAINS_EFFECTIVE))
                    tax = g * CAP_GAINS_EFFECTIVE
                    net = g - tax
                else:
                    g = need.copy()
                    base_tax = _fed(ordinary, status, f)
                    for _ in range(40):
                        nxt = need + _fed(ordinary + g, status, f) - base_tax + srate * g
                        done = np.abs(nxt - g).max() < 0.01
                        g = nxt
                        if done:
                            break
                    g = np.minimum(b, g)
                    tax = _fed(ordinary + g, status, f) - _fed(ordinary, status, f) + srate * g
                    net = g - tax
                    ordinary = ordinary + g
                bal[a['id']] = b - g
                need = np.maximum(0.0, need - net)
                if detail:
                    wd[a['id']][t] = g
                    wd_tax[t] += tax
            short = need > 1.0
            ruined |= short
            if detail:
                shortfall[t] = need
        for aid in bal:
            bal[aid] = bal[aid] * (1 + growth[aid][t])

    out = {'nw': nw, 'ruin': ruined.mean(), 'cf': cf}
    if detail:
        keep = ~ruined if (~ruined).any() else np.ones(n, dtype=bool)
        avg = lambda x: x[:, keep].mean(axis=1)
        out.update(wd={k: avg(v) for k, v in wd.items()}, wd_tax=avg(wd_tax), shortfall=avg(shortfall),
                   cash_used=avg(cash_used), acct_bal=ab)
    return out


def _unique_labels(items):
    seen, labels = {}, {}
    for it in items:
        base = it['name'] or it['kind'].title()
        seen[base] = seen.get(base, 0) + 1
        labels[it['id']] = base if seen[base] == 1 else f"{base} ({seen[base]})"
    return labels


def _sankey(sc, items, cf, out, labels):
    T = len(cf['ages'])
    result = []
    for t in range(T):
        links = []
        add = lambda a, b, v: links.append([a, b, round(float(v))]) if v >= 1 else None
        for it, arr in cf['inc_rows']:
            add(labels[it['id']], 'Money in', arr[t])
        wd_total = 0.0
        for a in items:
            if a['kind'] == 'account':
                add(f"{labels[a['id']]} (withdrawal)", 'Money in', out['wd'][a['id']][t])
                wd_total += out['wd'][a['id']][t]
        add('Cash savings (used)', 'Money in', out['cash_used'][t])
        add('Shortfall', 'Money in', out['shortfall'][t])
        add('Money in', 'Federal tax', cf['tax_fed'][t])
        add('Money in', 'State tax', cf['tax_state'][t])
        add('Money in', 'Payroll tax', cf['tax_payroll'][t])
        add('Money in', 'Tax on withdrawals', out['wd_tax'][t])
        for it, arr in cf['exp_rows']:
            add('Money in', labels[it['id']], arr[t])
        for aid, c in cf['contrib'].items():
            add('Money in', f"{labels[aid]} (saved)", c[t])
        for aid, m in cf['employer'].items():
            if aid in labels:
                add(f"Employer match ({labels[aid]})", f"{labels[aid]} (saved)", m[t])
        add('Money in', 'Unallocated cash', max(cf['free'][t], 0))
        result.append(links)
    return result


def run(sc, items, extras=True):
    """sc: dict(age, plan_to_age, filing_status, state, seed). Returns a JSON-ready results dict.
    extras=False leaves out the Premium series (per-account balances and the retire-at-other-ages odds)."""
    a0, plan = sc['age'], sc['plan_to_age']
    accounts = [i for i in items if i['kind'] == 'account']
    seed = sc['seed']
    base = {
        'status': 'empty', 'net_worth_now': sum(a['amount'] for a in accounts), 'fi_age': None,
        'coast_age': None, 'rule_age': None, 'success_pct': None, 'fi_number': None, 'unallocated_pct': 100, 'unallocated_now': 0,
        'ages': [], 'notes': [],
    }
    if not items:
        return base

    auto = not any(section(i) == 'taxable' for i in accounts)
    if auto and any(i['kind'] == 'income' for i in items):
        # Savings beyond the tax-advantaged limits need somewhere to go; idle cash would earn 0% for decades.
        items = items + [{
            'id': -1, 'kind': 'account', 'name': 'Taxable brokerage (automatic)', 'amount': 0, 'frequency': 'yearly',
            'growth_pct': 0, 'bonus_pct': 0, 'taxed': True, 'payroll_taxed': True, 'tax_deferred': False,
            'start_age': None, 'start_at_fi': False, 'end_mode': 'life', 'end_age': None, 'account_type': 'taxable',
            'contribution_type': 'posttax', 'contribution_limit': None, 'fixed_growth': False,
            'fixed_growth_pct': None, 'allocation_pct': 100, 'employer_match_pct': 0, 'savings_level': 'none',
            'priority': 0, 'linked_income': None}]
        accounts = [i for i in items if i['kind'] == 'account']
    else:
        auto = False

    def ok(age):
        return 1 - simulate(sc, items, age, N_SEARCH, seed)['ruin'] >= SUCCESS_THRESHOLD

    if ok(a0):
        fi = a0
    elif not ok(plan):
        fi = None
    else:
        lo, hi = a0, plan
        while hi - lo > 1:
            mid = (lo + hi) // 2
            lo, hi = (lo, mid) if ok(mid) else (mid, hi)
        fi = hi

    show_age = fi if fi is not None else plan + 1
    out = simulate(sc, items, show_age, N_FINAL, seed, detail=True)
    cf, nw = out['cf'], out['nw']
    ages = cf['ages']
    p10, p50, p90 = np.percentile(nw, [10, 50, 90], axis=1)
    # Only non-work income that keeps going (not a one-off such as an inheritance) offsets the magic number.
    lasting = np.minimum.accumulate(cf['nonwork'][::-1])[::-1]
    need_now = np.maximum(0.0, cf['expenses'] - lasting)
    magic = need_now / WITHDRAWAL_RATE
    saved = sum(cf['contrib'].values(), np.zeros(len(ages))) + np.maximum(cf['free'], 0)
    withdrawn = -(sum(out['wd'].values(), np.zeros(len(ages))) + out['cash_used'])
    success = 1 - out['ruin']

    gross = sum((arr for _, arr in cf['inc_rows']), np.zeros(len(ages)))
    contrib_total = sum(cf['contrib'].values(), np.zeros(len(ages)))
    savings_rate = [round(100 * float(c) / float(g)) if g > 0 else None for c, g in zip(contrib_total, gross)]
    if fi is not None:
        lo_r, hi_r = max(a0 + 1, fi - 10), min(plan - 1, fi + 10)
        opts_ages = list(range(lo_r, hi_r + 1, 2))
    else:
        opts_ages = list(range(max(a0 + 1, plan - 20), plan, 2))
    if fi is not None and fi not in opts_ages and fi < plan:
        opts_ages = sorted(opts_ages + [fi])
    retire_options = [{'age': a, 'success': round(100 * (1 - simulate(sc, items, a, N_SEARCH, seed)['ruin']))}
                      for a in opts_ages] if extras else []
    coast = None
    if fi is not None and fi > a0:
        mean = sum(a['amount'] * MARKET[a['account_type']][0] for a in accounts)
        total = sum(a['amount'] for a in accounts)
        mu = mean / total if total > 0 else 0.05
        target = magic[fi - a0]
        for t in range(0, fi - a0):
            if p50[t] * (1 + mu) ** (fi - a0 - t) >= target > 0:
                coast = int(ages[t])
                break

    # First age the median net worth reaches the 4% rule number (a quicker, rougher test than the FI age).
    rule_age = next((int(a) for a, n, m in zip(ages, p50, magic) if m > 0 and n >= m), None)

    notes = []
    surplus0 = float(cf['spendable'][0])
    left0 = max(0.0, float(cf['free'][0]))
    base['unallocated_pct'] = round(100 * left0 / surplus0) if surplus0 > 0 else 0
    base['unallocated_now'] = round(left0)
    if surplus0 > 0 and left0 >= 1:
        notes.append(f"About ${left0:,.0f} a year ({base['unallocated_pct']}% of your surplus) is unallocated and "
                     "earns 0%. Allocate it to an account below.")
    if auto:
        notes.append('Savings beyond your tax-advantaged limits are invested in an automatic taxable brokerage '
                     'account. Add your own taxable account to choose where that money goes.')
    if not accounts:
        notes.append('Add an account to invest your savings. Without one, surplus cash earns nothing.')
    if not any(i['kind'] == 'income' for i in items):
        notes.append('Add an income to see your savings capacity.')

    labels = _unique_labels(items)
    base.update({
        'status': 'ok',
        'ages': [int(a) for a in ages],
        'p10': [round(float(x)) for x in p10], 'p50': [round(float(x)) for x in p50], 'p90': [round(float(x)) for x in p90],
        'magic': [round(float(x)) for x in magic],
        'saved': [round(float(x)) for x in saved], 'withdrawn': [round(float(x)) for x in withdrawn],
        'defl': [round(1 / (1 + GENERAL_INFLATION) ** t, 4) for t in range(len(ages))],
        'fi_age': fi, 'coast_age': coast, 'rule_age': rule_age, 'success_pct': round(success * 100),
        'fi_number': round(float(magic[fi - a0])) if fi is not None and fi - a0 < len(ages) else None,
        'surplus_now': round(float(cf['spendable'][0])),
        'sankey': _sankey(sc, items, cf, out, labels),
        'acct_bal': ({str(k): [[round(float(x)) for x in row] for row in v] for k, v in out['acct_bal'].items()}
                     if extras else {}),
        'income': [round(float(x)) for x in gross],
        'expenses': [round(float(x)) for x in cf['expenses']],
        'taxes': [round(float(x)) for x in cf['tax_fed'] + cf['tax_state'] + cf['tax_payroll'] + out['wd_tax']],
        'savings_rate': savings_rate,
        'retire_options': retire_options,
        'node_kinds': {**{labels[i['id']]: i['kind'] for i in items if i['kind'] != 'account'},
                       **{f"{labels[a['id']]} (saved)": 'account' for a in accounts},
                       **{f"{labels[a['id']]} (withdrawal)": 'account' for a in accounts},
                       **{f"Employer match ({labels[a['id']]})": 'income' for a in accounts}},
        'notes': notes,
    })
    return base
