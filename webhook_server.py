"""
Webhook server to receive real-time updates from ERP systems
"""
from flask import Flask, request, jsonify
import json
import hmac
import hashlib
import os
from datetime import datetime
from threading import Thread
import time

from models import WebhookQueue, get_db, init_db
from sync_engine import SyncEngine
from frappe_client import FrappeClient
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Configuration
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'your_secure_webhook_secret')
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', '0.0.0.0')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', 5000))

# Initialize sync engine (will be set in main)
sync_engine = None


def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """
    Verify webhook signature from Frappe

    Args:
        payload: Request payload bytes
        signature: Signature from request header

    Returns:
        True if signature is valid
    """
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected_signature)


@app.route('/webhook/cloud', methods=['POST'])
def webhook_cloud():
    """Receive webhooks from cloud ERP"""
    return handle_webhook('cloud')


@app.route('/webhook/local', methods=['POST'])
def webhook_local():
    """Receive webhooks from local ERP"""
    return handle_webhook('local')


def handle_webhook(source: str):
    """
    Handle incoming webhook from either cloud or local ERP

    Args:
        source: 'cloud' or 'local'

    Returns:
        Flask response
    """
    try:
        # Verify signature if provided
        signature = request.headers.get('X-Frappe-Webhook-Signature')
        if signature:
            if not verify_webhook_signature(request.data, signature):
                return jsonify({'status': 'error', 'message': 'Invalid signature'}), 401

        # Parse webhook payload
        payload = request.get_json()

        if not payload:
            return jsonify({'status': 'error', 'message': 'No payload'}), 400

        # Extract document info
        doctype = payload.get('doctype')
        docname = payload.get('name')
        action = payload.get('action', 'update')  # Frappe sends: save, delete

        if not doctype or not docname:
            return jsonify({'status': 'error', 'message': 'Missing doctype or name'}), 400

        # Add to webhook queue for processing
        db = get_db()
        try:
            queue_item = WebhookQueue(
                source=source,
                doctype=doctype,
                docname=docname,
                action=action,
                payload=json.dumps(payload)
            )
            db.add(queue_item)
            db.commit()

            print(f"📨 Webhook received from {source}: {doctype}/{docname} ({action})")

            return jsonify({
                'status': 'success',
                'message': 'Webhook queued for processing'
            }), 200

        finally:
            db.close()

    except Exception as e:
        print(f"Error handling webhook from {source}: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'erpsync-webhook-server',
        'timestamp': datetime.utcnow().isoformat()
    }), 200


@app.route('/status', methods=['GET'])
def status():
    """Get sync status"""
    db = get_db()
    try:
        pending = db.query(WebhookQueue).filter_by(processed=False).count()
        processing = db.query(WebhookQueue).filter_by(processing=True).count()

        return jsonify({
            'status': 'running',
            'pending_webhooks': pending,
            'processing_webhooks': processing,
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    finally:
        db.close()


def process_webhook_queue():
    """
    Background worker to process webhook queue
    Runs in a separate thread
    """
    print("🔄 Webhook queue processor started")

    while True:
        try:
            db = get_db()
            try:
                # Get unprocessed webhooks
                webhooks = db.query(WebhookQueue).filter_by(
                    processed=False,
                    processing=False
                ).order_by(WebhookQueue.created_at).limit(10).all()

                for webhook in webhooks:
                    # Mark as processing
                    webhook.processing = True
                    db.commit()

                    try:
                        # Determine sync direction based on source
                        if webhook.source == 'cloud':
                            direction = 'cloud_to_local'
                        elif webhook.source == 'local':
                            direction = 'local_to_cloud'
                        else:
                            raise ValueError(f"Unknown webhook source: {webhook.source}")

                        # Sync the document
                        print(f"⚙️  Processing: {webhook.doctype}/{webhook.docname} ({direction})")

                        success, message = sync_engine.sync_document(
                            webhook.doctype,
                            webhook.docname,
                            direction=direction
                        )

                        # Mark as processed
                        webhook.processed = True
                        webhook.processing = False
                        webhook.processed_at = datetime.utcnow()

                        if not success:
                            webhook.error_message = message
                            webhook.retry_count += 1
                            print(f"  ✗ Failed: {message}")
                        else:
                            print(f"  ✓ Success: {message}")

                        db.commit()

                    except Exception as e:
                        webhook.processing = False
                        webhook.error_message = str(e)
                        webhook.retry_count += 1
                        db.commit()
                        print(f"  ✗ Error processing webhook: {e}")

            finally:
                db.close()

            # Sleep before next iteration
            time.sleep(2)

        except Exception as e:
            print(f"Error in webhook processor: {e}")
            time.sleep(5)


def start_webhook_server(cloud_client: FrappeClient, local_client: FrappeClient):
    """
    Start webhook server with background queue processor

    Args:
        cloud_client: Frappe client for cloud ERP
        local_client: Frappe client for local ERP
    """
    global sync_engine

    # Initialize database
    init_db()

    # Initialize sync engine
    sync_engine = SyncEngine(cloud_client, local_client)

    # Start background queue processor
    processor_thread = Thread(target=process_webhook_queue, daemon=True)
    processor_thread.start()

    # Print webhook URLs
    print("\n" + "="*60)
    print("🚀 ERP Sync Webhook Server Starting...")
    print("="*60)
    print(f"\nWebhook URLs:")
    print(f"  Cloud ERP → http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/webhook/cloud")
    print(f"  Local ERP → http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/webhook/local")
    print(f"\nHealth Check:")
    print(f"  http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/health")
    print(f"\nWebhook Secret: {WEBHOOK_SECRET}")
    print("\n" + "="*60 + "\n")

    # Start Flask server
    app.run(host=WEBHOOK_HOST, port=WEBHOOK_PORT, debug=False, threaded=True)


if __name__ == '__main__':
    # Initialize Frappe clients
    cloud = FrappeClient(
        url=os.getenv('CLOUD_ERP_URL'),
        api_key=os.getenv('CLOUD_API_KEY'),
        api_secret=os.getenv('CLOUD_API_SECRET'),
        instance_name='Cloud'
    )

    local = FrappeClient(
        url=os.getenv('LOCAL_ERP_URL'),
        api_key=os.getenv('LOCAL_API_KEY'),
        api_secret=os.getenv('LOCAL_API_SECRET'),
        instance_name='Local'
    )

    # Test connections
    print("Testing connections...")
    if not cloud.test_connection() or not local.test_connection():
        print("❌ Connection test failed. Please check your .env configuration.")
        exit(1)

    # Start server
    start_webhook_server(cloud, local)
