#!/bin/bash
# Script to run the MCP Market web server

cd /home/ubuntu/gitdirectory

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the Flask app
python3 app.py

