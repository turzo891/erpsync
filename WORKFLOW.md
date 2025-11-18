# ERP Sync - Operational Workflow Guide

This guide explains how to operate the ERP Sync system for day-to-day use, maintenance, and troubleshooting.

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Initial Setup Workflow](#initial-setup-workflow)
3. [Running Sync Operations](#running-sync-operations)
4. [Monitoring & Maintenance](#monitoring--maintenance)
5. [Handling Conflicts](#handling-conflicts)
6. [Troubleshooting Common Issues](#troubleshooting-common-issues)
7. [Backup & Recovery](#backup--recovery)
8. [Best Practices](#best-practices)

---

## Daily Operations

### Starting the Webhook Server (Real-time Sync)

**For Production/Daily Use**: Run the webhook server to enable real-time synchronization.

```bash
# Navigate to project directory
cd /Users/spoofing/Documents/erpsync

# Activate virtual environment
source venv/bin/activate

# Start webhook server
python main.py webhook
```

**Expected Output**:
```
=============================================================
🚀 ERP Sync Webhook Server Starting...
=============================================================

Webhook URLs:
  Cloud ERP → http://0.0.0.0:5000/webhook/cloud
  Local ERP → http://0.0.0.0:5000/webhook/local

Health Check:
  http://0.0.0.0:5000/health

Webhook Secret: your_webhook_secret

=============================================================

✓ Connected to Cloud (https://your-cloud-erp.com) as user: Administrator
✓ Connected to Local (http://localhost:8000) as user: Administrator
🔄 Webhook queue processor started
 * Running on http://0.0.0.0:5000
```

**Keep this running** - it will process webhooks in real-time as changes occur.

### Running as Background Service

To keep the webhook server running even after closing the terminal:

**Option 1: Using nohup**
```bash
nohup python main.py webhook > webhook.log 2>&1 &

# Check if running
ps aux | grep "main.py webhook"

# View logs
tail -f webhook.log

# Stop
kill <PID>
```

**Option 2: Using screen/tmux**
```bash
# Create new screen session
screen -S erpsync

# Start webhook server
python main.py webhook

# Detach: Ctrl+A, then D
# Reattach: screen -r erpsync
```

**Option 3: Systemd Service (Linux)**
```bash
# Copy service file
sudo cp /path/to/erpsync.service /etc/systemd/system/

# Enable and start
sudo systemctl enable erpsync
sudo systemctl start erpsync

# Check status
sudo systemctl status erpsync

# View logs
sudo journalctl -u erpsync -f
```

---

## Initial Setup Workflow

### Step 1: Installation

```bash
# Clone/navigate to project
cd /Users/spoofing/Documents/erpsync

# Run automated setup
./setup.sh
```

This will:
- Create Python virtual environment
- Install all dependencies
- Initialize SQLite database
- Create `.env` configuration file

### Step 2: Configuration

#### Get API Credentials

**For Cloud ERP**:
1. Login to your cloud ERPNext instance
2. Click your profile picture (top right)
3. Select "API Access"
4. Click "Generate Keys"
5. Copy **API Key** and **API Secret**

**For Local ERP**:
1. Login to your local ERPNext instance
2. Follow same steps as above
3. Copy **API Key** and **API Secret**

#### Edit Configuration

```bash
# Edit .env file
nano .env  # or use any text editor
```

Update these values:
```env
# Cloud ERP Configuration
CLOUD_ERP_URL=https://your-cloud-erp.example.com
CLOUD_API_KEY=your_actual_cloud_api_key_here
CLOUD_API_SECRET=your_actual_cloud_api_secret_here

# Local ERP Configuration
LOCAL_ERP_URL=http://localhost:8000
LOCAL_API_KEY=your_actual_local_api_key_here
LOCAL_API_SECRET=your_actual_local_api_secret_here

# Webhook Configuration
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000
WEBHOOK_SECRET=generate_random_secure_string_here

# Sync Settings
CONFLICT_RESOLUTION=latest_timestamp
```

**Generate Webhook Secret**:
```bash
# Generate random secret
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

#### Configure DocTypes to Sync

Edit `config.yaml` to specify which document types to synchronize:

```yaml
sync_rules:
  # List all DocTypes you want to sync
  doctypes:
    - Customer
    - Supplier
    - Item
    - Item Group
    - Sales Order
    - Purchase Order
    - Sales Invoice
    - Purchase Invoice
    - Quotation
    - Delivery Note
    - Payment Entry

  # Fields to exclude from sync (system fields)
  exclude_fields:
    - modified_by
    - creation
    - owner
    - idx
    - docstatus

  # Conflict resolution strategy
  # Options: latest_timestamp, cloud_wins, local_wins, manual
  conflict_resolution: latest_timestamp

  # Retry settings
  retry:
    max_attempts: 3
    backoff_seconds: 5

  # Batch processing
  batch_size: 50
```

### Step 3: Test Connections

```bash
# Activate virtual environment
source venv/bin/activate

# Run connection test
python main.py test
```

**Expected Output**:
```
✓ Connected to Cloud (https://your-cloud-erp.com) as user: Administrator
✓ Connected to Local (http://localhost:8000) as user: Administrator
✓ All connections successful
```

If this fails, see [Troubleshooting](#troubleshooting-common-issues).

### Step 4: Initial Full Sync

Before setting up webhooks, perform an initial sync to get both systems in sync:

```bash
# Sync all configured DocTypes
python main.py sync

# Or sync specific DocTypes
python main.py sync --doctype Customer
python main.py sync --doctype Item
```

**Monitor Progress**:
```
🔄 Starting full sync for 11 DocTypes...

Syncing Customer...
Syncing Supplier...
Syncing Item...
...

✅ Sync completed!
Total: 1500, Success: 1485, Failed: 5, Conflicts: 10, Skipped: 0
```

### Step 5: Setup Webhooks for Real-time Sync

#### View Setup Instructions

```bash
python main.py setup-webhook
```

#### Configure Webhooks in Cloud ERP

1. **Start webhook server** (in terminal):
   ```bash
   python main.py webhook
   ```

2. **Login to Cloud ERPNext**

3. **Navigate to**: Setup → Integrations → Webhook

4. **Click "New"**

5. **Configure Webhook**:
   - **Webhook Name**: `ERP Sync - Customer to Local`
   - **Document Type**: `Customer`
   - **Request URL**: `http://YOUR_SERVER_IP:5000/webhook/cloud`
     - Replace `YOUR_SERVER_IP` with your webhook server's IP
     - If webhook server is on same machine as local ERP, use: `http://localhost:5000/webhook/cloud`
     - If local machine is behind NAT, use ngrok (see below)
   - **Webhook Secret**: (paste the secret from your `.env` file)
   - **Request Structure**: `Form URL-Encoded`
   - **Condition**: (leave blank to sync all)
   - **Enabled**: ✓ Check
   - **Enable Event Streaming**: ✓ Check (if available)

6. **Enable Triggers**:
   - ✓ After Insert
   - ✓ After Save
   - ✓ After Delete

7. **Save**

8. **Repeat** for each DocType (Customer, Item, Sales Order, etc.)

#### Configure Webhooks in Local ERP

Same as above, but:
- **Request URL**: `http://YOUR_SERVER_IP:5000/webhook/local`
- Create for each DocType you want to sync

#### Using ngrok for Local Machine Behind NAT

If your local machine is not publicly accessible:

```bash
# Install ngrok from https://ngrok.com

# Start ngrok tunnel
ngrok http 5000
```

**Output**:
```
Forwarding  https://abc123xyz.ngrok.io -> http://localhost:5000
```

Use the ngrok URL in your webhook configuration:
- Cloud ERP: `https://abc123xyz.ngrok.io/webhook/cloud`
- Local ERP: `https://abc123xyz.ngrok.io/webhook/local`

### Step 6: Test Real-time Sync

1. **Ensure webhook server is running**

2. **Create a test customer in Cloud ERP**:
   - Login to Cloud ERPNext
   - Go to Customer → New
   - Enter customer details
   - Save

3. **Check webhook server logs**:
   ```
   📨 Webhook received from cloud: Customer/CUST-00001 (save)
   ⚙️  Processing: Customer/CUST-00001 (cloud_to_local)
     ✓ Success: Updated on local from cloud
   ```

4. **Verify in Local ERP**:
   - Login to Local ERPNext
   - Go to Customer list
   - Find the newly created customer
   - Verify all details match

5. **Test reverse sync** (Local → Cloud):
   - Edit the customer in Local ERP
   - Change some field
   - Save
   - Check webhook server logs
   - Verify change appears in Cloud ERP

**Success!** Your bidirectional sync is now working.

---

## Running Sync Operations

### Manual Sync Commands

Even with webhooks running, you can manually trigger syncs:

#### Sync All DocTypes

```bash
python main.py sync
```

Use when:
- Initial setup
- After system downtime
- Periodic verification

#### Sync Specific DocType

```bash
python main.py sync --doctype Customer
```

Use when:
- Testing specific DocType
- Fixing issues with one DocType
- Bulk updating one type

#### Sync Specific Document

```bash
python main.py sync --doctype Customer --docname "CUST-00123"
```

Use when:
- Fixing specific document issue
- Manual conflict resolution
- Testing

#### Force Sync Direction

```bash
# Force cloud to local
python main.py sync --doctype Customer --direction cloud_to_local

# Force local to cloud
python main.py sync --doctype Customer --direction local_to_cloud

# Auto-detect (default)
python main.py sync --doctype Customer --direction auto
```

Use when:
- You know which direction is correct
- Resolving conflicts manually
- Data recovery

#### Limit Number of Documents

```bash
# Sync only first 50 documents
python main.py sync --doctype Customer --limit 50
```

Use when:
- Testing
- Limited resources
- Incremental sync

---

## Monitoring & Maintenance

### Check Sync Status

```bash
python main.py status
```

**Output**:
```
Sync Status

Total Documents Tracked: 2,450
  Synced: 2,430
  Errors: 15
  Conflicts: 5

Recent Sync Operations:
  [14:23:45] SUCCESS - Customer/CUST-00001 (cloud_to_local)
  [14:23:46] SUCCESS - Item/ITEM-00123 (local_to_cloud)
  [14:23:50] FAILED - Sales Order/SO-00456 (cloud_to_local)
  ...

⚠ Unresolved Conflicts: 5
```

### View Webhook Queue Status

```bash
curl http://localhost:5000/status
```

**Output**:
```json
{
  "status": "running",
  "pending_webhooks": 3,
  "processing_webhooks": 1,
  "timestamp": "2025-11-18T14:30:00"
}
```

### Check Health

```bash
curl http://localhost:5000/health
```

**Output**:
```json
{
  "status": "healthy",
  "service": "erpsync-webhook-server",
  "timestamp": "2025-11-18T14:30:00"
}
```

### View Logs

```bash
# Real-time webhook server logs
tail -f erpsync.log

# Filter for errors
grep ERROR erpsync.log

# Last 100 lines
tail -n 100 erpsync.log
```

### Database Inspection

```bash
# Open database
sqlite3 sync_state.db

# Useful queries:

# Failed syncs
SELECT doctype, docname, error_message, retry_count
FROM sync_records
WHERE sync_status = 'error'
ORDER BY updated_at DESC;

# Recent sync operations
SELECT timestamp, doctype, docname, status, message
FROM sync_logs
ORDER BY timestamp DESC
LIMIT 20;

# Pending webhooks
SELECT * FROM webhook_queue
WHERE processed = FALSE;

# Conflict summary by DocType
SELECT doctype, COUNT(*) as count
FROM conflict_records
WHERE resolved = FALSE
GROUP BY doctype;

# Exit
.quit
```

### Diagnostics

Run comprehensive diagnostics:

```bash
python troubleshoot.py
```

This checks:
- Environment variables
- Database status
- Cloud ERP connection
- Local ERP connection
- Webhook server status

---

## Handling Conflicts

### View Conflicts

```bash
python main.py conflicts
```

**Output**:
```
Unresolved Conflicts: 5

1. Customer/CUST-00123
   Cloud modified: 2025-11-18 10:30:00
   Local modified: 2025-11-18 10:31:00

2. Item/ITEM-00456
   Cloud modified: 2025-11-18 11:00:00
   Local modified: 2025-11-18 11:05:00

3. Sales Order/SO-00789
   Cloud modified: 2025-11-18 12:15:00
   Local modified: 2025-11-18 12:20:00
```

### Automatic Conflict Resolution

Conflicts are automatically resolved based on your `conflict_resolution` setting in `config.yaml`:

**Latest Timestamp (Default)**:
```yaml
conflict_resolution: latest_timestamp
```
- Most recently modified version wins
- Automatic, no manual intervention

**Cloud Always Wins**:
```yaml
conflict_resolution: cloud_wins
```
- Cloud version always takes precedence
- Use if cloud is your primary system

**Local Always Wins**:
```yaml
conflict_resolution: local_wins
```
- Local version always takes precedence
- Use if local is your primary system

**Manual Resolution**:
```yaml
conflict_resolution: manual
```
- Conflicts require manual review
- Use for critical data

### Manual Conflict Resolution

For conflicts requiring manual intervention:

1. **View conflict details** in database:
   ```bash
   sqlite3 sync_state.db

   SELECT cloud_data, local_data
   FROM conflict_records
   WHERE doctype = 'Customer' AND docname = 'CUST-00123';
   ```

2. **Decide which version to keep**

3. **Force sync in desired direction**:
   ```bash
   # Keep cloud version
   python main.py sync --doctype Customer --docname "CUST-00123" --direction cloud_to_local

   # Keep local version
   python main.py sync --doctype Customer --docname "CUST-00123" --direction local_to_cloud
   ```

4. **Mark conflict as resolved** (optional):
   ```sql
   UPDATE conflict_records
   SET resolved = TRUE,
       resolution = 'cloud_wins',
       resolved_at = CURRENT_TIMESTAMP
   WHERE doctype = 'Customer' AND docname = 'CUST-00123';
   ```

### Preventing Conflicts

**Best Practices**:
1. Designate primary system for each DocType
2. Establish clear edit policies
3. Use workflow states to control who edits where
4. Monitor conflicts regularly
5. Resolve conflicts quickly

---

## Troubleshooting Common Issues

### Issue: Connection Failed

**Symptoms**:
```
✗ Failed to connect to Cloud (https://your-erp.com)
```

**Solutions**:

1. **Check ERP is running**:
   ```bash
   curl https://your-erp.com
   ```

2. **Verify credentials**:
   - Check `.env` file has correct values
   - Test API key in ERPNext UI

3. **Test network**:
   ```bash
   ping your-erp.com
   ```

4. **Check firewall**:
   - Ensure ports are open
   - Check security groups (AWS)

### Issue: Timestamp Mismatch Errors

**Symptoms**:
```
Error: Document has been modified after you have opened it
```

**Solution**:
- This is now **automatically handled** by the system
- System will retry up to 3 times
- If still fails after 3 retries, check for:
  - Concurrent edits from multiple users
  - Rapid updates from other processes
  - System clock synchronization issues

**Manual Check**:
```bash
# Check system time on both servers
date

# Sync time if needed (Linux)
sudo ntpdate -s time.nist.gov
```

### Issue: Webhooks Not Arriving

**Symptoms**:
- Changes in ERP don't trigger sync
- Webhook server shows no activity

**Solutions**:

1. **Check webhook server is running**:
   ```bash
   curl http://localhost:5000/health
   ```

2. **Verify webhook configuration in ERPNext**:
   - Setup → Integrations → Webhook
   - Check URL is correct
   - Check secret matches
   - Check triggers are enabled

3. **Test webhook manually**:
   ```bash
   curl -X POST http://localhost:5000/webhook/cloud \
     -H "Content-Type: application/json" \
     -d '{"doctype":"Customer","name":"TEST","action":"save"}'
   ```

4. **Check firewall/NAT**:
   - Ensure webhook URL is accessible from ERP
   - Use ngrok if behind NAT

5. **Check webhook logs in ERPNext**:
   - Setup → Integrations → Webhook → View Logs

### Issue: Sync Loops

**Symptoms**:
- Same document syncing repeatedly
- High CPU/network usage
- Webhook queue growing continuously

**Solutions**:

1. **Check for hash mismatches**:
   ```sql
   SELECT doctype, docname, sync_hash_cloud, sync_hash_local
   FROM sync_records
   WHERE sync_status = 'synced'
   AND last_synced > datetime('now', '-5 minutes');
   ```

2. **Temporarily stop webhooks**:
   - Disable webhooks in both ERPs
   - Let system settle
   - Clear webhook queue
   - Re-enable one at a time

3. **Reset sync state** for problematic document:
   ```sql
   DELETE FROM sync_records
   WHERE doctype = 'Customer' AND docname = 'CUST-00123';
   ```

4. **Re-sync manually**:
   ```bash
   python main.py sync --doctype Customer --docname "CUST-00123"
   ```

### Issue: High Error Rate

**Symptoms**:
```
python main.py status
...
Errors: 150
```

**Solutions**:

1. **Identify common errors**:
   ```sql
   SELECT error_message, COUNT(*) as count
   FROM sync_records
   WHERE sync_status = 'error'
   GROUP BY error_message
   ORDER BY count DESC;
   ```

2. **Check specific failures**:
   ```sql
   SELECT doctype, docname, error_message
   FROM sync_records
   WHERE sync_status = 'error'
   ORDER BY updated_at DESC
   LIMIT 10;
   ```

3. **Common causes**:
   - Permission issues: Check API key permissions
   - Data validation: Check if data meets ERP validation rules
   - Missing dependencies: Check if related documents exist
   - Network issues: Check connectivity

4. **Retry failed documents**:
   ```bash
   # Sync all failed Customers
   python main.py sync --doctype Customer
   ```

### Issue: Webhook Queue Building Up

**Symptoms**:
```
curl http://localhost:5000/status
{
  "pending_webhooks": 1500,
  ...
}
```

**Solutions**:

1. **Check queue processor is running**:
   - Webhook server should show: "🔄 Webhook queue processor started"

2. **Identify bottleneck**:
   ```sql
   SELECT source, doctype, COUNT(*) as count
   FROM webhook_queue
   WHERE processed = FALSE
   GROUP BY source, doctype;
   ```

3. **Increase processing speed**:
   - Reduce `time.sleep(2)` in webhook_server.py
   - Increase batch size in queue processor

4. **Clear old queue items**:
   ```sql
   -- Mark very old items as processed
   UPDATE webhook_queue
   SET processed = TRUE
   WHERE created_at < datetime('now', '-1 hour')
   AND processed = FALSE;
   ```

---

## Backup & Recovery

### Backup Sync Database

```bash
# Backup database
cp sync_state.db sync_state.db.backup.$(date +%Y%m%d_%H%M%S)

# Or use SQLite backup
sqlite3 sync_state.db ".backup 'sync_state.db.backup'"
```

### Restore Database

```bash
# Stop webhook server first
# Then restore
cp sync_state.db.backup.20251118_143000 sync_state.db

# Restart webhook server
python main.py webhook
```

### Export Sync Logs

```bash
# Export to CSV
sqlite3 sync_state.db <<EOF
.headers on
.mode csv
.output sync_logs_export.csv
SELECT * FROM sync_logs WHERE timestamp > datetime('now', '-7 days');
.quit
EOF
```

### Reset Sync State

**Warning**: This will clear all sync tracking and force full re-sync.

```bash
# Backup first!
cp sync_state.db sync_state.db.backup

# Reset
sqlite3 sync_state.db "DELETE FROM sync_records;"
sqlite3 sync_state.db "DELETE FROM webhook_queue;"

# Re-sync everything
python main.py sync
```

---

## Best Practices

### 1. Regular Monitoring

```bash
# Daily status check
python main.py status

# Weekly conflict review
python main.py conflicts

# Monthly database maintenance
sqlite3 sync_state.db "VACUUM;"
```

### 2. Scheduled Verification Syncs

Even with webhooks running, schedule periodic full syncs to catch any missed changes:

```bash
# Add to crontab (daily at 2 AM)
0 2 * * * cd /path/to/erpsync && ./venv/bin/python main.py sync >> sync-cron.log 2>&1
```

### 3. Log Rotation

```bash
# Rotate logs weekly
# Add to crontab
0 0 * * 0 mv /path/to/erpsync/erpsync.log /path/to/erpsync/erpsync.log.$(date +\%Y\%m\%d)
```

### 4. Alert on Errors

```bash
# Check for errors and send email alert
python main.py status | grep "Errors:" | awk '{if ($2 > 10) print}' | mail -s "ERP Sync Errors" admin@example.com
```

### 5. Database Maintenance

```bash
# Monthly database optimization
sqlite3 sync_state.db <<EOF
-- Delete old processed webhooks (older than 30 days)
DELETE FROM webhook_queue WHERE processed = TRUE AND processed_at < datetime('now', '-30 days');

-- Delete old sync logs (older than 90 days)
DELETE FROM sync_logs WHERE timestamp < datetime('now', '-90 days');

-- Vacuum to reclaim space
VACUUM;
EOF
```

### 6. Testing Before Production

```bash
# Test sync with limited documents
python main.py sync --doctype Customer --limit 10

# Monitor closely
python main.py status

# Review any issues
python troubleshoot.py
```

### 7. Documentation

Keep notes on:
- Custom configurations
- Conflict resolution decisions
- Sync schedule
- Maintenance procedures
- Contact information for ERP administrators

### 8. Gradual Rollout

1. Start with read-only DocTypes (Item, Item Group)
2. Add transactional DocTypes (Sales Order, Purchase Order)
3. Monitor for a week
4. Add master data (Customer, Supplier)
5. Full production rollout

---

## Summary Workflow

### Daily Workflow

```bash
# Morning: Check status
python main.py status

# Ensure webhook server is running
curl http://localhost:5000/health

# Review any new conflicts
python main.py conflicts
```

### Weekly Workflow

```bash
# Run verification sync
python main.py sync

# Check for errors
python main.py status

# Database maintenance
sqlite3 sync_state.db "VACUUM;"

# Backup database
cp sync_state.db sync_state.db.backup.$(date +%Y%m%d)
```

### Monthly Workflow

```bash
# Full system check
python troubleshoot.py

# Review sync logs
sqlite3 sync_state.db "SELECT doctype, status, COUNT(*) FROM sync_logs WHERE timestamp > datetime('now', '-30 days') GROUP BY doctype, status;"

# Clean old data
sqlite3 sync_state.db "DELETE FROM webhook_queue WHERE processed = TRUE AND processed_at < datetime('now', '-30 days');"

# Review and update configurations
nano config.yaml
```

---

## Getting Help

If you encounter issues not covered here:

1. **Check logs**: `tail -f erpsync.log`
2. **Run diagnostics**: `python troubleshoot.py`
3. **Check database**: `sqlite3 sync_state.db`
4. **Review MECHANISM.md** for technical details
5. **Check Frappe documentation**: https://frappeframework.com/docs

---

This workflow guide should help you operate the ERP Sync system effectively. For technical details on how the system works internally, see MECHANISM.md.
