import ast
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, TypedDict

PROJECT_ROOT = Path(__file__).parent.resolve()
IGNORE_DIRS: Set[str] = {
    '.git', '.hg', '.svn', '.idea', '.venv', '.env', '__pycache__',
    'logs', 'files', '.pytest_cache', '.mypy_cache', '.ruff_cache',
    '.coverage', 'htmlcov', '.tox', '.eggs', 'dist', 'build', 'files'
}
# Добавьте сюда имена файлов, которые нужно игнорировать
IGNORE_FILES: Set[str] = {
    'test_db_connection.py',   # пример, уберите или оставьте
    'temp.py',
    'generate_structure.py',
    'compact_code.py'
}
OUTPUT_FILE = PROJECT_ROOT / 'files' / 'structure.md'


class CodeAnalysis(TypedDict):
    imports: List[str]
    classes: List[Dict[str, Any]]
    functions: List[Dict[str, Any]]


class TreeNode(TypedDict):
    name: str
    type: str
    path: str
    children: List['TreeNode']
    imports: List[str]
    classes: List[Dict[str, Any]]
    functions: List[Dict[str, Any]]


def analyze_code(content: str) -> Optional[CodeAnalysis]:
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        print(f"Ошибка синтаксиса: {e}")
        return None
    analyzer = CodeAnalyzer()
    analyzer.visit(tree)
    return {
        'imports': analyzer.imports,
        'classes': analyzer.classes,
        'functions': analyzer.functions
    }


class CodeAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.imports: List[str] = []
        self.classes: List[Dict[str, Any]] = []
        self.functions: List[Dict[str, Any]] = []
        self.class_stack: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        parts = []
        for alias in node.names:
            parts.append(f"{alias.name} as {alias.asname}" if alias.asname else alias.name)
        self.imports.append(f"import {', '.join(parts)}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module if node.module is not None else ''
        level = '.' * node.level if node.level else ''
        names = []
        for alias in node.names:
            names.append(f"{alias.name} as {alias.asname}" if alias.asname else alias.name)
        self.imports.append(f"from {level}{module} import {', '.join(names)}")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.class_stack.append(node.name)
        class_info: Dict[str, Any] = {
            'name': node.name,
            'methods': [],
            'bases': [self._safe_unparse(b) for b in node.bases]
        }
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                class_info['methods'].append(self._parse_function(item))
        self.classes.append(class_info)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if not self.class_stack:
            self.functions.append(self._parse_function(node))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        # Асинхронные функции обрабатываем так же, но добавим маркер async
        if not self.class_stack:
            func = self._parse_function(node)
            func['async'] = True
            self.functions.append(func)
        self.generic_visit(node)

    def _parse_function(self, node: ast.AST) -> Dict[str, Any]:
        is_async = isinstance(node, ast.AsyncFunctionDef)
        return {
            'name': node.name,
            'args': self._parse_arguments(node.args),
            'returns': self._safe_unparse(node.returns) if hasattr(node, 'returns') and node.returns else None,
            'decorators': [self._safe_unparse(d) for d in node.decorator_list],
            'async': is_async
        }

    def _parse_arguments(self, args: ast.arguments) -> List[Dict[str, Optional[str]]]:
        params: List[Dict[str, Optional[str]]] = []
        for arg in args.args:
            params.append({
                'name': arg.arg,
                'type': self._safe_unparse(arg.annotation) if arg.annotation else None
            })
        if args.vararg:
            params.append({
                'name': '*' + args.vararg.arg,
                'type': self._safe_unparse(args.vararg.annotation) if args.vararg.annotation else None
            })
        for kwarg, default_expr in zip(args.kwonlyargs, args.kw_defaults):
            default = self._safe_unparse(default_expr) if default_expr else None
            params.append({
                'name': kwarg.arg,
                'type': self._safe_unparse(kwarg.annotation) if kwarg.annotation else None,
                'default': default
            })
        if args.kwarg:
            params.append({
                'name': '**' + args.kwarg.arg,
                'type': self._safe_unparse(args.kwarg.annotation) if args.kwarg.annotation else None
            })
        return params

    @staticmethod
    def _safe_unparse(node: ast.AST) -> str:
        try:
            return ast.unparse(node)
        except Exception:
            return '...'


def build_project_tree(root_path: Path, ignore_dirs: Set[str], ignore_files: Set[str]) -> TreeNode:
    project_tree: TreeNode = {
        'name': root_path.name,
        'type': 'directory',
        'path': '',
        'children': [],
        'imports': [],
        'classes': [],
        'functions': []
    }

    # Сортируем для детерминированного порядка
    for path in sorted(root_path.iterdir(), key=lambda p: (not p.is_dir(), p.name)):
        if path.name in ignore_dirs or (path.is_dir() and path.name.startswith('.')):
            continue
        if path.is_dir():
            project_tree['children'].append(build_project_tree(path, ignore_dirs, ignore_files))
        elif path.suffix == '.py' and path.name not in ignore_files:
            try:
                content = path.read_text(encoding='utf-8')
            except Exception as e:
                print(f"Не удалось прочитать файл {path}: {e}")
                continue
            analysis = analyze_code(content)
            if analysis is None:
                print(f"Пропускаем файл (ошибка парсинга): {path}")
                continue
            project_tree['children'].append({
                'name': path.name,
                'type': 'file',
                'path': str(path.relative_to(root_path)),
                'children': [],
                **analysis
            })
    return project_tree


def generate_tree_only(node: TreeNode, level: int = 0) -> List[str]:
    lines = []
    indent = '  ' * level
    suffix = '/' if node['type'] == 'directory' else ''
    lines.append(f"{indent}{node['name']}{suffix}")
    children = sorted(node['children'], key=lambda x: (x['type'] == 'file', x['name']))
    for child in children:
        lines.extend(generate_tree_only(child, level + 1))
    return lines


def generate_file_contents(node: TreeNode) -> List[str]:
    lines = []
    children = sorted(node['children'], key=lambda x: (x['type'] == 'file', x['name']))
    for child in children:
        if child['type'] == 'directory':
            lines.extend(generate_file_contents(child))
        else:
            lines.append(f"\n# {child['path']}")
            if child['imports']:
                lines.append("## Импорты")
                lines.extend(f"- {imp}" for imp in child['imports'])
            if child['classes']:
                lines.append("## Классы")
                for cls in child['classes']:
                    bases = f"({', '.join(cls['bases'])})" if cls['bases'] else ''
                    lines.append(f"class {cls['name']}{bases}:")
                    for method in cls['methods']:
                        lines.append(f"  {format_signature(method)}")
            if child['functions']:
                lines.append("## Функции")
                for func in child['functions']:
                    lines.append(format_signature(func))
    return lines


def format_signature(func: Dict[str, Any]) -> str:
    params = []
    for arg in func['args']:
        p = arg['name']
        if arg.get('type'):
            p += f": {arg['type']}"
        if arg.get('default'):
            p += f" = {arg['default']}"
        params.append(p)

    ret = f" -> {func['returns']}" if func.get('returns') else ''
    decs = ' '.join(f"@{d}" for d in func['decorators'])
    prefix = f"{decs} " if decs else ''
    async_prefix = "async " if func.get('async') else ""
    return f"{prefix}{async_prefix}def {func['name']}({', '.join(params)}){ret}"


def main() -> None:
    print("Сборка структуры проекта...")
    project_tree = build_project_tree(PROJECT_ROOT, IGNORE_DIRS, IGNORE_FILES)

    tree_lines = generate_tree_only(project_tree)
    content_lines = generate_file_contents(project_tree)

    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("# Дерево проекта\n\n")
        f.write('\n'.join(tree_lines))
        f.write("\n\n# Содержание файлов\n")
        f.write('\n'.join(content_lines))
        f.write('\n')

    print(f"Отчёт сохранён: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
