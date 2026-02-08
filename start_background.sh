#!/bin/bash
# Script to start MCP Market server in background using different methods

METHOD=${1:-screen}  # Default to screen

cd /home/ubuntu/gitdirectory

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

case $METHOD in
    screen)
        echo "Starting server in screen session 'mcp-market'..."
        screen -dmS mcp-market bash -c "source venv/bin/activate && python app.py"
        echo "Server started in screen session 'mcp-market'"
        echo "To attach: screen -r mcp-market"
        echo "To detach: Press Ctrl+A then D"
        ;;
    tmux)
        echo "Starting server in tmux session 'mcp-market'..."
        tmux new-session -d -s mcp-market "source venv/bin/activate && python app.py"
        echo "Server started in tmux session 'mcp-market'"
        echo "To attach: tmux attach -t mcp-market"
        echo "To detach: Press Ctrl+B then D"
        ;;
    nohup)
        echo "Starting server with nohup..."
        nohup python app.py > mcp-market.log 2>&1 &
        echo $! > mcp-market.pid
        echo "Server started with PID: $(cat mcp-market.pid)"
        echo "Logs: tail -f mcp-market.log"
        echo "Stop: kill $(cat mcp-market.pid)"
        ;;
    systemd)
        echo "Setting up systemd service..."
        sudo cp mcp-market.service /etc/systemd/system/
        sudo sed -i "s|ExecStart=/usr/bin/python3|ExecStart=$(pwd)/venv/bin/python3|" /etc/systemd/system/mcp-market.service
        sudo systemctl daemon-reload
        sudo systemctl enable mcp-market
        sudo systemctl start mcp-market
        echo "Service started. Check status with: sudo systemctl status mcp-market"
        ;;
    *)
        echo "Usage: $0 [screen|tmux|nohup|systemd]"
        echo "  screen  - Run in screen session (recommended for testing)"
        echo "  tmux    - Run in tmux session"
        echo "  nohup   - Run in background with nohup"
        echo "  systemd - Run as system service (recommended for production)"
        exit 1
        ;;
esac

