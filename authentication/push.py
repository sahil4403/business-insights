"""Web Push (VAPID) sending — free browser notifications, no Firebase needed.

Keys come from .env (VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY / VAPID_CLAIM_SUB).
Sends never raise: dead endpoints (410/404) are deleted, other errors logged.
"""

import json
import logging
import os

logger = logging.getLogger('trips')


def _vapid_config():
    return {
        'private_key': os.getenv('VAPID_PRIVATE_KEY', ''),
        'claims': {'sub': os.getenv('VAPID_CLAIM_SUB', 'mailto:admin@localhost')},
    }


def send_push_to_subscription(sub, title, body, url='/'):
    """Send one push. Returns True if delivered (or attempted); False if skipped."""
    from pywebpush import webpush, WebPushException

    cfg = _vapid_config()
    if not cfg['private_key']:
        logger.warning('Push skipped — VAPID_PRIVATE_KEY missing in .env')
        return False
    payload = json.dumps({'title': title, 'body': body, 'url': url})
    try:
        webpush(
            subscription_info=sub.subscription_info,
            data=payload,
            vapid_private_key=cfg['private_key'],
            vapid_claims=cfg['claims'],
            ttl=86400,
        )
        return True
    except WebPushException as e:
        status = getattr(e.response, 'status_code', None) if getattr(e, 'response', None) else None
        if status in (404, 410):
            logger.info('Push endpoint dead, deleting sub id=%s', sub.pk)
            sub.delete()
        else:
            logger.warning('Push failed for sub id=%s: %s', sub.pk, e)
        return False
    except Exception as e:  # network down etc — never break the request
        logger.warning('Push error for sub id=%s: %s', sub.pk, e)
        return False


def notify_users(users, title, body, url='/'):
    """Notify every subscribed user in the queryset. Returns delivered count."""
    from .models import PushSubscription

    sent = 0
    for sub in PushSubscription.objects.filter(user__in=users):
        if send_push_to_subscription(sub, title, body, url=url):
            sent += 1
    return sent


def notify_superusers(title, body, url='/', exclude_user=None):
    """Notify all superusers (admins) except the actor. Returns delivered count."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    qs = User.objects.filter(is_superuser=True, is_active=True)
    if exclude_user is not None:
        qs = qs.exclude(pk=exclude_user.pk)
    return notify_users(qs, title, body, url=url)
