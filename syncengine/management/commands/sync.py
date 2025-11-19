"""
Django management command to run synchronization
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from frappe_client import FrappeClient
from sync_engine import SyncEngine


class Command(BaseCommand):
    help = 'Run synchronization between ERPs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--doctype',
            type=str,
            help='Specific DocType to sync',
        )
        parser.add_argument(
            '--docname',
            type=str,
            help='Specific document name to sync',
        )
        parser.add_argument(
            '--direction',
            type=str,
            default='auto',
            choices=['auto', 'cloud_to_local', 'local_to_cloud'],
            help='Sync direction',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=100,
            help='Max documents to sync per DocType',
        )

    def handle(self, *args, **options):
        self.stdout.write('\nStarting synchronization...\n')

        # Initialize clients
        cloud = FrappeClient(
            url=settings.CLOUD_ERP_URL,
            api_key=settings.CLOUD_API_KEY,
            api_secret=settings.CLOUD_API_SECRET,
            instance_name='Cloud'
        )

        local = FrappeClient(
            url=settings.LOCAL_ERP_URL,
            api_key=settings.LOCAL_API_KEY,
            api_secret=settings.LOCAL_API_SECRET,
            instance_name='Local'
        )

        # Initialize sync engine
        engine = SyncEngine(cloud, local)

        # Sync specific document or all
        if options['doctype'] and options['docname']:
            self.stdout.write(f"Syncing {options['doctype']}/{options['docname']}...")
            success, message = engine.sync_document(
                options['doctype'],
                options['docname'],
                options['direction']
            )

            if success:
                self.stdout.write(self.style.SUCCESS(f'[OK] {message}'))
            else:
                self.stdout.write(self.style.ERROR(f'[FAIL] {message}'))

        elif options['doctype']:
            self.stdout.write(f"Syncing all {options['doctype']} documents...")
            stats = engine.sync_doctype(options['doctype'], limit=options['limit'])
            self._print_stats(stats)

        else:
            self.stdout.write("Syncing all configured DocTypes...")
            stats = engine.sync_all_doctypes(limit=options['limit'])
            self._print_stats(stats)

    def _print_stats(self, stats):
        """Print sync statistics"""
        self.stdout.write('\nSync Statistics:')
        self.stdout.write(f"  Total: {stats['total']}")
        self.stdout.write(self.style.SUCCESS(f"  Success: {stats['success']}"))
        self.stdout.write(f"  Skipped: {stats['skipped']}")
        self.stdout.write(self.style.WARNING(f"  Conflicts: {stats['conflicts']}"))
        self.stdout.write(self.style.ERROR(f"  Failed: {stats['failed']}"))
