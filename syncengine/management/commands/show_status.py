"""
Django management command to show sync status
"""
from django.core.management.base import BaseCommand
from syncengine.models import SyncRecord, SyncLog, ConflictRecord


class Command(BaseCommand):
    help = 'Show sync status and statistics'

    def handle(self, *args, **options):
        self.stdout.write('Sync Status\n')

        # Total sync records
        total_records = SyncRecord.objects.count()
        synced = SyncRecord.objects.filter(sync_status='synced').count()
        errors = SyncRecord.objects.filter(sync_status='error').count()
        conflicts = SyncRecord.objects.filter(sync_status='conflict').count()

        self.stdout.write(f'Total Documents Tracked: {total_records}')
        self.stdout.write(self.style.SUCCESS(f'  Synced: {synced}'))
        self.stdout.write(self.style.ERROR(f'  Errors: {errors}'))
        self.stdout.write(self.style.WARNING(f'  Conflicts: {conflicts}'))

        # Recent sync logs
        self.stdout.write('\nRecent Sync Operations:')
        recent_logs = SyncLog.objects.order_by('-timestamp')[:10]

        for log in recent_logs:
            time_str = log.timestamp.strftime('%H:%M:%S')
            status_str = log.status.upper()

            if log.status == 'success':
                status_display = self.style.SUCCESS(status_str)
            else:
                status_display = self.style.ERROR(status_str)

            self.stdout.write(
                f'  [{time_str}] {status_display} - '
                f'{log.doctype}/{log.docname} ({log.direction})'
            )

        # Unresolved conflicts
        unresolved = ConflictRecord.objects.filter(resolved=False).count()
        if unresolved > 0:
            self.stdout.write(
                self.style.WARNING(f'\nWARNING: Unresolved Conflicts: {unresolved}')
            )
