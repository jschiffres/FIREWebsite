from django.db.models import F
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import HttpResponse, Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import logging
logger = logging.getLogger(__name__)
import copy
import uuid

from .models import Plan, Feedback, Profile, user_is_premium
from django.conf import settings
from django.utils import timezone
from .forms import CreateUserForm, FeedbackForm, PlanForm, EditPlanForm
from .engine import PlanObject
from .plan_input import saveplan
from .emails import welcome_email
from . import auth_flows, billing, pdf_report

import math
import csv

def about(request):
    return render(request, 'FIRE/about.html')

def not_found(request, exception=None):
    return render(request, 'FIRE/404.html', status=404)

def server_error(request):
    return render(request, 'FIRE/500.html', status=500)

def _is_uuid(value):
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False

def _can_access_plan(request, plan):
    # Unowned (anonymous) plans stay reachable by their unguessable UUID
    return plan.user is None or plan.user == request.user

def _create_account(request, plan=None):
    """Shared signup logic; returns (redirect_response, None) or (None, error_response)."""
    form = CreateUserForm(request.POST)
    template = 'FIRE/signupuser.html'
    if request.POST.get('password1') != request.POST.get('password2'):
        return None, render(request, template, {'form': form, 'error': 'Passwords did not match.'})
    email = (request.POST.get('email') or '').strip()
    if email and User.objects.filter(email__iexact=email).exists():
        return None, render(request, template, {'form': form, 'error': 'Email provided is already associated with an account.'})
    if not form.is_valid():
        errors = " ".join(e for errs in form.errors.values() for e in errs)
        return None, render(request, template, {'form': form, 'error': errors})
    try:
        user = form.save()
    except IntegrityError:
        return None, render(request, template, {'form': form, 'error': 'Please try again.'})
    if plan is not None:
        plan.user = user
        plan.save()
    login(request, user)
    messages.success(request, "User created successfully! Check your email to confirm your address.")
    welcome_email(user)
    auth_flows.send_verification_email(user)
    return redirect('userplans'), None

# USER: Email verification
def verify_email(request, token):
    user = auth_flows.read_verification_token(token)
    if user is None:
        messages.error(request, "That confirmation link is invalid or has expired. Request a new one from My Account.")
        return redirect('myaccount' if request.user.is_authenticated else 'loginuser')
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.email_verified = True
    profile.save(update_fields=['email_verified'])
    messages.success(request, "Thanks! Your email address is confirmed.")
    return redirect('myaccount' if request.user.is_authenticated else 'loginuser')

@login_required
@require_POST
def resend_verification(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.email_verified:
        messages.info(request, "Your email is already confirmed.")
    elif not request.user.email:
        messages.warning(request, "Add an email address first.")
    elif auth_flows.send_verification_email(request.user):
        messages.success(request, f"Confirmation email sent to {request.user.email}.")
    else:
        messages.error(request, "We couldn't send the email right now. Please try again later.")
    return redirect(request.POST.get('next') if request.POST.get('next', '').startswith('/') and not request.POST.get('next', '').startswith('//') else 'myaccount')

# USER: Google sign-in
def google_login(request):
    if not auth_flows.google_enabled():
        messages.warning(request, "Google sign-in isn't configured on this site.")
        return redirect('loginuser')
    state = auth_flows.new_state()
    request.session['google_state'] = state
    plan_id = request.GET.get('plan')
    if plan_id and _is_uuid(plan_id):
        request.session['google_plan'] = plan_id
    else:
        request.session.pop('google_plan', None)
    return redirect(auth_flows.google_authorize_url(state))

def google_callback(request):
    expected = request.session.pop('google_state', None)
    plan_id = request.session.pop('google_plan', None)
    if not expected or request.GET.get('state') != expected or not request.GET.get('code'):
        messages.error(request, "Google sign-in was cancelled or could not be verified.")
        return redirect('loginuser')
    info = auth_flows.fetch_google_profile(request.GET['code'])
    if info is None:
        messages.error(request, "Google sign-in failed. Make sure your Google email is verified and try again.")
        return redirect('loginuser')

    email = info['email'].strip()
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        user = User.objects.create_user(
            username=auth_flows.unique_username(email),
            email=email,
            first_name=(info.get('given_name') or '')[:150],
        )
        user.set_unusable_password()
        user.save()
        welcome_email(user)
    elif not user.is_active:
        messages.error(request, "This account is disabled.")
        return redirect('loginuser')
    profile, _ = Profile.objects.get_or_create(user=user)
    if not profile.email_verified:
        # An unverified account may have been registered by someone else with this address; drop any password it had
        if user.has_usable_password():
            user.set_unusable_password()
            user.save(update_fields=['password'])
            messages.info(request, "For security your old password was cleared. Use 'Forgot your password?' to set a new one.")
        profile.email_verified = True
        profile.save(update_fields=['email_verified'])
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    if plan_id:
        plan = Plan.objects.filter(pk=plan_id, user__isnull=True).first()
        if plan is not None:
            plan.user = user
            plan.save()
    messages.success(request, "Signed in with Google.")
    return redirect('userplans')

# USER: Signup email availability (used for inline validation)
def check_email(request):
    email = (request.GET.get('email') or '').strip()
    taken = bool(email) and User.objects.filter(email__iexact=email).exists()
    return JsonResponse({'available': not taken})

# LANDING PAGE
LANDING_FAQ = [
    ("What is FIRE?", "Financial Independence, Retire Early: saving enough that investment returns can cover your spending."),
    ("What is Coast FI?", "The age at which you can stop contributing and still reach your FI number through growth alone."),
    ("What is the 4% rule?", "A guideline that you can withdraw about 4% of your portfolio per year, so your FI number is roughly 25x annual spending."),
    ("Do I need to link a bank account?", "No. You enter your numbers manually and can delete your data at any time from My Account."),
]

def landing(request):
    context = {'faq': LANDING_FAQ, 'premium_features': PREMIUM_FEATURES, 'premium_plan_limit': MAX_USER_PLANS}
    if request.user.is_authenticated:
        plans = Plan.objects.filter(user=request.user).order_by('-id')
        latest = plans.first()
        if latest:
            fi = _summarize(latest)
            context.update({
                'latest_plan': latest,
                'latest_fi_age': fi.fi_age if fi else None,
                'latest_funded': fi.funded_percent if fi else None,
            })
        count = plans.count()
        context['plan_count'] = count
        context['at_limit'] = not user_is_premium(request.user) and count >= settings.FREE_PLAN_LIMIT
    return render(request, 'FIRE/landing.html', context)

# USER: Signup
def signupuser(request):
    if request.method == "GET":
        return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm()})
    response, error = _create_account(request)
    return response or error

