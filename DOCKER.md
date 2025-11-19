# ERP Sync - Docker Deployment Guide

This guide explains how to deploy and run the ERP Sync system using Docker and Docker Compose.

## Table of Contents

1. [Why Docker?](#why-docker)
2. [Prerequisites](#prerequisites)
3. [Quick Start](#quick-start)
4. [Configuration](#configuration)
5. [Docker Commands](#docker-commands)
6. [Volume Management](#volume-management)
7. [Networking](#networking)
8. [Production Deployment](#production-deployment)
9. [Troubleshooting](#troubleshooting)
10. [Advanced Usage](#advanced-usage)

---

## Why Docker?

Running ERP Sync in Docker provides several benefits:

- **Portability**: Run anywhere Docker is installed
- **Isolation**: Doesn't interfere with system packages
- **Consistency**: Same environment in dev and production
- **Easy Updates**: Pull new image and restart
- **Resource Control**: Limit CPU and memory usage
- **Easy Backup**: Just backup volumes
- **Auto-restart**: Container restarts on failure or reboot

---

## Prerequisites

### Install Docker

**Ubuntu/Debian**:
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt-get install docker-compose-plugin

# Add your user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**macOS**:
```bash
# Download and install Docker Desktop
# https://www.docker.com/products/docker-desktop

# Docker Compose is included in Docker Desktop
```

**Windows**:
```bash
# Download and install Docker Desktop
# https://www.docker.com/products/docker-desktop

# Docker Compose is included in Docker Desktop
```

**Verify Installation**:
```bash
docker --version
docker compose version
```

---

## Quick Start

### 1. Clone/Navigate to Project

```bash
cd /Users/spoofing/Documents/erpsync
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with your credentials
nano .env
```

**Required Configuration** in `.env`:
```env
# Cloud ERP
CLOUD_ERP_URL=https://your-cloud-erp.com
CLOUD_API_KEY=your_cloud_api_key
CLOUD_API_SECRET=your_cloud_api_secret

# Local ERP
LOCAL_ERP_URL=http://host.docker.internal:8000
LOCAL_API_KEY=your_local_api_key
LOCAL_API_SECRET=your_local_api_secret

# Webhook Server
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000
WEBHOOK_SECRET=your_secure_random_secret

# Sync Configuration
CONFLICT_RESOLUTION=latest_timestamp
```

**Important**: If your Local ERP is on the same machine as Docker:
- Use `http://host.docker.internal:8000` (macOS/Windows)
- Use `http://172.17.0.1:8000` (Linux)

### 3. Initialize Database

First, initialize the database:

```bash
# Build the image
docker compose build

# Initialize database
docker compose run --rm erpsync python main.py init
```

### 4. Test Connections

```bash
docker compose run --rm erpsync python main.py test
```

**Expected Output**:
```
[OK] Connected to Cloud (https://your-cloud-erp.com) as user: Administrator
[OK] Connected to Local (http://host.docker.internal:8000) as user: Administrator
[OK] All connections successful
```

### 5. Start Webhook Server

```bash
# Start in background
docker compose up -d

# View logs
docker compose logs -f
```

**Expected Output**:
```
erpsync  | =============================================================
erpsync  | ERP Sync Webhook Server Starting...
erpsync  | =============================================================
erpsync  |
erpsync  | Webhook URLs:
erpsync  |   Cloud ERP → http://0.0.0.0:5000/webhook/cloud
erpsync  |   Local ERP → http://0.0.0.0:5000/webhook/local
erpsync  |
erpsync  | [OK] Connected to Cloud
erpsync  | [OK] Connected to Local
erpsync  | Webhook queue processor started
erpsync  |  * Running on http://0.0.0.0:5000
```

### 6. Verify It's Running

```bash
# Check container status
docker compose ps

# Check health
curl http://localhost:5000/health
```

**Success!** Your ERP Sync is now running in Docker.

---

## Configuration

### Environment Variables

All configuration is done through `.env` file, which is mounted into the container.

**Example `.env`**:
```env
# Cloud ERP Configuration
CLOUD_ERP_URL=https://cloud-erp.example.com
CLOUD_API_KEY=abc123...
CLOUD_API_SECRET=xyz789...

# Local ERP Configuration
LOCAL_ERP_URL=http://host.docker.internal:8000
LOCAL_API_KEY=def456...
LOCAL_API_SECRET=uvw012...

# Webhook Server Settings
WEBHOOK_HOST=0.0.0.0
WEBHOOK_PORT=5000
WEBHOOK_SECRET=your_secure_random_string

# Database
DATABASE_URL=sqlite:///sync_state.db

# Sync Settings
SYNC_DOCTYPES=Customer,Item,Sales Order,Purchase Order
CONFLICT_RESOLUTION=latest_timestamp

# Logging
LOG_LEVEL=INFO
LOG_FILE=/logs/erpsync.log
```

### DocType Configuration

Edit `config.yaml` to configure which DocTypes to sync:

```yaml
sync_rules:
  doctypes:
    - Customer
    - Supplier
    - Item
    - Sales Order
    - Purchase Order

  exclude_fields:
    - modified_by
    - creation
    - owner

  conflict_resolution: latest_timestamp

  retry:
    max_attempts: 3
    backoff_seconds: 5
```

### Port Configuration

Change webhook port in `.env`:
```env
WEBHOOK_PORT=8080
```

And update `docker-compose.yml`:
```yaml
ports:
  - "8080:5000"  # host:container
```

---

## Docker Commands

### Build & Start

```bash
# Build image
docker compose build

# Start services (detached)
docker compose up -d

# Start and view logs
docker compose up

# Rebuild and start
docker compose up -d --build
```

### Stop & Remove

```bash
# Stop services
docker compose stop

# Stop and remove containers
docker compose down

# Stop, remove containers and volumes
docker compose down -v
```

### View Logs

```bash
# View all logs
docker compose logs

# Follow logs (real-time)
docker compose logs -f

# Last 100 lines
docker compose logs --tail=100

# Logs for specific time
docker compose logs --since 30m
```

### Execute Commands

```bash
# Run sync manually
docker compose exec erpsync python main.py sync

# Check status
docker compose exec erpsync python main.py status

# View conflicts
docker compose exec erpsync python main.py conflicts

# Run diagnostics
docker compose exec erpsync python troubleshoot.py

# Open shell in container
docker compose exec erpsync /bin/bash

# Run one-off command
docker compose run --rm erpsync python main.py test
```

### Restart

```bash
# Restart all services
docker compose restart

# Restart specific service
docker compose restart erpsync
```

### Update

```bash
# Pull latest code changes
git pull  # if using git

# Rebuild and restart
docker compose up -d --build

# Or force recreate
docker compose up -d --force-recreate
```

---

## Volume Management

### Understanding Volumes

The Docker setup uses volumes for data persistence:

```yaml
volumes:
  # Database (must persist!)
  - ./sync_state.db:/app/sync_state.db

  # Configuration (read-only)
  - ./config.yaml:/app/config.yaml:ro
  - ./.env:/app/.env:ro

  # Logs
  - ./logs:/logs

  # Named volume for data
  - erpsync-data:/data
```

### Backup Database

```bash
# Method 1: Direct file copy (if using bind mount)
cp sync_state.db sync_state.db.backup.$(date +%Y%m%d_%H%M%S)

# Method 2: Copy from container
docker compose cp erpsync:/app/sync_state.db ./backup/sync_state.db

# Method 3: Using docker exec
docker compose exec erpsync sqlite3 /app/sync_state.db ".backup '/data/backup.db'"
docker compose cp erpsync:/data/backup.db ./backup/
```

### Restore Database

```bash
# Stop container first
docker compose stop

# Restore database file
cp backup/sync_state.db.backup sync_state.db

# Start container
docker compose up -d
```

### View Logs

```bash
# Logs are in ./logs directory
tail -f logs/erpsync.log

# Or inside container
docker compose exec erpsync tail -f /logs/erpsync.log
```

### Clean Up Volumes

```bash
# Remove all stopped containers and volumes
docker compose down -v

# Remove specific volume
docker volume rm erpsync_erpsync-data

# Prune all unused volumes (careful!)
docker volume prune
```

---

## Networking

### Accessing Local Services from Docker

When your local ERPNext is running on the **same machine** as Docker:

**macOS/Windows**:
```env
LOCAL_ERP_URL=http://host.docker.internal:8000
```

**Linux**:
```env
# Option 1: Use Docker bridge IP
LOCAL_ERP_URL=http://172.17.0.1:8000

# Option 2: Use host network mode (in docker-compose.yml)
network_mode: host
```

### Exposing Webhook Server

The webhook server runs on port 5000 inside the container, mapped to host:

```yaml
ports:
  - "5000:5000"  # host_port:container_port
```

**Access from**:
- **Host machine**: `http://localhost:5000`
- **LAN**: `http://YOUR_HOST_IP:5000`
- **Internet**: Requires port forwarding or reverse proxy

### Using Behind Reverse Proxy (Nginx)

**nginx.conf**:
```nginx
server {
    listen 80;
    server_name erpsync.example.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Using with SSL (HTTPS)

**docker-compose.yml** with Traefik:
```yaml
services:
  erpsync:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.erpsync.rule=Host(`erpsync.example.com`)"
      - "traefik.http.routers.erpsync.tls=true"
      - "traefik.http.routers.erpsync.tls.certresolver=letsencrypt"
```

---

## Production Deployment

### Production docker-compose.yml

```yaml
version: '3.8'

services:
  erpsync:
    image: erpsync:latest
    container_name: erpsync-prod
    restart: always  # Always restart on failure

    env_file:
      - .env.production

    ports:
      - "127.0.0.1:5000:5000"  # Bind to localhost only (use reverse proxy)

    volumes:
      - /opt/erpsync/sync_state.db:/app/sync_state.db
      - /opt/erpsync/config.yaml:/app/config.yaml:ro
      - /opt/erpsync/.env.production:/app/.env:ro
      - /var/log/erpsync:/logs

    # Resource limits for production
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 1G
        reservations:
          cpus: '1.0'
          memory: 512M

    # Health check
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 60s
      timeout: 10s
      retries: 3
      start_period: 30s

    # Logging with rotation
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "10"

    # Security
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
```

### Deployment Steps

1. **Prepare Production Server**:
   ```bash
   # Create directories
   sudo mkdir -p /opt/erpsync /var/log/erpsync
   sudo chown $USER:$USER /opt/erpsync /var/log/erpsync

   # Copy files
   cd /opt/erpsync
   git clone <your-repo> .  # or rsync files
   ```

2. **Configure**:
   ```bash
   cp .env.example .env.production
   nano .env.production
   ```

3. **Initialize**:
   ```bash
   docker compose -f docker-compose.prod.yml build
   docker compose -f docker-compose.prod.yml run --rm erpsync python main.py init
   docker compose -f docker-compose.prod.yml run --rm erpsync python main.py test
   ```

4. **Start**:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

5. **Setup Monitoring**:
   ```bash
   # Add to crontab
   */5 * * * * docker compose -f /opt/erpsync/docker-compose.prod.yml exec erpsync python main.py status | grep -i error && mail -s "ERP Sync Errors" admin@example.com
   ```

### Auto-start on Boot

Docker Compose with `restart: unless-stopped` will automatically start on boot.

**Verify**:
```bash
# Reboot server
sudo reboot

# After reboot, check
docker compose ps
```

### Backup Strategy

**Automated Backups**:
```bash
#!/bin/bash
# /opt/erpsync/backup.sh

BACKUP_DIR="/opt/erpsync/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
docker compose -f /opt/erpsync/docker-compose.prod.yml exec -T erpsync \
  sqlite3 /app/sync_state.db ".backup '/tmp/backup.db'"

docker compose -f /opt/erpsync/docker-compose.prod.yml cp \
  erpsync:/tmp/backup.db $BACKUP_DIR/sync_state_$DATE.db

# Keep only last 30 days
find $BACKUP_DIR -name "sync_state_*.db" -mtime +30 -delete

# Backup config
cp /opt/erpsync/config.yaml $BACKUP_DIR/config_$DATE.yaml
```

**Crontab**:
```bash
# Daily backup at 2 AM
0 2 * * * /opt/erpsync/backup.sh >> /var/log/erpsync/backup.log 2>&1
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker compose logs erpsync

# Check if port is in use
sudo lsof -i :5000

# Check container status
docker compose ps
docker inspect erpsync
```

### Can't Connect to Local ERP

**Issue**: Container can't reach local ERPNext.

**Solution**:
```bash
# Test from inside container
docker compose exec erpsync curl http://host.docker.internal:8000

# On Linux, try
docker compose exec erpsync curl http://172.17.0.1:8000

# Check if local ERP is running
curl http://localhost:8000
```

### Database Permission Issues

```bash
# Fix permissions
chmod 666 sync_state.db

# Or run container as your user
docker compose run --user $(id -u):$(id -g) erpsync python main.py init
```

### High Memory Usage

```bash
# Check resource usage
docker stats erpsync

# Limit memory in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 512M
```

### Logs Not Appearing

```bash
# Check log directory permissions
ls -la logs/

# Create if doesn't exist
mkdir -p logs
chmod 755 logs

# Check environment variable
docker compose exec erpsync env | grep LOG
```

### Container Keeps Restarting

```bash
# View last crash logs
docker compose logs --tail=100 erpsync

# Check health status
docker inspect --format='{{json .State.Health}}' erpsync | jq

# Disable auto-restart for debugging
docker compose up --no-start
docker compose start
docker compose logs -f
```

---

## Advanced Usage

### Multi-Stage Build (Smaller Image)

**Dockerfile.optimized**:
```dockerfile
# Build stage
FROM python:3.11-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application
COPY . .

EXPOSE 5000
CMD ["python", "main.py", "webhook"]
```

Build:
```bash
docker build -f Dockerfile.optimized -t erpsync:optimized .
```

### Using Docker Registry

```bash
# Tag image
docker tag erpsync:latest your-registry.com/erpsync:latest

# Push to registry
docker push your-registry.com/erpsync:latest

# Pull on production server
docker pull your-registry.com/erpsync:latest
```

### Running Multiple Sync Instances

**docker-compose.multi.yml**:
```yaml
version: '3.8'

services:
  erpsync-production:
    build: .
    container_name: erpsync-prod
    env_file: .env.production
    ports:
      - "5000:5000"
    volumes:
      - ./data/prod:/app/sync_state.db

  erpsync-staging:
    build: .
    container_name: erpsync-staging
    env_file: .env.staging
    ports:
      - "5001:5000"
    volumes:
      - ./data/staging:/app/sync_state.db
```

### Health Monitoring with Watchtower

Auto-update containers:

```yaml
services:
  watchtower:
    image: containrrr/watchtower
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    command: --interval 300  # Check every 5 minutes
```

### Integration with Portainer

Manage Docker through web UI:

```bash
docker run -d -p 9000:9000 --name portainer \
  --restart=always \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v portainer_data:/data \
  portainer/portainer-ce
```

Access at: `http://localhost:9000`

---

## Summary

### Quick Commands Reference

```bash
# Build and start
docker compose up -d --build

# View logs
docker compose logs -f

# Stop
docker compose stop

# Restart
docker compose restart

# Execute commands
docker compose exec erpsync python main.py status

# Backup database
docker compose cp erpsync:/app/sync_state.db ./backup/

# Remove everything
docker compose down -v
```

### Advantages of Docker Deployment

- Isolated environment
- Easy deployment and updates
- Automatic restarts
- Resource limits
- Portable across servers
- Consistent environment
- Easy backup/restore

### Production Checklist

- [ ] Configure `.env.production` with credentials
- [ ] Set up reverse proxy (nginx/Traefik)
- [ ] Enable SSL/TLS
- [ ] Configure resource limits
- [ ] Set up automated backups
- [ ] Configure log rotation
- [ ] Set up monitoring/alerts
- [ ] Test failover/restart
- [ ] Document disaster recovery

---

Your ERP Sync is now running in Docker! 
