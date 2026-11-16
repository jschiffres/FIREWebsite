from django.conf import settings

from .models import Profile, user_is_premium


def premium(request):
    user = request.user
    unverified = False
    if user.is_authenticated and user.email:
        unverified = not Profile.objects.filter(user=user, email_verified=True).exists()
    return {
        'is_premium': user_is_premium(user),
        'free_plan_limit': settings.FREE_PLAN_LIMIT,
        'email_unverified': unverified,
        'google_enabled': bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
    }
