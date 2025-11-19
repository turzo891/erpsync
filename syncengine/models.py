"""
Django models for ERP sync state tracking
"""
from django.db import models
from django.utils import timezone


class SyncRecord(models.Model):
    """Track sync state for each document"""

    doctype = models.CharField(max_length=200, db_index=True)
    docname = models.CharField(max_length=200, db_index=True)

    # Timestamps
    cloud_modified = models.DateTimeField(null=True, blank=True)
    local_modified = models.DateTimeField(null=True, blank=True)
    last_synced = models.DateTimeField(null=True, blank=True)

    # Sync metadata
    sync_hash_cloud = models.CharField(max_length=64, null=True, blank=True)
    sync_hash_local = models.CharField(max_length=64, null=True, blank=True)
    sync_direction = models.CharField(max_length=20, null=True, blank=True)

    # Status
    is_syncing = models.BooleanField(default=False)
    sync_status = models.CharField(max_length=50, default='pending')
    error_message = models.TextField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sync_records'
        indexes = [
            models.Index(fields=['doctype', 'docname']),
            models.Index(fields=['sync_status']),
        ]
        unique_together = ['doctype', 'docname']

    def __str__(self):
        return f"{self.doctype}/{self.docname} - {self.sync_status}"


class SyncLog(models.Model):
    """Audit log for all sync operations"""

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    doctype = models.CharField(max_length=200)
    docname = models.CharField(max_length=200)

    action = models.CharField(max_length=50)  # create, update, delete
    direction = models.CharField(max_length=20)  # cloud_to_local, local_to_cloud

    status = models.CharField(max_length=50, db_index=True)  # success, failed, conflict
    message = models.TextField(null=True, blank=True)

    # Store change details (optional)
    changes_json = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'sync_logs'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.timestamp} - {self.doctype}/{self.docname} - {self.status}"


class ConflictRecord(models.Model):
    """Track conflicts that need manual resolution"""

    doctype = models.CharField(max_length=200)
    docname = models.CharField(max_length=200)

    cloud_data = models.TextField()  # JSON string
    local_data = models.TextField()  # JSON string

    cloud_modified = models.DateTimeField()
    local_modified = models.DateTimeField()

    resolved = models.BooleanField(default=False)
    resolution = models.CharField(max_length=50, null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'conflict_records'
        ordering = ['-created_at']

    def __str__(self):
        status = "Resolved" if self.resolved else "Unresolved"
        return f"{self.doctype}/{self.docname} - {status}"


class WebhookQueue(models.Model):
    """Queue for webhook events to process"""

    source = models.CharField(max_length=20)  # 'cloud' or 'local'

    doctype = models.CharField(max_length=200)
    docname = models.CharField(max_length=200)
    action = models.CharField(max_length=50)  # create, update, delete

    payload = models.TextField()  # JSON string

    processed = models.BooleanField(default=False, db_index=True)
    processing = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    error_message = models.TextField(null=True, blank=True)
    retry_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'webhook_queue'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['processed', 'processing']),
        ]

    def __str__(self):
        status = "Processed" if self.processed else "Pending"
        return f"{self.source} - {self.doctype}/{self.docname} - {status}"
