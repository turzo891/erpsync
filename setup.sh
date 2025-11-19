#!/bin/bash
# Setup script for ERP Sync

set -e

echo "=========================================="
echo "    ERP Sync - Setup Script"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}[OK] Found Python $PYTHON_VERSION${NC}"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
if [ -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment already exists, skipping...${NC}"
else
    python3 -m venv venv
    echo -e "${GREEN}[OK] Virtual environment created${NC}"
fi

# Activate virtual environment
echo ""
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
echo -e "${GREEN}[OK] Dependencies installed${NC}"

# Create .env if it doesn't exist
echo ""
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo -e "${GREEN}[OK] .env file created${NC}"
    echo -e "${YELLOW}[WARNING] Please edit .env file with your ERP credentials${NC}"
else
    echo -e "${YELLOW}.env file already exists, skipping...${NC}"
fi

# Make main.py executable
chmod +x main.py

# Initialize database
echo ""
echo "Initializing database..."
python main.py init
echo -e "${GREEN}[OK] Database initialized${NC}"

echo ""
echo "=========================================="
echo -e "${GREEN}Setup completed successfully!${NC}"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit .env file with your ERP credentials:"
echo "   nano .env"
echo ""
echo "2. Test connections:"
echo "   python main.py test"
echo ""
echo "3. Run initial sync:"
echo "   python main.py sync"
echo ""
echo "4. Or start webhook server:"
echo "   python main.py webhook"
echo ""
echo "For more information, see README.md or QUICKSTART.md"
