from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest import mock

from django.test import client as _test_client

from .engine import PlanObject, money
from .models import Plan, Profile
# Django 4.2's test client copies template contexts, which breaks on Python 3.14+.
# These tests don't inspect response.context, so skip that bookkeeping.
_test_client.store_rendered_templates = lambda *args, **kwargs: None


def make_plan(savings, current_age=30, retirement_age=35, salary=100000, expense=40000):
    return SimpleNamespace(
        current_age=current_age,
        retirement_age=retirement_age,
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

    def test_coast_fi_age_computed(self):
        rich = PlanObject(make_plan(['Simple', {'simple_net_worth': 600000, 'simple_yearly_growth': 10.0}])).run()
        self.assertEqual(rich.coast_fi_age, 30)
        poor = PlanObject(make_plan(['Simple', {'simple_net_worth': 1000, 'simple_yearly_growth': 0.0}])).run()
        self.assertEqual(poor.coast_fi_age, 'N/A')
        middle = PlanObject(make_plan(['Simple', {        'simple_net_worth': 500000, 'simple_yearly_growth': 10.0}])).run()
        self.assertIsInstance(middle.coast_fi_age, int)
        self.assertGreater(middle.coast_fi_age, 30)

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


class EmailVerificationAndGoogleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('sam', 'sam@example.com', 'pw-12345-xyz')

    def test_token_verifies_and_goes_stale_when_email_changes(self):
        from . import auth_flows
        token = auth_flows.make_verification_token(self.user)
        self.assertFalse(Profile.objects.get_or_create(user=self.user)[0].email_verified)
        self.client.get(reverse('verify_email', args=[token]))
        self.assertTrue(Profile.objects.get(user=self.user).email_verified)
        self.user.email = 'new@example.com'
        self.user.save()
        self.assertIsNone(auth_flows.read_verification_token(token))
        self.assertIsNone(auth_flows.read_verification_token('garbage'))

    def test_signup_sends_verification_and_blocks_upgrade_until_verified(self):
        from django.core import mail
        self.client.post(reverse('signupuser'), {'email': 'newbie@example.com',
                                                 'password1': 'Str0ng-pass-99', 'password2': 'Str0ng-pass-99'})
        self.assertTrue(any('Confirm your FI Planner email' in m.subject for m in mail.outbox))
        user = User.objects.get(email='newbie@example.com')
        self.assertEqual(user.username, 'newbie')
        with self.settings(PREMIUM_DEMO_UPGRADE=True):
            self.client.post(reverse('myaccount'), {'action': 'upgrade'})
            self.assertFalse(Profile.objects.get(user=user).is_premium)
            Profile.objects.filter(user=user).update(email_verified=True)
            self.client.post(reverse('myaccount'), {'action': 'upgrade'})
            self.assertTrue(Profile.objects.get(user=user).is_premium)

    def test_login_with_email_and_unique_generated_usernames(self):
        for _ in range(2):
            self.client.logout()
        self.client.post(reverse('signupuser'), {'email': 'sam@other.com', 'password1': 'Str0ng-pass-99', 'password2': 'Str0ng-pass-99'})
        self.assertEqual(User.objects.get(email='sam@other.com').username, 'sam2')
        self.client.logout()
        self.client.post(reverse('loginuser'), {'email': 'SAM@OTHER.com', 'password': 'Str0ng-pass-99'})
        self.assertIn('_auth_user_id', self.client.session)

    def test_check_email_endpoint(self):
        url = reverse('check_email')
        self.assertFalse(self.client.get(url, {'email': 'SAM@example.com'}).json()['available'])
        self.assertTrue(self.client.get(url, {'email': 'free@example.com'}).json()['available'])

    def test_password_complexity_enforced_on_signup(self):
        base = {'email': 'pw@example.com'}
        for weak in ('alllowercase-pass', 'NoNumbers-here', 'NoSpecial1234x'):
            self.client.post(reverse('signupuser'), {**base, 'password1': weak, 'password2': weak})
            self.assertFalse(User.objects.filter(email='pw@example.com').exists(), weak)
        good = 'Str0ng-pass-99'
        self.client.post(reverse('signupuser'), {**base, 'password1': good, 'password2': good})
        self.assertTrue(User.objects.filter(email='pw@example.com').exists())

    def test_google_login_disabled_without_credentials(self):
        response = self.client.get(reverse('google_login'))
        self.assertRedirects(response, reverse('loginuser'), fetch_redirect_response=False)

    def test_google_callback_creates_and_links_accounts(self):
        from unittest import mock
        session = self.client.session
        session['google_state'] = 'abc'
        session.save()
        info = {'email': 'sam@example.com', 'email_verified': True, 'given_name': 'Sam'}
        with mock.patch('FIRE.auth_flows.fetch_google_profile', return_value=info):
            self.client.get(reverse('google_callback'), {'state': 'wrong', 'code': 'x'})
            self.assertNotIn('_auth_user_id', self.client.session)
            session = self.client.session
            session['google_state'] = 'abc'
            session.save()
            self.client.get(reverse('google_callback'), {'state': 'abc', 'code': 'x'})
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)
        self.user.refresh_from_db()
        self.assertFalse(self.user.has_usable_password())
        self.assertTrue(Profile.objects.get(user=self.user).email_verified)

        self.client.logout()
        session = self.client.session
        session['google_state'] = 'def'
        session.save()
        info = {'email': 'fresh@example.com', 'email_verified': True}
        with mock.patch('FIRE.auth_flows.fetch_google_profile', return_value=info):
            self.client.get(reverse('google_callback'), {'state': 'def', 'code': 'x'})
        fresh = User.objects.get(email='fresh@example.com')
        self.assertTrue(Profile.objects.get(user=fresh).email_verified)


