"""Viewer (read-only) role helper.

Role storage: plain Django Group named "Viewer" — zero schema change.
Existing users is group me nahi hain, isliye unka behavior 100% unchanged.
Superuser hamesha full power rakhta hai, chahe group me ho ya na ho.
"""

from django.contrib.auth.models import Group

VIEWER_GROUP_NAME = 'Viewer'


def get_viewer_group():
    group, _ = Group.objects.get_or_create(name=VIEWER_GROUP_NAME)
    return group


def is_viewer(user):
    """True sirf read-only viewer ke liye (Raj jaisa user)."""
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_superuser', False):
        return False
    return user.groups.filter(name=VIEWER_GROUP_NAME).exists()
