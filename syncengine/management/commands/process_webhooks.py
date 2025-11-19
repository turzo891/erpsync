"""
Django management command to process webhook queue
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from frappe_client import FrappeClient
from sync_engine import SyncEngine
from syncengine.models import WebhookQueue


class Command(BaseCommand):
    help = 'Process webhook queue (background worker)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--once',
            action='store_true',
            help='Process queue once and exit (instead of continuous loop)',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=2,
            help='Sleep interval between queue checks (seconds)',
        )

    def handle(self, *args, **options):
        self.stdout.write('Webhook queue processor started\n')

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

        run_once = options['once']
        interval = options['interval']

        while True:
            try:
                # Get unprocessed webhooks
                webhooks = WebhookQueue.objects.filter(
                    processed=False,
                    processing=False
                ).order_by('created_at')[:10]

                for webhook in webhooks:
                    # Mark as processing
                    webhook.processing = True
                    webhook.save()

                    try:
                        # Determine sync direction based on source
                        if webhook.source == 'cloud':
                            direction = 'cloud_to_local'
                        elif webhook.source == 'local':
                            direction = 'local_to_cloud'
                        else:
                            raise ValueError(f"Unknown webhook source: {webhook.source}")

                        # Sync the document
                        self.stdout.write(
                            f"PROCESSING: Processing: {webhook.doctype}/{webhook.docname} ({direction})"
                        )

                        success, message = engine.sync_document(
                            webhook.doctype,
                            webhook.docname,
                            direction=direction
                        )

                        # Mark as processed
                        webhook.processed = True
                        webhook.processing = False
                        webhook.processed_at = timezone.now()

                        if not success:
                            webhook.error_message = message
                            webhook.retry_count += 1
                            self.stdout.write(self.style.ERROR(f"  [FAIL] Failed: {message}"))
                        else:
                            self.stdout.write(self.style.SUCCESS(f"  [OK] Success: {message}"))

                        webhook.save()

                    except Exception as e:
                        webhook.processing = False
                        webhook.error_message = str(e)
                        webhook.retry_count += 1
                        webhook.save()
                        self.stdout.write(self.style.ERROR(f"  [FAIL] Error processing webhook: {e}"))

                if run_once:
                    break

                # Sleep before next iteration
                time.sleep(interval)

            except KeyboardInterrupt:
                self.stdout.write('\nShutting down webhook processor...')
                break
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error in webhook processor: {e}"))
                time.sleep(5)
