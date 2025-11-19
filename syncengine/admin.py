"""
Django admin configuration for ERP Sync models
"""
from django.contrib import admin
from .models import SyncRecord, SyncLog, ConflictRecord, WebhookQueue


@admin.register(SyncRecord)
class SyncRecordAdmin(admin.ModelAdmin):
    list_display = ['doctype', 'docname', 'sync_status', 'last_synced', 'retry_count']
    list_filter = ['sync_status', 'doctype', 'is_syncing']
    search_fields = ['doctype', 'docname']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Document Info', {
            'fields': ('doctype', 'docname')
        }),
        ('Sync Status', {
            'fields': ('sync_status', 'is_syncing', 'sync_direction', 'last_synced')
        }),
        ('Timestamps', {
            'fields': ('cloud_modified', 'local_modified')
        }),
        ('Hashes', {
            'fields': ('sync_hash_cloud', 'sync_hash_local')
        }),
        ('Error Info', {
            'fields': ('error_message', 'retry_count')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'doctype', 'docname', 'action', 'direction', 'status']
    list_filter = ['status', 'action', 'direction', 'doctype']
    search_fields = ['doctype', 'docname', 'message']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'


@admin.register(ConflictRecord)
class ConflictRecordAdmin(admin.ModelAdmin):
    list_display = ['doctype', 'docname', 'resolved', 'resolution', 'created_at']
    list_filter = ['resolved', 'resolution', 'doctype']
    search_fields = ['doctype', 'docname']
    readonly_fields = ['created_at', 'cloud_modified', 'local_modified']
    fieldsets = (
        ('Document Info', {
            'fields': ('doctype', 'docname')
        }),
        ('Conflict Data', {
            'fields': ('cloud_data', 'local_data', 'cloud_modified', 'local_modified')
        }),
        ('Resolution', {
            'fields': ('resolved', 'resolution', 'resolved_at')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )


@admin.register(WebhookQueue)
class WebhookQueueAdmin(admin.ModelAdmin):
    list_display = ['source', 'doctype', 'docname', 'action', 'processed', 'created_at']
    list_filter = ['processed', 'processing', 'source', 'action', 'doctype']
    search_fields = ['doctype', 'docname']
    readonly_fields = ['created_at', 'processed_at']
    fieldsets = (
        ('Webhook Info', {
            'fields': ('source', 'doctype', 'docname', 'action')
        }),
        ('Payload', {
            'fields': ('payload',)
        }),
        ('Status', {
            'fields': ('processed', 'processing', 'created_at', 'processed_at')
        }),
        ('Error Info', {
            'fields': ('error_message', 'retry_count')
        }),
    )
