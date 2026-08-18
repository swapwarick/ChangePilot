"""File classification and architectural relevance filtering for ChangePilot.

Distinguishes:
  1. Low-level file categories (FileTypeCategory):
     - SOURCE: Genuine language source code (.kt, .java, .py, .ts, .tsx, .js, .rs, .go, .c, .cpp, .cs)
     - TEST: Unit and integration test specifications
     - CONFIGURATION: Application & environment configurations (.json, .toml, .yaml, .env)
     - BUILD: Build system definitions (build.gradle.kts, pom.xml, Makefile, Dockerfile)
     - IDE_METADATA: IDE settings & project files (.idea/, .vscode/, .iml)
     - GENERATED: Compiled or generated code (build/, dist/, out/, *.min.js)
     - ASSET: Images, audio, fonts, binaries (.png, .webp, .svg, .ttf, .jar)
     - DOCUMENTATION: Markdown, documentation, license (.md, .txt, LICENSE)
     - BACKUP: Backup and temp files (*.bak, *~, *.orig)

  2. High-level architectural role classification (FileClassification):
     - ENTRYPOINT: Main application entrypoints, CLI commands, web routes, SDK client roots, Android activities/services
     - CLI_SCRIPT: Standalone execution scripts (scripts/, script.js, *.sh, *.bat, etc.)
     - EXAMPLE: Sample code and demonstrations (examples/, samples/, demo/)
     - TEST: Unit and integration test specifications (tests/, *.test.*, *.spec.*, *Test.kt)
     - CONFIGURATION: Application & build configurations (package.json, tsconfig.json, *.gradle, Dockerfile)
     - DOCUMENTATION: Documentation files (docs/, *.md, README, LICENSE)
     - GENERATED: Compiled or generated code (dist/, build/, .next/, node_modules/, *.min.js)
     - SOURCE_MODULE: Genuine internal source code module
     - ORPHAN_CANDIDATE: SOURCE_MODULE with zero incoming internal source imports
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import PurePosixPath
from typing import Any

from app.models.enums import FileClassification


class FileTypeCategory(StrEnum):
    SOURCE = "SOURCE"
    TEST = "TEST"
    CONFIGURATION = "CONFIGURATION"
    BUILD = "BUILD"
    IDE_METADATA = "IDE_METADATA"
    GENERATED = "GENERATED"
    ASSET = "ASSET"
    DOCUMENTATION = "DOCUMENTATION"
    BACKUP = "BACKUP"


SOURCE_EXTENSIONS = {
    ".kt", ".kts", ".java", ".py", ".ts", ".tsx", ".js", ".jsx",
    ".rs", ".go", ".c", ".cpp", ".cc", ".h", ".hpp", ".cs",
    ".swift", ".scala", ".rb", ".php", ".m", ".mm"
}

ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".svg",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".mp3", ".mp4", ".wav", ".ogg", ".jar", ".aar", ".so", ".dll", ".exe"
}

DOC_EXTENSIONS = {
    ".md", ".mdx", ".rst", ".txt", ".adoc", ".pdf", ".html"
}

BACKUP_EXTENSIONS = {
    ".bak", ".tmp", ".orig", ".swp", ".swo", "~"
}

BUILD_FILENAMES = {
    "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts",
    "pom.xml", "makefile", "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "gemfile", "cmakelists.txt", "cargo.toml"
}

CONFIG_FILENAMES = {
    "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock",
    "tsconfig.json", "tsconfig.base.json", "tsconfig.node.json", "pyproject.toml",
    "requirements.txt", "setup.py", "setup.cfg", "next.config.js", "next.config.mjs",
    "next.config.ts", "vite.config.js", "vite.config.ts", "vite.config.mjs",
    "webpack.config.js", "rollup.config.js", "babel.config.js", "tailwind.config.js",
    "tailwind.config.ts", "postcss.config.js", "postcss.config.mjs", "eslint.config.js",
    ".eslintrc.json", ".eslintrc.js", ".eslintrc.yml", ".prettierrc",
    ".env", ".env.local", ".env.example", ".env.development", ".env.production",
    "androidmanifest.xml"
}

SCRIPT_FILENAMES = {
    "script.js", "scripts.js", "build.js", "setup.js", "deploy.js",
    "seed.js", "migrate.js", "release.js", "run.js", "manage.py",
    "script.py", "scripts.py", "run.py", "seed.py", "build.py"
}

ENTRYPOINT_FILENAMES = {
    "main.py", "app.py", "server.py", "index.py", "cli.py", "worker.py",
    "main.ts", "main.tsx", "server.ts", "server.tsx", "index.ts", "index.tsx",
    "app.tsx", "app.ts", "main.js", "main.jsx", "server.js", "server.jsx",
    "index.js", "index.jsx", "app.js", "app.jsx", "worker.js", "worker.ts",
    "cli.ts", "cli.js", "client.ts", "client.js", "client.py", "sdk.ts",
    "sdk.js", "sdk.py", "api-client.ts", "api_client.py",
    "MainActivity.kt", "MainApplication.kt", "App.kt", "Application.kt"
}


def classify_file_type(file_path: str) -> FileTypeCategory:
    """Classifies a relative file path into a low-level architectural category."""
    norm = file_path.replace("\\", "/").strip()
    norm_lower = norm.lower()
    parts = [p.lower() for p in norm_lower.split("/") if p]
    basename = parts[-1] if parts else ""
    suffix = PurePosixPath(norm_lower).suffix

    # 1. Backups
    if any(norm_lower.endswith(b) for b in BACKUP_EXTENSIONS) or basename.startswith(".~"):
        return FileTypeCategory.BACKUP

    # 2. IDE Metadata
    if any(p in (".idea", ".vscode", ".settings", ".gradle") for p in parts) or suffix in (".iml", ".ipr", ".iws"):
        return FileTypeCategory.IDE_METADATA

    # 3. Generated or Build Output
    if any(p in ("build", "dist", "out", "target", "generated", "__pycache__", ".next", "coverage") for p in parts):
        return FileTypeCategory.GENERATED

    # 4. Assets & Media Binaries
    if suffix in ASSET_EXTENSIONS:
        return FileTypeCategory.ASSET

    # 5. Documentation
    if suffix in DOC_EXTENSIONS or basename in ("license", "notice", "readme", "contributing"):
        return FileTypeCategory.DOCUMENTATION

    # 6. Test Files
    if (
        any(p in ("test", "tests", "androidtest", "__tests__", "spec", "specs") for p in parts)
        or any(basename.endswith(s) for s in ("test.kt", "tests.kt", "spec.kt", "test.java", "spec.ts", "test.ts", "test.py", "_test.py"))
    ):
        return FileTypeCategory.TEST

    # 7. Build Definitions
    if basename in BUILD_FILENAMES or suffix in (".gradle", ".kts") and "build" in basename or basename in ("settings.gradle.kts", "build.gradle.kts"):
        return FileTypeCategory.BUILD

    # 8. Configurations
    if basename in CONFIG_FILENAMES or (suffix in (".json", ".toml", ".yaml", ".yml", ".xml", ".properties") and suffix != ".xml") or basename == "androidmanifest.xml":
        return FileTypeCategory.CONFIGURATION

    # 9. Source Code
    if suffix in SOURCE_EXTENSIONS:
        return FileTypeCategory.SOURCE

    return FileTypeCategory.SOURCE if "." in basename else FileTypeCategory.CONFIGURATION


def filter_architecturally_relevant_files(changed_files: list[str]) -> list[str]:
    """Returns only source, test, build, and config files (excluding IDE, generated, assets, backups, docs)."""
    relevant: list[str] = []
    relevant_categories = {
        FileTypeCategory.SOURCE,
        FileTypeCategory.TEST,
        FileTypeCategory.BUILD,
        FileTypeCategory.CONFIGURATION,
    }
    for f in changed_files:
        cat = classify_file_type(f)
        if cat in relevant_categories:
            relevant.append(f)
    return relevant


def classify_file(
    file_path: str,
    manifest_entrypoints: set[str] | None = None,
    package_json_entrypoints: set[str] | None = None,
    framework_signals: list[str] | None = None,
    android_entrypoints: set[str] | None = None,
) -> FileClassification:
    """Classifies a file path into its primary architectural role for AST & Orphan analysis.

    Precedence order:
      1. GENERATED / VENDOR / ASSET / BACKUP
      2. DOCUMENTATION (docs/, *.md, README)
      3. EXAMPLE (examples/, samples/, demo/)
      4. TEST (tests/, *.test.*, *.spec.*, *Test.kt)
      5. CLI_SCRIPT (scripts/, script.js, *.sh, *.bat)
      6. CONFIGURATION / BUILD (package.json, tsconfig.json, *.gradle, Dockerfile)
      7. ENTRYPOINT / ROUTE (main.*, app.*, index.*, client.*, pages/*, routes/*, Android activities)
      8. SOURCE_MODULE (Genuine application code)
    """
    if not file_path:
        return FileClassification.SOURCE_MODULE

    norm = file_path.replace("\\", "/").strip()
    norm_lower = norm.lower()
    parts = [p for p in norm.split("/") if p]
    parts_lower = [p.lower() for p in parts]
    filename = parts[-1] if parts else ""
    filename_lower = filename.lower()
    suffix = PurePosixPath(norm_lower).suffix
    stem_lower = PurePosixPath(norm_lower).stem

    # Combined entrypoint sets
    all_manifest_entrypoints = (manifest_entrypoints or set()) | (android_entrypoints or set())

    # 1. GENERATED & VENDOR & ASSETS & BACKUPS
    if any(norm_lower.endswith(b) for b in BACKUP_EXTENSIONS) or filename_lower.startswith(".~"):
        return FileClassification.GENERATED

    if any(p in (
        "dist", "build", "out", "target", "generated", "__pycache__",
        ".next", "coverage", ".git", ".gradle", ".idea", ".vscode",
        "node_modules", "venv", ".venv", ".turbo", ".cache", "vendor",
        "third_party", "third-party"
    ) for p in parts_lower):
        return FileClassification.GENERATED

    if any(filename_lower.endswith(m) for m in (
        ".min.js", ".min.css", ".bundle.js", ".d.ts.map", ".chunk.js", ".map", ".pyc", ".class"
    )):
        return FileClassification.GENERATED

    if suffix in ASSET_EXTENSIONS:
        return FileClassification.GENERATED

    # 2. DOCUMENTATION (docs/ folder or doc files)
    if any(p in ("docs", "doc", "documentation", "guides", "guide", "manual", "specifications") for p in parts_lower):
        return FileClassification.DOCUMENTATION

    if suffix in DOC_EXTENSIONS or stem_lower in (
        "readme", "license", "copying", "notice", "contributing",
        "changelog", "authors", "code_of_conduct", "security"
    ):
        return FileClassification.DOCUMENTATION

    # 3. EXAMPLES (examples/, samples/, demo/, showcase/)
    # Distinguish example directories from Java/Kotlin package namespaces like com.example
    is_example_dir = False
    for i, p in enumerate(parts_lower[:-1]):
        if p in ("examples", "samples", "sample", "demo", "demos", "quickstart", "tutorials", "showcase"):
            is_example_dir = True
            break
        if p == "example":
            if i > 0 and parts_lower[i - 1] in ("com", "org", "net", "io", "java", "kotlin", "src"):
                continue
            is_example_dir = True
            break

    if is_example_dir:
        return FileClassification.EXAMPLE

    # 4. TESTS
    if (
        any(p in ("test", "tests", "androidtest", "__tests__", "__test__", "spec", "specs", "testfixtures", "fixtures", "mocks", "stubs") for p in parts_lower)
        or any(filename_lower.endswith(s) for s in (
            "test.kt", "tests.kt", "spec.kt", "test.java", "tests.java",
            "spec.ts", "spec.tsx", "test.ts", "test.tsx", "test.js", "test.jsx", "spec.js", "spec.jsx",
            "test.py", "_test.py", "_test.go", "_test.rs"
        ))
        or (stem_lower.startswith("test_") and suffix in SOURCE_EXTENSIONS)
        or (stem_lower.endswith("test") and suffix in (".kt", ".java"))
    ):
        return FileClassification.TEST

    # 5. CLI SCRIPTS
    if (
        any(p in ("scripts", "script", "bin", "tools", "ci/scripts", "dev/scripts") for p in parts_lower)
        or filename_lower in SCRIPT_FILENAMES
        or suffix in (".sh", ".bash", ".zsh", ".bat", ".cmd", ".ps1", ".fish")
    ):
        return FileClassification.CLI_SCRIPT

    # 6. CONFIGURATION & BUILD DEFINITIONS
    if (
        filename_lower in CONFIG_FILENAMES
        or filename_lower in BUILD_FILENAMES
        or (suffix in (".json", ".toml", ".yaml", ".yml", ".xml", ".properties", ".ini", ".cfg", ".conf", ".gradle") and suffix not in SOURCE_EXTENSIONS)
    ):
        return FileClassification.CONFIGURATION

    # 7. ENTRYPOINTS & WEB ROUTES
    # Manifest / Android Entrypoints
    if all_manifest_entrypoints:
        if stem_lower in {e.lower() for e in all_manifest_entrypoints} or filename_lower in {e.lower() for e in all_manifest_entrypoints}:
            return FileClassification.ENTRYPOINT

    # Package.json bin / main / exports entrypoints
    if package_json_entrypoints:
        if norm in package_json_entrypoints or filename in package_json_entrypoints:
            return FileClassification.ENTRYPOINT

    # Android Component naming conventions
    if any(stem_lower.endswith(s.lower()) for s in (
        "activity", "service", "receiver", "broadcastreceiver", "provider",
        "contentprovider", "application", "screen", "viewmodel"
    )):
        return FileClassification.ENTRYPOINT

    if framework_signals:
        if any(s in framework_signals for s in ("Activity", "Service", "BroadcastReceiver", "ViewModel", "Jetpack Compose")):
            return FileClassification.ENTRYPOINT

    # Web framework routes (Next.js / Nuxt / Remix)
    if filename_lower in ("page.tsx", "page.jsx", "page.ts", "page.js", "layout.tsx", "layout.jsx", "route.ts", "route.js", "loading.tsx", "error.tsx", "not-found.tsx"):
        return FileClassification.ROUTE

    if any(p in ("pages", "routes", "controllers", "api", "endpoints") for p in parts_lower):
        return FileClassification.ROUTE

    # Standard Application / Server / Client / SDK / Worker Entrypoints
    if filename in ENTRYPOINT_FILENAMES or filename_lower in ENTRYPOINT_FILENAMES:
        return FileClassification.ENTRYPOINT

    # Client SDK files in src/ (e.g. src/client.ts, src/diary/client.ts)
    if stem_lower in ("client", "sdk", "api_client", "api-client", "agent-client") and suffix in SOURCE_EXTENSIONS:
        return FileClassification.ENTRYPOINT

    # 8. GENUINE SOURCE MODULE
    if suffix in SOURCE_EXTENSIONS:
        return FileClassification.SOURCE_MODULE

    return FileClassification.SOURCE_MODULE if "." in filename else FileClassification.CONFIGURATION


def extract_package_json_entrypoints(package_json_content: str | bytes | dict) -> set[str]:
    """Extracts all declared entrypoints and script targets from package.json."""
    entrypoints: set[str] = set()
    try:
        data = package_json_content if isinstance(package_json_content, dict) else json.loads(package_json_content)
    except Exception:
        return entrypoints

    # main, module, browser, types
    for key in ("main", "module", "browser", "types", "typings"):
        val = data.get(key)
        if isinstance(val, str) and val:
            clean = val.lstrip("./").replace("\\", "/")
            entrypoints.add(clean)
            entrypoints.add(clean.split("/")[-1])

    # bin
    bin_val = data.get("bin")
    if isinstance(bin_val, str) and bin_val:
        clean = bin_val.lstrip("./").replace("\\", "/")
        entrypoints.add(clean)
        entrypoints.add(clean.split("/")[-1])
    elif isinstance(bin_val, dict):
        for path_val in bin_val.values():
            if isinstance(path_val, str) and path_val:
                clean = path_val.lstrip("./").replace("\\", "/")
                entrypoints.add(clean)
                entrypoints.add(clean.split("/")[-1])

    # exports
    exports_val = data.get("exports")
    if isinstance(exports_val, str) and exports_val:
        clean = exports_val.lstrip("./").replace("\\", "/")
        entrypoints.add(clean)
    elif isinstance(exports_val, dict):
        def _extract_exp(obj: Any):
            if isinstance(obj, str) and obj:
                clean = obj.lstrip("./").replace("\\", "/")
                entrypoints.add(clean)
                entrypoints.add(clean.split("/")[-1])
            elif isinstance(obj, dict):
                for v in obj.values():
                    _extract_exp(v)
        _extract_exp(exports_val)

    return entrypoints
