"""Inspect MCP server repositories and list their exposed tools.
you need to provide github repository url as an argument to the script.
for example: mcp_tool_inspector.py https://github.com/D4Vinci/Scrapling

"""

import argparse
import ast
import re
import shutil
import subprocess

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set


SKIP_DIR_NAMES = {
    "node_modules",
    "dist",
    "build",
    "public",
    "coverage",
    ".next",
    "out",
    "__pycache__",
    ".venv",
    "venv",
    "tmp",
    "temp",
    "frontend",
    "locales",
    "__tests__",
    "tests",
    "spec",
    "models",
}


class RepositoryError(Exception):
    """Raised when the repository cannot be fetched or processed."""


def clone_repository(repo_url: str, workdir: Path) -> Path:
    """Clone the provided Git repository URL into a temporary directory.

    Args:
        repo_url: HTTPS or SSH URL pointing to a GitHub repository.
        workdir: The parent directory where the repository clone should live.

    Returns:
        Path to the cloned repository root.

    Raises:
        RepositoryError: If cloning fails or the target directory cannot be determined.
    """

    repo_name = repo_url.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    target_dir = workdir / repo_name

    if target_dir.exists():
        shutil.rmtree(target_dir)

    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(target_dir)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
        raise RepositoryError(f"Git clone failed with exit code {exc.returncode}: {stderr.strip()}") from exc
    except OSError as exc:
        raise RepositoryError(f"Unable to execute git: {exc}") from exc

    if not target_dir.exists():
        raise RepositoryError("Repository clone did not produce expected directory")

    return target_dir


def _is_tool_decorator(node: ast.AST) -> bool:
    """Return True if the decorator node looks like an MCP tool decorator."""

    if isinstance(node, ast.Name):
        return node.id.lower() == "tool"
    if isinstance(node, ast.Attribute):
        return node.attr.lower() in {"tool", "register_tool"}
    if isinstance(node, ast.Call):
        return _is_tool_decorator(node.func)
    return False


def _extract_constant(node: ast.AST) -> Optional[str]:
    """Extract constant string values from AST nodes."""

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Str):
        return node.s
    return None


def _callable_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _should_skip_path(path: Path) -> bool:
    return any(part.startswith(".") or part in SKIP_DIR_NAMES for part in path.parts)


@dataclass
class ToolInfo:
    name: str
    description: Optional[str]
    origin: str


