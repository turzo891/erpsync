# ERP Sync - Bidirectional Synchronization for Frappe/ERPNext

A Python-based bidirectional synchronization system for syncing data between two Frappe/ERPNext instances (Cloud and Local).

## Features

- **Real-time Bidirectional Sync**: Changes in either ERP system automatically sync to the other
- **Webhook-based**: Efficient real-time synchronization using webhooks
- **Conflict Resolution**: Automatic conflict handling with configurable strategies
- **Change Tracking**: SQLite database tracks sync state and prevents sync loops
- **Retry Logic**: Automatic retry for failed syncs
- **Manual Sync**: On-demand sync for specific documents or all DocTypes
- **Audit Logging**: Complete audit trail of all sync operations
- **CLI Interface**: Easy-to-use command-line tool

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   Cloud ERP     │◄───────►│   Sync Engine    │◄───────►│   Local ERP     │
│   (AWS EC2)     │         │                  │         │  (Your Machine) │
└─────────────────┘         └──────────────────┘         └─────────────────┘
        │                            │                            │
        │        Webhooks            │                            │
        └───────────────────────────►│                            │
                                     │◄───────────────────────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │  SQLite DB      │
                            │  (Sync State)   │
                            └─────────────────┘
```

## Prerequisites

- Python 3.8 or higher
- Access to both ERP instances (Cloud and Local)
- API credentials for both ERP systems
- Network connectivity between sync server and both ERPs

## Installation

### 1. Clone/Download the Project

```bash
cd /Users/spoofing/Documents/erpsync
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

Copy the example environment file and edit it:

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials:

```bash
# Cloud ERP (AWS EC2)
CLOUD_ERP_URL=https://your-cloud-erp.com
CLOUD_API_KEY=your_cloud_api_key
CLOUD_API_SECRET=your_cloud_api_secret

# Local ERP
LOCAL_ERP_URL=http://localhost:8000
LOCAL_API_KEY=your_local_api_key
LOCAL_API_SECRET=your_local_api_secret

# Webhook Configuration
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000
WEBHOOK_SECRET=your_secure_webhook_secret_change_this

# Sync Configuration
CONFLICT_RESOLUTION=latest_timestamp
```

### 5. Get API Credentials from Frappe/ERPNext

For both Cloud and Local ERP:

1. Login to ERPNext
2. Go to: User Menu > API Access
3. Click "Generate Keys"
4. Copy the API Key and API Secret
5. Add them to your `.env` file

### 6. Configure DocTypes to Sync

Edit `config.yaml` to specify which DocTypes to sync:

```yaml
sync_rules:
  doctypes:
    - Customer
    - Supplier
    - Item
    - Sales Order
    - Purchase Order
    # Add more DocTypes as needed
```

### 7. Initialize Database

```bash
python main.py init
```

### 8. Test Connections

```bash
python main.py test
```

You should see:
```
✓ Connected to Cloud (https://your-cloud-erp.com) as user: Administrator
✓ Connected to Local (http://localhost:8000) as user: Administrator
✓ All connections successful
```

## Usage

### Method 1: Real-time Sync with Webhooks (Recommended)

This provides automatic real-time synchronization.

#### Step 1: Start Webhook Server

```bash
python main.py webhook
```

This will start a Flask server listening for webhooks.

#### Step 2: Configure Webhooks in Cloud ERP

1. Login to your Cloud ERP
2. Go to: **Setup > Integrations > Webhook**
3. Click "New"
4. Configure:
   - **Document Type**: Customer (or any DocType you want to sync)
   - **Request URL**: `http://YOUR_SERVER_IP:5000/webhook/cloud`
   - **Webhook Secret**: (same as in your .env file)
   - **Enable**: Check "After Insert", "After Save", "After Delete"
5. Save

Repeat for each DocType you want to sync.

#### Step 3: Configure Webhooks in Local ERP

Same as above, but use:
- **Request URL**: `http://YOUR_SERVER_IP:5000/webhook/local`

**Important**: If your local machine is behind NAT/firewall, use a tunneling service like ngrok:

```bash
# Install ngrok: https://ngrok.com
ngrok http 5000
```

Use the ngrok URL (e.g., `https://abc123.ngrok.io/webhook/local`) in your webhook configuration.

#### Step 4: Test the Sync

1. Create a new Customer in Cloud ERP
2. Check webhook server logs - you should see the sync happening
3. Verify the Customer appears in Local ERP

### Method 2: Manual Sync (On-Demand)

Useful for initial sync or periodic syncs.

#### Sync All DocTypes

```bash
python main.py sync
```

#### Sync Specific DocType

```bash
python main.py sync --doctype Customer
```

#### Sync Specific Document

```bash
python main.py sync --doctype Customer --docname "CUST-00001"
```

#### Force Sync Direction

```bash
python main.py sync --doctype Customer --direction cloud_to_local
```

## Monitoring

### Check Sync Status

```bash
python main.py status
```

