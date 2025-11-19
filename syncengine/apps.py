"""
Django app configuration for syncengine
"""
from django.apps import AppConfig


class SyncengineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'syncengine'
    verbose_name = 'ERP Sync Engine'

    def ready(self):
        """Initialize app when Django starts"""
        # Import signals if needed
        pass
