# MCP Market

A web-based marketplace and catalog for discovering Model Context Protocol (MCP) servers. Browse, search, and explore MCP servers with their exposed tools and capabilities.

## Features

- **Browse MCP Servers** - Paginated listing of MCP servers sorted by GitHub stars
- **Search** - Filter servers by name or description
- **Server Details** - View full repository information, README content, and available tools
- **Tool Inspector** - Automatically analyzes repositories to extract exposed MCP tools
- **CSV Export** - Download top MCP servers list as CSV
- **Caching** - MongoDB-based caching for tool inspection results (6-hour TTL)

## Tech Stack

- **Backend**: Flask 3.0
- **Database**: MongoDB
- **Frontend**: HTML templates with server-side rendering

## Prerequisites

- Python 3.8+
- MongoDB running locally or remote
- Git (for cloning MCP repositories during tool inspection)

## Quick Start

```bash
# Clone the repository
git clone https://github.com/rdwr-namikb/mcp-market.git
cd mcp-market

# Import the database (MongoDB must be running)
./import_data.sh

# Run the quick start script
./quick_start.sh
```

Or manually:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the server
python app.py
```

Access the application at `http://localhost:8080`

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `MONGO_URI` | `mongodb://localhost:27017/` | MongoDB connection string |
| `PORT` | `8080` | Server port |
| `FLASK_DEBUG` | `False` | Enable debug mode |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main page |
| `/server/<slug>` | GET | Server detail page |
| `/api/servers` | GET | List servers (paginated) |
| `/api/server/<slug>` | GET | Get server details |
| `/api/server/<slug>/tools` | GET | Get MCP tools for a server |
| `/api/servers/export` | GET | Export servers to CSV |

### Query Parameters

**`/api/servers`**
- `page` - Page number (default: 1)
- `per_page` - Items per page (default: 12)
- `search` - Search term for filtering

## Project Structure

```
├── app.py                    # Main Flask application
├── mcp_tool_inspector.py     # Tool to analyze MCP repositories
├── mcp_servers_top_100.csv   # Pre-generated list of top MCP servers
├── requirements.txt          # Python dependencies
├── templates/                # HTML templates
│   ├── index.html           # Main listing page
│   └── server_detail.html   # Server detail page
├── static/                   # Static assets (CSS, JS)
├── check_mcp_server/         # MCP server verification tools
├── quick_start.sh           # Setup script
├── run_server.sh            # Server run script
└── start_background.sh      # Background service starter
```

## MCP Tool Inspector

The `mcp_tool_inspector.py` script analyzes GitHub repositories to discover MCP tools:

```bash
python mcp_tool_inspector.py https://github.com/owner/repo
```

It clones the repository, parses Python/JavaScript files, and extracts tool definitions.

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment instructions including:
- Systemd service configuration
- Firewall setup
- Running as a background service

## MongoDB Collections

- `repositories` - Repository metadata from GitHub
- `readmes` - README content for each repository
- `is_mcp_server` - Flags indicating valid MCP servers
- `tools_cache` - Cached tool inspection results

## License

MIT
