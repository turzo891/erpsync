# ERP Sync - Django Implementation Guide

This version of ERP Sync has been rewritten using Django framework instead of Flask. This guide explains the Django-specific features and usage.

## Table of Contents

1. [What Changed](#what-changed)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Django Management Commands](#django-management-commands)
5. [Running the Server](#running-the-server)
6. [Django Admin Interface](#django-admin-interface)
7. [API Endpoints](#api-endpoints)
8. [Background Task Processing](#background-task-processing)
9. [Docker Deployment](#docker-deployment)
10. [Production Deployment](#production-deployment)

---

## What Changed

### From Flask to Django

**Previous (Flask)**:
- Flask web framework for webhooks
- SQLAlchemy for database ORM
- Custom CLI tool (main.py)
- Background threading for webhook processing

**New (Django)**:
- Django web framework with full MVC architecture
- Django ORM for database management
- Django management commands
- Django admin interface for database management
- Production-ready with Gunicorn

### Benefits of Django Version

- **Admin Interface**: Built-in web interface to manage sync records, logs, and conflicts
- **Better ORM**: More powerful database queries and relationships
- **Production Ready**: Better suited for large-scale deployments
- **Extensibility**: Easy to add custom features and APIs
- **Battle-tested**: Django is proven in enterprise environments

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                  DJANGO APPLICATION                           │
└──────────────────────────────────────────────────────────────┘

erpsync_project/          # Django project (settings, URLs, WSGI)
├── settings.py           # Configuration
├── urls.py               # URL routing
├── wsgi.py              # WSGI application
└── asgi.py              # ASGI application (async)

syncengine/              # Django app (sync functionality)
├── models.py            # Django ORM models
├── views.py             # Webhook endpoints
├── urls.py              # App URLs
├── admin.py             # Django admin configuration
└── management/
    └── commands/        # Django management commands
        ├── test_connections.py
        ├── sync.py
        ├── process_webhooks.py
        ├── show_status.py
        └── show_conflicts.py

frappe_client.py         # Frappe API client (unchanged)
sync_engine.py           # Sync logic (unchanged)
config.yaml              # Sync rules configuration
```

---

## Installation

### 1. Install Python Dependencies

```bash
cd /Users/spoofing/Documents/erpsync

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Django and dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit configuration
nano .env
```

Add your credentials:
```env
# Cloud ERP
CLOUD_ERP_URL=https://your-cloud-erp.com
CLOUD_API_KEY=your_cloud_api_key
CLOUD_API_SECRET=your_cloud_api_secret

# Local ERP
LOCAL_ERP_URL=http://localhost:8000
LOCAL_API_KEY=your_local_api_key
LOCAL_API_SECRET=your_local_api_secret

# Django Settings
DJANGO_SECRET_KEY=your-long-random-secret-key-here
DEBUG=False
ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Webhook Secret
WEBHOOK_SECRET=your_secure_webhook_secret
```

### 3. Initialize Django Database

```bash
# Run Django migrations
python manage.py migrate

# Create superuser for Django admin
python manage.py createsuperuser
```

### 4. Test Connections

```bash
python manage.py test_connections
```

---

## Django Management Commands

Django management commands replace the old `main.py` CLI tool.

### Test Connections

```bash
python manage.py test_connections
```

### Run Sync

```bash
# Sync all DocTypes
python manage.py sync

# Sync specific DocType
python manage.py sync --doctype Customer

# Sync specific document
python manage.py sync --doctype Customer --docname "CUST-00001"

# Force sync direction
python manage.py sync --doctype Customer --direction cloud_to_local

# Limit number of documents
python manage.py sync --limit 50
```

### Show Status

```bash
python manage.py show_status
```

### Show Conflicts

```bash
# Show unresolved conflicts
python manage.py show_conflicts

# Show all conflicts (including resolved)
python manage.py show_conflicts --all
```

### Process Webhook Queue

```bash
# Run continuously (background worker)
python manage.py process_webhooks

# Process once and exit
python manage.py process_webhooks --once

# Custom interval (default: 2 seconds)
python manage.py process_webhooks --interval 5
```

---

## Running the Server

### Development Server

```bash
# Run Django development server
python manage.py runserver 0.0.0.0:8000
```

This starts the webhook server at `http://localhost:8000`

**In another terminal**, run the webhook processor:
```bash
python manage.py process_webhooks
```

### Production Server (Gunicorn)

```bash
# Install gunicorn (already in requirements.txt)
pip install gunicorn

# Run with gunicorn
gunicorn erpsync_project.wsgi:application --bind 0.0.0.0:8000 --workers 3

# With access logging
gunicorn erpsync_project.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 3 \
  --access-logfile - \
  --error-logfile -
```

### Running Both Server and Processor

**Option 1: Multiple terminals**
```bash
# Terminal 1: Web server
gunicorn erpsync_project.wsgi:application --bind 0.0.0.0:8000 --workers 3

# Terminal 2: Webhook processor
python manage.py process_webhooks
```

**Option 2: Using supervisord** (see Production Deployment section)

---

## Django Admin Interface

Django provides a built-in web interface to manage your data.

### Access Admin

1. Create superuser (if not already done):
   ```bash
   python manage.py createsuperuser
   ```

2. Start server:
   ```bash
   python manage.py runserver
   ```

3. Open browser to: `http://localhost:8000/admin`

4. Login with your superuser credentials

### Available Admin Features

- **Sync Records**: View/edit sync state for each document
- **Sync Logs**: Browse complete audit trail
- **Conflict Records**: View and resolve conflicts
- **Webhook Queue**: Monitor webhook processing queue

### Admin Screenshots

**Sync Records**:
- Filter by doctype, status
- Search by docname
- View sync hashes, timestamps
- See error messages

**Sync Logs**:
- Browse all sync operations
- Filter by success/failure
- Date hierarchy browsing

**Conflicts**:
- View conflict data (cloud vs local)
- Mark as resolved
- See resolution method

---

## API Endpoints

### Webhook Endpoints

**Cloud Webhook**:
```
POST /webhook/cloud
```

**Local Webhook**:
```
POST /webhook/local
```

Both endpoints:
- Accept JSON payload from Frappe webhooks
- Verify HMAC signature
- Queue event for processing
- Return JSON response

### Health & Status Endpoints

**Health Check**:
```
GET /health
```

Response:
```json
{
  "status": "healthy",
  "service": "erpsync-django-server",
  "timestamp": "2025-11-19T10:30:00Z"
}
```

**Queue Status**:
```
GET /status
```

Response:
```json
{
  "status": "running",
  "pending_webhooks": 5,
  "processing_webhooks": 1,
  "timestamp": "2025-11-19T10:30:00Z"
}
```

---

## Background Task Processing

The webhook processor runs as a background worker that continuously processes the webhook queue.

### Running the Processor

**Development**:
```bash
python manage.py process_webhooks
```

**Production** (see Production Deployment section for systemd/supervisor setup)

### How It Works

1. Webhooks arrive at `/webhook/cloud` or `/webhook/local`
2. Django view adds them to `WebhookQueue` model
3. Background processor picks up unprocessed webhooks
4. Processes each webhook using the sync engine
5. Updates webhook status and logs results

### Monitoring

```bash
# Check queue status via API
curl http://localhost:8000/status

# Check via Django admin
# Go to: http://localhost:8000/admin/syncengine/webhookqueue/

# Check via management command
python manage.py show_status
```

---

## Docker Deployment

### Quick Start with Docker

```bash
# Build image
docker compose build

# Run migrations
docker compose run --rm erpsync python manage.py migrate

# Create superuser
docker compose run --rm erpsync python manage.py createsuperuser

# Start services
docker compose up -d

# View logs
docker compose logs -f
```

### Docker Compose Services

The Django version runs two processes:

1. **Web Server** (Gunicorn): Handles webhook HTTP requests
2. **Webhook Processor**: Background worker processing queue

**Option A: Single container with multiple commands**

Create `docker-compose.yml`:
```yaml
version: '3.8'

services:
  web:
    build: .
    container_name: erpsync-web
    restart: unless-stopped
    env_file: .env
    ports:
      - "8000:8000"
    volumes:
      - ./sync_state.db:/app/sync_state.db
      - ./config.yaml:/app/config.yaml:ro
    command: gunicorn erpsync_project.wsgi:application --bind 0.0.0.0:8000 --workers 3

  processor:
    build: .
    container_name: erpsync-processor
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./sync_state.db:/app/sync_state.db
      - ./config.yaml:/app/config.yaml:ro
    command: python manage.py process_webhooks
```

Start both:
```bash
docker compose up -d
```

---

## Production Deployment

### Using Systemd

**Web Server Service** (`/etc/systemd/system/erpsync-web.service`):
```ini
[Unit]
Description=ERP Sync Django Web Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/erpsync
Environment="PATH=/opt/erpsync/venv/bin"
ExecStart=/opt/erpsync/venv/bin/gunicorn erpsync_project.wsgi:application --bind 0.0.0.0:8000 --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

**Webhook Processor Service** (`/etc/systemd/system/erpsync-processor.service`):
```ini
[Unit]
Description=ERP Sync Webhook Processor
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/erpsync
Environment="PATH=/opt/erpsync/venv/bin"
ExecStart=/opt/erpsync/venv/bin/python manage.py process_webhooks
Restart=always

[Install]
WantedBy=multi-user.target
```

**Enable and start**:
```bash
sudo systemctl enable erpsync-web erpsync-processor
sudo systemctl start erpsync-web erpsync-processor
sudo systemctl status erpsync-web erpsync-processor
```

### Using Supervisor

**Configuration** (`/etc/supervisor/conf.d/erpsync.conf`):
```ini
[program:erpsync-web]
command=/opt/erpsync/venv/bin/gunicorn erpsync_project.wsgi:application --bind 0.0.0.0:8000 --workers 3
directory=/opt/erpsync
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/erpsync/web.err.log
stdout_logfile=/var/log/erpsync/web.out.log

[program:erpsync-processor]
command=/opt/erpsync/venv/bin/python manage.py process_webhooks
directory=/opt/erpsync
user=www-data
autostart=true
autorestart=true
stderr_logfile=/var/log/erpsync/processor.err.log
stdout_logfile=/var/log/erpsync/processor.out.log

[group:erpsync]
programs=erpsync-web,erpsync-processor
```

**Control**:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start erpsync:*
sudo supervisorctl status erpsync:*
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name erpsync.example.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /opt/erpsync/staticfiles/;
    }
}
```

### Production Checklist

- [ ] Set `DEBUG=False` in `.env`
- [ ] Generate secure `DJANGO_SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Run `python manage.py collectstatic`
- [ ] Set up systemd/supervisor services
- [ ] Configure Nginx reverse proxy
- [ ] Enable SSL/TLS (Let's Encrypt)
- [ ] Set up database backups
- [ ] Configure log rotation
- [ ] Set up monitoring/alerts

---

## Comparison: Flask vs Django

### Command Comparison

| Task | Flask Version | Django Version |
|------|--------------|----------------|
| Test connections | `python main.py test` | `python manage.py test_connections` |
| Run sync | `python main.py sync` | `python manage.py sync` |
| Start webhook server | `python main.py webhook` | `python manage.py runserver` or `gunicorn ...` |
| Process webhooks | (Background thread) | `python manage.py process_webhooks` |
| Show status | `python main.py status` | `python manage.py show_status` |
| Show conflicts | `python main.py conflicts` | `python manage.py show_conflicts` |

### File Comparison

| Component | Flask Version | Django Version |
|-----------|--------------|----------------|
| Web framework | Flask (`webhook_server.py`) | Django (`syncengine/views.py`) |
| Database | SQLAlchemy (`models.py`) | Django ORM (`syncengine/models.py`) |
| CLI | Custom (`main.py`) | Django commands (`management/commands/`) |
| Configuration | `.env` | `.env` + `settings.py` |
| Entry point | `main.py` | `manage.py` |

---

## Summary

The Django version provides:

- Professional web framework with MVC architecture
- Built-in admin interface for database management
- Production-ready deployment with Gunicorn
- Better ORM and database management
- Django management commands for all operations
- Easier to extend and customize

The core sync logic (Frappe client and sync engine) remains unchanged, ensuring the same reliable synchronization between your ERP systems.

For questions or issues, refer to the main README.md or Django documentation at https://docs.djangoproject.com/
