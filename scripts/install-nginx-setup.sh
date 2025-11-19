#!/bin/bash
# Installation script for ERP Sync with Nginx
# Run as root or with sudo

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "  ERP Sync - Nginx Setup Installation"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Please run as root or with sudo${NC}"
    exit 1
fi

# Variables
APP_DIR="/opt/erpsync"
LOG_DIR="/var/log/erpsync"
USER="www-data"
GROUP="www-data"
DOMAIN="erpsync.yourdomain.com"

echo "Configuration:"
echo "  Application Directory: $APP_DIR"
echo "  Log Directory: $LOG_DIR"
echo "  User/Group: $USER:$GROUP"
echo "  Domain: $DOMAIN"
echo ""
read -p "Continue with installation? (y/n) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
fi

# Create directories
echo -e "${YELLOW}[1/10] Creating directories...${NC}"
mkdir -p $APP_DIR
mkdir -p $LOG_DIR
mkdir -p /var/www/certbot

# Set ownership
chown -R $USER:$GROUP $APP_DIR
chown -R $USER:$GROUP $LOG_DIR

echo -e "${GREEN}[OK] Directories created${NC}"

# Install system dependencies
echo -e "${YELLOW}[2/10] Installing system dependencies...${NC}"
apt-get update
apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    nginx \
    certbot \
    python3-certbot-nginx \
    curl \
    git

echo -e "${GREEN}[OK] Dependencies installed${NC}"

# Copy application files
echo -e "${YELLOW}[3/10] Copying application files...${NC}"
echo "Please copy your ERP Sync files to $APP_DIR"
echo "Example: rsync -av /path/to/erpsync/ $APP_DIR/"
read -p "Press Enter after copying files..."

# Create Python virtual environment
echo -e "${YELLOW}[4/10] Creating Python virtual environment...${NC}"
cd $APP_DIR
sudo -u $USER python3 -m venv venv
echo -e "${GREEN}[OK] Virtual environment created${NC}"

# Install Python dependencies
echo -e "${YELLOW}[5/10] Installing Python dependencies...${NC}"
sudo -u $USER $APP_DIR/venv/bin/pip install --upgrade pip
sudo -u $USER $APP_DIR/venv/bin/pip install -r $APP_DIR/requirements.txt
echo -e "${GREEN}[OK] Python packages installed${NC}"

# Configure Django
echo -e "${YELLOW}[6/10] Configuring Django...${NC}"
if [ ! -f "$APP_DIR/.env" ]; then
    echo "Creating .env file..."
    cp $APP_DIR/.env.example $APP_DIR/.env
    echo -e "${YELLOW}WARNING: Please edit $APP_DIR/.env with your credentials${NC}"
    read -p "Press Enter after editing .env file..."
fi

# Run Django migrations
echo "Running Django migrations..."
sudo -u $USER $APP_DIR/venv/bin/python $APP_DIR/manage.py migrate

# Collect static files
echo "Collecting static files..."
sudo -u $USER $APP_DIR/venv/bin/python $APP_DIR/manage.py collectstatic --noinput

echo -e "${GREEN}[OK] Django configured${NC}"

# Install Nginx configuration
echo -e "${YELLOW}[7/10] Installing Nginx configuration...${NC}"

# Ask if SSL is needed
read -p "Do you want to set up SSL with Let's Encrypt? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Use HTTP-only config initially for certbot
    cp $APP_DIR/nginx/erpsync-http-only.conf /etc/nginx/conf.d/erpsync.conf
else
    cp $APP_DIR/nginx/erpsync-http-only.conf /etc/nginx/conf.d/erpsync.conf
fi

# Update domain in config
read -p "Enter your domain name [$DOMAIN]: " INPUT_DOMAIN
if [ ! -z "$INPUT_DOMAIN" ]; then
    DOMAIN=$INPUT_DOMAIN
fi

sed -i "s/erpsync.yourdomain.com/$DOMAIN/g" /etc/nginx/conf.d/erpsync.conf

# Test Nginx configuration
nginx -t
if [ $? -eq 0 ]; then
    echo -e "${GREEN}[OK] Nginx configuration valid${NC}"
    systemctl reload nginx
else
    echo -e "${RED}[FAIL] Nginx configuration invalid${NC}"
    exit 1
fi

# Install systemd services
echo -e "${YELLOW}[8/10] Installing systemd services...${NC}"
cp $APP_DIR/systemd/erpsync-gunicorn.service /etc/systemd/system/
cp $APP_DIR/systemd/erpsync-processor.service /etc/systemd/system/
cp $APP_DIR/systemd/erpsync.target /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable services
systemctl enable erpsync-gunicorn.service
systemctl enable erpsync-processor.service

echo -e "${GREEN}[OK] Systemd services installed${NC}"

# Set up SSL if requested
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}[9/10] Setting up SSL certificate...${NC}"

    # Ensure Nginx is running
    systemctl start nginx

    # Obtain certificate
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos --email admin@$DOMAIN || {
        echo -e "${YELLOW}WARNING: SSL setup failed. You can run this later:${NC}"
        echo "  certbot --nginx -d $DOMAIN"
    }

    # Replace with SSL config if cert was obtained
    if [ -f "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" ]; then
        cp $APP_DIR/nginx/erpsync.conf /etc/nginx/conf.d/erpsync.conf
        sed -i "s/erpsync.yourdomain.com/$DOMAIN/g" /etc/nginx/conf.d/erpsync.conf
        nginx -t && systemctl reload nginx
        echo -e "${GREEN}[OK] SSL configured${NC}"
    fi
else
    echo -e "${YELLOW}[9/10] Skipping SSL setup${NC}"
fi

# Start services
echo -e "${YELLOW}[10/10] Starting services...${NC}"
systemctl start erpsync-gunicorn.service
systemctl start erpsync-processor.service

# Wait a moment for services to start
sleep 3

# Check service status
if systemctl is-active --quiet erpsync-gunicorn.service; then
    echo -e "${GREEN}[OK] Gunicorn service running${NC}"
else
    echo -e "${RED}[FAIL] Gunicorn service not running${NC}"
    systemctl status erpsync-gunicorn.service
fi

if systemctl is-active --quiet erpsync-processor.service; then
    echo -e "${GREEN}[OK] Webhook processor running${NC}"
else
    echo -e "${RED}[FAIL] Webhook processor not running${NC}"
    systemctl status erpsync-processor.service
fi

# Summary
echo ""
echo "========================================"
echo -e "${GREEN}  Installation Complete!${NC}"
echo "========================================"
echo ""
echo "Services installed:"
echo "  - erpsync-gunicorn.service (Django web server)"
echo "  - erpsync-processor.service (Webhook processor)"
echo ""
echo "Access your application:"
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "  https://$DOMAIN"
else
    echo "  http://$DOMAIN"
fi
echo ""
echo "Useful commands:"
echo "  systemctl status erpsync-gunicorn"
echo "  systemctl status erpsync-processor"
echo "  systemctl restart erpsync-gunicorn"
echo "  systemctl restart erpsync-processor"
echo "  journalctl -u erpsync-gunicorn -f"
echo "  journalctl -u erpsync-processor -f"
echo "  tail -f /var/log/nginx/erpsync.access.log"
echo ""
echo "Next steps:"
echo "  1. Create Django admin user: sudo -u www-data $APP_DIR/venv/bin/python $APP_DIR/manage.py createsuperuser"
echo "  2. Test connections: sudo -u www-data $APP_DIR/venv/bin/python $APP_DIR/manage.py test_connections"
echo "  3. Configure webhooks in your ERP systems"
echo ""
