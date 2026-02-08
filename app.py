from flask import Flask, render_template, jsonify, request, make_response
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timedelta
import csv
import io
import os
import subprocess
import sys
from pathlib import Path

app = Flask(__name__)

# MongoDB connection
# Default to localhost if MONGO_URI is not set
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
DB_NAME = 'mcp_servers'
TOOLS_CACHE_TTL = timedelta(hours=6)

def get_db():
    """Get MongoDB database connection"""
    client = MongoClient(MONGO_URI)
    return client[DB_NAME]


def get_tools_cache_collection(db):
    return db['tools_cache']


def get_tools_from_cache(db, full_name):
    cache_collection = get_tools_cache_collection(db)
    doc = cache_collection.find_one({'full_name': full_name})
    if not doc:
        return None, None
    updated_at = doc.get('updated_at')
    if updated_at and isinstance(updated_at, datetime):
        if datetime.utcnow() - updated_at > TOOLS_CACHE_TTL:
            return None, None
    return doc.get('tools'), doc.get('raw_output')


def save_tools_to_cache(db, full_name, tools, raw_output):
    cache_collection = get_tools_cache_collection(db)
    cache_collection.update_one(
        {'full_name': full_name},
        {
            '$set': {
                'tools': tools,
                'raw_output': raw_output,
                'updated_at': datetime.utcnow(),
            }
        },
        upsert=True,
    )


def run_tool_inspector(full_name, github_url):
    # Use absolute path to current directory
    current_dir = Path(__file__).parent.absolute()
    script_path = current_dir / 'mcp_tool_inspector.py'

    if not script_path.exists():
        raise FileNotFoundError(f'Tool inspector script not found at {script_path}')

    venv_python = current_dir / 'venv/bin/python'
    if not venv_python.exists():
        # Fallback to system python if venv not found
        venv_python = Path(sys.executable)

    python_exec = str(venv_python)

    result = subprocess.run(
        [python_exec, str(script_path), github_url],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=str(script_path.parent),
        env=os.environ.copy(),
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or 'Failed to analyze repository')

    output = result.stdout
    tools = parse_tools_output(output)
    return tools, output


def fetch_tools_for_repo(db, full_name, github_url, force_refresh=False):
    if not force_refresh:
        cached_tools, cached_output = get_tools_from_cache(db, full_name)
        if cached_tools is not None:
            return cached_tools, cached_output

    tools, raw_output = run_tool_inspector(full_name, github_url)
    save_tools_to_cache(db, full_name, tools, raw_output)
    return tools, raw_output

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError(f"Type {type(obj)} not serializable")

@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/server/<slug>')
def server_detail(slug):
    """Render the server detail page"""
    return render_template('server_detail.html', slug=slug)

@app.route('/api/server/<slug>')
def get_server_detail(slug):
    """API endpoint to get server details by slug"""
    try:
        db = get_db()
        
        # Convert slug back to full_name (e.g., "owner-repo" -> "owner/repo")
        full_name = slug.replace('-', '/', 1)
        
        # Get repository details
        repos_collection = db['repositories']
        repo = repos_collection.find_one({'full_name': full_name})
        
        # If not found with direct conversion, try case-insensitive search
        if not repo:
            # Try to find by searching repositories and matching slug
            all_repos = repos_collection.find({})
            for r in all_repos:
                repo_slug = r.get('full_name', '').replace('/', '-').lower()
                if repo_slug == slug.lower():
                    full_name = r.get('full_name')
                    repo = r
                    break
        
        if not repo:
            return jsonify({'error': 'Server not found'}), 404
        
        # Get README content
        readmes_collection = db['readmes']
        readme_doc = readmes_collection.find_one({'full_name': full_name})
        readme_content = readme_doc.get('readme_content', '') if readme_doc else ''
        
        # Convert ObjectId to string and handle date objects
        if '_id' in repo:
            repo['_id'] = str(repo['_id'])
        for key, value in repo.items():
            if isinstance(value, datetime):
                repo[key] = value.isoformat()
            elif hasattr(value, 'isoformat'):
                repo[key] = value.isoformat()
        
        # Add README content
        repo['readme_content'] = readme_content
        
        # Extract owner name
        repo['owner'] = full_name.split('/')[0] if '/' in full_name else ''
        
        return jsonify(repo)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/servers')
