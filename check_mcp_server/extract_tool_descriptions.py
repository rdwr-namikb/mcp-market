import os
import ast
import re
import json
import argparse
from typing import List, Dict, Optional

def extract_python_tool_descriptions(filepath: str) -> List[Dict[str, str]]:
    """Extract tool names and descriptions from Python files."""
    tools = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Check for @mcp.tool or @tool decorators
                has_tool_decorator = False
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Attribute) and decorator.attr == 'tool':
                        has_tool_decorator = True
                    elif isinstance(decorator, ast.Name) and decorator.id == 'tool':
                        has_tool_decorator = True
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'tool':
                            has_tool_decorator = True
                        elif isinstance(decorator.func, ast.Name) and decorator.func.id == 'tool':
                            has_tool_decorator = True
                
                if has_tool_decorator:
                    # Extract docstring as description
                    description = ast.get_docstring(node) or ""
                    # Clean up description (first line only)
                    if description:
                        description = description.split('\n')[0].strip()
                    
                    tools.append({
                        'name': node.name,
                        'description': description,
                        'file': filepath
                    })
            
            # Check for Tool(name="...") instantiation
            if isinstance(node, ast.Call):
                is_tool_call = False
                if isinstance(node.func, ast.Name) and node.func.id == 'Tool':
                    is_tool_call = True
                elif isinstance(node.func, ast.Attribute) and node.func.attr == 'Tool':
                    is_tool_call = True
                
                if is_tool_call:
                    tool_name = None
                    tool_desc = None
                    for keyword in node.keywords:
                        if keyword.arg == 'name':
                            if isinstance(keyword.value, ast.Constant):
                                tool_name = keyword.value.value
                        if keyword.arg == 'description':
                            if isinstance(keyword.value, ast.Constant):
                                tool_desc = keyword.value.value
                    
                    if tool_name:
                        tools.append({
                            'name': tool_name,
                            'description': tool_desc or "",
                            'file': filepath
                        })
    
    except Exception as e:
        pass
    
    return tools

def extract_js_ts_tool_descriptions(filepath: str) -> List[Dict[str, str]]:
    """Extract tool names and descriptions from JS/TS files."""
    tools = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern 1: server.tool("name", ...) with description
        # Looking for: server.tool("toolName", { description: "..." })
        pattern = r'\.(?:tool|registerTool)\(\s*["\']([^"\']+)["\']\s*,\s*\{[^}]*description\s*:\s*["\']([^"\']+)["\']'
        matches = re.findall(pattern, content, re.DOTALL)
        for name, desc in matches:
            tools.append({
                'name': name,
                'description': desc,
                'file': filepath
            })
        
        # Pattern 2: Without description in the same line, just get name
        simple_pattern = r'\.(?:tool|registerTool)\(\s*["\']([^"\']+)["\']'
        simple_matches = re.findall(simple_pattern, content)
        existing_names = {t['name'] for t in tools}
        for name in simple_matches:
            if name not in existing_names:
                # Try to find description in JSDoc comment above
                jsdoc_pattern = rf'/\*\*\s*\n\s*\*\s*([^\n]+).*?\*/.*?\.(?:tool|registerTool)\(\s*["\']' + re.escape(name) + r'["\']'
                jsdoc_match = re.search(jsdoc_pattern, content, re.DOTALL)
                description = jsdoc_match.group(1).strip() if jsdoc_match else ""
                
                tools.append({
                    'name': name,
                    'description': description,
                    'file': filepath
                })
    
    except Exception as e:
        pass
    
    return tools

def extract_php_tool_descriptions(filepath: str) -> List[Dict[str, str]]:
    """Extract tool names and descriptions from PHP files."""
    tools = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern: class ToolName extends Tool with description property
        class_pattern = r'class\s+(\w+)\s+extends\s+(?:\w+\\)*Tool'
        class_matches = re.finditer(class_pattern, content)
        
        for match in class_matches:
            class_name = match.group(1)
            # Find the class body
            class_start = match.end()
            # Look for protected string $description = "..."
            desc_pattern = r'protected\s+string\s+\$description\s*=\s*["\']([^"\']+)["\']'
            desc_match = re.search(desc_pattern, content[class_start:class_start+2000])
            
            description = desc_match.group(1) if desc_match else ""
            
            # Also try to get from PHPDoc comment
            if not description:
                phpdoc_pattern = r'/\*\*[^*]*\*\s*([^\n*]+).*?\*/\s*class\s+' + re.escape(class_name)
                phpdoc_match = re.search(phpdoc_pattern, content, re.DOTALL)
                if phpdoc_match:
                    description = phpdoc_match.group(1).strip()
            
            tools.append({
                'name': class_name,
                'description': description,
                'file': filepath
            })
    
    except Exception as e:
        pass
    
    return tools

