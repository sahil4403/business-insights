from django.contrib import admin

from core.models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'user',
        'action',
        'model_name',
        'object_repr',
        'ip_address',
    )
    list_filter = ('action', 'model_name')
    search_fields = ('object_repr', 'details', 'user__username')
    readonly_fields = [f.name for f in AuditLog._meta.fields]