def get_servers():
    """API endpoint to get MCP servers with pagination"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 12))
        
        db = get_db()
        
        # Get repositories that are flagged as MCP servers
        # Join with is_mcp_server collection to filter
        is_mcp_collection = db['is_mcp_server']
        
        # Get all full_names that are flagged as MCP servers
        mcp_repos = is_mcp_collection.find({'is_mcp_server': True})
        mcp_full_names = [repo.get('full_name') for repo in mcp_repos if repo.get('full_name')]
        
        # Query repositories collection
        repos_collection = db['repositories']
        
        # Base query for MCP servers
        query = {'full_name': {'$in': mcp_full_names}}
        
        # Add search filter if provided
        search_term = request.args.get('search', '').strip()
        if search_term:
            search_regex = {'$regex': search_term, '$options': 'i'}
            query['$or'] = [
                {'full_name': search_regex},
                {'description': search_regex}
            ]
        
        # Calculate skip for pagination
        skip = (page - 1) * per_page
        
        # Get total count
        total = repos_collection.count_documents(query)
        
        # Get paginated results
        repos = list(repos_collection.find(query)
                    .sort('stargazers_count', -1)
                    .skip(skip)
                    .limit(per_page))
        
        # Convert ObjectId to string and handle date objects for JSON serialization
        for repo in repos:
            if '_id' in repo:
                repo['_id'] = str(repo['_id'])
            # Convert date objects if present
            for key, value in repo.items():
                if isinstance(value, datetime):
                    repo[key] = value.isoformat()
                elif hasattr(value, 'isoformat'):
                    repo[key] = value.isoformat()
        
        return jsonify({
            'servers': repos,
            'page': page,
            'per_page': per_page,
            'total': total,
            'has_more': skip + len(repos) < total
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/servers/export')
def export_servers():
    """Export top MCP servers to CSV"""
    try:
        # Use existing pre-generated CSV file if it exists
        csv_path = Path('/home/ubuntu/gitdirectory/mcp_servers_top_100.csv')
        if csv_path.exists():
            with open(csv_path, 'r', encoding='utf-8') as f:
                csv_content = f.read()
            
            response = make_response(csv_content)
            response.headers['Content-Disposition'] = 'attachment; filename=mcp_servers_top_100.csv'
            response.headers['Content-Type'] = 'text/csv'
            return response

        # Fallback to generating from DB if file doesn't exist
        limit = int(request.args.get('limit', 100))
        db = get_db()
        
        is_mcp_collection = db['is_mcp_server']
        mcp_repos = is_mcp_collection.find({'is_mcp_server': True})
        mcp_full_names = [repo.get('full_name') for repo in mcp_repos if repo.get('full_name')]
        
        repos_collection = db['repositories']
        query = {'full_name': {'$in': mcp_full_names}}
        
        repos = list(
            repos_collection.find(query)
            .sort('stargazers_count', -1)
            .limit(limit)
        )
        
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(['full_name', 'description', 'tools'])
        
        for repo in repos:
            full_name = repo.get('full_name')
            description = (repo.get('description') or '').replace('\n', ' ').strip()
            github_url = repo.get('html_url') or f"https://github.com/{full_name}"
            
            try:
                tools, _ = fetch_tools_for_repo(db, full_name, github_url)
                tool_names = '; '.join(tool.get('name', '') for tool in tools) if tools else ''
            except Exception as tools_error:
                tool_names = f'Error: {tools_error}'
            
            writer.writerow([full_name, description, tool_names])
        
        response = make_response(csv_buffer.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename=mcp_servers_top_{limit}.csv'
        response.headers['Content-Type'] = 'text/csv'
        return response
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/server/<slug>/tools')
def get_server_tools(slug):
    """API endpoint to get MCP tools from a server repository"""
    try:
        db = get_db()
        
        # Convert slug back to full_name
        full_name = slug.replace('-', '/', 1)
        
        # Get repository details to get the GitHub URL
        repos_collection = db['repositories']
        repo = repos_collection.find_one({'full_name': full_name})
        
        # If not found with direct conversion, try case-insensitive search
        if not repo:
            all_repos = repos_collection.find({})
            for r in all_repos:
                repo_slug = r.get('full_name', '').replace('/', '-').lower()
                if repo_slug == slug.lower():
                    full_name = r.get('full_name')
                    repo = r
                    break
        
        if not repo:
            return jsonify({'error': 'Server not found'}), 404
        
        # Get GitHub URL
        github_url = repo.get('html_url') or f"https://github.com/{full_name}"
        
        tools, raw_output = fetch_tools_for_repo(db, full_name, github_url)
        
        return jsonify({
            'tools': tools,
            'raw_output': raw_output,
            'tools_count': len(tools),
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def parse_tools_output(output: str) -> list:
    """Parse the output from mcp_tool_inspector.py into a structured format"""
    tools = []
    current_tool = None
    collecting_description = False
    description_lines = []
    
    lines = output.split('\n')
    for i, line in enumerate(lines):
        line_stripped = line.strip()
        
        # Skip header lines and empty lines at start
        if line_stripped == 'Discovered MCP tools:':
            continue
        
        # Start of a new tool
        if line_stripped.startswith('- Name:'):
            # Save previous tool if exists
            if current_tool:
                if description_lines:
                    # Join description lines, preserving paragraph breaks
                    current_tool['description'] = '\n'.join(description_lines).strip()
                tools.append(current_tool)
            
            # Start new tool
            current_tool = {
                'name': line_stripped.replace('- Name:', '').strip(),
                'description': None,
                'origin': None
            }
            collecting_description = False
            description_lines = []
        
        # Description line - can be multi-line (starts with "  Description:")
        elif line.startswith('  Description:') and current_tool:
            # Remove "  Description:" prefix and get the rest
            desc_text = line.replace('  Description:', '', 1).strip()
            if desc_text:
                description_lines.append(desc_text)
            collecting_description = True
        
        # Collecting description continuation (lines after Description: until Declared in:)
        elif collecting_description and current_tool:
            # Stop if we hit "  Declared in:"
            if line.startswith('  Declared in:'):
                collecting_description = False
                current_tool['origin'] = line.replace('  Declared in:', '').strip()
            # Continue collecting description lines
            # All lines between "  Description:" and "  Declared in:" are part of description
            # unless they start with "- Name:" (which would be a new tool)
            elif not line_stripped.startswith('- Name:'):
                # Add the line as-is (preserving formatting)
                # Lines can be empty (paragraph breaks) or have content
                description_lines.append(line)
        
        # Declared in line (when not collecting description - shouldn't happen but just in case)
        elif line_stripped.startswith('Declared in:') and current_tool and not collecting_description:
            current_tool['origin'] = line_stripped.replace('Declared in:', '').strip()
    
    # Save last tool
    if current_tool:
        if description_lines:
            current_tool['description'] = '\n'.join(description_lines).strip()
        tools.append(current_tool)
    
    return tools

if __name__ == '__main__':
    # Set debug=False for production
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    port = int(os.getenv('PORT', 8080))
    app.run(debug=debug_mode, host='0.0.0.0', port=port)

