from pathlib import PurePosixPath


class RepositoryParser:
    def detect_language(self, file_paths: list[str]) -> str | None:
        extension_counts: dict[str, int] = {}
        for file_path in file_paths:
            suffix = PurePosixPath(file_path).suffix.lower()
            if suffix:
                extension_counts[suffix] = extension_counts.get(suffix, 0) + 1
        if not extension_counts:
            return None
        extension = max(extension_counts, key=extension_counts.get)
        return {
            ".ts": "TypeScript",
            ".tsx": "TypeScript",
            ".js": "JavaScript",
            ".jsx": "JavaScript",
            ".py": "Python",
            ".go": "Go",
            ".rs": "Rust",
            ".java": "Java",
            ".cs": "C#",
        }.get(extension, extension.removeprefix(".").upper())

    def detect_frameworks(self, file_paths: list[str]) -> list[str]:
        normalized = [path.replace("\\", "/").lower() for path in file_paths]
        frameworks: set[str] = set()
        if any("next.config" in path or "/app/" in path for path in normalized):
            frameworks.add("Next.js")
        if any("fastapi" in path or "main.py" in path for path in normalized):
            frameworks.add("FastAPI")
        if any("package.json" in path for path in normalized):
            frameworks.add("Node.js")
        if any("pyproject.toml" in path for path in normalized):
            frameworks.add("Python")
        return sorted(frameworks)

