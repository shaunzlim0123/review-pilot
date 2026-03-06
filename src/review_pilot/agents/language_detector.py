"""Language detection by file extension — port of src/agents/language-detector.ts."""

from __future__ import annotations

EXT_TO_LANGUAGE: dict[str, str] = {
    "go": "go",
    "ts": "typescript",
    "tsx": "typescript",
    "js": "typescript",
    "jsx": "typescript",
    "mjs": "typescript",
    "cjs": "typescript",
    "py": "python",
    "java": "java",
    "kt": "kotlin",
    "kts": "kotlin",
    "rb": "ruby",
    "rs": "rust",
    "c": "c",
    "h": "c",
    "cpp": "cpp",
    "cc": "cpp",
    "cxx": "cpp",
    "hpp": "cpp",
    "cs": "csharp",
    "php": "php",
    "sh": "shell",
    "bash": "shell",
    "zsh": "shell",
}


def detect_language(path: str) -> str:
    last_dot = path.rfind(".")
    if last_dot == -1:
        return "unknown"
    ext = path[last_dot + 1 :].lower()
    return EXT_TO_LANGUAGE.get(ext, "unknown")
