# ERP Sync - Technical Mechanism Documentation

This document provides a detailed technical explanation of how the bidirectional ERP synchronization system works.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Core Components](#core-components)
3. [Synchronization Process](#synchronization-process)
4. [Change Detection Mechanism](#change-detection-mechanism)
5. [Timestamp Mismatch Handling](#timestamp-mismatch-handling)
6. [Conflict Resolution](#conflict-resolution)
7. [Sync Loop Prevention](#sync-loop-prevention)
8. [Webhook Processing](#webhook-processing)
9. [Database Schema](#database-schema)
10. [Error Handling & Retry Logic](#error-handling--retry-logic)

---

## Architecture Overview

The ERP Sync system uses a **hub-and-spoke** architecture where a central sync engine manages bidirectional data flow between two Frappe/ERPNext instances.

```
┌──────────────────────────────────────────────────────────────┐
│                     SYNC ARCHITECTURE                        │
└──────────────────────────────────────────────────────────────┘

┌─────────────────┐                                ┌─────────────────┐
│   Cloud ERP     │                                │   Local ERP     │
│   (AWS EC2)     │                                │  (Your Machine) │
└────────┬────────┘                                └────────┬────────┘
         │                                                  │
         │ Webhooks (Real-time)                            │ Webhooks (Real-time)
         │                                                  │
         ▼                                                  ▼
    ┌────────────────────────────────────────────────────────────┐
    │              Webhook Server (Flask)                        │
    │  - Receives POST requests from both ERPs                   │
    │  - Validates webhook signatures                            │
    │  - Queues events for processing                            │
    └────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────────────────────┐
    │              Webhook Queue Processor                       │
    │  - Background thread                                       │
    │  - Processes queued webhook events                         │
    │  - Invokes sync engine for each event                      │
    └────────────────────┬───────────────────────────────────────┘
                         │
                         ▼
    ┌────────────────────────────────────────────────────────────┐
    │                  Sync Engine                               │
    │  - Determines sync direction                               │
    │  - Detects conflicts                                       │
    │  - Executes synchronization                                │
    │  - Handles errors and retries                              │
    └──────┬─────────────────────────────────────────────┬───────┘
           │                                             │
           ▼                                             ▼
    ┌──────────────┐                             ┌──────────────┐
    │ Frappe Client│                             │ Frappe Client│
    │  (Cloud API) │                             │  (Local API) │
    └──────┬───────┘                             └──────┬───────┘
           │                                             │
           └──────────────────┬──────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │   SQLite DB      │
                    │  - sync_records  │
                    │  - sync_logs     │
                    │  - conflicts     │
                    │  - webhook_queue │
                    └──────────────────┘
```

---

## Core Components

### 1. Frappe Client (`frappe_client.py`)

**Purpose**: Handles all API communication with Frappe/ERPNext instances.

**Key Methods**:
- `get_doc()`: Retrieve a single document
- `get_list()`: Retrieve multiple documents with filters
- `create_doc()`: Create a new document
- `update_doc()`: Update existing document (with timestamp mismatch handling)
- `delete_doc()`: Delete a document
- `calculate_hash()`: Generate MD5 hash of document for change detection

**Authentication**: Uses token-based authentication with API Key + Secret.

```python
headers = {
    'Authorization': f'token {api_key}:{api_secret}',
    'Content-Type': 'application/json'
}
```

### 2. Sync Engine (`sync_engine.py`)

**Purpose**: Core synchronization logic and orchestration.

**Key Methods**:
- `sync_document()`: Synchronize a single document
- `sync_doctype()`: Synchronize all documents of a DocType
- `sync_all_doctypes()`: Synchronize all configured DocTypes
- `_determine_sync_direction()`: Automatically determine which way to sync
- `_execute_sync()`: Perform the actual sync operation
- `_handle_conflict()`: Resolve conflicts using configured strategy
- `_clean_doc_for_sync()`: Remove system fields before syncing

### 3. Webhook Server (`webhook_server.py`)

**Purpose**: Receive real-time notifications from ERPs and queue them for processing.

**Components**:
- **Flask Web Server**: Listens on configured port (default: 5000)
- **Webhook Endpoints**:
  - `/webhook/cloud`: Receives webhooks from cloud ERP
  - `/webhook/local`: Receives webhooks from local ERP
  - `/health`: Health check endpoint
  - `/status`: Queue status endpoint
- **Background Queue Processor**: Thread that processes queued webhooks

### 4. Database Models (`models.py`)

**Purpose**: Track sync state, audit logs, and conflicts using SQLite.

**Tables**:
- `sync_records`: Current sync state for each document
- `sync_logs`: Audit trail of all sync operations
- `conflict_records`: Unresolved conflicts requiring manual intervention
- `webhook_queue`: Queue of webhook events to process

---

## Synchronization Process

### Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  SYNC PROCESS FLOW                          │
└─────────────────────────────────────────────────────────────┘

1. TRIGGER
   ├─ Webhook received (real-time)
   └─ Manual sync command

2. FETCH DOCUMENTS
   ├─ Get document from Cloud ERP
   └─ Get document from Local ERP

3. RETRIEVE SYNC RECORD
   ├─ Query sync_records table
   └─ Create new record if doesn't exist

4. DETERMINE SYNC DIRECTION
   ├─ Check if document exists on both sides
   ├─ Calculate MD5 hashes of current documents
   ├─ Compare with stored hashes in sync_records
   └─ Decision:
      ├─ 'none': No changes detected
      ├─ 'cloud_to_local': Cloud changed, local didn't
      ├─ 'local_to_cloud': Local changed, cloud didn't
      └─ 'conflict': Both changed since last sync

5. EXECUTE SYNC
   ├─ If 'none': Skip
   ├─ If 'cloud_to_local':
   │  ├─ Clean cloud document (remove system fields)
   │  ├─ Update/Create on local ERP
   │  └─ Update sync_records with new hashes & timestamps
   ├─ If 'local_to_cloud':
   │  ├─ Clean local document (remove system fields)
   │  ├─ Update/Create on cloud ERP
   │  └─ Update sync_records with new hashes & timestamps
   └─ If 'conflict':
      └─ Apply conflict resolution strategy

6. UPDATE SYNC STATE
   ├─ Mark sync as complete
   ├─ Update last_synced timestamp
   ├─ Reset retry_count if successful
   └─ Log operation in sync_logs

7. ERROR HANDLING
   ├─ Catch exceptions
   ├─ Log error in sync_records
   ├─ Increment retry_count
   └─ Queue for retry if needed
```

---

## Change Detection Mechanism

The system uses **MD5 hash-based change detection** to efficiently determine if a document has changed and needs syncing.

### How It Works

1. **Hash Calculation**:
   ```python
   def calculate_hash(doc_data: Dict, exclude_fields: List[str]) -> str:
       # Remove system fields that change on every save
       clean_data = {k: v for k, v in doc_data.items()
                    if k not in exclude_fields}

       # Sort keys for consistent hashing
       json_str = json.dumps(clean_data, sort_keys=True)

       # Calculate MD5 hash
       return hashlib.md5(json_str.encode()).hexdigest()
   ```

2. **Excluded Fields** (don't affect hash):
   - `modified`: Timestamp of last modification
   - `modified_by`: User who modified
   - `creation`: Creation timestamp
   - `owner`: Document owner
   - `idx`: Index field
   - Custom fields defined in `config.yaml`

3. **Sync Decision Logic**:

   ```python
   cloud_hash_current = calculate_hash(cloud_doc)
   local_hash_current = calculate_hash(local_doc)

   cloud_hash_stored = sync_record.sync_hash_cloud
   local_hash_stored = sync_record.sync_hash_local

   # Determine what changed
   if cloud_hash_current == cloud_hash_stored and local_hash_current == local_hash_stored:
       # Neither changed
       direction = 'none'

   elif cloud_hash_current != cloud_hash_stored and local_hash_current == local_hash_stored:
       # Only cloud changed
       direction = 'cloud_to_local'

   elif cloud_hash_current == cloud_hash_stored and local_hash_current != local_hash_stored:
       # Only local changed
       direction = 'local_to_cloud'

   else:
       # Both changed - CONFLICT
       direction = 'conflict'
   ```

4. **Benefits**:
   - **Efficient**: No need to compare every field
   - **Accurate**: Detects any data change
   - **Fast**: MD5 hash calculation is quick
   - **Reliable**: Catches even small changes

---

## Timestamp Mismatch Handling

### The Problem

Frappe/ERPNext implements **optimistic locking** using the `modified` timestamp field. When you update a document:

1. You send the document data including the `modified` timestamp you read
2. Frappe checks if this timestamp matches the current timestamp in the database
3. If they don't match, someone else modified the document in the meantime
4. Frappe throws a **TimestampMismatchError** to prevent overwriting changes

**Example Error**:
```
frappe.exceptions.TimestampMismatchError: Document has been modified after you have opened it
```

### The Solution

Our system handles this automatically with a **retry mechanism**:

```python
def update_doc(self, doctype, docname, doc_data, retry_on_timestamp_mismatch=True):
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        try:
            # If retrying, fetch the latest version first
            if retry_count > 0:
                latest_doc = self.get_doc(doctype, docname)
                # Use the current timestamp
                doc_data['modified'] = latest_doc.get('modified')

            # Attempt update
            response = self.session.put(url, json=doc_data)
            response.raise_for_status()
            return response.json().get('data')

        except HTTPError as e:
            # Check if it's a timestamp mismatch error
            error_message = extract_error_message(e)

            if is_timestamp_error(error_message):
                retry_count += 1
                print(f"WARNING: Timestamp mismatch, retrying ({retry_count}/{max_retries})...")
                continue
            else:
                raise

    raise Exception("Failed after max retries")
```

### How It Works

**Attempt 1**: Try update with current data
```
Cloud Doc (modified: 2025-11-18 10:00:00)
    ↓
Update Request (modified: 2025-11-18 10:00:00)
    ↓
ERROR: ERROR: Timestamp mismatch (someone edited at 10:05:00)
```

**Attempt 2**: Fetch latest and retry
```
Fetch Latest Doc (modified: 2025-11-18 10:05:00)
    ↓
Update Request (modified: 2025-11-18 10:05:00)
    ↓
SUCCESS: SUCCESS: Timestamps match!
```

### Error Detection

The system detects timestamp mismatch errors by checking for these keywords in the error message:
- `"timestamp mismatch"`
- `"document has been modified"`
- `"has been modified after you have opened it"`

### Retry Strategy

- **Max Retries**: 3 attempts
- **Fetch Latest**: Before each retry, fetch the latest document version
- **Update Timestamp**: Use the latest `modified` timestamp
- **Preserve Data**: Keep your data changes, only update the timestamp

### Benefits

1. **Automatic Recovery**: No manual intervention needed
2. **Data Safety**: Ensures you're updating the latest version
3. **Concurrent Sync**: Multiple webhooks can sync simultaneously
4. **User Friendly**: Silent handling with informative logging

---

## Conflict Resolution

A **conflict** occurs when the same document is modified on both Cloud and Local ERPs between sync operations.

### Conflict Detection

```python
# Scenario: Both systems modified the document
cloud_changed = (cloud_hash_current != cloud_hash_stored)
local_changed = (local_hash_current != local_hash_stored)

if cloud_changed and local_changed:
    # CONFLICT DETECTED!
    create_conflict_record()
    apply_resolution_strategy()
```

### Resolution Strategies

#### 1. Latest Timestamp (Default)

The most recently modified version wins.

```python
if conflict_resolution == 'latest_timestamp':
    cloud_time = parse_datetime(cloud_doc['modified'])
    local_time = parse_datetime(local_doc['modified'])

    if cloud_time > local_time:
        # Cloud is newer
        direction = 'cloud_to_local'
    else:
        # Local is newer
        direction = 'local_to_cloud'
```

**Pros**: Fair, automatic, based on actual edit time
**Cons**: Doesn't consider content importance

#### 2. Cloud Wins

Cloud version always takes precedence.

```python
if conflict_resolution == 'cloud_wins':
    direction = 'cloud_to_local'
```

**Pros**: Simple, predictable
**Cons**: Local changes may be lost
**Use Case**: Cloud is primary/production system

#### 3. Local Wins

Local version always takes precedence.

```python
if conflict_resolution == 'local_wins':
    direction = 'local_to_cloud'
```

**Pros**: Simple, predictable
**Cons**: Cloud changes may be lost
**Use Case**: Local is primary/development system

#### 4. Manual Resolution

Conflicts are recorded and require manual intervention.

```python
if conflict_resolution == 'manual':
    # Save conflict to database
    conflict = ConflictRecord(
        doctype=doctype,
        docname=docname,
        cloud_data=json.dumps(cloud_doc),
        local_data=json.dumps(local_doc),
        resolved=False
    )
    db.add(conflict)

    # Do not sync automatically
    return False, "Conflict requires manual resolution"
```

**Pros**: Maximum control, no data loss
**Cons**: Requires human review
**Use Case**: Critical data, complex business logic

### Conflict Records

All conflicts are logged in the `conflict_records` table:

```sql
CREATE TABLE conflict_records (
    id INTEGER PRIMARY KEY,
    doctype VARCHAR(200),
    docname VARCHAR(200),
    cloud_data TEXT,  -- Full cloud document as JSON
    local_data TEXT,  -- Full local document as JSON
    cloud_modified DATETIME,
    local_modified DATETIME,
    resolved BOOLEAN DEFAULT FALSE,
    resolution VARCHAR(50),  -- How it was resolved
    resolved_at DATETIME,
    created_at DATETIME
);
```

### Viewing Conflicts

```bash
# List all unresolved conflicts
python main.py conflicts

# Output:
# Unresolved Conflicts: 2
#
# 1. Customer/CUST-00123
#    Cloud modified: 2025-11-18 10:30:00
#    Local modified: 2025-11-18 10:31:00
#
# 2. Item/ITEM-00456
#    Cloud modified: 2025-11-18 11:00:00
#    Local modified: 2025-11-18 11:05:00
```

---

## Sync Loop Prevention

**Sync loops** occur when a change triggers a sync, which triggers another webhook, which triggers another sync, infinitely.

### Prevention Mechanisms

#### 1. Document Hashing

Before syncing, we check if the document actually changed:

```python
# Calculate hash after sync
new_hash = calculate_hash(synced_doc)

# Store in sync_records
sync_record.sync_hash_cloud = new_hash
sync_record.sync_hash_local = new_hash

# Next webhook arrives
current_hash = calculate_hash(current_doc)

if current_hash == sync_record.sync_hash_cloud:
    # No actual change - skip sync
    return 'none'
```

#### 2. Sync Lock

Prevent concurrent syncs of the same document:

```python
if sync_record.is_syncing:
    return False, "Document is already being synced"

# Set lock
sync_record.is_syncing = True
db.commit()

try:
    # Perform sync
    execute_sync()
finally:
    # Release lock
    sync_record.is_syncing = False
    db.commit()
```

#### 3. Last Sync Timestamp

Track when each document was last synced:

```python
sync_record.last_synced = datetime.utcnow()

# If webhook arrives immediately after sync, we can skip
if (current_time - sync_record.last_synced) < timedelta(seconds=5):
    # Likely our own change
    if hash_matches:
        return 'none'
```

#### 4. Webhook Source Tracking

Know which system triggered the webhook:

```python
# Webhook from cloud
if source == 'cloud':
    # Sync cloud → local
    direction = 'cloud_to_local'

# Webhook from local
if source == 'local':
    # Sync local → cloud
    direction = 'local_to_cloud'
```

This ensures we don't sync back to the source system.

### Example Scenario

```
Step 1: User edits Customer on Cloud
    └─> Cloud modified = 10:00:00, hash = ABC123

Step 2: Cloud sends webhook
    └─> Webhook server receives: source='cloud', doctype='Customer'

Step 3: Sync engine processes
    └─> Fetches from Cloud (hash = ABC123)
    └─> Fetches from Local (hash = XYZ789)
    └─> Compares: cloud_hash ≠ local_hash → sync needed
    └─> Direction: cloud_to_local

Step 4: Update Local ERP
    └─> Local now has: hash = ABC123, modified = 10:00:05

Step 5: Local sends webhook (because document changed)
    └─> Webhook server receives: source='local', doctype='Customer'

Step 6: Sync engine processes again
    └─> Fetches from Local (hash = ABC123)
    └─> Fetches from Cloud (hash = ABC123)
    └─> Compares: cloud_hash == local_hash → NO SYNC NEEDED
    └─> Direction: 'none'
    └─> SUCCESS: Loop prevented!
```

---

## Webhook Processing

### Webhook Payload

When a document changes in Frappe, it sends a webhook POST request:

```json
{
  "doctype": "Customer",
  "name": "CUST-00123",
  "action": "save",
  "doc": {
    "name": "CUST-00123",
    "customer_name": "John Doe",
    "modified": "2025-11-18 10:30:00",
    ...
  }
}
```

### Webhook Signature Validation

Webhooks are secured with HMAC-SHA256 signatures:

```python
def verify_webhook_signature(payload: bytes, signature: str) -> bool:
    expected = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, expected)
```

### Queue Processing

Webhooks are queued to handle high throughput:

```
Webhook Arrives
    ↓
Add to webhook_queue table (processed=False)
    ↓
HTTP 200 Response (immediate)
    ↓
Background Thread picks up
    ↓
Mark as processing=True
    ↓
Invoke sync_engine.sync_document()
    ↓
Mark as processed=True, processed_at=now()
```

### Queue Processor Loop

```python
def process_webhook_queue():
    while True:
        # Get unprocessed webhooks
        webhooks = db.query(WebhookQueue).filter_by(
            processed=False,
            processing=False
        ).limit(10).all()

        for webhook in webhooks:
            # Mark as processing
            webhook.processing = True
            db.commit()

            # Determine direction based on source
            if webhook.source == 'cloud':
                direction = 'cloud_to_local'
            else:
                direction = 'local_to_cloud'

            # Sync the document
            sync_engine.sync_document(
                webhook.doctype,
                webhook.docname,
                direction=direction
            )

            # Mark as complete
            webhook.processed = True
            webhook.processing = False
            webhook.processed_at = datetime.utcnow()
            db.commit()

        # Sleep before next iteration
        time.sleep(2)
```

---

## Database Schema

### sync_records

Tracks the current sync state for each document.

```sql
CREATE TABLE sync_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctype VARCHAR(200) NOT NULL,
    docname VARCHAR(200) NOT NULL,

    -- Timestamps
    cloud_modified DATETIME,
    local_modified DATETIME,
    last_synced DATETIME,

    -- Change detection
    sync_hash_cloud VARCHAR(64),  -- MD5 hash of cloud version
    sync_hash_local VARCHAR(64),  -- MD5 hash of local version
    sync_direction VARCHAR(20),   -- Last sync direction

    -- Status tracking
    is_syncing BOOLEAN DEFAULT FALSE,
    sync_status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_doctype_docname (doctype, docname)
);
```

### sync_logs

Audit trail of all sync operations.

```sql
CREATE TABLE sync_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

    doctype VARCHAR(200) NOT NULL,
    docname VARCHAR(200) NOT NULL,

    action VARCHAR(50) NOT NULL,      -- sync, create, update, delete
    direction VARCHAR(20) NOT NULL,   -- cloud_to_local, local_to_cloud

    status VARCHAR(50) NOT NULL,      -- success, failed, conflict
    message TEXT,

    changes_json TEXT,                -- Optional: details of changes

    INDEX idx_timestamp (timestamp),
    INDEX idx_status (status)
);
```

### conflict_records

Stores conflicts for manual resolution.

```sql
CREATE TABLE conflict_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctype VARCHAR(200) NOT NULL,
    docname VARCHAR(200) NOT NULL,

    cloud_data TEXT NOT NULL,         -- Full cloud document as JSON
    local_data TEXT NOT NULL,         -- Full local document as JSON

    cloud_modified DATETIME NOT NULL,
    local_modified DATETIME NOT NULL,

    resolved BOOLEAN DEFAULT FALSE,
    resolution VARCHAR(50),            -- cloud_wins, local_wins, merge
    resolved_at DATETIME,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### webhook_queue

Queue of incoming webhook events.

```sql
CREATE TABLE webhook_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source VARCHAR(20) NOT NULL,      -- 'cloud' or 'local'

    doctype VARCHAR(200) NOT NULL,
    docname VARCHAR(200) NOT NULL,
    action VARCHAR(50) NOT NULL,      -- create, update, delete

    payload TEXT NOT NULL,            -- Full webhook payload as JSON

    processed BOOLEAN DEFAULT FALSE,
    processing BOOLEAN DEFAULT FALSE,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    processed_at DATETIME,

    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    INDEX idx_processed (processed),
    INDEX idx_created_at (created_at)
);
```

---

## Error Handling & Retry Logic

### Error Categories

1. **Network Errors**: Connection failures, timeouts
2. **Authentication Errors**: Invalid API credentials
3. **Permission Errors**: User doesn't have access
4. **Timestamp Mismatch**: Covered in detail above
5. **Data Validation Errors**: Invalid data from source
6. **Conflict Errors**: Both systems modified document

### Retry Strategy

```python
# Configuration in config.yaml
retry:
  max_attempts: 3
  backoff_seconds: 5
```

**Exponential Backoff**:
```python
def retry_with_backoff(func, max_attempts=3, backoff=5):
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt == max_attempts - 1:
                raise

            wait_time = backoff * (2 ** attempt)
            print(f"Retry {attempt+1}/{max_attempts} in {wait_time}s...")
            time.sleep(wait_time)
```

### Error Tracking

All errors are recorded in `sync_records`:

```python
sync_record.sync_status = 'error'
sync_record.error_message = str(e)
sync_record.retry_count += 1
```

### Retry Limits

Documents with too many failures are flagged:

```python
if sync_record.retry_count > max_retries:
    sync_record.sync_status = 'failed'
    send_alert(f"Document {doctype}/{docname} has failed {max_retries} times")
```

---

## Performance Considerations

### Batch Processing

When syncing large numbers of documents:

```python
# Config
batch_size: 50

# Implementation
for i in range(0, total_docs, batch_size):
    batch = docs[i:i+batch_size]
    for doc in batch:
        sync_document(doc)
    time.sleep(1)  # Breathe between batches
```

### Parallel Processing

Multiple webhooks can be processed simultaneously:

```python
# Flask server runs with threaded=True
app.run(threaded=True)

# Queue processor handles up to 10 webhooks at once
webhooks = db.query(WebhookQueue).limit(10).all()
```

### Database Indexing

Key indexes for performance:

```python
# Fast lookup by document
INDEX idx_doctype_docname ON sync_records(doctype, docname)

# Fast filtering by status
INDEX idx_sync_status ON sync_records(sync_status)

# Fast time-based queries
INDEX idx_timestamp ON sync_logs(timestamp)
```

---

## Security Considerations

1. **API Credentials**: Stored in `.env` (not committed to git)
2. **Webhook Secrets**: HMAC signature validation
3. **HTTPS**: Use HTTPS in production for all API calls
4. **Access Control**: API keys should have minimum required permissions
5. **Audit Logging**: All operations logged in `sync_logs`

---

## Monitoring & Debugging

### Log Files

```bash
# Application log
tail -f erpsync.log

# Webhook server output
python main.py webhook  # See real-time webhook processing
```

### Database Queries

```sql
-- Recent sync operations
SELECT * FROM sync_logs ORDER BY timestamp DESC LIMIT 20;

-- Failed syncs
SELECT * FROM sync_records WHERE sync_status = 'error';

-- Pending webhooks
SELECT * FROM webhook_queue WHERE processed = FALSE;

-- Conflict summary
SELECT doctype, COUNT(*) FROM conflict_records
WHERE resolved = FALSE
GROUP BY doctype;
```

### Status Commands

```bash
# Overall status
python main.py status

# Conflicts
python main.py conflicts

# Diagnostics
python troubleshoot.py
```

---

## Summary

The ERP Sync system provides robust, bidirectional synchronization through:

1. **MD5 hash-based change detection**
2. **Automatic timestamp mismatch handling**
3. **Configurable conflict resolution**
4. **Sync loop prevention**
5. **Webhook-based real-time sync**
6. **Comprehensive error handling**
7. **Audit logging**
8. **SQLite state tracking**

This architecture ensures data consistency while handling edge cases and errors gracefully.
