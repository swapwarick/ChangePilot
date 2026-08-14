"""Tree-sitter Multilingual AST Code Parser.

Parses Python, TypeScript, and JavaScript source code into detailed AST representations
to extract imports, exports, module dependencies, API routes, database schemas, and framework usage.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter_javascript as ts_js
import tree_sitter_python as ts_py
import tree_sitter_typescript as ts_ts
from tree_sitter import Language, Parser


IGNORED_PATTERNS = (
    "node_modules/", ".git/", ".next/", "dist/", "build/", "coverage/",
    "venv/", ".venv/", "__pycache__/", "target/", ".pytest_cache/"
)

CONFIG_FILENAMES = (
    "next.config.js", "next.config.mjs", "next.config.ts",
    "vite.config.js", "vite.config.ts", "vitest.config.js", "vitest.config.ts",
    "eslint.config.js", "eslint.config.mjs", "tsconfig.json", "package.json",
    "Dockerfile", "docker-compose.yml", "pyproject.toml", "setup.py"
)


def is_generated_or_vendor(file_path: str) -> bool:
    norm = file_path.replace("\\", "/").lower()
    return any(p in norm or norm.startswith(p) for p in IGNORED_PATTERNS)


def is_config_file(file_path: str) -> bool:
    norm = file_path.replace("\\", "/").lower()
    name = norm.split("/")[-1]
    return name in CONFIG_FILENAMES or any(name.startswith(c.split("*")[0]) for c in CONFIG_FILENAMES if "*" in c)


@dataclass
class ImportSymbol:
    source_module: str
    imported_name: str
    alias: str | None = None
    is_relative: bool = False
    import_type: str = "SOURCE_IMPORT"
    line_number: int | None = None


@dataclass
class ClassSymbol:
    name: str
    base_classes: list[str] = field(default_factory=list)
    methods: list[str] = field(default_factory=list)
    is_db_model: bool = False
    line_number: int | None = None


@dataclass
class FunctionSymbol:
    name: str
    calls: list[str] = field(default_factory=list)
    line_number: int | None = None


@dataclass
class ParsedFileAST:
    file_path: str
    file_hash: str
    language: str
    imports: list[ImportSymbol] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    defined_classes: list[str] = field(default_factory=list)
    defined_functions: list[str] = field(default_factory=list)
    class_symbols: list[ClassSymbol] = field(default_factory=list)
    function_symbols: list[FunctionSymbol] = field(default_factory=list)
    call_references: list[str] = field(default_factory=list)
    api_routes: list[str] = field(default_factory=list)
    db_tables: list[str] = field(default_factory=list)
    framework_signals: list[str] = field(default_factory=list)
    package_deps: list[str] = field(default_factory=list)


class PathNormalizer:
    @staticmethod
    def normalize_path(path_str: str) -> str:
        if not path_str:
            return ""
        clean = path_str.replace("\\", "/").strip()
        parts = []
        for segment in clean.split("/"):
            if segment == "..":
                if parts:
                    parts.pop()
            elif segment != "." and segment != "":
                parts.append(segment)
        return "/".join(parts)

    @staticmethod
    def resolve_import_path(
        current_file: str,
        import_src: str,
        all_files: set[str],
        alias_map: dict[str, str] | None = None
    ) -> str | None:
        if not import_src:
            return None

        clean_src = import_src.replace("\\", "/").strip()

        # Handle path aliases (e.g. @/ -> src/ or frontend/)
        if alias_map:
            for alias_prefix, real_prefix in alias_map.items():
                if clean_src.startswith(alias_prefix):
                    clean_src = clean_src.replace(alias_prefix, real_prefix, 1)
                    break

        if clean_src.startswith("@/"):
            candidate_prefixes = ["src/", "frontend/", "app/", ""]
            for pref in candidate_prefixes:
                alt_src = pref + clean_src[2:]
                target = PathNormalizer._match_candidates(alt_src, all_files)
                if target:
                    return target

        if clean_src.startswith("."):
            current_dir = "/".join(current_file.replace("\\", "/").split("/")[:-1])
            combined = f"{current_dir}/{clean_src}" if current_dir else clean_src
            norm = PathNormalizer.normalize_path(combined)
            return PathNormalizer._match_candidates(norm, all_files)
        else:
            norm = PathNormalizer.normalize_path(clean_src)
            match = PathNormalizer._match_candidates(norm, all_files)
            if match:
                return match
            for file_path in all_files:
                if file_path.startswith(norm) or norm in file_path:
                    return file_path
            return None

    @staticmethod
    def _match_candidates(candidate_base: str, all_files: set[str]) -> str | None:
        if candidate_base in all_files:
            return candidate_base
        for ext in (".ts", ".tsx", ".js", ".jsx", ".py", ".mjs", ".cjs", ".json"):
            cand = f"{candidate_base}{ext}"
            if cand in all_files:
                return cand
        for index_file in ("/index.ts", "/index.tsx", "/index.js", "/index.jsx", "/__init__.py"):
            cand = f"{candidate_base}{index_file}"
            if cand in all_files:
                return cand
        return None


class TreeSitterCodeParser:
    """Multilingual AST Code Parser using Tree-Sitter."""

    def __init__(self) -> None:
        self._languages: dict[str, Language] = {
            "python": Language(ts_py.language()),
            "javascript": Language(ts_js.language()),
            "typescript": Language(ts_ts.language_typescript()),
            "tsx": Language(ts_ts.language_tsx()),
        }

    def detect_language(self, file_path: str) -> str | None:
        if is_generated_or_vendor(file_path):
            return None
        path = Path(file_path)
        ext = path.suffix.lower()
        if ext == ".py":
            return "python"
        if ext in (".ts", ".cts", ".mts"):
            return "typescript"
        if ext in (".tsx", ".jsx"):
            return "tsx"
        if ext in (".js", ".cjs", ".mjs"):
            return "javascript"
        if is_config_file(file_path):
            return "config"
        return None

    def compute_file_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def parse_file(self, relative_path: str, content: bytes) -> ParsedFileAST:
        file_hash = self.compute_file_hash(content)
        language_name = self.detect_language(relative_path)

        if not language_name or language_name not in self._languages:
            ast_res = ParsedFileAST(file_path=relative_path, file_hash=file_hash, language=language_name or "text")
            if relative_path.endswith("package.json"):
                self._extract_package_json(content, ast_res)
            elif relative_path.endswith("requirements.txt"):
                self._extract_requirements_txt(content, ast_res)
            return ast_res

        parser = Parser(self._languages[language_name])
        tree = parser.parse(content)
        code_str = content.decode("utf-8", errors="replace")

        ast_result = ParsedFileAST(file_path=relative_path, file_hash=file_hash, language=language_name)

        if language_name == "python":
            self._extract_python_ast(tree.root_node, code_str, ast_result)
        else:
            self._extract_js_ts_ast(tree.root_node, code_str, ast_result)

        return ast_result

    def _extract_package_json(self, content: bytes, result: ParsedFileAST) -> None:
        import json
        try:
            data = json.loads(content.decode("utf-8", errors="replace"))
            deps = list(data.get("dependencies", {}).keys()) + list(data.get("devDependencies", {}).keys())
            result.package_deps = deps[:50]
        except Exception:
            pass

    def _extract_requirements_txt(self, content: bytes, result: ParsedFileAST) -> None:
        text = content.decode("utf-8", errors="replace")
        for line in text.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                pkg_name = line.split("==")[0].split(">=")[0].split("<=")[0].strip()
                if pkg_name:
                    result.package_deps.append(pkg_name)

    def _extract_python_ast(self, root_node, code: str, result: ParsedFileAST) -> None:

        def traverse(node):
            line_no = node.start_point[0] + 1
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        mod_name = code[child.start_byte:child.end_byte]
                        result.imports.append(
                            ImportSymbol(source_module=mod_name, imported_name="*", line_number=line_no)
                        )
            elif node.type == "import_from_statement":
                module_name = ""
                for child in node.children:
                    if child.type in ("dotted_name", "relative_import"):
                        module_name = code[child.start_byte:child.end_byte]
                    elif child.type == "import_prefix":
                        module_name += code[child.start_byte:child.end_byte]
                    elif child.type == "dotted_name" and module_name:
                        imported_item = code[child.start_byte:child.end_byte]
                        result.imports.append(
                            ImportSymbol(
                                source_module=module_name,
                                imported_name=imported_item,
                                is_relative=module_name.startswith("."),
                                line_number=line_no,
                            )
                        )
            elif node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    cls_name = code[name_node.start_byte:name_node.end_byte]
                    result.defined_classes.append(cls_name)
                    result.exports.append(cls_name)

                    base_classes = []
                    superclasses = node.child_by_field_name("superclasses")
                    if superclasses:
                        base_classes = [c.strip() for c in code[superclasses.start_byte:superclasses.end_byte].strip("()").split(",") if c.strip()]

                    is_db = any("base" in b.lower() or "model" in b.lower() or "declarative" in b.lower() for b in base_classes)
                    if is_db:
                        result.db_tables.append(cls_name.lower())

                    methods = []
                    body_node = node.child_by_field_name("body")
                    if body_node:
                        for child in body_node.children:
                            if child.type == "function_definition":
                                m_name = child.child_by_field_name("name")
                                if m_name:
                                    methods.append(code[m_name.start_byte:m_name.end_byte])

                    result.class_symbols.append(
                        ClassSymbol(name=cls_name, base_classes=base_classes, methods=methods, is_db_model=is_db, line_number=line_no)
                    )

            elif node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    fn_name = code[name_node.start_byte:name_node.end_byte]
                    result.defined_functions.append(fn_name)
                    result.exports.append(fn_name)

                    calls = []
                    def extract_calls(n):
                        if n.type == "call":
                            fn_child = n.child_by_field_name("function")
                            if fn_child:
                                calls.append(code[fn_child.start_byte:fn_child.end_byte])
                        for c in n.children:
                            extract_calls(c)

                    body_node = node.child_by_field_name("body")
                    if body_node:
                        extract_calls(body_node)

                    result.function_symbols.append(FunctionSymbol(name=fn_name, calls=calls[:20], line_number=line_no))

            elif node.type == "decorator":
                decorator_text = code[node.start_byte:node.end_byte]
                if any(verb in decorator_text for verb in ("router.get", "router.post", "app.get", "app.post", "router.put", "router.delete", "router.patch")):
                    route_line = decorator_text.splitlines()[0]
                    result.api_routes.append(route_line)
                    result.framework_signals.append("fastapi")

            elif node.type == "call":
                fn_child = node.child_by_field_name("function")
                if fn_child:
                    c_name = code[fn_child.start_byte:fn_child.end_byte]
                    result.call_references.append(c_name)

            for child in node.children:
                traverse(child)

        traverse(root_node)

    def _extract_js_ts_ast(self, root_node, code: str, result: ParsedFileAST) -> None:

        def traverse(node):
            line_no = node.start_point[0] + 1
            if node.type == "import_statement":
                # import { foo } from 'bar'
                source_node = node.child_by_field_name("source")
                if source_node:
                    source_val = code[source_node.start_byte:source_node.end_byte].strip("'\"")
                    result.imports.append(
                        ImportSymbol(
                            source_module=source_val,
                            imported_name="*",
                            is_relative=source_val.startswith("."),
                            import_type="SOURCE_IMPORT",
                            line_number=line_no,
                        )
                    )
            elif node.type == "export_statement":
                decl = node.child_by_field_name("declaration")
                if decl:
                    name_node = decl.child_by_field_name("name")
                    if name_node:
                        result.exports.append(code[name_node.start_byte:name_node.end_byte])
            elif node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    cls_name = code[name_node.start_byte:name_node.end_byte]
                    result.defined_classes.append(cls_name)
                    result.class_symbols.append(ClassSymbol(name=cls_name, line_number=line_no))
            elif node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    fn_name = code[name_node.start_byte:name_node.end_byte]
                    result.defined_functions.append(fn_name)
                    result.function_symbols.append(FunctionSymbol(name=fn_name, line_number=line_no))
            elif node.type == "call_expression":
                fn_node = node.child_by_field_name("function")
                if fn_node:
                    fn_name = code[fn_node.start_byte:fn_node.end_byte]
                    result.call_references.append(fn_name)
                    if fn_name in ("require", "import"):
                        # Extract require('module') or import('module')
                        args_node = node.child_by_field_name("arguments")
                        if args_node and args_node.children:
                            first_arg = args_node.children[1] if len(args_node.children) > 1 else args_node.children[0]
                            source_val = code[first_arg.start_byte:first_arg.end_byte].strip("'\"` ")
                            if source_val and not source_val.startswith("("):
                                import_kind = "DYNAMIC_IMPORT" if fn_name == "import" else "SOURCE_IMPORT"
                                result.imports.append(
                                    ImportSymbol(
                                        source_module=source_val,
                                        imported_name="*",
                                        is_relative=source_val.startswith("."),
                                        import_type=import_kind,
                                        line_number=line_no,
                                    )
                                )
                    elif fn_name in ("fetch", "axios.get", "axios.post", "useQuery", "useMutation"):
                        result.framework_signals.append("react-query/http")

            # Check Next.js App Router API route conventions (export async function GET / POST)
            if "route.ts" in result.file_path or "route.js" in result.file_path:
                if node.type == "export_statement":
                    text = code[node.start_byte:node.end_byte]
                    for verb in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                        if f"function {verb}" in text or f"const {verb}" in text:
                            route_path = f"/{result.file_path.replace('app/', '').replace('/route.ts', '').replace('/route.js', '')}"
                            result.api_routes.append(f"{verb} {route_path}")

            for child in node.children:
                traverse(child)

        traverse(root_node)