class MCPToolAnalyzer(ast.NodeVisitor):
    """Visitor that looks for MCP tool registrations inside an AST tree."""

    def __init__(self, module_path: Path) -> None:
        self.module_path = module_path
        self.tools: List[ToolInfo] = []
        self._docstrings: Dict[str, Optional[str]] = {}

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Detect class-based tools (e.g. inheriting from a Tool class)."""
        self._docstrings[node.name] = ast.get_docstring(node)

        # Check base classes for "Tool" or "BaseTool"
        is_tool_class = False
        for base in node.bases:
            if isinstance(base, ast.Name) and "tool" in base.id.lower():
                is_tool_class = True
            elif isinstance(base, ast.Attribute) and "tool" in base.attr.lower():
                is_tool_class = True

        if is_tool_class:
            description = ast.get_docstring(node)
            # Look for 'name' and 'description' assignments in class body
            name = node.name  # Default to class name
            for item in node.body:
                if isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            if target.id == "name" and isinstance(item.value, ast.Constant):
                                name = item.value.value
                            elif target.id == "description" and isinstance(item.value, ast.Constant):
                                description = item.value.value

            self.tools.append(
                ToolInfo(name=name, description=description, origin=str(self.module_path))
            )

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._docstrings[node.name] = ast.get_docstring(node)
        self._maybe_collect_from_decorators(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._docstrings[node.name] = ast.get_docstring(node)
        self._maybe_collect_from_decorators(node)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        if self._looks_like_tool_constructor(node):
            info = self._extract_tool_from_constructor(node)
            if info:
                self.tools.append(info)
        elif self._looks_like_registry_registration(node):
            info = self._extract_tool_from_registry_call(node)
            if info:
                self.tools.append(info)
        self.generic_visit(node)

    def _maybe_collect_from_decorators(self, node: ast.AST) -> None:
        decorators = getattr(node, "decorator_list", [])
        if not decorators:
            return

        if any(_is_tool_decorator(deco) for deco in decorators):
            name = getattr(node, "name", "<anonymous>")
            description = self._docstrings.get(name) if isinstance(name, str) else None
            self.tools.append(
                ToolInfo(name=name, description=description, origin=str(self.module_path))
            )

    def _looks_like_tool_constructor(self, node: ast.Call) -> bool:
        func = node.func
        if isinstance(func, ast.Name) and func.id.lower() == "tool":
            return True
        if isinstance(func, ast.Attribute) and func.attr.lower() == "tool":
            return True
        if isinstance(func, ast.Call):
            return self._looks_like_tool_constructor(func)
        return False

    def _extract_tool_from_constructor(self, node: ast.Call) -> Optional[ToolInfo]:
        name = None
        description = None

        for kw in node.keywords:
            if kw.arg == "name":
                name = _extract_constant(kw.value)
            elif kw.arg == "description":
                description = _extract_constant(kw.value)

        if name is None and node.args:
            first_arg = node.args[0]
            name = _extract_constant(first_arg)
            if name is None:
                name = _callable_name(first_arg)
                if isinstance(name, str) and description is None:
                    description = self._docstrings.get(name)
        if description is None and len(node.args) > 1:
            description = _extract_constant(node.args[1])

        if name:
            return ToolInfo(name=name, description=description, origin=str(self.module_path))
        return None

    def _looks_like_registry_registration(self, node: ast.Call) -> bool:
        func = node.func
        if isinstance(func, ast.Attribute):
            lower = func.attr.lower()
            return any(needle in lower for needle in ("register", "add_tool", "register_tool"))
        if isinstance(func, ast.Name):
            lower = func.id.lower()
            return "register" in lower or lower.endswith("tool")
        return False

    def _extract_tool_from_registry_call(self, node: ast.Call) -> Optional[ToolInfo]:
        name = None
        description = None

        for kw in node.keywords:
            if kw.arg == "name":
                name = _extract_constant(kw.value)
            elif kw.arg == "description":
                description = _extract_constant(kw.value)
            elif kw.arg in {"title", "label"} and name is None:
                name = _extract_constant(kw.value)
            elif kw.arg in {"tool", "tool_obj"}:
                # Attempt nested extraction from Tool(...) constructor
                inner = kw.value
                if isinstance(inner, ast.Call) and self._looks_like_tool_constructor(inner):
                    info = self._extract_tool_from_constructor(inner)
                    if info:
                        return info

        if name:
            return ToolInfo(name=name, description=description, origin=str(self.module_path))

        # Try positional args heuristics
        if node.args:
            potential_name = _extract_constant(node.args[0])
            if potential_name:
                name = potential_name
            else:
                potential_callable = _callable_name(node.args[0])
                if potential_callable:
                    name = potential_callable
                    if description is None:
                        description = self._docstrings.get(potential_callable)
            if len(node.args) > 1:
                potential_description = _extract_constant(node.args[1])
                if potential_description:
                    description = potential_description

        if name:
            return ToolInfo(name=name, description=description, origin=str(self.module_path))
        return None


STRING_LITERAL_PATTERN = re.compile(
    r"""
    (?P<quote>['"`])           # opening quote
    (?P<value>                 # capture value
        (?:\\.|(?!\1).)*?      # allow escaped characters, stop at matching quote
    )
    \1                         # closing quote
    """,
    re.VERBOSE | re.DOTALL,
)

TOOL_CALL_PATTERN = re.compile(
    r"""
    (?P<prefix>
        register[A-Za-z]*|
        addTool|
        defineTool|
        createTool|
        tool(?=\s*\()|
        \.tool(?=\s*\()|
        toolRegistry\.[A-Za-z]+|
        tools?\s*:\s*\[|
        aibitat\.function
    )
    """,
    re.VERBOSE,
)

TOOL_OBJECT_DECL_PATTERN = re.compile(
    r"""
    (?:export\s+)?const\s+
    (?P<identifier>[A-Za-z_][A-Za-z0-9_]*)
    \s*(?::[^=]+)?=\s*{
    """,
    re.VERBOSE,
)

CONST_LITERAL_PATTERN = re.compile(
    r"""
    (?:export\s+)?const\s+
    (?P<identifier>[A-Za-z_][A-Za-z0-9_]*)
    \s*=\s*
    (?P<value>(?P<delim>['"`]).*?(?P=delim))
    \s*;
    """,
    re.VERBOSE | re.DOTALL,
)

CLASS_BASETOOL_PATTERN = re.compile(
    r"(?:export\s+)?class\s+(?P<class_name>[A-Za-z_][A-Za-z0-9_]*)\s+extends\s+BaseTool\s*{",
)


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"', "`"}:
        value = value[1:-1]
    return value.replace(r"\'", "'").replace(r"\"", '"').replace(r"\`", "`")


def _split_top_level(value: str, separator: str = ",") -> List[str]:
    parts: List[str] = []
    current: List[str] = []
    depth_paren = depth_brace = depth_bracket = 0
    in_string: Optional[str] = None
    escape = False

    for char in value:
        if in_string:
            current.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
            continue

        if char in {"'", '"', "`"}:
            in_string = char
            current.append(char)
            continue

        if char == "(":
            depth_paren += 1
        elif char == ")":
            depth_paren = max(depth_paren - 1, 0)
        elif char == "{":
            depth_brace += 1
        elif char == "}":
            depth_brace = max(depth_brace - 1, 0)
        elif char == "[":
            depth_bracket += 1
        elif char == "]":
            depth_bracket = max(depth_bracket - 1, 0)

        if char == separator and depth_paren == depth_brace == depth_bracket == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(char)

    if current:
        parts.append("".join(current).strip())

    return [part for part in parts if part]


def _extract_balanced_segment(
    source: str, start_index: int, open_char: str, close_char: str
) -> Optional[str]:
    """Extract text inside matching delimiters starting at ``start_index``."""

    if start_index >= len(source) or source[start_index] != open_char:
        return None

    depth = 1
    in_string: Optional[str] = None
    escape = False
    segment_start = start_index + 1
    index = segment_start

    while index < len(source):
        char = source[index]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == in_string:
                in_string = None
            index += 1
            continue

        if char == "/" and index + 1 < len(source):
            next_char = source[index + 1]
            if next_char == "/":
                newline = source.find("\n", index + 2)
                if newline == -1:
                    return None
                index = newline + 1
                continue
            if next_char == "*":
                end_comment = source.find("*/", index + 2)
                if end_comment == -1:
                    return None
                index = end_comment + 2
                continue

        if char in {"'", '"', "`"}:
            in_string = char
            index += 1
            continue

        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return source[segment_start:index]

        index += 1

    return None


def _extract_field_from_object(text: str, field_name: str) -> Optional[str]:
    pattern = re.compile(
        rf"\b{field_name}\s*:\s*(?P<value>(['\"`]).*?\2)",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        return None
    return _unquote(match.group("value"))


def _parse_tool_object(obj_text: str, origin: Path) -> Optional[ToolInfo]:
    name = _extract_field_from_object(obj_text, "name")
    if not name:
        # Sometimes tools export `title` instead of `name`
        name = _extract_field_from_object(obj_text, "title")
    if not name:
        return None

    description = (
        _extract_field_from_object(obj_text, "description")
        or _extract_field_from_object(obj_text, "summary")
    )

    return ToolInfo(name=name, description=description, origin=str(origin))


def _extract_property_value(body: str, property_name: str, constants: Dict[str, str]) -> Optional[str]:
    literal_pattern = re.compile(
        rf"^\s*(?:this\.)?{re.escape(property_name)}(?![A-Za-z0-9_])\s*=\s*(?P<value>(?P<delim>['\"`]).*?(?P=delim))",
        re.MULTILINE | re.DOTALL,
    )
    match = literal_pattern.search(body)
    if match:
        return _unquote(match.group("value"))

    identifier_pattern = re.compile(
        rf"^\s*(?:this\.)?{re.escape(property_name)}(?![A-Za-z0-9_])\s*=\s*(?P<identifier>[A-Za-z_][A-Za-z0-9_]*)\s*;",
        re.MULTILINE,
    )
    match = identifier_pattern.search(body)
    if not match:
        return None

    identifier = match.group("identifier")
    return constants.get(identifier)


def analyze_go_source(source: str, relative_path: Path) -> List[ToolInfo]:
    """Best-effort tool discovery for Go sources."""
    tools: List[ToolInfo] = []

    # Look for NewTool function calls
    # Example: NewTool("tool_name", "description", ...)
    new_tool_pattern = re.compile(
        r'NewTool\s*\(\s*"(?P<name>[^"]+)"\s*,\s*"(?P<description>[^"]+)"',
        re.MULTILINE
    )

    for match in new_tool_pattern.finditer(source):
        tools.append(ToolInfo(
            name=match.group("name"),
            description=match.group("description"),
            origin=str(relative_path)
        ))

    # Look for structs defining tools via field tags or naming conventions could be added here
    return tools


def analyze_typescript_source(source: str, relative_path: Path) -> List[ToolInfo]:
    """Best-effort tool discovery for TypeScript/JavaScript sources."""

    tools: List[ToolInfo] = []

    constants: Dict[str, str] = {}
    for match in CONST_LITERAL_PATTERN.finditer(source):
        constants[match.group("identifier")] = _unquote(match.group("value"))

    for match in TOOL_OBJECT_DECL_PATTERN.finditer(source):
        identifier = match.group("identifier")
        block = _extract_balanced_segment(source, match.end() - 1, "{", "}")
        if block is None:
            continue
        info = _parse_tool_object(block, relative_path)
        if info:
            tools.append(info)
            constants.setdefault(identifier, info.name)

    for match in CLASS_BASETOOL_PATTERN.finditer(source):
        brace_index = match.end() - 1
        body = _extract_balanced_segment(source, brace_index, "{", "}")
        if body is None:
            continue

        name = _extract_property_value(body, "name", constants)
        description = _extract_property_value(body, "description", constants)
        if name:
            tools.append(ToolInfo(name=name, description=description, origin=str(relative_path)))

    for match in TOOL_CALL_PATTERN.finditer(source):
        prefix = match.group("prefix")
        index = match.end()

        while index < len(source) and source[index].isspace():
            index += 1

        if index >= len(source):
            continue

        if prefix.strip().endswith("["):
            open_index = source.find("[", match.start(), match.end())
            if open_index == -1:
                continue
            block = _extract_balanced_segment(source, open_index, "[", "]")
            if block is None:
                continue
            elements = _split_top_level(block, separator=",")
            for element in elements:
                element = element.strip()
                if element.startswith("{"):
                    info = _parse_tool_object(element, relative_path)
                    if info:
                        tools.append(info)
            continue

        if source[index] != "(":
            continue

        arguments = _extract_balanced_segment(source, index, "(", ")")
        if arguments is None:
            continue

        arg_parts = _split_top_level(arguments)
        if not arg_parts:
            continue

        first_arg = arg_parts[0]
        if first_arg.startswith("{"):
            info = _parse_tool_object(first_arg, relative_path)
            if info:
                tools.append(info)
            continue

        literal_match = STRING_LITERAL_PATTERN.match(first_arg.strip())
        name = _unquote(literal_match.group(0)) if literal_match else None
        description = None

        if len(arg_parts) > 1:
            second_arg = arg_parts[1]
            if second_arg.startswith("{"):
                info = _parse_tool_object(second_arg, relative_path)
                if info:
                    description = info.description
            else:
                literal_match = STRING_LITERAL_PATTERN.match(second_arg.strip())
                if literal_match:
                    description = _unquote(literal_match.group(0))

        if name:
            tools.append(ToolInfo(name=name, description=description, origin=str(relative_path)))

        if name is None and first_arg.startswith("["):
            # registerTools([...])
            elements = _split_top_level(first_arg.strip()[1:-1])
            for element in elements:
                if element.strip().startswith("{"):
                    info = _parse_tool_object(element, relative_path)
                    if info:
                        tools.append(info)

    return tools
def analyze_repository(root: Path) -> List[ToolInfo]:
    """Walk the repository tree collecting MCP tool definitions."""

    collected: List[ToolInfo] = []

    python_files = list(root.rglob("*.py"))
    ts_files = list(root.rglob("*.ts")) + list(root.rglob("*.tsx"))
    js_files = list(root.rglob("*.js")) + list(root.rglob("*.jsx"))
    go_files = list(root.rglob("*.go"))

    for path in python_files:
        relative_path = path.relative_to(root)
        if _should_skip_path(relative_path):
            continue

        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError:
            continue

        analyzer = MCPToolAnalyzer(module_path=relative_path)
        analyzer.visit(tree)
        collected.extend(analyzer.tools)

    for path in ts_files + js_files:
        relative_path = path.relative_to(root)
        if _should_skip_path(relative_path):
            continue
        if path.name.endswith(".min.js") or path.name.endswith(".min.ts"):
            continue

        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        collected.extend(
            analyze_typescript_source(source, relative_path)
        )

    for path in go_files:
        relative_path = path.relative_to(root)
        if _should_skip_path(relative_path):
            continue

        try:
            source = path.read_text(encoding="utf-8")
            collected.extend(analyze_go_source(source, relative_path))
        except (OSError, UnicodeDecodeError):
            continue

    return collected


def deduplicate_tools(tools: Iterable[ToolInfo]) -> List[ToolInfo]:
    """Remove duplicate tool entries keeping the first occurrence."""

    seen: Set[str] = set()
    unique: List[ToolInfo] = []

    for tool in tools:
        if tool.name not in seen:
            seen.add(tool.name)
            unique.append(tool)

    return unique


def run_inspection(repo_url: str) -> List[ToolInfo]:
    """Clone the repository and return discovered MCP tools."""

    with tempfile.TemporaryDirectory(prefix="mcp_repo_") as tmpdir:
        repo_path = clone_repository(repo_url, Path(tmpdir))
        tools = analyze_repository(repo_path)
        return deduplicate_tools(tools)


def format_results(tools: List[ToolInfo]) -> str:
    """Create a human-readable summary of tool discovery results."""

    if not tools:
        return "No MCP tools were discovered in the repository."

    lines = ["Discovered MCP tools:\n"]
    for tool in tools:
        lines.append(f"- Name: {tool.name}")
        if tool.description:
            lines.append(f"  Description: {tool.description}")
        lines.append(f"  Declared in: {tool.origin}\n")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect MCP server repositories and list tools.")
    parser.add_argument("repo", help="GitHub repository URL (HTTPS or SSH)")
    args = parser.parse_args(argv)

    try:
        tools = run_inspection(args.repo)
    except RepositoryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(format_results(tools))
    return 0


if __name__ == "__main__":
    sys.exit(main())
