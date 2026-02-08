#!/bin/bash
echo "=== MCP Market Quick Start ==="
echo ""
echo "1. Setting up virtual environment..."
cd /home/ubuntu/gitdirectory
python3 -m venv venv
source venv/bin/activate

echo "2. Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "3. Configuring firewall..."
sudo ufw allow 8080/tcp 2>/dev/null || echo "Firewall already configured or not available"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the server, run:"
echo "  cd /home/ubuntu/gitdirectory"
echo "  source venv/bin/activate"
echo "  python app.py"
echo ""
echo "Then access at: http://$(curl -s ifconfig.me):8080"
echo ""