def extract_csharp_tool_descriptions(filepath: str) -> List[Dict[str, str]]:
    """Extract tool names and descriptions from C# files."""
    tools = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern: public sealed class XCommand : BaseCommand
        class_pattern = r'(?:public|internal)?\s*(?:sealed|abstract)?\s*class\s+(\w+Command)\s*(?::|where)'
        class_matches = re.finditer(class_pattern, content)
        
        for match in class_matches:
            class_name = match.group(1)
            description = ""
            
            # Method 1: Look for Description property with => or = 
            class_start = match.end()
            # Pattern: public override string Description => "...";
            desc_pattern = r'(?:public|private|protected)?\s*(?:override\s+)?string\s+Description\s*(?:=>|=)\s*"([^"]+)"'
            desc_match = re.search(desc_pattern, content[class_start:class_start+3000])
            if desc_match:
                description = desc_match.group(1).strip()
            
            # Method 2: Look for XML documentation comment above the class
            if not description:
                # Get up to 1000 characters before the class definition
                search_start = max(0, match.start() - 1000)
                search_text = content[search_start:match.start()]
                
                # Pattern for multi-line XML summary
                xml_pattern = r'///\s*<summary>\s*\n\s*///\s*([^\n]+)'
                xml_matches = re.findall(xml_pattern, search_text)
                if xml_matches:
                    # Take the last match (closest to class definition)
                    description = xml_matches[-1].strip()
            
            # Method 3: Look for [Description("...")] attribute
            if not description:
                search_start = max(0, match.start() - 500)
                attr_pattern = r'\[Description\("([^"]+)"\)\]'
                attr_match = re.search(attr_pattern, content[search_start:match.start()])
                if attr_match:
                    description = attr_match.group(1).strip()
            
            tools.append({
                'name': class_name,
                'description': description,
                'file': filepath
            })
    
    except Exception as e:
        pass
    
    return tools

def scan_directory_with_descriptions(directory: str) -> List[Dict[str, str]]:
    """Scan directory and extract all tools with descriptions."""
    all_tools = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            relative_path = os.path.relpath(filepath, directory)
            
            if file.endswith('.py'):
                tools = extract_python_tool_descriptions(filepath)
                for tool in tools:
                    tool['file'] = relative_path
                    tool['language'] = 'Python'
                all_tools.extend(tools)
            
            elif file.endswith(('.js', '.ts')):
                tools = extract_js_ts_tool_descriptions(filepath)
                for tool in tools:
                    tool['file'] = relative_path
                    tool['language'] = 'TypeScript/JavaScript'
                all_tools.extend(tools)
            
            elif file.endswith('.php'):
                tools = extract_php_tool_descriptions(filepath)
                for tool in tools:
                    tool['file'] = relative_path
                    tool['language'] = 'PHP'
                all_tools.extend(tools)
            
            elif file.endswith('.cs'):
                tools = extract_csharp_tool_descriptions(filepath)
                for tool in tools:
                    tool['file'] = relative_path
                    tool['language'] = 'C#'
                all_tools.extend(tools)
    
    # Remove duplicates and sort
    seen = set()
    unique_tools = []
    for tool in all_tools:
        key = (tool['name'], tool['file'])
        if key not in seen:
            seen.add(key)
            unique_tools.append(tool)
    
    return sorted(unique_tools, key=lambda x: x['name'])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract MCP tool descriptions from a repository")
    parser.add_argument("directory", help="Directory to scan")
    parser.add_argument("--format", choices=['json', 'table', 'markdown'], default='table', 
                       help="Output format (default: table)")
    parser.add_argument("--output", help="Output file (default: stdout)")
    args = parser.parse_args()
    
    if not os.path.isdir(args.directory):
        print(json.dumps({"error": "Directory not found"}))
        exit(1)
    
    tools = scan_directory_with_descriptions(args.directory)
    
    if args.format == 'json':
        output = json.dumps(tools, indent=2)
    
    elif args.format == 'markdown':
        output_lines = ["# MCP Tools\n"]
        output_lines.append(f"**Total Tools:** {len(tools)}\n")
        output_lines.append("| Tool Name | Description | Language | File |")
        output_lines.append("|-----------|-------------|----------|------|")
        for tool in tools:
            desc = tool['description'][:80] + "..." if len(tool['description']) > 80 else tool['description']
            output_lines.append(f"| {tool['name']} | {desc} | {tool['language']} | {tool['file']} |")
        output = '\n'.join(output_lines)
    
    else:  # table format
        output_lines = [f"{'Tool Name':<40} {'Description':<60} {'Language':<15} File"]
        output_lines.append("=" * 150)
        for tool in tools:
            desc = tool['description'][:57] + "..." if len(tool['description']) > 60 else tool['description']
            file_short = tool['file'] if len(tool['file']) < 30 else "..." + tool['file'][-27:]
            output_lines.append(f"{tool['name']:<40} {desc:<60} {tool['language']:<15} {file_short}")
        output_lines.append(f"\nTotal tools found: {len(tools)}")
        output = '\n'.join(output_lines)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output)
        print(f"Results saved to {args.output}")
    else:
        print(output)

