#!/bin/bash
# Docker quick start script for ERP Sync

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=========================================="
echo "    ERP Sync - Docker Setup"
echo -e "==========================================${NC}"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed${NC}"
    echo "Please install Docker first: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is available
if ! docker compose version &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not available${NC}"
    echo "Please install Docker Compose plugin"
    exit 1
fi

echo -e "${GREEN}[OK] Docker is installed${NC}"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${GREEN}[OK] .env file created${NC}"
        echo -e "${YELLOW}[WARNING] Please edit .env file with your ERP credentials before continuing${NC}"
        echo ""
        read -p "Press Enter after editing .env file, or Ctrl+C to exit..."
    else
        echo -e "${RED}Error: .env.example not found${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}[OK] .env file exists${NC}"
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Check if database exists
if [ ! -f "sync_state.db" ]; then
    echo -e "${YELLOW}Initializing database...${NC}"
    docker compose build
    docker compose run --rm erpsync python main.py init
    echo -e "${GREEN}[OK] Database initialized${NC}"
else
    echo -e "${GREEN}[OK] Database exists${NC}"
fi

# Test connections
echo ""
echo -e "${YELLOW}Testing connections to ERP systems...${NC}"
if docker compose run --rm erpsync python main.py test; then
    echo ""
    echo -e "${GREEN}[OK] Connection test successful${NC}"
else
    echo ""
    echo -e "${RED}[FAIL] Connection test failed${NC}"
    echo "Please check your .env configuration"
    exit 1
fi

# Ask what to do
echo ""
echo "What would you like to do?"
echo "  1) Start webhook server (real-time sync)"
echo "  2) Run manual sync"
echo "  3) Check status"
echo "  4) View conflicts"
echo "  5) Open shell in container"
echo "  6) Stop containers"
echo ""
read -p "Enter choice [1-6]: " choice

case $choice in
    1)
        echo -e "${YELLOW}Starting webhook server...${NC}"
        docker compose up -d
        echo ""
        echo -e "${GREEN}[OK] Webhook server started${NC}"
        echo ""
        echo "View logs with:"
        echo "  docker compose logs -f"
        echo ""
        echo "Stop with:"
        echo "  docker compose stop"
        echo ""
        echo "Webhook URLs:"
        echo "  Cloud → http://YOUR_IP:5000/webhook/cloud"
        echo "  Local → http://YOUR_IP:5000/webhook/local"
        ;;
    2)
        echo -e "${YELLOW}Running manual sync...${NC}"
        docker compose run --rm erpsync python main.py sync
        ;;
    3)
        echo -e "${YELLOW}Checking status...${NC}"
        docker compose run --rm erpsync python main.py status
        ;;
    4)
        echo -e "${YELLOW}Viewing conflicts...${NC}"
        docker compose run --rm erpsync python main.py conflicts
        ;;
    5)
        echo -e "${YELLOW}Opening shell...${NC}"
        docker compose run --rm erpsync /bin/bash
        ;;
    6)
        echo -e "${YELLOW}Stopping containers...${NC}"
        docker compose stop
        echo -e "${GREEN}[OK] Containers stopped${NC}"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}Done!${NC}"
