from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User


class CaseInsensitiveModelBackend(ModelBackend):
    """
    Foolproof authentication backend supporting case-insensitive username lookup
    and automatic whitespace stripping.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        username = username.strip()

        # 1. Try exact username match first
        user = User.objects.filter(username=username).first()

        # 2. If not found, try case-insensitive match
        if not user:
            user = User.objects.filter(username__iexact=username).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None
