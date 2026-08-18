"""File classification and architectural relevance filtering for ChangePilot.

Distinguishes:
  - SOURCE: Actual language source code (.kt, .java, .py, .ts, .tsx, .js, .rs, .go, .c, .cpp, .cs)
  - TEST: Unit and integration test specifications
  - CONFIGURATION: Application & environment configurations (.json, .toml, .yaml, .env)
  - BUILD: Build system definitions (build.gradle.kts, pom.xml, Makefile, Dockerfile)
  - IDE_METADATA: IDE settings & project files (.idea/, .vscode/, .iml)
  - GENERATED: Compiled or generated code (build/, dist/, out/, *.min.js)
  - ASSET: Images, audio, fonts, binaries (.png, .webp, .svg, .ttf, .jar)
  - DOCUMENTATION: Markdown, documentation, license (.md, .txt, LICENSE)
  - BACKUP: Backup and temp files (*.bak, *~, *.orig)
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePosixPath


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
    ".md", ".rst", ".txt", ".adoc", ".pdf", ".html"
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
    "package.json", "package-lock.json", "tsconfig.json", "pyproject.toml",
    "requirements.txt", "setup.py", "next.config.js", "next.config.mjs", "next.config.ts",
    "vite.config.js", "vite.config.ts", "eslint.config.js", ".eslintrc.json",
    ".env", ".env.local", ".env.example", "androidmanifest.xml"
}


def classify_file_type(file_path: str) -> FileTypeCategory:
    """Classifies a relative file path into an architectural category."""
    norm = file_path.replace("\\", "/").strip()
    norm_lower = norm.lower()
    parts = [p.lower() for p in norm_lower.split("/")]
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
    if basename in BUILD_FILENAMES or suffix in (".gradle", ".kts") and "build" in basename:
        return FileTypeCategory.BUILD

    # 8. Configurations
    if basename in CONFIG_FILENAMES or suffix in (".json", ".toml", ".yaml", ".yml", ".xml", ".properties") and not suffix == ".xml" or basename == "androidmanifest.xml":
        return FileTypeCategory.CONFIGURATION

    # 9. Source Code
    if suffix in SOURCE_EXTENSIONS:
        return FileTypeCategory.SOURCE

    return FileTypeCategory.SOURCE if "." in basename else FileTypeCategory.CONFIGURATION


def filter_architecturally_relevant_files(changed_files: list[str]) -> list[str]:
    """Returns only source, test, build, and config files (excluding IDE, generated, assets, backups)."""
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
