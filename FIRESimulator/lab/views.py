import json
from functools import wraps

from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from FIRE import taxes

from . import simulation
from .forms import item_form
from .models import Item, Scenario

NUM = ('amount', 'growth_pct', 'bonus_pct', 'contribution_limit', 'fixed_growth_pct', 'employer_match_pct')


def lab_only(view):
    @wraps(view)
    def wrapper(request, *a, **kw):
        if not settings.LAB_ENABLED:
            raise Http404
        return view(request, *a, **kw)
    return wrapper


def serialize_item(it):
    d = {f: (float(getattr(it, f)) if getattr(it, f) is not None else None) for f in NUM}
    d.update(id=it.pk, kind=it.kind, name=it.name, frequency=it.frequency, taxed=it.taxed,
             payroll_taxed=it.payroll_taxed, tax_deferred=it.tax_deferred, start_age=it.start_age,
                          start_at_fi=it.start_at_fi,             end_mode=it.end_mode, end_age=it.end_age, account_type=it.account_type,
             contribution_type=it.contribution_type, fixed_growth=it.fixed_growth,
             allocation_pct=it.allocation_pct, linked_income=it.linked_income_id,
             savings_level=it.savings_level, priority=it.priority)
    d['section'] = simulation.section(d)
    return d


def state(sc):
    items = [serialize_item(i) for i in sc.items.all()]
    cfg = {'age': sc.age, 'plan_to_age': sc.plan_to_age, 'filing_status': sc.filing_status,
           'state': sc.state, 'seed': sc.id.int % (2 ** 32)}
    return {'scenario': {k: cfg[k] for k in ('age', 'plan_to_age', 'filing_status', 'state')},
            'items': items, 'results': simulation.run(cfg, items)}


def _body(request):
    try:
        data = json.loads(request.body or '{}')
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


@lab_only
def home(request):
    error = ''
    if request.method == 'POST':
        try:
            age = int(request.POST.get('age', ''))
        except ValueError:
            age = 0
        if 16 <= age <= 90:
            return redirect('lab_scenario', pk=Scenario.objects.create(age=age).pk)
        error = 'Enter an age between 16 and 90.'
    return render(request, 'lab/home.html', {'error': error})


@lab_only
def scenario(request, pk):
    sc = get_object_or_404(Scenario, pk=pk)
    rebalance(sc)
    return render(request, 'lab/scenario.html', {
        'sc': sc, 'state': state(sc), 'states': taxes.state_choices(),
        'frequencies': Item.FREQUENCIES, 'account_types': Item.ACCOUNT_TYPES,
        'contribution_types': [c for c in Item.CONTRIBUTION_TYPES if c[0] != 'none'],
    })


@lab_only
@require_POST
def save_item(request, pk, item_pk=None):
    sc = get_object_or_404(Scenario, pk=pk)
    data = _body(request)
    kind = data.get('kind')
    inst = get_object_or_404(Item, pk=item_pk, scenario=sc) if item_pk else None
    if inst:
        kind = inst.kind
    if kind not in ('income', 'expense', 'account'):
        return JsonResponse({'errors': {'kind': ['Unknown item type.']}}, status=400)
    form = item_form(kind, data, inst, sc)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors}, status=400)
    obj = form.save(commit=False)
    obj.scenario, obj.kind = sc, kind
    if kind == 'account' and obj.contribution_type not in ('pretax', 'posttax'):
        obj.allocation_pct, obj.savings_level = 0, 'none'
    if not inst:
        obj.priority = sc.items.count()
    obj.save()
    rebalance(sc)
    return JsonResponse(state(sc))


@lab_only
@require_POST
def delete_item(request, pk, item_pk):
    sc = get_object_or_404(Scenario, pk=pk)
    get_object_or_404(Item, pk=item_pk, scenario=sc).delete()
    rebalance(sc)
    return JsonResponse(state(sc))


@lab_only
@require_POST
def settings_view(request, pk):
    sc = get_object_or_404(Scenario, pk=pk)
    data = _body(request)
    try:
        age = int(data.get('age', sc.age))
        plan = int(data.get('plan_to_age', sc.plan_to_age))
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid ages.'}, status=400)
    if not (16 <= age <= 90 and age + 5 <= plan <= 110):
        return JsonResponse({'error': 'Plan-to age must be at least 5 years past your age (max 110).'}, status=400)
    if data.get('filing_status') in dict(Scenario.FILING):
        sc.filing_status = data['filing_status']
    if data.get('state') in dict(taxes.state_choices()):
        sc.state = data['state']
    sc.age, sc.plan_to_age = age, plan
    sc.save()
    return JsonResponse(state(sc))


@lab_only
@require_POST
def allocate(request, pk):
    """Body (all optional): {order: [ids], levels: {id: none|match|max}, pct: {id: percent}}.
    Taxable-section percentages are always rebalanced to total 100."""
    sc = get_object_or_404(Scenario, pk=pk)
    raw = _body(request)
    accounts = {str(i.pk): i for i in sc.items.filter(kind='account', contribution_type__in=['pretax', 'posttax'])}
    changed = set()

    order = raw.get('order') if isinstance(raw.get('order'), list) else []
    for n, k in enumerate(str(x) for x in order):
        if k in accounts:
            accounts[k].priority = n
            changed.add(k)

    levels = raw.get('levels') if isinstance(raw.get('levels'), dict) else {}
    for k, v in levels.items():
        if k in accounts and v in ('none', 'match', 'max'):
            accounts[k].savings_level = v
            changed.add(k)

    pct = raw.get('pct') if isinstance(raw.get('pct'), dict) else {}
    anchor = None
    for k, v in pct.items():
        try:
            anchor = (int(k), max(0, min(100, int(v))))
        except (TypeError, ValueError):
            pass

    for k in changed:
        accounts[k].save(update_fields=['priority', 'savings_level'])
    rebalance(sc, anchor)
    return JsonResponse(state(sc))


def rebalance(sc, anchor=None):
    """Keep taxable-account percentages summing to exactly 100.
    anchor=(item_id, pct) pins one account and rescales the others to fill the rest."""
    accts = [i for i in sc.items.filter(kind='account') if simulation.section(serialize_item(i)) == 'taxable']
    if not accts:
        return
    pcts = {a.pk: float(a.allocation_pct) for a in accts}
    if anchor and anchor[0] in pcts:
        pcts[anchor[0]] = float(anchor[1])
        others = [a.pk for a in accts if a.pk != anchor[0]]
        target = 100 - pcts[anchor[0]]
    else:
        others, target = [a.pk for a in accts], 100.0
    if others:
        osum = sum(pcts[k] for k in others)
        for k in others:
            pcts[k] = pcts[k] * target / osum if osum > 0 else target / len(others)
    else:
        pcts[accts[0].pk] = 100.0
    new = {k: int(v) for k, v in pcts.items()}
    new[others[-1] if others else accts[0].pk] += 100 - sum(new.values())
    for a in accts:
        if a.allocation_pct != new[a.pk]:
            a.allocation_pct = new[a.pk]
            a.save(update_fields=['allocation_pct'])
