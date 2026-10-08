"""Read-only viewer user seed — safe aur re-runnable (upsert).

Usage:
    .venv/bin/python manage.py create_viewer
    .venv/bin/python manage.py create_viewer --username Raj --password 0707

Dobara chalane par duplicate NAHI banta — same user update hota hai.
Password hamesha hashed store hota hai (Django ka default hasher).
Password-strength validators yahan apply nahi hote (sirf forms par hote
hain), isliye chhota password sirf isi command se banta hai — global
rules bilkul unchanged rehte hain.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from authentication.permissions import VIEWER_GROUP_NAME, get_viewer_group


class Command(BaseCommand):
    help = 'Create/update a read-only viewer user (default Raj / 0707).'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='Raj')
        parser.add_argument('--password', default='0707')

    def handle(self, *args, **options):
        username = (options['username'] or '').strip()
        password = options['password'] or ''
        if not username or not password:
            self.stderr.write('Username aur password dono chahiye.')
            return

        User = get_user_model()
        user, created = User.objects.update_or_create(
            username=username,
            defaults={
                'is_active': True,
                'is_staff': False,
                'is_superuser': False,
            },
        )
        user.set_password(password)  # hashed, kabhi plain text nahi
        user.save()
        user.groups.add(get_viewer_group())

        action = 'banaya gaya' if created else 'update ho gaya'
        self.stdout.write(
            self.style.SUCCESS(
                f'Viewer "{user.username}" {action} '
                f'(role={VIEWER_GROUP_NAME}, read-only).'
            )
        )
