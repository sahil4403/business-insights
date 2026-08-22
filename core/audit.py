"""Tiny audit helper — money-related mutations get recorded.

Audit must NEVER break the business flow, so every failure is swallowed.
"""

import logging

logger = logging.getLogger(__name__)


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip() or None
    return request.META.get('REMOTE_ADDR') or None


def log_action(request, action, obj=None, model_name='', object_repr='', details=''):
    try:
        from core.models import AuditLog

        user = getattr(request, 'user', None)
        if user is not None and not user.is_authenticated:
            user = None

        if obj is not None:
            model_name = model_name or obj.__class__.__name__
            object_repr = object_repr or str(obj)[:200]

        AuditLog.objects.create(
            user=user,
            action=action,
            model_name=model_name,
            object_repr=object_repr,
            details=details or '',
            ip_address=_client_ip(request),
        )
    except Exception:
        logger.exception('audit log failed for action=%s', action)
