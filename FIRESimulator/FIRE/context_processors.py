import os

from django.conf import settings

from .models import Profile, user_is_premium

_CSS_PATH = os.path.join(os.path.dirname(__file__), 'static', 'main.css')


def _css_version():
    try:
        return int(os.path.getmtime(_CSS_PATH))
    except OSError:
        return 0


def premium(request):
    user = request.user
    unverified = False
    if user.is_authenticated and user.email:
        unverified = not Profile.objects.filter(user=user, email_verified=True).exists()
    return {
        'css_version': _css_version(),
        'site_url': settings.SITE_URL.rstrip('/'),
        'is_premium': user_is_premium(user),
        'free_plan_limit': settings.FREE_PLAN_LIMIT,
        'email_unverified': unverified,
        'google_enabled': bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
    }
