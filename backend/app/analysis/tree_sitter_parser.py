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


@dataclass
class ImportSymbol:
    source_module: str
    imported_name: str
    alias: str | None = None
    is_relative: bool = False


@dataclass
class ParsedFileAST:
    file_path: str
    file_hash: str
    language: str
    imports: list[ImportSymbol] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    defined_classes: list[str] = field(default_factory=list)
    defined_functions: list[str] = field(default_factory=list)
    api_routes: list[str] = field(default_factory=list)
    db_tables: list[str] = field(default_factory=list)
    framework_signals: list[str] = field(default_factory=list)


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
        return None

    def compute_file_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def parse_file(self, relative_path: str, content: bytes) -> ParsedFileAST:
        file_hash = self.compute_file_hash(content)
        language_name = self.detect_language(relative_path)

        if not language_name or language_name not in self._languages:
            return ParsedFileAST(file_path=relative_path, file_hash=file_hash, language="text")

        parser = Parser(self._languages[language_name])
        tree = parser.parse(content)
        code_str = content.decode("utf-8", errors="replace")

        ast_result = ParsedFileAST(file_path=relative_path, file_hash=file_hash, language=language_name)

        if language_name == "python":
            self._extract_python_ast(tree.root_node, code_str, ast_result)
        else:
            self._extract_js_ts_ast(tree.root_node, code_str, ast_result)

        return ast_result

    def _extract_python_ast(self, root_node, code: str, result: ParsedFileAST) -> None:

        def traverse(node):
            if node.type == "import_statement":
                # import foo, bar
                for child in node.children:
                    if child.type == "dotted_name":
                        mod_name = code[child.start_byte:child.end_byte]
                        result.imports.append(ImportSymbol(source_module=mod_name, imported_name="*"))
            elif node.type == "import_from_statement":
                # from foo import bar
                module_name = ""
                for child in node.children:
                    if child.type == "dotted_name" or child.type == "relative_import":
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
                            )
                        )
            elif node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte]
                    result.defined_classes.append(name)
                    result.exports.append(name)
                    # Check for DB models
                    superclasses = node.child_by_field_name("superclasses")
                    if superclasses and ("Base" in code[superclasses.start_byte:superclasses.end_byte] or "Model" in code[superclasses.start_byte:superclasses.end_byte]):
                        result.db_tables.append(name.lower())
            elif node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    name = code[name_node.start_byte:name_node.end_byte]
                    result.defined_functions.append(name)
                    result.exports.append(name)
            elif node.type == "decorator":
                decorator_text = code[node.start_byte:node.end_byte]
                if any(verb in decorator_text for verb in ("router.get", "router.post", "app.get", "app.post", "router.put", "router.delete")):
                    result.api_routes.append(decorator_text.splitlines()[0])
                    result.framework_signals.append("fastapi")

            for child in node.children:
                traverse(child)

        traverse(root_node)

    def _extract_js_ts_ast(self, root_node, code: str, result: ParsedFileAST) -> None:

        def traverse(node):
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
                    result.defined_classes.append(code[name_node.start_byte:name_node.end_byte])
            elif node.type == "function_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    result.defined_functions.append(code[name_node.start_byte:name_node.end_byte])
            elif node.type == "call_expression":
                fn_node = node.child_by_field_name("function")
                if fn_node:
                    fn_name = code[fn_node.start_byte:fn_node.end_byte]
                    if fn_name in ("fetch", "axios.get", "axios.post", "useQuery", "useMutation"):
                        result.framework_signals.append("react-query/http")

            for child in node.children:
                traverse(child)

        traverse(root_node)
