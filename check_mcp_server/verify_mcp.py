import os
import re
import argparse
from typing import List, Set
import json

def check_mcp_imports(filepath: str) -> bool:
    """Check if a file imports MCP server modules (not client)"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # MCP SERVER imports (exclude client imports)
        server_patterns = [
            # Python - Standard MCP SDK
            r'from mcp\.server import',
            r'import mcp\.server',
            r'from mcp\.server\.stdio import',
            r'from mcp\.server\.sse import',
            r'Server\(.*["\'].*["\'].*\)',  # Server("name")
            # Python - FastMCP Framework
            r'from mcp\.server\.fastmcp import',
            r'from mcp\.server\.fastmcp\.server import',
            r'FastMCP\(',
            # TypeScript/JavaScript - Standard SDK
            r'@modelcontextprotocol/sdk/server',
            # TypeScript/JavaScript - Custom FastMCP packages
            r'from ["\'][^"\']*fastmcp[^"\']*["\']',  # from 'firecrawl-fastmcp'
            r'import.*from ["\'][^"\']*fastmcp[^"\']*["\']',  # import { FastMCP } from 'custom-fastmcp'
            # Go
            r'github\.com/modelcontextprotocol/go-sdk/server',
            r'"github\.com/modelcontextprotocol/go-sdk/server"',
            r'mcp\.Server',
            r'server\.NewMCPServer',
            # Kotlin
            r'io\.modelcontextprotocol\.kotlin\.sdk',
            r'io\.modelcontextprotocol\.kotlin\.sdk\.server',
            # PHP - Laravel MCP
            r'use Laravel\\Mcp\\',
            r'Laravel\\Mcp\\Server',
            r'use.*\\Mcp\\Server\\Tool',
            r'namespace.*\\Mcp\\',
            # C# - Microsoft MCP
            r'using Azure\.Mcp',
            r'using Microsoft\.Mcp',
            r'using Fabric\.Mcp',
            r'namespace Azure\.Mcp',
            r'namespace Microsoft\.Mcp',
            r'namespace Fabric\.Mcp',
        ]
        
        # Exclude if it's a client
        client_patterns = [
            r'from mcp\.client import',
            r'from mcp import ClientSession',
            r'ClientSession\(',
            r'stdio_client\(',
        ]
        
        has_server = any(re.search(pattern, content) for pattern in server_patterns)
        has_client_only = any(re.search(pattern, content) for pattern in client_patterns)
        
        # Only count as MCP server if it has server imports and NO client-only code
        return has_server and not has_client_only
    except Exception:
        return False

def check_mcp_decorators(filepath: str) -> bool:
    """Check if file uses MCP server decorators/registrations"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # MCP-specific patterns
        mcp_patterns = [
            # Python
            r'@server\.list_tools\(\)',
            r'@server\.call_tool\(\)',
            # TypeScript/JavaScript - Standard SDK
            r'server\.registerTool\(',
            r'McpServer\(',
            r'new McpServer\(',
            # TypeScript/JavaScript - FastMCP (custom packages)
            r'server\.addTool\(',  # FastMCP pattern
            r'\.addTool\(\s*\{',   # FastMCP pattern with object
            # Go
            r'server\.RegisterTool\(',
            r'server\.AddTool\(',
            r'NewMCPServer\(',
            r'mcp\.NewServer\(',
            r'\.ListTools\(',
            r'\.CallTool\(',
            # Kotlin
            r'server\.addTool\(',
            # PHP - Laravel MCP
            r'class\s+\w+\s+extends\s+Tool',
            r'implements.*Tool',
            r'#\[IsReadOnly\]',
            r'#\[Tool\]',
            r'protected\s+string\s+\$description',  # Common MCP tool pattern
            # C# - Microsoft MCP
            r'class\s+\w+Command\s*:',  # Command pattern
            r'BaseAzureCommand',
            r'BaseMcpCommand',
            r'ExecuteAsync\s*\(',
            r'HandleAsync\s*\(',
            r'IMcpTool',
            r'IMcpServer',
            r'\[McpTool\]',
            r'\[Tool\]',
        ]
        
        for pattern in mcp_patterns:
            if re.search(pattern, content):
                return True
        
        return False
    except Exception:
        return False

def verify_mcp_server(directory: str) -> dict:
    """
    Verify if a directory contains an actual MCP server implementation.
    
    Returns:
        dict with keys:
            - is_mcp: bool
            - evidence: list of files with MCP patterns
            - confidence: str ('high', 'medium', 'low')
    """
    mcp_files = []
    has_imports = False
    has_decorators = False
    
    # Search for MCP patterns in Python, TypeScript, Go, Kotlin, PHP, and C# files
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(('.py', '.ts', '.js', '.go', '.kt', '.php', '.cs')):
                filepath = os.path.join(root, file)
                
                if check_mcp_imports(filepath):
                    has_imports = True
                    mcp_files.append(os.path.relpath(filepath, directory))
                
                if check_mcp_decorators(filepath):
                    has_decorators = True
                    if os.path.relpath(filepath, directory) not in mcp_files:
                        mcp_files.append(os.path.relpath(filepath, directory))
    
    # Determine confidence level
    if has_imports and has_decorators:
        confidence = 'high'
        is_mcp = True
    elif has_imports or has_decorators:
        confidence = 'medium'
        is_mcp = True
    else:
        confidence = 'low'
        is_mcp = False
    
    return {
        'is_mcp': is_mcp,
        'has_imports': has_imports,
        'has_decorators': has_decorators,
        'evidence_files': mcp_files,
        'confidence': confidence
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify if a directory contains an MCP server")
    parser.add_argument("directory", help="Directory to verify")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    if not os.path.isdir(args.directory):
        print(json.dumps({"error": "Directory not found", "is_mcp": False}))
        exit(1)
    
    result = verify_mcp_server(args.directory)
    
    if args.json:
        print(json.dumps(result))
    else:
        print(f"Is MCP Server: {result['is_mcp']}")
        print(f"Confidence: {result['confidence']}")
        print(f"Has MCP Imports: {result['has_imports']}")
        print(f"Has MCP Decorators: {result['has_decorators']}")
        if result['evidence_files']:
            print(f"\nEvidence files:")
            for f in result['evidence_files']:
                print(f"  - {f}")