@override_settings(STRIPE_ENABLED=False, PREMIUM_DEMO_UPGRADE=True)
class SurveyAndPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user('owner', 'owner@example.com', 'pw-12345-xyz')
        self.other = User.objects.create_user('other', 'other@example.com', 'pw-12345-xyz')

    def make_premium(self, *users):
        for user in users:
            Profile.objects.update_or_create(user=user, defaults={'is_premium': True, 'email_verified': True})

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

    def test_survey_ignores_coast_fire_age_and_dashboard_shows_coast_fi(self):
        plan_response = self.client.post(reverse('newplan'), survey_post(coast_fire_age='32'))
        self.assertEqual(plan_response.status_code, 302)
        plan = Plan.objects.latest('created_at')
        page = self.client.get(reverse('runplan', args=[plan.id])).content.decode()
        self.assertIn('id="kpi-coast-fi"', page)
        self.assertNotIn('name="coast_fire_age"', page)

    def test_dashboard_modals_have_guard_and_hidden_errors(self):
        self.client.force_login(self.owner)
        plan = self.create_plan()
        page = self.client.get(reverse('runplan', args=[plan.id])).content.decode()
        self.assertIn('fireModalGuard', page)
        self.assertIn('data-method="Simple"', page)
        self.assertNotIn('name="saving_option" id="saving_option_custom" value="Custom"  hx-get', page)
        self.assertIn('Coast FI age', page)

    def test_csv_download(self):
        self.make_premium(self.owner)
        self.client.force_login(self.owner)
        plan = self.create_plan()
        response = self.client.get(reverse('downloadplan', args=[plan.id]))
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_pdf_download(self):
        self.make_premium(self.owner)
        self.client.force_login(self.owner)
        plan = self.create_plan()
        response = self.client.get(reverse('downloadpdf', args=[plan.id]))
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))

    def test_free_users_are_paywalled(self):
        self.client.force_login(self.owner)
        plan = self.create_plan()
        for url in (reverse('downloadplan', args=[plan.id]), reverse('downloadpdf', args=[plan.id]), reverse('compareplans')):
            response = self.client.get(url)
            self.assertRedirects(response, reverse('myaccount'), fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('whatif', args=[plan.id])).status_code, 403)
        page = self.client.get(reverse('runplan', args=[plan.id])).content.decode()
        self.assertNotIn('id="whatif-retirement"', page)
        self.assertIn('Unlock with Premium', page)

    def test_free_plan_limit_and_premium_lifts_it(self):
        self.client.force_login(self.owner)
        for _ in range(3):
            self.create_plan()
        blocked = self.client.post(reverse('newplan'), survey_post())
        self.assertEqual(blocked.status_code, 200)
        self.assertRedirects(self.client.get(reverse('newplan')), reverse('myaccount'), fetch_redirect_response=False)
        self.assertEqual(Plan.objects.filter(user=self.owner).count(), 3)
        self.make_premium(self.owner)
        self.assertEqual(self.client.post(reverse('newplan'), survey_post()).status_code, 302)

    def test_my_account_upgrade_downgrade_and_details(self):
        self.assertEqual(self.client.get(reverse('myaccount')).status_code, 302)
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse('myaccount')), 'Upgrade to Premium')
        self.client.post(reverse('myaccount'), {'action': 'upgrade'})
        self.assertFalse(Profile.objects.get(user=self.owner).is_premium)
        Profile.objects.filter(user=self.owner).update(email_verified=True)
        self.client.post(reverse('myaccount'), {'action': 'upgrade'})
        self.assertTrue(Profile.objects.get(user=self.owner).is_premium)
        with self.settings(PREMIUM_DEMO_UPGRADE=False):
            self.client.post(reverse('myaccount'), {'action': 'downgrade'})
            self.client.post(reverse('myaccount'), {'action': 'upgrade'})
        self.assertFalse(Profile.objects.get(user=self.owner).is_premium)
        bad = self.client.post(reverse('myaccount'), {'action': 'profile', 'email': 'other@example.com'})
        self.assertContains(bad, 'already associated')
        self.client.post(reverse('myaccount'), {'action': 'profile', 'email': 'new@example.com', 'first_name': 'Sam'})
        self.owner.refresh_from_db()
        self.assertEqual((self.owner.email, self.owner.first_name), ('new@example.com', 'Sam'))

    def test_delete_account_requires_password(self):
        self.client.force_login(self.owner)
        self.client.post(reverse('myaccount'), {'action': 'delete', 'password': 'wrong'})
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())
        self.client.post(reverse('myaccount'), {'action': 'delete', 'password': 'pw-12345-xyz'})
        self.assertFalse(User.objects.filter(pk=self.owner.pk).exists())

    def test_delete_cancels_stripe_subscription(self):
        from unittest import mock
        profile = Profile.objects.get_or_create(user=self.owner)[0]
        profile.stripe_customer_id = 'cus_123'
        profile.save()
        self.client.force_login(self.owner)
        with self.settings(STRIPE_ENABLED=True), \
                mock.patch('FIRE.billing._client') as client:
            client.return_value.Subscription.list.return_value = {'data': [{'id': 'sub_1'}]}
            self.client.post(reverse('myaccount'), {'action': 'delete', 'password': 'pw-12345-xyz'})
            client.return_value.Subscription.cancel.assert_called_once_with('sub_1')
        self.assertFalse(User.objects.filter(pk=self.owner.pk).exists())

    def test_delete_blocked_if_stripe_cancel_fails(self):
        from unittest import mock
        profile = Profile.objects.get_or_create(user=self.owner)[0]
        profile.stripe_customer_id = 'cus_123'
        profile.save()
        self.client.force_login(self.owner)
        with self.settings(STRIPE_ENABLED=True), \
                mock.patch('FIRE.billing._client', side_effect=RuntimeError('boom')):
            self.client.post(reverse('myaccount'), {'action': 'delete', 'password': 'pw-12345-xyz'})
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())

    def test_google_only_user_gets_password_reset_email(self):
        google = User.objects.create_user('g_user', 'g@example.com')
        google.set_unusable_password()
        google.save()
        from django.core import mail
        self.client.post(reverse('password_reset'), {'email': 'g@example.com'})
        self.assertEqual(len(mail.outbox), 1)

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
            'email': 'OWNER@example.com', 'password1': 'Str0ng-pass-99', 'password2': 'Str0ng-pass-99'})
        self.assertEqual(User.objects.filter(email__iexact='owner@example.com').count(), 1)
        self.assertEqual(response.status_code, 200)

    def test_landing_varies_by_auth_state(self):
        anon = self.client.get(reverse('landing')).content.decode()
        self.assertNotIn('Quick estimate', anon)
        self.assertIn('Sign up to get Premium', anon)
        self.client.force_login(self.owner)
        self.create_plan()
        page = self.client.get(reverse('landing')).content.decode()
        self.assertIn('Open dashboard', page)
        self.assertIn('Upgrade to Premium', page)
        self.make_premium(self.owner)
        self.assertNotIn('Upgrade to Premium', self.client.get(reverse('landing')).content.decode())

    def test_dashboard_embeds_chart_json_and_lists_show_fi_age(self):
        self.client.force_login(self.owner)
        plan = self.create_plan()
        page = self.client.get(reverse('runplan', args=[plan.id])).content.decode()
        self.assertIn('id="plan-chart-data"', page)
        self.assertNotIn('data-networths', page)
        self.assertContains(self.client.get(reverse('userplans')), 'FI Age')

    def test_about_page_is_public(self):
        self.assertContains(self.client.get(reverse('about')), 'not financial')

    def test_whatif_returns_projection_and_enforces_access(self):
        self.make_premium(self.owner)
        self.client.force_login(self.owner)
        plan = self.create_plan()
        url = reverse('whatif', args=[plan.id])
        base = self.client.get(url).json()
        more = self.client.get(url, {'extra_savings': 20000}).json()
        self.assertEqual(set(['ages', 'net_worths', 'magic_numbers', 'fi_age']) - set(more), set())
        self.assertGreater(more['net_worths'][-1], base['net_worths'][-1])
        self.client.logout()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_withdrawal_is_premium_and_models_depletion(self):
        self.client.force_login(self.owner)
        plan = self.create_plan()
        url = reverse('withdrawal', args=[plan.id])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertContains(self.client.get(reverse('runplan', args=[plan.id])), 'Unlock with Premium')
        self.make_premium(self.owner)
        base = self.client.get(url, {'end_age': 95}).json()
        heavy = self.client.get(url, {'end_age': 110, 'spending': 200, 'return': 0}).json()
        self.assertEqual(len(base['ages']), base['end_age'] - base['start_age'])
        self.assertTrue(0 <= base['success_probability'] <= 100)
        self.assertIsNotNone(heavy['depleted_age'])
        self.assertLessEqual(heavy['success_probability'], base['success_probability'])
        self.assertContains(self.client.get(reverse('runplan', args=[plan.id])), 'WithdrawalChart')
        self.client.logout()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)

    def test_dashboard_has_scenarios_and_whatif_panel(self):
        self.client.force_login(self.owner)
        plan = self.create_plan()
        page = self.client.get(reverse('runplan', args=[plan.id])).content.decode()
        self.assertIn('whatif-panel', page)
        self.assertIn('"p10"', page)
        self.assertIn('success_probability', page)

    def test_userplans_search_and_sort(self):
        self.client.force_login(self.owner)
        first = self.create_plan()
        first.plan_name = 'Alpha'
        first.save()
        second = self.create_plan()
        second.plan_name = 'Zeta'
        second.save()
        found = self.client.get(reverse('userplans'), {'q': 'zet'}).content.decode()
        self.assertIn('Zeta', found)
        self.assertNotIn('Alpha', found)
        ordered = self.client.get(reverse('userplans'), {'sort': 'name', 'dir': 'desc'}).content.decode()
        self.assertLess(ordered.index('Zeta'), ordered.index('Alpha'))

    def test_anonymous_plan_limit(self):
        from .views import MAX_ANONYMOUS_PLANS
        for _ in range(MAX_ANONYMOUS_PLANS):
            self.assertEqual(self.client.post(reverse('newplan'), survey_post()).status_code, 302)
        self.assertEqual(Plan.objects.count(), MAX_ANONYMOUS_PLANS)
        blocked = self.client.post(reverse('newplan'), survey_post())
        self.assertEqual(Plan.objects.count(), MAX_ANONYMOUS_PLANS)
        self.assertNotEqual(blocked.status_code, 500)

    def test_password_reset_pages_and_custom_404(self):
        self.assertContains(self.client.get(reverse('password_reset')), 'Reset password')
        self.assertContains(self.client.get(reverse('loginuser')), 'Forgot your password?')
        self.client.raise_request_exception = False
        missing = self.client.get('/no-such-page/')
        self.assertContains(missing, 'Page not found', status_code=404)

    def test_compare_plans_requires_own_plans(self):
        self.make_premium(self.owner, self.other)
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



