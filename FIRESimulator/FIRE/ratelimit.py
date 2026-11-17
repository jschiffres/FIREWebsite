import functools

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse


def _client_ip(request):
    """Client IP, reading X-Forwarded-For only from the configured number of trusted proxies."""
    hops = getattr(settings, 'TRUSTED_PROXY_HOPS', 0)
    forwarded = [p.strip() for p in request.META.get('HTTP_X_FORWARDED_FOR', '').split(',') if p.strip()]
    if hops and len(forwarded) >= hops:
        return forwarded[-hops]
    return request.META.get('REMOTE_ADDR', 'unknown')


def ratelimit(name, limit, window, methods=('POST',)):
    """Allow ``limit`` requests per ``window`` seconds per client IP.

    Uses the Django cache. The default per-process cache is fine for one server;
    configure a shared cache (Redis, database) when running several workers.
    """
    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if not getattr(settings, 'RATELIMIT_ENABLED', True) or request.method not in methods:
                return view(request, *args, **kwargs)
            key = f'rl:{name}:{_client_ip(request)}'
            cache.add(key, 0, window)
            try:
                count = cache.incr(key)
            except ValueError:
                cache.set(key, 1, window)
                count = 1
            if count > limit:
                response = HttpResponse('Too many attempts. Please wait a few minutes and try again.',
                                        status=429, content_type='text/plain')
                response['Retry-After'] = str(window)
                return response
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
