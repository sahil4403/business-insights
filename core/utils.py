from urllib.parse import urlparse

from django.utils.http import url_has_allowed_host_and_scheme


def get_safe_next(request, default):
    """
    Returns a safe internal redirect target from the 'next' parameter.
    External/hostile URLs are ignored and the default is returned instead.
    """
    raw_next = (
        request.GET.get('next')
        or request.POST.get('next')
        or ''
    ).strip()

    if raw_next and url_has_allowed_host_and_scheme(
        raw_next,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return raw_next

    return default


def get_safe_next_or_referer(request, default):
    """
    Like get_safe_next, but falls back to a validated HTTP_REFERER
    before using the supplied default.
    """
    safe_next = get_safe_next(request, '')
    if safe_next:
        return safe_next

    referer = request.META.get('HTTP_REFERER', '')
    if referer and url_has_allowed_host_and_scheme(
        referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return referer

    return default


# Form/action pages jahan wapas jaana Back-loop banata hai
# (e.g. payment form se Cancel karke trip par aao, phir Back dabao).
_ACTION_PATH_BITS = (
    '/add/',
    '/edit/',
    '/delete/',
    '/remove/',
    '/payment/',
    'record-payment',
    'link-customer',
    '/settle',
    '/revert',
    '/outstanding/',
)


def get_safe_back_url(request, default):
    """
    Back-button target: explicit ?next= > safe referer > default.
    Referer ko ignore karo agar wo form/action page ho — warna Back
    usi form par wapas bhejkar loop bana deta hai.
    """
    safe_next = get_safe_next(request, '')
    if safe_next:
        return safe_next

    referer = request.META.get('HTTP_REFERER', '')
    if referer and url_has_allowed_host_and_scheme(
        referer,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        path = urlparse(referer).path
        if not any(bit in path for bit in _ACTION_PATH_BITS):
            return referer

    return default