@override_settings(STRIPE_ENABLED=True, STRIPE_SECRET_KEY='sk_test_x', STRIPE_WEBHOOK_SECRET='whsec_x',
                   STRIPE_MONTHLY_PRICE_ID='price_m', STRIPE_YEARLY_PRICE_ID='price_y', PREMIUM_DEMO_UPGRADE=False)
class StripeBillingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('payer', 'payer@example.com', 'Str0ng-pass-99')
        Profile.objects.update_or_create(user=self.user, defaults={'email_verified': True, 'stripe_customer_id': 'cus_1'})
        self.client.force_login(self.user)

    def test_checkout_redirects_to_stripe_and_requires_verified_email(self):
        with mock.patch('FIRE.billing.create_checkout_url', return_value='https://checkout.stripe.test/s') as create:
            response = self.client.post(reverse('start_checkout'), {'interval': 'year'})
        self.assertEqual(response['Location'], 'https://checkout.stripe.test/s')
        create.assert_called_once()
        self.assertEqual(create.call_args[0][1], 'year')
        Profile.objects.filter(user=self.user).update(email_verified=False)
        with mock.patch('FIRE.billing.create_checkout_url') as create:
            response = self.client.post(reverse('start_checkout'), {'interval': 'month'})
        create.assert_not_called()
        self.assertRedirects(response, reverse('myaccount'), fetch_redirect_response=False)

    def test_webhook_grants_and_revokes_premium(self):
        def send(event_type, status):
            event = {'type': event_type, 'data': {'object': {'id': 'sub_1', 'customer': 'cus_1', 'status': status}}}
            with mock.patch('stripe.Webhook.construct_event', return_value=event):
                return self.client.post(reverse('stripe_webhook'), '{}', content_type='application/json',
                                        HTTP_STRIPE_SIGNATURE='sig')
        self.assertEqual(send('customer.subscription.created', 'active').status_code, 200)
        self.assertTrue(Profile.objects.get(user=self.user).is_premium)
        send('customer.subscription.deleted', 'canceled')
        profile = Profile.objects.get(user=self.user)
        self.assertFalse(profile.is_premium)
        self.assertEqual(profile.stripe_status, 'canceled')

    def test_premium_emails_sent_only_on_transitions(self):
        from django.core import mail
        def send(event_type, status):
            event = {'type': event_type, 'data': {'object': {'id': 'sub_1', 'customer': 'cus_1', 'status': status}}}
            with mock.patch('stripe.Webhook.construct_event', return_value=event):
                self.client.post(reverse('stripe_webhook'), '{}', content_type='application/json', HTTP_STRIPE_SIGNATURE='sig')
        mail.outbox.clear()
        send('customer.subscription.created', 'active')
        send('customer.subscription.updated', 'active')
        self.assertEqual([m.subject for m in mail.outbox], ['Welcome to FI Planner Premium'])
        self.assertIn('Premium', mail.outbox[0].body)
        self.assertNotIn('<', mail.outbox[0].body)
        send('customer.subscription.deleted', 'canceled')
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('ended', mail.outbox[1].subject)

    def test_payment_failed_email(self):
        from django.core import mail
        mail.outbox.clear()
        event = {'type': 'invoice.payment_failed', 'data': {'object': {'customer': 'cus_1'}}}
        with mock.patch('stripe.Webhook.construct_event', return_value=event):
            self.client.post(reverse('stripe_webhook'), '{}', content_type='application/json', HTTP_STRIPE_SIGNATURE='sig')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('payment', mail.outbox[0].subject.lower())

    def test_webhook_rejects_bad_signature(self):
        response = self.client.post(reverse('stripe_webhook'), '{}', content_type='application/json',
                                    HTTP_STRIPE_SIGNATURE='bad')
        self.assertEqual(response.status_code, 400)


