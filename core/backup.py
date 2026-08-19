import os
import sqlite3
from datetime import date

from django.conf import settings


def run_auto_backup():
    import sys
    print("BACKUP_DEBUG engine:", getattr(settings, 'DB_ENGINE', 'mysql'), flush=True)
    if getattr(settings, 'DB_ENGINE', 'mysql') != 'sqlite':
        return

    db_path = (
        settings.DATABASES['default']
        .get('NAME')
    )

    if not db_path or not os.path.exists(str(db_path)):
        return

    backup_dir = os.path.expanduser('~/backups')

    os.makedirs(backup_dir, exist_ok=True)

    today = date.today().strftime('%Y%m%d')

    dest_path = os.path.join(
        backup_dir,
        f'db_{today}.sqlite3'
    )

    if os.path.exists(dest_path):
        return

    try:
        source = sqlite3.connect(str(db_path))
        dest = sqlite3.connect(dest_path)

        with dest:
            source.backup(dest)

        dest.close()
        source.close()
    except Exception:
        return

    backups = sorted(
        f
        for f in os.listdir(backup_dir)
        if f.startswith('db_') and f.endswith('.sqlite3')
    )

    for old in backups[:-30]:
        try:
            os.remove(
                os.path.join(backup_dir, old)
            )
        except OSError:
            pass


class AutoBackupMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)

        if response.status_code < 500:
            run_auto_backup()

        return response