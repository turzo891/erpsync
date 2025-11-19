"""
Django views for webhook handling and status endpoints
"""
import json
import hmac
import hashlib
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.utils import timezone
from .models import WebhookQueue


def verify_webhook_signature(payload_bytes, signature):
    """
    Verify webhook signature from Frappe

    Args:
        payload_bytes: Request payload bytes
        signature: Signature from request header

    Returns:
        True if signature is valid
    """
    expected_signature = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@csrf_exempt
@require_http_methods(["POST"])
def webhook_cloud(request):
    """Receive webhooks from cloud ERP"""
    return handle_webhook(request, 'cloud')


@csrf_exempt
@require_http_methods(["POST"])
def webhook_local(request):
    """Receive webhooks from local ERP"""
    return handle_webhook(request, 'local')


def handle_webhook(request, source):
    """
    Handle incoming webhook from either cloud or local ERP

    Args:
        request: Django HTTP request
        source: 'cloud' or 'local'

    Returns:
        JsonResponse
    """
    try:
        # Verify signature if provided
        signature = request.headers.get('X-Frappe-Webhook-Signature')
        if signature:
            if not verify_webhook_signature(request.body, signature):
                return JsonResponse(
                    {'status': 'error', 'message': 'Invalid signature'},
                    status=401
                )

        # Parse webhook payload
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {'status': 'error', 'message': 'Invalid JSON'},
                status=400
            )

        if not payload:
            return JsonResponse(
                {'status': 'error', 'message': 'No payload'},
                status=400
            )

        # Extract document info
        doctype = payload.get('doctype')
        docname = payload.get('name')
        action = payload.get('action', 'update')  # Frappe sends: save, delete

        if not doctype or not docname:
            return JsonResponse(
                {'status': 'error', 'message': 'Missing doctype or name'},
                status=400
            )

        # Add to webhook queue for processing
        webhook = WebhookQueue.objects.create(
            source=source,
            doctype=doctype,
            docname=docname,
            action=action,
            payload=json.dumps(payload)
        )

        print(f"WEBHOOK: Webhook received from {source}: {doctype}/{docname} ({action})")

        return JsonResponse({
            'status': 'success',
            'message': 'Webhook queued for processing',
            'id': webhook.id
        }, status=200)

    except Exception as e:
        print(f"Error handling webhook from {source}: {e}")
        return JsonResponse(
            {'status': 'error', 'message': str(e)},
            status=500
        )


@require_http_methods(["GET"])
def health(request):
    """Health check endpoint"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'erpsync-django-server',
        'timestamp': timezone.now().isoformat()
    }, status=200)


@require_http_methods(["GET"])
def status(request):
    """Get sync status"""
    pending = WebhookQueue.objects.filter(processed=False).count()
    processing = WebhookQueue.objects.filter(processing=True).count()

    return JsonResponse({
        'status': 'running',
        'pending_webhooks': pending,
        'processing_webhooks': processing,
        'timestamp': timezone.now().isoformat()
    }, status=200)
