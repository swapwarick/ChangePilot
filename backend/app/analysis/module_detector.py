"""Architectural Application Module Detector for ChangePilot.

Extracts genuine application components and Gradle/Maven/Node workspace modules
from repository paths and configuration files (settings.gradle, package.json, etc.).
Strictly excludes IDE metadata (.idea, .vscode), generated build outputs, and assets.
"""

from __future__ import annotations

import re

from app.analysis.file_classifier import FileTypeCategory, classify_file_type


class ModuleDetector:
    """Detects and normalizes architectural module names across languages and frameworks."""

    @staticmethod
    def detect_gradle_modules(settings_gradle_content: str) -> list[str]:
        """Extracts declared Gradle modules from settings.gradle / settings.gradle.kts."""
        modules = []
        # Matches include(":app"), include ':core', include(":feature:login")
        matches = re.findall(r"""include\s*\(?['":]([a-zA-Z0-9_\-:]+)['"]?\)?|\binclude\s+['"]([^'"]+)['"]""", settings_gradle_content)
        for m1, m2 in matches:
            raw = m1 or m2
            clean = raw.strip(":").replace(":", "/")
            if clean and clean not in modules:
                modules.append(clean)
        return modules

    @staticmethod
    def extract_impacted_modules(
        changed_files: list[str],
        declared_modules: list[str] | None = None,
    ) -> list[str]:
        """Returns only genuine architectural/source modules impacted by changes."""
        impacted: set[str] = set()

        for f in changed_files:
            norm = f.replace("\\", "/").strip()
            cat = classify_file_type(norm)

            # Exclude IDE metadata, assets, generated code, and backups from architectural modules
            if cat in (
                FileTypeCategory.IDE_METADATA,
                FileTypeCategory.ASSET,
                FileTypeCategory.GENERATED,
                FileTypeCategory.BACKUP,
            ):
                continue

            parts = [p for p in norm.split("/") if p]
            if not parts:
                continue

            # 1. Match against explicitly declared Gradle/Maven/Monorepo modules
            if declared_modules:
                matched_declared = False
                for mod in declared_modules:
                    if norm.startswith(f"{mod}/") or norm == mod or f"/{mod}/" in norm:
                        impacted.add(f":{mod.replace('/', ':')}")
                        matched_declared = True
                        break
                if matched_declared:
                    continue

            # 2. Source directories matching
            top_dir = parts[0].lower()
            if top_dir in ("src", "app", "lib", "packages", "modules", "core", "server", "client", "ui", "data", "feature"):
                if len(parts) > 1 and top_dir in ("src", "packages", "modules"):
                    impacted.add(f"{top_dir}/{parts[1]}")
                else:
                    impacted.add(parts[0])
            elif cat in (FileTypeCategory.SOURCE, FileTypeCategory.TEST):
                if len(parts) > 1:
                    impacted.add(parts[0])
                else:
                    impacted.add("root")
            elif cat == FileTypeCategory.BUILD:
                if len(parts) > 1:
                    impacted.add(parts[0])
                else:
                    impacted.add("build")

        return sorted(list(impacted))
