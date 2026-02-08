# Running MCP Market Server in Background

This guide shows how to run the server so it continues running after closing Cursor or your terminal.

## Quick Start (Easiest Method)

### Option 1: Using Screen (Recommended for Testing)

```bash
cd /home/ubuntu/gitdirectory
./start_background.sh screen
```

**To check if it's running:**
```bash
screen -ls
```

**To view the server output:**
```bash
screen -r mcp-market
```

**To detach (keep running):**
- Press `Ctrl+A` then `D`

**To stop the server:**
```bash
screen -r mcp-market
# Then press Ctrl+C to stop
```

### Option 2: Using Systemd Service (Recommended for Production)

```bash
cd /home/ubuntu/gitdirectory
./start_background.sh systemd
```

**Check status:**
```bash
sudo systemctl status mcp-market
```

**View logs:**
```bash
sudo journalctl -u mcp-market -f
```

**Stop the server:**
```bash
sudo systemctl stop mcp-market
```

**Start the server:**
```bash
sudo systemctl start mcp-market
```

**Restart the server:**
```bash
sudo systemctl restart mcp-market
```

**Enable auto-start on boot:**
```bash
sudo systemctl enable mcp-market
```

## Other Methods

### Option 3: Using nohup

```bash
cd /home/ubuntu/gitdirectory
./start_background.sh nohup
```

**View logs:**
```bash
tail -f /home/ubuntu/gitdirectory/mcp-market.log
```

**Stop the server:**
```bash
kill $(cat /home/ubuntu/gitdirectory/mcp-market.pid)
```

### Option 4: Using tmux

```bash
cd /home/ubuntu/gitdirectory
./start_background.sh tmux
```

**To view:**
```bash
tmux attach -t mcp-market
```

**To detach:**
- Press `Ctrl+B` then `D`

## Manual Setup (Systemd)

If you prefer to set up systemd manually:

```bash
cd /home/ubuntu/gitdirectory

# 1. Copy service file
sudo cp mcp-market.service /etc/systemd/system/

# 2. Update the Python path in the service file
sudo sed -i "s|ExecStart=/usr/bin/python3|ExecStart=$(pwd)/venv/bin/python3|" /etc/systemd/system/mcp-market.service

# 3. Reload systemd
sudo systemctl daemon-reload

# 4. Enable and start
sudo systemctl enable mcp-market
sudo systemctl start mcp-market

# 5. Check status
sudo systemctl status mcp-market
```

## Troubleshooting

### Check if server is running:
```bash
# Check port 8080
sudo netstat -tlnp | grep 8080
# or
sudo ss -tlnp | grep 8080

# Check process
ps aux | grep "python.*app.py"
```

### View logs (systemd):
```bash
sudo journalctl -u mcp-market -n 50  # Last 50 lines
sudo journalctl -u mcp-market -f     # Follow logs
```

### Restart after code changes:
```bash
# If using systemd
sudo systemctl restart mcp-market

# If using screen/tmux
screen -r mcp-market
# Press Ctrl+C, then restart:
source venv/bin/activate && python app.py
```

### Check firewall:
```bash
sudo ufw status
sudo ufw allow 8080/tcp  # If not already allowed
```

## Recommended Setup for Production

1. **Use systemd service** - Auto-restarts on failure, starts on boot
2. **Set up Nginx reverse proxy** - Better performance and security
3. **Use SSL certificate** - HTTPS encryption
4. **Set debug=False** - Production mode

See `DEPLOYMENT.md` for full production setup guide.

