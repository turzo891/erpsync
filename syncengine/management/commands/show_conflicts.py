"""
Django management command to show conflicts
"""
from django.core.management.base import BaseCommand
from syncengine.models import ConflictRecord


class Command(BaseCommand):
    help = 'Show unresolved conflicts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Show all conflicts including resolved ones',
        )

    def handle(self, *args, **options):
        if options['all']:
            conflicts = ConflictRecord.objects.all().order_by('-created_at')
            self.stdout.write('All Conflicts:\n')
        else:
            conflicts = ConflictRecord.objects.filter(resolved=False).order_by('-created_at')
            self.stdout.write('Unresolved Conflicts:\n')

        if not conflicts:
            self.stdout.write(self.style.SUCCESS('No conflicts found'))
            return

        self.stdout.write(f'Total: {conflicts.count()}\n')

        for i, conflict in enumerate(conflicts, 1):
            status = "Resolved" if conflict.resolved else "Unresolved"
            style = self.style.SUCCESS if conflict.resolved else self.style.WARNING

            self.stdout.write(style(f'{i}. {conflict.doctype}/{conflict.docname} - {status}'))
            self.stdout.write(f'   Cloud modified: {conflict.cloud_modified}')
            self.stdout.write(f'   Local modified: {conflict.local_modified}')

            if conflict.resolved:
                self.stdout.write(f'   Resolution: {conflict.resolution} at {conflict.resolved_at}')

            self.stdout.write('')
