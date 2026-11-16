"""Email verification tokens and Google sign-in (OAuth 2.0 authorization-code flow)."""
import json
import re
import secrets
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib.auth.models import User
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags

VERIFY_SALT = 'fire.email-verification'
VERIFY_MAX_AGE = 60 * 60 * 24 * 3

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://openidconnect.googleapis.com/v1/userinfo'


def site_url():
    return getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')


def make_verification_token(user):
    # The email is part of the payload so changing it invalidates older links
    return signing.dumps({'uid': user.pk, 'email': user.email.lower()}, salt=VERIFY_SALT)


def read_verification_token(token):
    """Return the matching user, or None if the token is bad, expired or stale."""
    try:
        payload = signing.loads(token, salt=VERIFY_SALT, max_age=VERIFY_MAX_AGE)
        user = User.objects.get(pk=payload['uid'])
    except (signing.BadSignature, User.DoesNotExist, KeyError, TypeError):
        return None
    return user if user.email.lower() == payload.get('email') else None


def send_verification_email(user):
    if not user.email:
        return False
    context = {
        'user': user,
        'verify_url': site_url() + reverse('verify_email', args=[make_verification_token(user)]),
    }
    html = render_to_string('emails/verify_email.html', context)
    try:
        message = EmailMultiAlternatives('Confirm your FI Planner email', strip_tags(html), settings.DEFAULT_FROM_EMAIL, [user.email])
        message.attach_alternative(html, 'text/html')
        message.send()
    except Exception as e:
        print(e)
        return False
    return True


def google_enabled():
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def google_redirect_uri():
    return site_url() + reverse('google_callback')


def google_authorize_url(state):
    return GOOGLE_AUTH_URL + '?' + urllib.parse.urlencode({
        'client_id': settings.GOOGLE_CLIENT_ID,
        'redirect_uri': google_redirect_uri(),
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'prompt': 'select_account',
    })


def new_state():
    return secrets.token_urlsafe(32)


def _post(url, data):
    request = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), method='POST')
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


def fetch_google_profile(code):
    """Exchange an authorization code for the signed-in Google user's profile, or None on any failure."""
    try:
        token = _post(GOOGLE_TOKEN_URL, {
            'code': code,
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'redirect_uri': google_redirect_uri(),
            'grant_type': 'authorization_code',
        })
        request = urllib.request.Request(GOOGLE_USERINFO_URL, headers={'Authorization': 'Bearer ' + token['access_token']})
        with urllib.request.urlopen(request, timeout=10) as response:
            profile = json.load(response)
    except Exception as e:
        print(f"Google sign-in failed: {e}")
        return None
    if not profile.get('email') or profile.get('email_verified') is not True:
        return None
    return profile


def unique_username(email):
    base = re.sub(r'[^\w.@+-]', '', email.split('@')[0])[:130] or 'user'
    name, n = base, 1
    while User.objects.filter(username__iexact=name).exists():
        n += 1
        name = f"{base}{n}"
    return name
