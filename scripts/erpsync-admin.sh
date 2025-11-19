#!/bin/bash
# ERP Sync Administration Helper Script

APP_DIR="/opt/erpsync"
USER="www-data"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

show_help() {
    echo "ERP Sync Administration Helper"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  status          - Show service status"
    echo "  start           - Start all services"
    echo "  stop            - Stop all services"
    echo "  restart         - Restart all services"
    echo "  logs            - Show recent logs"
    echo "  logs-follow     - Follow logs in real-time"
    echo "  test            - Test ERP connections"
    echo "  sync            - Run manual sync"
    echo "  conflicts       - Show conflicts"
    echo "  superuser       - Create Django superuser"
    echo "  shell           - Open Django shell"
    echo "  migrate         - Run Django migrations"
    echo "  collectstatic   - Collect static files"
    echo "  backup-db       - Backup database"
    echo "  nginx-test      - Test Nginx configuration"
    echo "  nginx-reload    - Reload Nginx"
    echo ""
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}Error: This command requires root privileges${NC}"
        exit 1
    fi
}

case "$1" in
    status)
        echo "Service Status:"
        echo ""
        systemctl status erpsync-gunicorn.service --no-pager
        echo ""
        systemctl status erpsync-processor.service --no-pager
        echo ""
        systemctl status nginx.service --no-pager | head -n 10
        ;;

    start)
        check_root
        echo "Starting services..."
        systemctl start erpsync-gunicorn.service
        systemctl start erpsync-processor.service
        echo -e "${GREEN}[OK] Services started${NC}"
        ;;

    stop)
        check_root
        echo "Stopping services..."
        systemctl stop erpsync-gunicorn.service
        systemctl stop erpsync-processor.service
        echo -e "${GREEN}[OK] Services stopped${NC}"
        ;;

    restart)
        check_root
        echo "Restarting services..."
        systemctl restart erpsync-gunicorn.service
        systemctl restart erpsync-processor.service
        echo -e "${GREEN}[OK] Services restarted${NC}"
        ;;

    logs)
        echo "Recent logs (last 50 lines):"
        echo ""
        echo "=== Gunicorn ==="
        journalctl -u erpsync-gunicorn.service -n 50 --no-pager
        echo ""
        echo "=== Webhook Processor ==="
        journalctl -u erpsync-processor.service -n 50 --no-pager
        echo ""
        echo "=== Nginx Access ==="
        tail -n 20 /var/log/nginx/erpsync.access.log
        ;;

    logs-follow)
        echo "Following logs (Ctrl+C to stop)..."
        journalctl -u erpsync-gunicorn.service -u erpsync-processor.service -f
        ;;

    test)
        echo "Testing ERP connections..."
        sudo -u $USER $APP_DIR/venv/bin/python $APP_DIR/manage.py test_connections
        ;;

    sync)
        echo "Running manual sync..."
        sudo -u $USER $APP_DIR/venv/bin/python $APP_DIR/manage.py sync "$@"
        ;;

    conflicts)
        echo "Showing conflicts..."
        sudo -u $USER $APP_DIR/venv/bin/python $APP_DIR/manage.py show_conflicts
        ;;

    superuser)
        echo "Creating Django superuser..."
        sudo -u $USER $APP_DIR/venv/bin/python $APP_DIR/manage.py createsuperuser
        ;;

    shell)
        echo "Opening Django shell..."
        sudo -u $USER $APP_DIR/venv/bin/python $APP_DIR/manage.py shell
        ;;

    migrate)
        echo "Running Django migrations..."
        sudo -u $USER $APP_DIR/venv/bin/python $APP_DIR/manage.py migrate
        ;;

    collectstatic)
        echo "Collecting static files..."
        sudo -u $USER $APP_DIR/venv/bin/python $APP_DIR/manage.py collectstatic --noinput
        ;;

    backup-db)
        BACKUP_DIR="$APP_DIR/backups"
        BACKUP_FILE="$BACKUP_DIR/sync_state_$(date +%Y%m%d_%H%M%S).db"

        mkdir -p $BACKUP_DIR
        cp $APP_DIR/sync_state.db $BACKUP_FILE
        echo -e "${GREEN}[OK] Database backed up to: $BACKUP_FILE${NC}"

        # Keep only last 30 backups
        cd $BACKUP_DIR
        ls -t sync_state_*.db | tail -n +31 | xargs -r rm
        ;;

    nginx-test)
        echo "Testing Nginx configuration..."
        nginx -t
        ;;

    nginx-reload)
        check_root
        echo "Reloading Nginx..."
        nginx -t && systemctl reload nginx
        echo -e "${GREEN}[OK] Nginx reloaded${NC}"
        ;;

    *)
        show_help
        ;;
esac
