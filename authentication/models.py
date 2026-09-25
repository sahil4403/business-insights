from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    """Browser push subscription (Web Push / VAPID) for a user.

    One row per (user, endpoint) — same phone + same browser = one row.
    Rows whose endpoint dies (410/404 from push service) are deleted.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_subscriptions',
    )
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} · {self.endpoint[:60]}…"

    @property
    def subscription_info(self):
        return {
            'endpoint': self.endpoint,
            'keys': {'p256dh': self.p256dh, 'auth': self.auth},
        }