Output:
```
Total Documents Tracked: 150
  Synced: 145
  Errors: 3
  Conflicts: 2

Recent Sync Operations:
  [14:23:45] SUCCESS - Customer/CUST-00001 (cloud_to_local)
  [14:23:46] SUCCESS - Item/ITEM-00123 (local_to_cloud)
  ...
```

### View Conflicts

```bash
python main.py conflicts
```

## Conflict Resolution

When the same document is modified on both systems, conflicts can occur. The system handles them based on your configuration:

### Strategies (in config.yaml or .env):

1. **latest_timestamp** (default): The most recently modified version wins
2. **cloud_wins**: Cloud version always takes precedence
3. **local_wins**: Local version always takes precedence
4. **manual**: Conflicts require manual resolution

### View and Resolve Conflicts

```bash
python main.py conflicts --resolve
```

## Configuration Options

### config.yaml

```yaml
sync_rules:
  # DocTypes to sync
  doctypes:
    - Customer
    - Item

  # Fields to exclude from sync
  exclude_fields:
    - modified_by
    - creation
    - owner

  # Conflict resolution: latest_timestamp, cloud_wins, local_wins, manual
  conflict_resolution: latest_timestamp

  # Per-DocType rules
  doctype_rules:
    Item:
      direction: bidirectional
      priority: cloud

  # Retry settings
  retry:
    max_attempts: 3
    backoff_seconds: 5

  # Batch size for bulk sync
  batch_size: 50
```

## Troubleshooting

### Connection Issues

```bash
# Test connections
python main.py test
```

If connections fail:
- Check URLs in `.env`
- Verify API credentials
- Check network connectivity
- Ensure firewall allows connections

### Webhooks Not Working

1. Check webhook server is running: `python main.py webhook`
2. Test webhook endpoint: `curl http://localhost:5000/health`
3. Check webhook configuration in Frappe UI
4. Verify webhook secret matches
5. Check logs in webhook server

### Sync Errors

```bash
# Check status for errors
python main.py status

# Check database directly
sqlite3 sync_state.db "SELECT * FROM sync_logs WHERE status='failed' ORDER BY timestamp DESC LIMIT 10;"
```

### Sync Loops (Infinite Syncing)

The system prevents sync loops by:
- Tracking document hashes
- Checking last sync timestamp
- Marking documents during sync

If you suspect a loop:
1. Stop the webhook server
2. Check logs: `cat erpsync.log`
3. Reset sync state for specific document:
   ```bash
   sqlite3 sync_state.db "DELETE FROM sync_records WHERE doctype='Customer' AND docname='CUST-00001';"
   ```

## Advanced Usage

### Running as a Service (Linux)

Create `/etc/systemd/system/erpsync.service`:

```ini
[Unit]
Description=ERP Sync Webhook Server
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/Users/spoofing/Documents/erpsync
Environment="PATH=/Users/spoofing/Documents/erpsync/venv/bin"
ExecStart=/Users/spoofing/Documents/erpsync/venv/bin/python main.py webhook
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable erpsync
sudo systemctl start erpsync
sudo systemctl status erpsync
```

### Cron Job for Periodic Sync

Add to crontab (`crontab -e`):

```bash
# Sync every hour
0 * * * * cd /Users/spoofing/Documents/erpsync && ./venv/bin/python main.py sync >> /tmp/erpsync-cron.log 2>&1
```

## Database Schema

The sync system uses SQLite with these tables:

- **sync_records**: Tracks sync state for each document
- **sync_logs**: Audit log of all sync operations
- **conflict_records**: Stores conflicts for resolution
- **webhook_queue**: Queues webhook events for processing

To inspect:
```bash
sqlite3 sync_state.db
.tables
.schema sync_records
```

## Security Considerations

1. **API Credentials**: Keep your `.env` file secure, never commit to git
2. **Webhook Secret**: Use a strong random secret
3. **HTTPS**: Use HTTPS for production webhook endpoints
4. **Firewall**: Restrict webhook server access to your ERP IPs only
5. **Authentication**: Consider adding additional authentication layers

## Performance

- **Webhook mode**: Near real-time sync (< 5 seconds)
- **Manual sync**: Depends on document count (typically 10-50 docs/second)
- **Database**: SQLite handles 100K+ sync records efficiently
- **Memory**: Typically < 100MB RAM usage

## Limitations

1. Does not sync file attachments (only document data)
2. Does not handle complex nested child tables (can be extended)
3. Webhooks require network accessibility
4. Large documents (>1MB) may be slow

## Support

For issues or questions:
1. Check the logs: `cat erpsync.log`
2. Run diagnostics: `python main.py test` and `python main.py status`
3. Review Frappe webhook documentation
4. Check database state: `sqlite3 sync_state.db`

## License

MIT License - Feel free to modify and extend for your needs.

## Contributing

Contributions welcome! Areas for improvement:
- File attachment sync
- Web UI for monitoring
- Support for more conflict resolution strategies
- Performance optimizations
- Docker containerization
