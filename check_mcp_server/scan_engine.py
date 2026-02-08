import os
import ast
import re
import json
import argparse
from typing import List, Set

class ValueResolver(ast.NodeVisitor):
    def __init__(self):
        self.constants = {}
        self.class_constants = {} # ClassName -> {Attr -> Value}
        self.current_class = None

    def visit_ClassDef(self, node):
        prev_class = self.current_class
        self.current_class = node.name
        if node.name not in self.class_constants:
            self.class_constants[node.name] = {}
        self.generic_visit(node)
        self.current_class = prev_class

    def visit_Assign(self, node):
        # Handle simple assignments: NAME = "VALUE"
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if isinstance(node.value, ast.Constant):
                 if self.current_class:
                     self.class_constants[self.current_class][node.targets[0].id] = node.value.value
                 else:
                     self.constants[node.targets[0].id] = node.value.value

    def resolve(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            return self.constants.get(node.id)
        elif isinstance(node, ast.Attribute):
            # Handle Class.Attr
            if isinstance(node.value, ast.Name):
                class_name = node.value.id
                attr_name = node.attr
                val = self.class_constants.get(class_name, {}).get(attr_name)
                if val is not None:
                    return val
            
            # Handle Something.value (common in Enums)
            if node.attr == 'value':
                return self.resolve(node.value)
        return None

def scan_python_file(filepath: str) -> List[str]:
    tools = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        resolver = ValueResolver()
        resolver.visit(tree)

        for node in ast.walk(tree):
            # Check for decorators @mcp.tool or @tool
            if isinstance(node, ast.FunctionDef):
                for decorator in node.decorator_list:
                    # Handle @mcp.tool
                    if isinstance(decorator, ast.Attribute) and decorator.attr == 'tool':
                        tools.append(node.name)
                    # Handle @tool
                    elif isinstance(decorator, ast.Name) and decorator.id == 'tool':
                        tools.append(node.name)
                    # Handle @mcp.tool() call
                    elif isinstance(decorator, ast.Call):
                        if isinstance(decorator.func, ast.Attribute) and decorator.func.attr == 'tool':
                             tools.append(node.name)
                        elif isinstance(decorator.func, ast.Name) and decorator.func.id == 'tool':
                             tools.append(node.name)

            # Check for Tool(name="...") instantiation
            if isinstance(node, ast.Call):
                is_tool_call = False
                if isinstance(node.func, ast.Name) and node.func.id == 'Tool':
                    is_tool_call = True
                elif isinstance(node.func, ast.Attribute) and node.func.attr == 'Tool':
                    is_tool_call = True
                
                if is_tool_call:
                    for keyword in node.keywords:
                        if keyword.arg == 'name':
                            resolved_name = resolver.resolve(keyword.value)
                            if resolved_name:
                                tools.append(resolved_name)
    except Exception as e:
        # print(f"Error parsing {filepath}: {e}")
        pass
    return tools

def scan_js_ts_file(filepath: str) -> List[str]:
    tools = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Regex for server.tool("name", ...) or .tool("name", ...)
        # Matches: server.tool("add", ...), this.server.tool('add', ...)
        # Also matches: server.registerTool("name", ...)
        
        # Pattern 1: .tool("name" or .registerTool("name"
        matches = re.findall(r'\.(?:tool|registerTool)\(\s*["\']([^"\']+)["\']', content)
        tools.extend(matches)

        # Pattern 2: name: "toolname" inside a tool definition object (common in some libraries)
        # This is harder to regex reliably without false positives, skipping for now unless needed.

    except Exception as e:
        # print(f"Error reading {filepath}: {e}")
        pass
    return tools

def scan_php_file(filepath: str) -> List[str]:
    """Scan PHP files for MCP tool definitions."""
    tools = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern 1: Classes that extend Tool
        # Example: class ListRoutes extends Tool
        class_matches = re.findall(r'class\s+(\w+)\s+extends\s+(?:\w+\\)*Tool', content)
        tools.extend(class_matches)
        
        # Pattern 2: Check for MCP-related use statements (imports)
        # If a file imports Laravel\Mcp or similar, and defines classes, those are likely tools
        has_mcp_import = bool(re.search(r'use\s+(?:Laravel\\Mcp|Mcp\\)', content))
        
        # Pattern 3: Tool registration patterns like $server->registerTool()
        # Example: $server->registerTool('toolName', ...)
        register_matches = re.findall(r'registerTool\(\s*["\']([^"\']+)["\']', content)
        tools.extend(register_matches)
        
        # Pattern 4: If we have MCP imports and class definitions, extract class names
        if has_mcp_import and not tools:
            # Get class names from files with MCP imports
            simple_class_matches = re.findall(r'class\s+(\w+)', content)
            # Only add if it's likely a tool (avoid helpers, traits, etc.)
            for class_name in simple_class_matches:
                # Look for common MCP method patterns in the class
                if re.search(rf'class\s+{class_name}.*?{{.*?(?:handle|schema|execute)\s*\(', content, re.DOTALL):
                    tools.append(class_name)
        
    except Exception as e:
        # print(f"Error reading {filepath}: {e}")
        pass
    return tools

def scan_csharp_file(filepath: str) -> List[str]:
    """Scan C# files for MCP tool definitions."""
    tools = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Pattern 1: Classes that inherit from BaseCommand or end with Command
        # Example: public sealed class StorageAccountGetCommand : BaseAzureCommand
        class_matches = re.findall(r'class\s+(\w+Command)\s*(?::|where)', content)
        tools.extend(class_matches)
        
        # Pattern 2: Check for MCP-related using statements
        has_mcp_import = bool(re.search(r'using\s+(?:Azure\.Mcp|Microsoft\.Mcp|Fabric\.Mcp)', content))
        
        # Pattern 3: Classes in MCP-related namespaces
        has_mcp_namespace = bool(re.search(r'namespace\s+(?:Azure\.Mcp|Microsoft\.Mcp|Fabric\.Mcp)', content))
        
        # Pattern 4: Tool registration or command patterns
        # Look for classes that have ExecuteAsync or Handle methods (common MCP patterns)
        if (has_mcp_import or has_mcp_namespace) and not tools:
            # Get all class names
            simple_class_matches = re.findall(r'(?:public|internal|private)?\s*(?:sealed|abstract)?\s*class\s+(\w+)', content)
            for class_name in simple_class_matches:
                # Look for ExecuteAsync, HandleAsync, or similar MCP command patterns
                if re.search(rf'class\s+{class_name}.*?{{.*?(?:ExecuteAsync|HandleAsync|Execute|Handle)\s*\(', content, re.DOTALL):
                    tools.append(class_name)
        
        # Pattern 5: [McpTool] or [Tool] attributes (if they use attributes)
        attribute_matches = re.findall(r'\[(?:Mcp)?Tool\(["\']([^"\']+)["\']\)\]', content)
        tools.extend(attribute_matches)
        
    except Exception as e:
        # print(f"Error reading {filepath}: {e}")
        pass
    return tools

def scan_directory(directory: str) -> List[str]:
    all_tools: Set[str] = set()
    
    for root, _, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            if file.endswith('.py'):
                all_tools.update(scan_python_file(filepath))
            elif file.endswith(('.js', '.ts')):
                all_tools.update(scan_js_ts_file(filepath))
            elif file.endswith('.php'):
                all_tools.update(scan_php_file(filepath))
            elif file.endswith('.cs'):
                all_tools.update(scan_csharp_file(filepath))
                
    return sorted(list(all_tools))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scan directory for MCP tools")
    parser.add_argument("directory", help="Directory to scan")
    args = parser.parse_args()
    
    if os.path.isdir(args.directory):
        tools = scan_directory(args.directory)
        print(json.dumps(tools))
    else:
        print(json.dumps([]))
