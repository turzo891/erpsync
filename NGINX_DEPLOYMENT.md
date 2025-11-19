# ERP Sync - Nginx Deployment Guide

This guide provides complete instructions for deploying ERP Sync with Nginx as a reverse proxy in production.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Quick Installation](#quick-installation)
4. [Manual Installation](#manual-installation)
5. [SSL/TLS Setup](#ssltls-setup)
6. [Service Management](#service-management)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)
9. [Performance Tuning](#performance-tuning)
10. [Security Best Practices](#security-best-practices)

---

## Overview

This deployment uses:
- **Nginx** as reverse proxy (handles HTTP/HTTPS, static files)
- **Gunicorn** as WSGI server (runs Django application)
- **Systemd** for service management (auto-start, restart on failure)
- **Let's Encrypt** for SSL certificates (optional)

### Architecture

```
Internet
    ↓
Nginx (Port 80/443)
    ↓
Gunicorn (Port 8000)
    ↓
Django Application
    ↓
SQLite Database
```

---

## Prerequisites

### System Requirements

- **OS**: Ubuntu 20.04+ / Debian 10+ / CentOS 8+
- **RAM**: Minimum 1GB (2GB+ recommended)
- **Disk**: 10GB free space
- **Python**: 3.8 or higher
- **Network**: Port 80 and 443 open

### Required Software

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    certbot \
    python3-certbot-nginx \
    curl \
    git
```

### Domain Name

You need a domain name pointing to your server:
```
erpsync.yourdomain.com  →  Your Server IP
```

Update DNS A record:
```
Type: A
Name: erpsync
Value: YOUR_SERVER_IP
TTL: 3600
```

---

## Quick Installation

### Automated Setup

Use the provided installation script:

```bash
cd /path/to/erpsync

# Make script executable
chmod +x scripts/install-nginx-setup.sh

# Run installation (as root)
sudo ./scripts/install-nginx-setup.sh
```

The script will:
1. Create directories
2. Install dependencies
3. Setup Python virtual environment
4. Configure Django
5. Install Nginx configuration
6. Setup systemd services
7. Optionally configure SSL
8. Start all services

**Follow the prompts** and provide:
- Your domain name
- ERP API credentials (in .env file)
- Whether to setup SSL

---

## Manual Installation

If you prefer manual installation or need to customize:

### Step 1: Prepare Directories

```bash
# Create application directory
sudo mkdir -p /opt/erpsync
sudo mkdir -p /var/log/erpsync

# Create user (if not exists)
sudo useradd -r -s /bin/false -m -d /opt/erpsync erpsync || true

# Set permissions
sudo chown -R www-data:www-data /opt/erpsync
sudo chown -R www-data:www-data /var/log/erpsync
```

### Step 2: Copy Application Files

```bash
# Copy files to production directory
sudo rsync -av /path/to/erpsync/ /opt/erpsync/ --exclude venv --exclude '*.db'

# Set ownership
sudo chown -R www-data:www-data /opt/erpsync
```

### Step 3: Setup Python Environment

```bash
cd /opt/erpsync

# Create virtual environment
sudo -u www-data python3 -m venv venv

# Install dependencies
sudo -u www-data venv/bin/pip install --upgrade pip
sudo -u www-data venv/bin/pip install -r requirements.txt
```

### Step 4: Configure Django

```bash
# Copy environment file
sudo cp .env.example .env

# Edit configuration
sudo nano .env
```

Update these values:
```env
# Cloud ERP
CLOUD_ERP_URL=https://your-cloud-erp.com
CLOUD_API_KEY=your_api_key
CLOUD_API_SECRET=your_api_secret

# Local ERP
LOCAL_ERP_URL=http://your-local-erp:8000
LOCAL_API_KEY=your_api_key
LOCAL_API_SECRET=your_api_secret

# Django
DJANGO_SECRET_KEY=generate-long-random-string-here
DEBUG=False
ALLOWED_HOSTS=erpsync.yourdomain.com,localhost

# Webhook
WEBHOOK_SECRET=your_secure_random_secret
```

**Generate Django secret key**:
```bash
python3 -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### Step 5: Initialize Django

```bash
# Run migrations
sudo -u www-data /opt/erpsync/venv/bin/python manage.py migrate

# Collect static files
sudo -u www-data /opt/erpsync/venv/bin/python manage.py collectstatic --noinput

# Create superuser
sudo -u www-data /opt/erpsync/venv/bin/python manage.py createsuperuser
```

### Step 6: Install Nginx Configuration

```bash
# Copy Nginx config (HTTP-only initially)
sudo cp /opt/erpsync/nginx/erpsync-http-only.conf /etc/nginx/conf.d/erpsync.conf

# Update domain name
sudo sed -i 's/erpsync.yourdomain.com/your-actual-domain.com/g' /etc/nginx/conf.d/erpsync.conf

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

### Step 7: Install Systemd Services

```bash
# Copy service files
sudo cp /opt/erpsync/systemd/erpsync-gunicorn.service /etc/systemd/system/
sudo cp /opt/erpsync/systemd/erpsync-processor.service /etc/systemd/system/
sudo cp /opt/erpsync/systemd/erpsync.target /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable services
sudo systemctl enable erpsync-gunicorn.service
sudo systemctl enable erpsync-processor.service

# Start services
sudo systemctl start erpsync-gunicorn.service
sudo systemctl start erpsync-processor.service

# Check status
sudo systemctl status erpsync-gunicorn.service
sudo systemctl status erpsync-processor.service
```

### Step 8: Test Installation

```bash
# Test from server
curl http://localhost:8000/health

# Test through Nginx
curl http://your-domain.com/health

# Should return: {"status": "healthy", ...}
```

---

## SSL/TLS Setup

### Using Let's Encrypt (Recommended)

#### Install Certbot

```bash
sudo apt install certbot python3-certbot-nginx
```

#### Obtain Certificate

```bash
# Stop Nginx temporarily
sudo systemctl stop nginx

# Get certificate
sudo certbot certonly --standalone -d erpsync.yourdomain.com

# Or use Nginx plugin (if Nginx is running)
sudo certbot --nginx -d erpsync.yourdomain.com

# Start Nginx
sudo systemctl start nginx
```

#### Update Nginx Configuration

```bash
# Replace with SSL version
sudo cp /opt/erpsync/nginx/erpsync.conf /etc/nginx/conf.d/erpsync.conf

# Update domain
sudo sed -i 's/erpsync.yourdomain.com/your-actual-domain.com/g' /etc/nginx/conf.d/erpsync.conf

# Test configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx
```

#### Setup Auto-Renewal

Certbot automatically installs a cron job or systemd timer. Verify:

```bash
# Test renewal
sudo certbot renew --dry-run

# Check timer status
sudo systemctl status certbot.timer
```

### Using Custom SSL Certificate

If you have your own SSL certificate:

```bash
# Copy certificate files
sudo cp your-cert.pem /etc/ssl/certs/erpsync.pem
sudo cp your-key.pem /etc/ssl/private/erpsync-key.pem

# Set permissions
sudo chmod 644 /etc/ssl/certs/erpsync.pem
sudo chmod 600 /etc/ssl/private/erpsync-key.pem
```

Update Nginx config:
```nginx
ssl_certificate /etc/ssl/certs/erpsync.pem;
ssl_certificate_key /etc/ssl/private/erpsync-key.pem;
```

---

## Service Management

### Using systemctl Commands

```bash
# Start services
sudo systemctl start erpsync-gunicorn
sudo systemctl start erpsync-processor

# Stop services
sudo systemctl stop erpsync-gunicorn
sudo systemctl stop erpsync-processor

# Restart services
sudo systemctl restart erpsync-gunicorn
sudo systemctl restart erpsync-processor

# Check status
sudo systemctl status erpsync-gunicorn
sudo systemctl status erpsync-processor

# View logs
sudo journalctl -u erpsync-gunicorn -f
sudo journalctl -u erpsync-processor -f

# Enable auto-start on boot
sudo systemctl enable erpsync-gunicorn
sudo systemctl enable erpsync-processor
```

### Using Admin Helper Script

```bash
# Make script executable
sudo chmod +x /opt/erpsync/scripts/erpsync-admin.sh

# Create symlink for easy access
sudo ln -s /opt/erpsync/scripts/erpsync-admin.sh /usr/local/bin/erpsync-admin

# Available commands
erpsync-admin status          # Show service status
erpsync-admin start           # Start all services
erpsync-admin stop            # Stop all services
erpsync-admin restart         # Restart all services
erpsync-admin logs            # Show recent logs
erpsync-admin logs-follow     # Follow logs
erpsync-admin test            # Test ERP connections
erpsync-admin sync            # Run manual sync
erpsync-admin conflicts       # Show conflicts
erpsync-admin backup-db       # Backup database
```

---

## Monitoring

### Check Service Health

```bash
# Health endpoint
curl https://erpsync.yourdomain.com/health

# Status endpoint
curl https://erpsync.yourdomain.com/status
```

### View Logs

**Nginx Logs**:
```bash
# Access log
tail -f /var/log/nginx/erpsync.access.log

# Error log
tail -f /var/log/nginx/erpsync.error.log
```

**Application Logs**:
```bash
# Gunicorn
tail -f /var/log/erpsync/gunicorn-access.log
tail -f /var/log/erpsync/gunicorn-error.log

# Systemd journals
journalctl -u erpsync-gunicorn -f
journalctl -u erpsync-processor -f
```

### Monitor Resource Usage

```bash
# CPU and Memory
htop

# Disk space
df -h

# Nginx connections
sudo ss -tulpn | grep nginx

# Gunicorn workers
ps aux | grep gunicorn
```

### Log Rotation

Install log rotation configuration:

```bash
sudo cp /opt/erpsync/scripts/logrotate-erpsync /etc/logrotate.d/erpsync

# Test logrotate
sudo logrotate -d /etc/logrotate.d/erpsync
```

---

## Troubleshooting

### Service Won't Start

**Check logs**:
```bash
journalctl -u erpsync-gunicorn -n 50
journalctl -u erpsync-processor -n 50
```

**Common issues**:

1. **Permission errors**:
   ```bash
   sudo chown -R www-data:www-data /opt/erpsync
   sudo chown -R www-data:www-data /var/log/erpsync
   ```

2. **Port already in use**:
   ```bash
   sudo lsof -i :8000
   # Kill process using port or change port in systemd service
   ```

3. **Missing dependencies**:
   ```bash
   cd /opt/erpsync
   sudo -u www-data venv/bin/pip install -r requirements.txt
   ```

### Nginx 502 Bad Gateway

**Causes**:
- Gunicorn not running
- Wrong upstream address
- Firewall blocking connection

**Solutions**:
```bash
# Check if Gunicorn is running
sudo systemctl status erpsync-gunicorn

# Check Gunicorn is listening on correct port
sudo ss -tulpn | grep 8000

# Check Nginx error log
tail -f /var/log/nginx/erpsync.error.log

# Restart services
sudo systemctl restart erpsync-gunicorn
sudo systemctl restart nginx
```

### SSL Certificate Issues

**Certificate not found**:
```bash
# Check if certificate exists
sudo ls -la /etc/letsencrypt/live/erpsync.yourdomain.com/

# Re-obtain certificate
sudo certbot --nginx -d erpsync.yourdomain.com
```

**Certificate expired**:
```bash
# Renew certificate
sudo certbot renew

# Reload Nginx
sudo systemctl reload nginx
```

### Webhooks Not Working

**Check webhook queue**:
```bash
curl https://erpsync.yourdomain.com/status
```

**Test webhook manually**:
```bash
curl -X POST https://erpsync.yourdomain.com/webhook/cloud \
  -H "Content-Type: application/json" \
  -d '{"doctype":"Customer","name":"TEST-001","action":"save"}'
```

**Check processor logs**:
```bash
journalctl -u erpsync-processor -f
```

---

## Performance Tuning

### Gunicorn Workers

Adjust number of workers in `/etc/systemd/system/erpsync-gunicorn.service`:

**Formula**: (2 x CPU cores) + 1

```ini
# For 2 CPU cores:
--workers 5

# For 4 CPU cores:
--workers 9
```

Reload after changes:
```bash
sudo systemctl daemon-reload
sudo systemctl restart erpsync-gunicorn
```

### Nginx Optimization

Edit `/etc/nginx/conf.d/erpsync.conf`:

**Enable caching**:
```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=erpsync_cache:10m max_size=100m;

location /static/ {
    proxy_cache erpsync_cache;
    proxy_cache_valid 200 30d;
}
```

**Increase worker connections**:
Edit `/etc/nginx/nginx.conf`:
```nginx
worker_processes auto;
worker_connections 2048;
```

### Database Optimization

**Regular vacuuming** (SQLite):
```bash
sqlite3 /opt/erpsync/sync_state.db "VACUUM;"
```

**Create backup before vacuuming**:
```bash
erpsync-admin backup-db
```

---

## Security Best Practices

### 1. Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### 2. Restrict Nginx Access

Add IP whitelist in Nginx config:
```nginx
location /admin/ {
    allow 1.2.3.4;      # Your IP
    deny all;
}
```

### 3. Enable Fail2Ban

```bash
sudo apt install fail2ban

# Create filter for Django admin
sudo nano /etc/fail2ban/filter.d/django-admin.conf
```

Add:
```ini
[Definition]
failregex = Invalid login attempt from <HOST>
```

### 4. Regular Updates

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python packages
cd /opt/erpsync
sudo -u www-data venv/bin/pip install --upgrade -r requirements.txt

# Restart services
sudo systemctl restart erpsync-gunicorn
```

### 5. Backup Strategy

**Automated daily backup**:
```bash
# Add to crontab
sudo crontab -e

# Add line:
0 2 * * * /opt/erpsync/scripts/erpsync-admin.sh backup-db
```

**Offsite backup**:
```bash
# Sync to remote server
rsync -avz /opt/erpsync/backups/ user@backup-server:/backups/erpsync/
```

---

## Summary

You now have a production-ready ERP Sync deployment with:

- Nginx reverse proxy with SSL/TLS
- Gunicorn WSGI server
- Systemd service management
- Automated SSL renewal
- Log rotation
- Monitoring tools
- Admin helper scripts

For additional help, see:
- DJANGO_GUIDE.md
- WORKFLOW.md
- MECHANISM.md

Your ERP Sync system is ready for production!
