from django.conf import settings

from .models import user_is_premium


def premium(request):
    return {'is_premium': user_is_premium(request.user), 'free_plan_limit': settings.FREE_PLAN_LIMIT}
