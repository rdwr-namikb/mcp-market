# Deployment Guide - Making MCP Market Accessible on the Internet

## Current Setup
- Your server's public IP: **51.84.129.114**
- Flask app is configured to run on `0.0.0.0:8080` (accessible from internet)

## Step 1: Install Dependencies

```bash
cd /home/ubuntu/gitdirectory

# Create virtual environment if it doesn't exist
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Step 2: Configure Firewall (UFW)

```bash
# Allow HTTP (port 80) and HTTPS (port 443) if using nginx
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# OR allow direct access to Flask on port 8080 (less secure, not recommended for production)
sudo ufw allow 8080/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status
```

## Step 3: Configure AWS Security Group (if on AWS)

If you're on AWS EC2, you need to configure the Security Group:

1. Go to AWS Console → EC2 → Security Groups
2. Select your instance's security group
3. Add Inbound Rules:
   - Type: Custom TCP
   - Port: 5000 (or 80/443 if using nginx)
   - Source: 0.0.0.0/0 (or specific IPs for better security)
   - Description: MCP Market Web Server

## Step 4: Run the Server

### Option A: Run Directly (Simple, for testing)

```bash
cd /home/ubuntu/gitdirectory
source venv/bin/activate
python app.py
```

Access at: `http://51.84.129.114:8080`

### Option B: Run as Systemd Service (Recommended for production)

```bash
# Copy service file to systemd directory
sudo cp /home/ubuntu/gitdirectory/mcp-market.service /etc/systemd/system/

# Update the service file to use venv Python
sudo sed -i 's|ExecStart=/usr/bin/python3|ExecStart=/home/ubuntu/gitdirectory/venv/bin/python3|' /etc/systemd/system/mcp-market.service

# Reload systemd
sudo systemctl daemon-reload

# Start the service
sudo systemctl start mcp-market

# Enable it to start on boot
sudo systemctl enable mcp-market

# Check status
sudo systemctl status mcp-market

# View logs
sudo journalctl -u mcp-market -f
```

Access at: `http://51.84.129.114:8080`

## Step 5: Set Up Nginx Reverse Proxy (Recommended for Production)

### Install Nginx

```bash
sudo apt update
sudo apt install nginx -y
```

### Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/mcp-market
```

Add this configuration:

```nginx
server {
    listen 80;
    server_name 51.84.129.114;  # Replace with your domain if you have one

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Enable the Site

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/mcp-market /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx

# Enable nginx on boot
sudo systemctl enable nginx
```

Now access at: `http://51.84.129.114` (port 80, standard HTTP)

## Step 6: Set Up SSL with Let's Encrypt (Optional but Recommended)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Get SSL certificate (replace with your domain if you have one)
sudo certbot --nginx -d your-domain.com

# Or if you only have IP, you can use:
# Note: Let's Encrypt doesn't support IP addresses directly
# You'll need a domain name for SSL
```

## Step 7: Update Flask App for Production

Update `app.py` to remove debug mode:

```python
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)  # Change debug=False
```

## Security Considerations

1. **Change debug mode to False** in production
2. **Use environment variables** for sensitive data (MongoDB credentials)
3. **Set up rate limiting** to prevent abuse
4. **Use HTTPS** (SSL certificate)
5. **Restrict MongoDB access** to localhost only
6. **Regular updates** of dependencies

## Troubleshooting

### Check if server is running:
```bash
sudo netstat -tlnp | grep 8080
# or
sudo ss -tlnp | grep 8080
```

### Check firewall:
```bash
sudo ufw status verbose
```

### Check nginx status:
```bash
sudo systemctl status nginx
```

### View Flask logs:
```bash
# If running as systemd service
sudo journalctl -u mcp-market -f

# If running directly, check terminal output
```

### Test from command line:
```bash
curl http://localhost:8080
curl http://51.84.129.114:8080
```

## Quick Start (Simplest Method)

```bash
cd /home/ubuntu/gitdirectory
source venv/bin/activate
pip install -r requirements.txt
sudo ufw allow 8080/tcp
python app.py
```

Then access: `http://51.84.129.114:8080`

