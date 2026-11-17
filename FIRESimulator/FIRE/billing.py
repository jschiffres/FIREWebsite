"""Stripe Checkout, Customer Portal and subscription syncing."""
import stripe
from django.conf import settings
from django.utils import timezone

from .models import Profile

ACTIVE_STATUSES = {'active', 'trialing'}


def _client():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _plain(obj):
    """Stripe objects aren't dicts in newer SDKs; convert to plain dicts."""
    return obj.to_dict() if hasattr(obj, 'to_dict') else obj


def resolve_price_id(interval):
    """Return the price ID for 'month' or 'year', looking it up from the product if needed."""
    direct = settings.STRIPE_YEARLY_PRICE_ID if interval == 'year' else settings.STRIPE_MONTHLY_PRICE_ID
    if direct:
        return direct
    product_id = settings.STRIPE_YEARLY_PRODUCT_ID if interval == 'year' else settings.STRIPE_MONTHLY_PRODUCT_ID
    if not product_id:
        return None
    product = _plain(_client().Product.retrieve(product_id))
    default_price = product.get('default_price')
    if default_price:
        return default_price if isinstance(default_price, str) else default_price['id']
    prices = _plain(_client().Price.list(product=product_id, active=True, type='recurring', limit=1))
    return prices['data'][0]['id'] if prices['data'] else None


def available_intervals():
    intervals = []
    if settings.STRIPE_MONTHLY_PRICE_ID or settings.STRIPE_MONTHLY_PRODUCT_ID:
        intervals.append('month')
    if settings.STRIPE_YEARLY_PRICE_ID or settings.STRIPE_YEARLY_PRODUCT_ID:
        intervals.append('year')
    return intervals


def get_or_create_customer(profile):
    if profile.stripe_customer_id:
        return profile.stripe_customer_id
    user = profile.user
    customer = _client().Customer.create(email=user.email, metadata={'user_id': str(user.pk)})
    profile.stripe_customer_id = customer['id']
    profile.save(update_fields=['stripe_customer_id'])
    return customer['id']


def create_checkout_url(profile, interval):
    price_id = resolve_price_id(interval)
    if not price_id:
        return None
    site = settings.SITE_URL.rstrip('/')
    session = _client().checkout.Session.create(
        mode='subscription',
        customer=get_or_create_customer(profile),
        client_reference_id=str(profile.user_id),
        line_items=[{'price': price_id, 'quantity': 1}],
        allow_promotion_codes=True,
        success_url=f'{site}/account/?checkout=success',
        cancel_url=f'{site}/account/?checkout=cancelled',
    )
    return session['url']


def create_portal_url(profile):
    site = settings.SITE_URL.rstrip('/')
    session = _client().billing_portal.Session.create(
        customer=profile.stripe_customer_id, return_url=f'{site}/account/',
    )
    return session['url']


def sync_subscription(subscription):
    """Apply a Stripe subscription object to the matching profile."""
    customer_id = subscription['customer']
    profile = Profile.objects.filter(stripe_customer_id=customer_id).first()
    if profile is None:
        return None
    status = subscription['status']
    profile.stripe_subscription_id = subscription['id']
    profile.stripe_status = status
    should_be_premium = status in ACTIVE_STATUSES
    was_premium = profile.is_premium
    if should_be_premium and not profile.is_premium:
        profile.is_premium = True
        profile.premium_since = timezone.now()
    elif not should_be_premium and profile.is_premium:
        profile.is_premium = False
        profile.premium_since = None
    changed = profile.is_premium != was_premium
    profile.save()
    if changed:
        from . import emails
        (emails.premium_welcome_email if profile.is_premium else emails.premium_ended_email)(profile.user)
    return profile


def handle_event(event):
    kind = event['type']
    obj = _plain(event['data']['object'])
    if kind == 'checkout.session.completed':
        if obj.get('mode') != 'subscription':
            return
        profile = Profile.objects.filter(user_id=obj.get('client_reference_id') or 0).first()
        if profile and obj.get('customer') and not profile.stripe_customer_id:
            profile.stripe_customer_id = obj['customer']
            profile.save(update_fields=['stripe_customer_id'])
        if obj.get('subscription'):
            sync_subscription(_plain(_client().Subscription.retrieve(obj['subscription'])))
    elif kind in ('customer.subscription.created', 'customer.subscription.updated', 'customer.subscription.deleted'):
        sync_subscription(obj)
    elif kind == 'invoice.payment_failed':
        profile = Profile.objects.filter(stripe_customer_id=obj.get('customer')).first()
        if profile:
            from . import emails
            emails.payment_failed_email(profile.user)