class LegalAndEmailTemplateTests(TestCase):
    def test_legal_pages_and_footer_links(self):
        for name in ('privacy', 'terms'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        html = self.client.get(reverse('about')).content.decode()
        self.assertIn(reverse('privacy'), html)
        self.assertIn(reverse('terms'), html)

    def test_password_reset_email_is_branded_html(self):
        from django.core import mail
        User.objects.create_user('reset', 'reset@example.com', 'Str0ng-pass-99')
        self.client.post(reverse('password_reset'), {'email': 'reset@example.com'})
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertIn('FI Planner', message.subject)
        self.assertNotIn('FIRE Simulator', message.body)
        self.assertEqual(message.alternatives[0][1], 'text/html')
        self.assertIn('/password-reset/', message.alternatives[0][0])


class FaqFeedbackTests(TestCase):
    def test_faq_page_has_schema_and_footer_link(self):
        r = self.client.get('/faq/')
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('application/ld+json', html)
        self.assertIn('FAQPage', html)
        self.assertIn('href="/faq/"', self.client.get('/about/').content.decode())

    def test_share_preview_tags(self):
        html = self.client.get('/').content.decode()
        self.assertIn('property="og:image" content="', html)
        self.assertIn('og-image.png', html)
        self.assertIn('twitter:card" content="summary_large_image"', html)

    def test_robots_and_sitemap(self):
        self.assertIn('Sitemap:', self.client.get('/robots.txt').content.decode())
        self.assertIn('/faq/', self.client.get('/sitemap.xml').content.decode())

    def test_feedback_sends_email(self):
        from django.core import mail
        from .models import Feedback
        r = self.client.post('/feedback/', {'category': 'Bug Report', 'feedback': 'Broken', 'reply_email': 'a@b.com'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['hello@fiplanner.app'])

    def test_feedback_honeypot_and_invalid(self):
        from django.core import mail
        from .models import Feedback
        self.client.post('/feedback/', {'category': 'Bug Report', 'feedback': 'x', 'website': 'spam'})
        self.client.post('/feedback/', {'category': 'Nope', 'feedback': 'x'})
        self.assertEqual(Feedback.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_premium_copy_mentions_pdf(self):
        self.assertIn('PDF', self.client.get('/').content.decode())



class RenamePlanTests(TestCase):
    def test_rename_only_own_plan(self):
        u = User.objects.create_user('r1', 'r1@x.com', 'Passw0rd!x')
        o = User.objects.create_user('r2', 'r2@x.com', 'Passw0rd!x')
        p = Plan.objects.create(user=u, plan_name='Old', current_age=30, retirement_age=65)
        self.client.login(username='r2', password='Passw0rd!x')
        self.assertEqual(self.client.post(f'/renameplan/{p.id}', {'plan_name': 'X'}).status_code, 404)
        self.client.login(username='r1', password='Passw0rd!x')
        self.client.post(f'/renameplan/{p.id}', {'plan_name': ' New '})
        p.refresh_from_db()
        self.assertEqual(p.plan_name, 'New')



class RateLimitTests(TestCase):
    def test_login_is_rate_limited(self):
        from django.core.cache import cache
        cache.clear()
        with override_settings(RATELIMIT_ENABLED=True):
            codes = [self.client.post('/login/', {'email': 'a@b.com', 'password': 'x'}).status_code for _ in range(12)]
        cache.clear()
        self.assertEqual(codes[0], 200)
        self.assertEqual(codes[-1], 429)

class ClientIpTests(TestCase):
    def test_forwarded_ip_used_only_with_trusted_hops(self):
        from django.test import RequestFactory, override_settings
        from .ratelimit import _client_ip
        req = RequestFactory().get('/', HTTP_X_FORWARDED_FOR='6.6.6.6, 1.2.3.4', REMOTE_ADDR='10.0.0.1')
        with override_settings(TRUSTED_PROXY_HOPS=0):
            self.assertEqual(_client_ip(req), '10.0.0.1')
        with override_settings(TRUSTED_PROXY_HOPS=1):
            self.assertEqual(_client_ip(req), '1.2.3.4')


class CustomSavingsPremiumTests(TestCase):
    def custom_post(self):
        return survey_post(saving_option='Custom', saving_name=['Mine'], saving_category=['TBA'],
                           tba_current_value=['500'], tba_yearly_growth=['6'])

    def setUp(self):
        self.user = User.objects.create_user('cust', 'cust@example.com', 'pw-12345-xyz')
        self.client.force_login(self.user)

    def test_free_user_cannot_use_custom(self):
        self.assertEqual(self.client.get(reverse('savings-method'), {'saving_option': 'Custom'}).status_code, 200)
        page = self.client.get(reverse('savings-method'), {'saving_option': 'Custom'}).content.decode()
        self.assertIn('Premium feature', page)
        self.assertNotIn('id="saving-div"', page)
        response = self.client.post(reverse('newplan'), self.custom_post())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Plan.objects.count(), 0)

    def test_premium_user_can_use_custom(self):
        Profile.objects.update_or_create(user=self.user, defaults={'is_premium': True})
        page = self.client.get(reverse('savings-method'), {'saving_option': 'Custom'}).content.decode()
        self.assertIn('data-sortable', page)
        self.assertEqual(self.client.post(reverse('newplan'), self.custom_post()).status_code, 302)

    def test_recommended_is_fixed_order_and_not_sortable(self):
        page = self.client.get(reverse('savings-method'), {'saving_option': 'Recommended'}).content.decode()
        self.assertNotIn('data-sortable', page)
        post = survey_post(saving_option='Recommended', saving_name=['T', 'E'], saving_category=['TBA', 'ESRP'],
                           tba_current_value=['1'], tba_yearly_growth=['6'], esrp_current_value=['1'],
                           esrp_yearly_growth=['6'], esrp_contribution_rate=['3'], esrp_contribution_limit=['23000'],
                           esrp_contribution_limit_step=['500'])
        self.assertEqual(self.client.post(reverse('newplan'), post).status_code, 302)
        saved = Plan.objects.latest('created_at').savings
        self.assertEqual([s['saving_category'] for s in saved[1:]], ['ESRP', 'TBA'])

    def test_favicon_linked(self):
        self.assertIn('rel="icon"', self.client.get('/').content.decode())
        self.assertEqual(self.client.get('/favicon.ico').status_code, 301)


class AnonymousLiveTableTests(TestCase):
    def test_anonymous_entries_include_live_table_hooks(self):
        page = self.client.get(reverse('income-fields'), {'income_category': 'Salary', 'min_age': 30, 'max_age': 40, 'salary_count': 0}).content.decode()
        self.assertIn('hx-get="/', page)
        self.assertIn('income-table', page)
        table = self.client.get(reverse('income-table'), {
            'income_category': 'Salary', 'min_age': 30, 'max_age': 35, 'starting_amount': 75000, 'yearly_change': 3,
            'bonus_rate': 1, 'tax_rate': 15, 'tax_rate_change': 0, 'start_age': 30, 'stop_age': 34})
        self.assertEqual(table.status_code, 200)
        self.assertIn('<table', table.content.decode())


class AnonymousTrialTests(TestCase):
    def setUp(self):
        self.client.post(reverse('newplan'), survey_post())
        self.plan = Plan.objects.latest('created_at')

    def test_anonymous_can_create_and_view_plan(self):
        self.assertIsNone(self.plan.user)
        page = self.client.get(reverse('runplan', args=[self.plan.id]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Sign-up to gain access')

    def test_anonymous_cannot_edit_plan(self):
        before = self.plan.retirement_age
        response = self.client.post(reverse('runplan', args=[self.plan.id]), survey_post(retirement_age='40'))
        self.assertRedirects(response, reverse('signupsave', args=[self.plan.id]), fetch_redirect_response=False)
        self.plan.refresh_from_db()
        self.assertEqual(self.plan.retirement_age, before)
        htmx = self.client.post(reverse('runplan', args=[self.plan.id]), survey_post(retirement_age='40'), HTTP_HX_REQUEST='true')
        self.assertEqual(htmx['HX-Redirect'], reverse('signupsave', args=[self.plan.id]))

    def test_anonymous_cannot_download_or_copy(self):
        for name in ('downloadplan', 'downloadpdf', 'copyplan'):
            response = self.client.get(reverse(name, args=[self.plan.id]))
            self.assertEqual(response.status_code, 302, name)
            self.assertNotIn('csv', response.get('Content-Type', ''), name)

    def test_signup_claims_the_plan(self):
        response = self.client.post(reverse('signupsave', args=[self.plan.id]), {
            'email': 'new@example.com', 'first_name': 'New', 'password1': 'Str0ng!Pass99', 'password2': 'Str0ng!Pass99',
            'terms': 'on'})
        self.assertEqual(response.status_code, 302)
        self.plan.refresh_from_db()
        self.assertIsNotNone(self.plan.user)