# USER: Signup & Save Plan            
def signupsave(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    if plan.user is not None:
        messages.warning(request, "This plan already belongs to an account.")
        return redirect('loginuser')
    if request.method == "GET":
        return render(request, 'FIRE/signupuser.html', {'form':CreateUserForm(), 'plan': plan})
    response, error = _create_account(request, plan)
    return response or error

# USER: Login
def loginuser(request):
    if request.method == "GET":
        if request.user.is_authenticated:
            return redirect('userplans')
        else:
            return render(request, 'FIRE/loginuser.html', {'form':AuthenticationForm()})
    else:
        identifier = (request.POST.get('email') or request.POST.get('username') or '').strip()
        match = User.objects.filter(email__iexact=identifier).first() or User.objects.filter(username__iexact=identifier).first()
        user = authenticate(request, username=match.username if match else identifier, password=request.POST.get('password'))
        if user is None:
            return render(request, 'FIRE/loginuser.html', {'form':AuthenticationForm(), 'error': "Email and password did not match."})
        else:
            login(request, user)
            messages.success(request, "Logged in successfully!")
            return redirect('userplans')

# USER: Logout     
@login_required
def logoutuser(request):
    if request.method == "POST":
        logout(request)
        messages.success(request, "Logged out successfully!")
        return redirect('landing')
    else:
        return redirect('userplans')

# USER: Feedback    
def feedback(request):
    if request.method == "GET":
        if request.user.is_superuser: # just using request.user attributes
            feedback = Feedback.objects.all()
            return render(request, 'FIRE/feedback.html', {'form': FeedbackForm(), 'feedback': feedback})
        return render(request, 'FIRE/feedback.html', {'form': FeedbackForm()})
    else:
        form = FeedbackForm(request.POST)
        if not form.is_valid():
            messages.warning(request, "Please provide your feedback before submitting.")
            return redirect('feedback')
        newfeedback = form.save(commit=False)
        if request.user.is_authenticated:
            newfeedback.user = request.user
        newfeedback.save()
        messages.success(request, "Feedback submitted successfully!")
        return redirect('feedback')

def _summarize(plan):
    try:
        fi = PlanObject(plan).run()
    except Exception as e:
        print(f"summary failed for {plan.pk}: {e}")
        return None
    return fi

PLAN_SORTS = {
    'name': lambda p: p.plan_name.lower(),
    'created': lambda p: p.created_at,
    'retirement': lambda p: p.retirement_age,
    'fi_age': lambda p: (not isinstance(p.fi_age, int), p.fi_age if isinstance(p.fi_age, int) else 0),
    'funded': lambda p: -1 if p.funded_percent is None else p.funded_percent,
}

PREMIUM_FEATURES = [
    ('What-if scenarios', 'Drag sliders for retirement age, savings and returns and see the projection update live.'),
    ('Retirement withdrawal planning', 'See how long your portfolio lasts once you stop working, with spending, inflation and market-risk odds.'),
    ('Plan comparison', 'Compare up to three plans side by side on one chart.'),
    ('CSV download', 'Export the full year-by-year projection to a spreadsheet.'),
    ('More saved plans', 'Save up to 50 plans instead of the free limit.'),
]

# USER: My Account
@login_required
def myaccount(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    errors = {}
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'profile':
            email = (request.POST.get('email') or '').strip()
            first_name = (request.POST.get('first_name') or '').strip()[:150]
            try:
                validate_email(email)
            except ValidationError:
                errors['email'] = 'Enter a valid email address.'
            else:
                if User.objects.filter(email__iexact=email).exclude(pk=request.user.pk).exists():
                    errors['email'] = 'That email is already associated with another account.'
            if not errors:
                email_changed = email.lower() != request.user.email.lower()
                request.user.email = email
                request.user.first_name = first_name
                request.user.save(update_fields=['email', 'first_name'])
                if email_changed:
                    profile.email_verified = False
                    profile.save(update_fields=['email_verified'])
                    auth_flows.send_verification_email(request.user)
                    messages.success(request, "Your details were updated. We sent a confirmation link to your new email.")
                else:
                    messages.success(request, "Your details were updated.")
                return redirect('myaccount')
        elif action == 'upgrade':
            if not settings.PREMIUM_DEMO_UPGRADE:
                messages.error(request, "Online upgrades are not available yet.")
            elif not profile.email_verified:
                messages.warning(request, "Please confirm your email address before upgrading.")
            elif not profile.is_premium:
                profile.is_premium = True
                profile.premium_since = timezone.now()
                profile.save()
                messages.success(request, "Welcome to Premium! All premium features are now unlocked.")
            return redirect('myaccount')
        elif action == 'downgrade':
            if settings.STRIPE_ENABLED:
                messages.info(request, "Use 'Manage billing' to cancel your subscription.")
            elif profile.is_premium:
                profile.is_premium = False
                profile.premium_since = None
                profile.save()
                messages.success(request, "Your account is back on the Free plan. Your saved plans are untouched.")
            return redirect('myaccount')
        elif action == 'delete':
            if request.user.has_usable_password():
                confirmed = request.user.check_password(request.POST.get('password', ''))
            else:
                confirmed = request.POST.get('password', '').strip().lower() == request.user.email.lower()
            if confirmed:
                user = request.user
                logout(request)
                user.delete()
                messages.success(request, "Your account and plans were deleted.")
                return redirect('landing')
            errors['delete'] = 'Incorrect confirmation. Your account was not deleted.'

    plan_count = Plan.objects.filter(user=request.user).count()
    return render(request, 'FIRE/account/myaccount.html', {
        'profile': profile,
        'errors': errors,
        'plan_count': plan_count,
        'plan_limit': MAX_USER_PLANS if profile.is_premium else settings.FREE_PLAN_LIMIT,
        'premium_features': PREMIUM_FEATURES,
        'can_upgrade': settings.PREMIUM_DEMO_UPGRADE,
        'stripe_enabled': settings.STRIPE_ENABLED,
        'billing_intervals': billing.available_intervals() if settings.STRIPE_ENABLED else [],
        'has_customer': bool(profile.stripe_customer_id),
    })


@login_required
@require_POST
def start_checkout(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if not settings.STRIPE_ENABLED:
        messages.error(request, "Online payments are not available yet.")
    elif not profile.email_verified:
        messages.warning(request, "Please confirm your email address before upgrading.")
    elif profile.is_premium:
        messages.info(request, "You already have Premium.")
    else:
        interval = 'year' if request.POST.get('interval') == 'year' else 'month'
        try:
            url = billing.create_checkout_url(profile, interval)
        except Exception:
            logger.exception("Stripe checkout failed")
            url = None
        if url:
            return redirect(url)
        messages.error(request, "We couldn't start checkout. Please try again shortly.")
    return redirect('myaccount')


@login_required
@require_POST
def billing_portal(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if settings.STRIPE_ENABLED and profile.stripe_customer_id:
        try:
            return redirect(billing.create_portal_url(profile))
        except Exception:
            logger.exception("Stripe portal failed")
    messages.error(request, "We couldn't open billing right now. Please try again shortly.")
    return redirect('myaccount')


@csrf_exempt
@require_POST
def stripe_webhook(request):
    import stripe
    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=503)
    try:
        event = stripe.Webhook.construct_event(
            request.body, request.META.get('HTTP_STRIPE_SIGNATURE', ''), settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)
    try:
        billing.handle_event(event)
    except Exception:
        logger.exception("Stripe webhook handling failed")
        return HttpResponse(status=500)
    return HttpResponse(status=200)

# USER: Plans
def userplans(request):
    if request.user.is_authenticated:
        query = request.GET.get('q', '').strip()
        sort = request.GET.get('sort', 'created')
        if sort not in PLAN_SORTS:
            sort = 'created'
        descending = request.GET.get('dir', 'desc' if sort == 'created' else 'asc') == 'desc'

        queryset = Plan.objects.filter(user=request.user)
        if query:
            queryset = queryset.filter(plan_name__icontains=query)
        plans = list(queryset)
        for plan in plans:
            fi = _summarize(plan)
            plan.fi_age = fi.fi_age if fi else "N/A"
            plan.funded_percent = fi.funded_percent if fi else None
        plans.sort(key=PLAN_SORTS[sort], reverse=descending)
        return render(request, 'FIRE/userplans.html', {
            'plans': plans, 'q': query, 'sort': sort, 'dir': 'desc' if descending else 'asc',
            'total_plans': Plan.objects.filter(user=request.user).count(),
            'sort_columns': [('name', 'Name'), ('created', 'Date Created'), ('retirement', 'Retirement Age'), ('fi_age', 'FI Age'), ('funded', 'Funded')],
        })
    else:
        messages.warning(request, "You must be logged in to view your plans.")
        return redirect('loginuser')

def _premium_required(request, feature):
    messages.warning(request, f"{feature} is a Premium feature. Upgrade your account to unlock it.")
    return redirect('myaccount')

# PLANS: Compare (2-3 of the user's own plans)
@login_required
def compareplans(request):
    if not user_is_premium(request.user):
        return _premium_required(request, "Plan comparison")
    ids = request.GET.getlist('plans')
    plans = list(Plan.objects.filter(user=request.user, pk__in=[i for i in ids if _is_uuid(i)]))
    if not 2 <= len(plans) <= 3:
        messages.warning(request, "Select two or three plans to compare.")
        return redirect('userplans')

    rows, series = [], []
    max_age = max(plan.retirement_age for plan in plans)
    for plan in plans:
        fi = _summarize(plan)
        if fi is None:
            messages.warning(request, f"Could not generate {plan.plan_name}.")
            return redirect('userplans')
        rows.append({'plan': plan, 'fi': fi})
        series.append({
            'name': plan.plan_name,
            'points': [{'x': age, 'y': nw} for age, nw in zip(fi.ages, fi.net_worths)],
            'magic': [{'x': age, 'y': m} for age, m in zip(fi.ages, fi.magic_numbers)],
        })
    return render(request, 'FIRE/compareplans.html', {'rows': rows, 'compare_data': {'series': series, 'max_age': max_age}})

def _build_fiplan(plan):
    FIplan = PlanObject(plan).run()
    FIplan.update_final_net_worth()
    return FIplan

# PLANS: Run
def runplan(request, plan_id):
    # Retrieve plan object from Django model
    plan = get_object_or_404(Plan, pk=plan_id)

    # Ensure plan belongs to requesting user
    if not _can_access_plan(request, plan):
        messages.warning(request, "You are not authorized to view that plan.")
        return redirect('userplans' if request.user.is_authenticated else 'loginuser')

    error = None
    form = None
    # If post request, update the plan in the database by saving the form
    if request.method == "POST":
        form = EditPlanForm(request.POST, instance=plan)
        try:
            updatedplan = saveplan(form, request, dashboard_edit=True)
            if isinstance(updatedplan, str):
                error = updatedplan
                plan.refresh_from_db()
        except Exception as e:
            print(f"Error updating: {e}")
            error = f"Error updating {plan.plan_name}."
            plan.refresh_from_db()

    FIplan = None
    sankey = None
    try:
        FIplan = _build_fiplan(plan)
        sankey = FIplan.sankey_chart()
    except Exception as e:
        print(f"Error generating: {e}")
        error = error or f"Error generating {plan.plan_name}."

    if FIplan is None:
        messages.warning(request, error)
        return render(request, 'FIRE/newplan.html', {'form': PlanForm(), 'error': error})

    context = {'plan': plan, 'FIplan': FIplan, 'sankey_chart': sankey, 'chart_data': FIplan.chart_data()}
    if error:
        context['error'] = error
    if request.method == "POST":
        context['form'] = form
        if not error:
            messages.success(request, f"{plan.plan_name} updated successfully!")
        return render(request, 'FIRE/partials/plandashboard.html', context)
    context['form'] = EditPlanForm()
    return render(request, "FIRE/runplan.html", context)

# PLANS: Create New
MAX_ANONYMOUS_PLANS = 5
MAX_USER_PLANS = 50

def _plan_limit_error(request):
    if request.user.is_authenticated:
        count = Plan.objects.filter(user=request.user).count()
        if not user_is_premium(request.user):
            if count >= settings.FREE_PLAN_LIMIT:
                return f"Free accounts can save {settings.FREE_PLAN_LIMIT} plans. Delete a plan or upgrade to Premium to create more."
        elif count >= MAX_USER_PLANS:
            return f"You have reached the limit of {MAX_USER_PLANS} plans. Delete one to create another."
    elif len(request.session.get('anonymous_plans', [])) >= MAX_ANONYMOUS_PLANS:
        return f"You have created {MAX_ANONYMOUS_PLANS} plans without an account. Sign up to save more."
    return None

def newplan(request):

    if request.method == "GET":
        limit_error = _plan_limit_error(request)
        if limit_error and request.user.is_authenticated:
            messages.warning(request, limit_error)
            return redirect('userplans' if user_is_premium(request.user) else 'myaccount')
        return render(request, 'FIRE/newplan.html', {'form': PlanForm(), 'error': limit_error})
    limit_error = _plan_limit_error(request)
    if limit_error:
        return render(request, 'FIRE/newplan.html', {'form': PlanForm(request.POST), 'error': limit_error})
    form = PlanForm(request.POST)
    try:
        newplan = saveplan(form, request)
        if isinstance(newplan, str):
            return render(request, 'FIRE/newplan.html', {'form': form, 'error': newplan})
        if not request.user.is_authenticated:
            request.session['anonymous_plans'] = request.session.get('anonymous_plans', []) + [str(newplan.id)]
        return redirect('runplan', plan_id=newplan.id)
    except Exception as e:
        print(e)
        return render(request, 'FIRE/newplan.html', {'form': form, 'error': "Error saving plan, please try again."})

# PLANS: Withdrawal-phase projection (Premium, never saved)
def withdrawal(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    if not _can_access_plan(request, plan):
        raise Http404("Plan not found.")
    if not user_is_premium(request.user):
        return JsonResponse({'error': 'Withdrawal planning is a Premium feature.'}, status=403)

    def number(name, default, low, high):
        try:
            return min(max(float(request.GET.get(name, default)), low), high)
        except (TypeError, ValueError):
            return default

    try:
        fi = PlanObject(plan).run()
        raw_return = request.GET.get('return')
        annual_return = None if raw_return in (None, '') else number('return', 0, 0, 12)
        return JsonResponse(fi.withdrawal_data(
            end_age=int(number('end_age', 95, plan.retirement_age + 1, 110)),
            inflation=number('inflation', 2.5, 0, 8),
            annual_return=annual_return,
            spending_percent=number('spending', 100, 25, 200),
        ))
    except Exception as e:
        print(f"withdrawal failed for {plan.pk}: {e}")
        return JsonResponse({'error': 'Could not calculate retirement spending.'}, status=400)

# PLANS: What-if projection (never saved)
def whatif(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    if not _can_access_plan(request, plan):
        raise Http404("Plan not found.")
    if not user_is_premium(request.user):
        return JsonResponse({'error': 'What-if scenarios are a Premium feature.'}, status=403)

    def number(name, default, low, high):
        try:
            return min(max(float(request.GET.get(name, default)), low), high)
        except (TypeError, ValueError):
            return default

    scenario = copy.copy(plan)
    scenario.retirement_age = int(number('retirement_age', plan.retirement_age, plan.current_age + 1, 101))
    try:
        fi = PlanObject(
            scenario,
            return_delta=number('return_delta', 0, -10, 10),
            extra_savings=number('extra_savings', 0, -1_000_000, 1_000_000),
        ).run()
    except Exception as e:
        print(f"what-if failed for {plan.pk}: {e}")
        return JsonResponse({'error': 'Could not calculate this scenario.'}, status=400)
    return JsonResponse(fi.whatif_data())

def _owned_plan(request, plan_id):
    plan = get_object_or_404(Plan, pk=plan_id)
    if plan.user != request.user:
        raise Http404("Plan not found.")
    return plan

# PLANS: Delete        
@login_required
@require_POST
def deleteplan(request, plan_id):
    plan = _owned_plan(request, plan_id)
    name = plan.plan_name
    try:
        plan.delete()
        messages.success(request, f"{name} deleted successfully!")
    except Exception as e:
        messages.warning(request, f"Error deleting {name}.")
    return redirect('userplans')
    
# PLANS: Copy
@login_required
def copyplan(request, plan_id):
    plan = _owned_plan(request, plan_id)
    plan_name = plan.plan_name
    limit_error = _plan_limit_error(request)
    if limit_error:
        messages.warning(request, limit_error)
        return redirect('userplans')
    try:
        plan.pk = None
        plan.id = uuid.uuid4()
        plan._state.adding = True
        plan.plan_name = f"{plan_name} (copy)"[:50]
        plan.save()
        messages.success(request, f"{plan_name} copied successfully!")
    except Exception as e:
        print(f"copyplan: {e}")
        messages.warning(request, f"Error copying {plan_name}.")
    return redirect('userplans')


# PLANS: Download PDF (Premium)
def downloadpdf(request, plan_id):
    plan = get_object_or_404(Plan, id=plan_id)
    if not _can_access_plan(request, plan):
        raise Http404("Plan not found.")
    if not user_is_premium(request.user):
        return _premium_required(request, "PDF report")
    try:
        FIplan = _build_fiplan(plan)
        pdf = pdf_report.build_plan_pdf(plan, FIplan, FIplan.chart_data())
    except Exception:
        logging.getLogger(__name__).exception("PDF generation failed")
        messages.warning(request, f"Could not create the PDF for {plan.plan_name}.")
        return redirect('runplan', plan_id=plan.id)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="plan_{plan_id}.pdf"'
    return response


# PLANS: Download
def downloadplan(request, plan_id):
    # Retrieve plan object from Django model
    plan = get_object_or_404(Plan, id=plan_id)
    if not _can_access_plan(request, plan):
        raise Http404("Plan not found.")
    if not user_is_premium(request.user):
        return _premium_required(request, "CSV download")

    try:
        FIplan = _build_fiplan(plan)

        # Set up response object for return of csv file
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="plan_{plan_id}.csv"'

        # Set up writer object to store plan data
        writer = csv.writer(response)

        # Create header row based on plan entires
        header_row = ['Age', 'Year']

        for income in FIplan.incomes:
            if income['income_category'] == "Salary":
                header_row.extend([income['income_name'] + ': Gross', income['income_name'] + ': Bonus', income['income_name'] + ': Tax', income['income_name'] + ': Net'])
            else:
                header_row.extend([income['income_name'] + ': Gross', income['income_name'] + ': Tax', income['income_name'] + ': Net'])
        
        for expense in FIplan.expenses:
            header_row.extend([expense['expense_name']])
        
        header_row.extend(['Savings'])
        
        for account in FIplan.accounts[1:]:
            category = account.get('saving_category')
            name = account.get('saving_name', 'Investments')
            if category == "ESRP":
                header_row.extend([name + ": Start", name + ": Cont. Limit", name + ": Cont. Amount", name + ": Employer Cont. Amount", name + ": End"])
            elif category in ("HSA", "IRA"):
                header_row.extend([name + ": Start", name + ": Cont. Limit", name + ": Cont. Amount", name + ": End"])
            else:
                header_row.extend([name + ": Start", name + ": Cont. Amount", name + ": End"])
        
        header_row.extend(['Net Worth', 'Magic Number', 'Withdraw Rate'])
        
        # Write header row
        writer.writerow(header_row)

        # Write data rows
        for row in FIplan.plan_data:
            writer.writerow(row)

        # Return csv response
        return response
    except Exception as e:
        print(f"downloadplan: {e}")
        messages.warning(request, f"Error downloading {plan.plan_name}.")
        return redirect('userplans')
    

# HTMX: Add Section
def create_incomes_section(request):
    return render(request, 'FIRE/partials/section_incomes.html')

# HTMX: Add Section
def create_expenses_section(request):
    return render(request, 'FIRE/partials/section_expenses.html')

# HTMX: Add Section
def create_savings_section(request):
    return render(request, 'FIRE/partials/section_savings.html')

# HTMX: Add New Entry
def create_income(request):
    entry_count = int(request.GET.get("entry_count"))+1
    return render(request, 'FIRE/partials/new_income.html', {'entry_count': entry_count})

# HTMX: Add New Entry
def create_expense(request):
    entry_count = int(request.GET.get("entry_count"))+1
    return render(request, 'FIRE/partials/new_expense.html', {'entry_count': entry_count})

#HTMX: Savings Method
def savings_method(request):
    if request.GET.get('saving_option') == 'Simple':
        return render(request, 'FIRE/partials/savings_method_simple.html')
    elif request.GET.get('saving_option') == 'Recommended':
        return render(request, 'FIRE/partials/savings_method_recommended.html')
    elif request.GET.get('saving_option') == 'Custom':
        print("Here")
        return render(request, 'FIRE/partials/savings_method_custom.html')
    else:
        return render(request, 'FIRE/partials/none.html')

# HTMX: Add New Entry
def create_saving(request):
    entry_count = int(request.GET.get("entry_count"))
    esrp_count = int(request.GET.get("esrp_count"))
    hsa_count = int(request.GET.get("hsa_count"))
    ira_count = int(request.GET.get("ira_count"))
    tba_count = int(request.GET.get("tba_count"))
    if entry_count < 4:
        return render(request, 'FIRE/partials/new_saving.html', {'entry_count': entry_count, 'esrp_count': esrp_count, 'hsa_count': hsa_count, 'ira_count': ira_count, 'tba_count': tba_count})
    else:
        return render(request, 'FIRE/partials/none.html')

# HTMX: Add Category Fields
def income_fields(request):
    category = request.GET.get("income_category")
    salary_count = request.GET.get("salary_count")
    recurring_income_count = request.GET.get("recurring_income_count")
    one_time_income_count = request.GET.get("one_time_income_count")
    ages = [num for num in range(int(request.GET.get("min_age")),int(request.GET.get("max_age")))]
    if category == "Salary":
        ages[0] = "Current Age"
        ages[-1] = "Target Retirement Age"
        return render(request, 'FIRE/partials/fields_income_salary.html', {'ages' : ages, 'salary_count' : salary_count})
    elif category == "Recurring":
        ages[0] = "Current Age"
        ages[-1] = "Target Retirement Age"
        return render(request, 'FIRE/partials/fields_income_recurring.html', {'ages' : ages, 'recurring_income_count' : recurring_income_count})
    elif category == "One-time":
        return render(request, 'FIRE/partials/fields_income_one_time.html', {'ages' : ages, 'one_time_income_count' : one_time_income_count})
    else:
        return render(request, 'FIRE/partials/fields_income_none.html')

# HTMX: Add Category Fields    
def expense_fields(request):
    category = request.GET.get("expense_category")
    recurring_expense_count = request.GET.get("recurring_expense_count")
    one_time_expense_count = request.GET.get("one_time_expense_count")
    ages = [num for num in range(int(request.GET.get("min_age")),int(request.GET.get("max_age")))]
    if category == "Recurring":
        ages[0] = "Current Age"
        ages[-1] = "Target Retirement Age"
        return render(request, 'FIRE/partials/fields_expenses_recurring.html', {'ages' : ages, 'recurring_expense_count' : recurring_expense_count})
    elif category == "One-time":
        return render(request, 'FIRE/partials/fields_expenses_one_time.html', {'ages' : ages, 'one_time_expense_count' : one_time_expense_count})
    else:
        return render(request, 'FIRE/partials/fields_expenses_none.html')

# HTMX: Add Category Fields
def saving_fields(request):
    category = request.GET.get("saving_category")
    ages = [num for num in range(int(request.GET.get("min_age")),int(request.GET.get("max_age")))]
    if category == "ESRP":        
        if int(request.GET.get("esrp_count")) == 0:
            return render(request, 'FIRE/partials/fields_savings_esrp.html', {'ages' : ages})
        else:
            return render(request, 'FIRE/partials/fields_savings_none.html')
    elif category == "IRA":
        if int(request.GET.get("ira_count")) == 0:
            return render(request, 'FIRE/partials/fields_savings_ira.html', {'ages' : ages})
        else:
            return render(request, 'FIRE/partials/fields_savings_none.html')
    elif category == "HSA":
        if int(request.GET.get("hsa_count")) == 0:
            return render(request, 'FIRE/partials/fields_savings_hsa.html', {'ages' : ages})
        else:
            return render(request, 'FIRE/partials/fields_savings_none.html')
    elif category == "TBA":
        if int(request.GET.get("tba_count")) == 0:
            return render(request, 'FIRE/partials/fields_savings_tba.html', {'ages' : ages})
        else:
            return render(request, 'FIRE/partials/fields_savings_none.html')
    else:
        return render(request, 'FIRE/partials/fields_savings_none.html')

# HTMX: Add Entry Table    
def income_table(request):
    if request.GET.get('income_category') == "None":
        return render(request, 'FIRE/partials/table_none.html')
    
    try:
        min_age = int(request.GET.get("min_age"))
        max_age = int(request.GET.get("max_age"))
        ages = [age for age in range(min_age,max_age)]

        if request.GET.get('income_category') == "One-time":
            amount = int(request.GET.get("amount"))
            lump_sum_age = int(request.GET.get("age"))
            tax_rate = float(request.GET.get("tax_rate"))

            data = []
            year_dict = {}
            year_dict['age'] = lump_sum_age
            year_dict['gross_amount'] = '${:,}'.format(amount)
            year_dict['tax_amount'] = '${:,}'.format(math.floor(amount * round(tax_rate/100,3)))
            year_dict['net_amount'] = '${:,}'.format(amount - math.floor(amount * round(tax_rate/100,3)))
            data.append(year_dict)
            return render(request, 'FIRE/partials/table_income_one_time.html', {'data': data})
        
        else:
            starting_amount = int(request.GET.get("starting_amount"))
            yearly_change = float(request.GET.get("yearly_change"))
            tax_rate = float(request.GET.get("tax_rate"))
            tax_rate_change = float(request.GET.get("tax_rate_change"))
            start_age = request.GET.get("start_age")
            if start_age == "Current Age":
                start_age = min_age
            else:
                start_age = int(start_age)
            stop_age = request.GET.get("stop_age")
            if stop_age == "Target Retirement Age":
                stop_age = max_age-1
            else:
                stop_age = int(stop_age)
            income_age_range = [age for age in range(start_age,stop_age+1)]
            gross_amounts = [math.floor(starting_amount * ((1 + round(yearly_change/100,3)) ** year)) for year in range(0,len(income_age_range))]
            gross_amounts_dict = dict(zip(income_age_range, gross_amounts))
            gross_amounts = [gross_amounts_dict[age] if age in gross_amounts_dict else 0 for age in ages]
            tax_rates = [round(((tax_rate) + (year * tax_rate_change)),3) for year in range(0,len(income_age_range))]
            tax_rates_dict = dict(zip(income_age_range,tax_rates))
            tax_rates = [tax_rates_dict[age] if age in tax_rates_dict else 0 for age in ages]

            if request.GET.get('income_category') == "Salary":
                bonus_rate = float(request.GET.get("bonus_rate"))
                bonus_amounts = [math.floor(gross_amounts[year] * round(bonus_rate/100,3)) for year in range(0,len(ages))]
                tax_amounts = [math.floor((gross_amounts[year] + bonus_amounts[year]) * round(tax_rates[year]/100,3)) for year in range(0,len(ages))]
                net_amounts = [math.floor(gross_amounts[year] + bonus_amounts[year] - tax_amounts[year]) for year in range(0,len(ages))]
                
                data = []
                for age in range(0,len(ages)):
                    year_dict = {}
                    year_dict['age'] = ages[age]
                    year_dict['gross_amount'] = '${:,}'.format(gross_amounts[age])
                    year_dict['bonus_amount'] = '${:,}'.format(bonus_amounts[age])
                    year_dict['tax_amount'] = '${:,}'.format(tax_amounts[age])
                    year_dict['net_amount'] = '${:,}'.format(net_amounts[age])
                    data.append(year_dict)
                return render(request, 'FIRE/partials/table_income_salary.html', {'data': data})
            
            else: 
                tax_amounts = [math.floor((gross_amounts[year]) * round(tax_rates[year]/100,3)) for year in range(0,len(ages))]
                net_amounts = [math.floor(gross_amounts[year] - tax_amounts[year]) for year in range(0,len(ages))]
                
                data = []
                for age in range(0,len(ages)):
                    year_dict = {}
                    year_dict['age'] = ages[age]
                    year_dict['gross_amount'] = '${:,}'.format(gross_amounts[age])
                    year_dict['tax_amount'] = '${:,}'.format(tax_amounts[age])
                    year_dict['net_amount'] = '${:,}'.format(net_amounts[age])
                    data.append(year_dict)
                return render(request, 'FIRE/partials/table_income_recurring.html', {'data': data})
    except Exception as e:
        print(f"Income Table: {e}")
        return render(request, 'FIRE/partials/table_none.html')

# HTMX: Add Entry Table 
def expense_table(request):
    if request.GET.get('expense_category') == "None":
        return render(request, 'FIRE/partials/table_none.html')
    min_age = int(request.GET.get("min_age"))
    max_age = int(request.GET.get("max_age"))
    ages = [age for age in range(min_age,max_age)]

    if request.GET.get('expense_category') == "One-time":
        amount = int(request.GET.get("amount"))
        lump_sum_age = int(request.GET.get("age"))

        data = []
        year_dict = {}
        year_dict['age'] = lump_sum_age
        year_dict['amount'] = '${:,}'.format(amount)
        data.append(year_dict)
        return render(request, 'FIRE/partials/table_expense_one_time.html', {'data': data})
    
    else:
        starting_amount = int(request.GET.get("starting_amount"))
        yearly_change = float(request.GET.get("yearly_change"))
        start_age = request.GET.get("start_age")
        if start_age == "Current Age":
            start_age = min_age
        else:
            start_age = int(start_age)
        stop_age = request.GET.get("stop_age")
        if stop_age == "Target Retirement Age":
            stop_age = max_age-1
        else:
            stop_age = int(stop_age)

        expense_age_range = [age for age in range(start_age,stop_age+1)]
        amounts = [math.floor(starting_amount * ((1 + round(yearly_change/100,3)) ** year)) for year in range(0,len(expense_age_range))]
        amounts_dict = dict(zip(expense_age_range, amounts))
        amounts = [amounts_dict[age] if age in amounts_dict else 0 for age in ages]
            
        data = []
        for age in range(0,len(ages)):
            year_dict = {}
            year_dict['age'] = ages[age]
            year_dict['amount'] = '${:,}'.format(amounts[age])
            data.append(year_dict)
        return render(request, 'FIRE/partials/table_expense_recurring.html', {'data': data})

