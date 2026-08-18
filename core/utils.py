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
