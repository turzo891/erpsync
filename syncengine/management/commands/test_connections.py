"""
Django management command to test ERP connections
"""
from django.core.management.base import BaseCommand
from django.conf import settings
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from frappe_client import FrappeClient


class Command(BaseCommand):
    help = 'Test connections to both ERP systems'

    def handle(self, *args, **options):
        self.stdout.write('\nTesting connections...\n')

        # Test cloud connection
        cloud = FrappeClient(
            url=settings.CLOUD_ERP_URL,
            api_key=settings.CLOUD_API_KEY,
            api_secret=settings.CLOUD_API_SECRET,
            instance_name='Cloud'
        )

        # Test local connection
        local = FrappeClient(
            url=settings.LOCAL_ERP_URL,
            api_key=settings.LOCAL_API_KEY,
            api_secret=settings.LOCAL_API_SECRET,
            instance_name='Local'
        )

        cloud_ok = cloud.test_connection()
        local_ok = local.test_connection()

        if cloud_ok and local_ok:
            self.stdout.write(self.style.SUCCESS('\n[OK] All connections successful'))
            return
        else:
            self.stdout.write(self.style.ERROR('\n[FAIL] Connection test failed'))
            sys.exit(1)
