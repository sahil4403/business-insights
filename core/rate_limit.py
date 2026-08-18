import time

from django.core.cache import cache

MAX_ATTEMPTS = 10
WINDOW_SECONDS = 900


def get_client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '') or 'unknown'


def _key(prefix, request):
    return f'login_rate_limit:{prefix}:{get_client_ip(request)}'


def login_rate_limit_check(request, prefix):
    """
    Returns (allowed, retry_after_seconds).
    Only counts POST attempts; GET requests are never blocked.
    """
    if request.method != 'POST':
        return True, 0

    data = cache.get(_key(prefix, request))
    if data:
        attempts, first_attempt_at = data
        if attempts >= MAX_ATTEMPTS:
            elapsed = int(time.time() - first_attempt_at)
            return False, max(1, WINDOW_SECONDS - elapsed)

    return True, 0


def record_login_failure(request, prefix):
    key = _key(prefix, request)
    data = cache.get(key)
    if data:
        attempts, first_attempt_at = data
        cache.set(key, (attempts + 1, first_attempt_at), WINDOW_SECONDS)
    else:
        cache.set(key, (1, time.time()), WINDOW_SECONDS)


def clear_login_rate_limit(request, prefix):
    cache.delete(_key(prefix, request))
