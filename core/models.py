from django.db import models
from django.contrib.auth.models import User


class AuditLog(models.Model):
    """Who changed what money-related record, and when."""

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=60, db_index=True)
    model_name = models.CharField(max_length=60, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} | {self.model_name} | {self.object_repr}"
