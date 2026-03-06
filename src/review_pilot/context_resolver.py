"""File content fetching and import parsing — port of src/context-resolver.ts."""

from __future__ import annotations

import math
import re

from github.Repository import Repository

from .models import ChangedFile, FileContent, RepoMetadata, ReviewContext

LANG_MAP: dict[str, str] = {
    "ts": "typescript",
    "tsx": "typescript",
    "js": "javascript",
    "jsx": "javascript",
    "py": "python",
    "go": "go",
    "java": "java",
    "rs": "rust",
    "rb": "ruby",
    "yml": "yaml",
    "yaml": "yaml",
    "json": "json",
    "md": "markdown",
    "sh": "shell",
    "bash": "shell",
}


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4) if text else 0


def _get_language(file_path: str) -> str:
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    return LANG_MAP.get(ext, ext)


def extract_imports(content: str, language: str) -> list[str]:
    imports: list[str] = []

    if language in ("typescript", "javascript"):
        import_re = re.compile(r"""(?:import\s+.*?\s+from\s+['"](.+?)['"]|require\s*\(\s*['"](.+?)['"]\s*\))""")
        for m in import_re.finditer(content):
            import_path = m.group(1) or m.group(2)
            if import_path.startswith((".", "/")):
                imports.append(import_path)

    elif language == "python":
        py_re = re.compile(r"(?:from\s+(\S+)\s+import|^import\s+(\S+))", re.MULTILINE)
        for m in py_re.finditer(content):
            mod = m.group(1) or m.group(2)
            if mod.startswith("."):
                imports.append(mod)

    elif language == "go":
        go_re = re.compile(r'import\s+(?:"([^"]+)"|\(\s*([\s\S]*?)\s*\))')
        for m in go_re.finditer(content):
            if m.group(1):
                imports.append(m.group(1))
            elif m.group(2):
                group_imports = re.findall(r'"([^"]+)"', m.group(2))
                imports.extend(group_imports)

    return imports


def resolve_import_path(
    import_path: str,
    from_file: str,
    language: str,
) -> list[str]:
    dir_parts = from_file.split("/")[:-1]
    candidates: list[str] = []

    normalized_import = import_path
    parent_traversals = 0
    if language == "python":
        dot_match = re.match(r"^(\.+)(.*)", import_path)
        if dot_match:
            parent_traversals = len(dot_match.group(1)) - 1
            normalized_import = dot_match.group(2) or ""

    parts = list(dir_parts)
    for _ in range(parent_traversals):
        if parts:
            parts.pop()

    import_parts = [p for p in normalized_import.split("/") if p]
    all_parts = parts + import_parts
    resolved: list[str] = []
    for part in all_parts:
        if part == ".":
            continue
        if part == "..":
            if resolved:
                resolved.pop()
        else:
            resolved.append(part)
    base_path = "/".join(resolved)

    if language in ("typescript", "javascript"):
        candidates.extend([
            base_path + ".ts",
            base_path + ".tsx",
            base_path + ".js",
            base_path + ".jsx",
            base_path + "/index.ts",
            base_path + "/index.js",
        ])
    else:
        candidates.append(base_path)

    return candidates


def _fetch_file_content(
    repo: Repository,
    path: str,
    ref: str,
) -> str | None:
    try:
        content_file = repo.get_contents(path, ref=ref)
        if isinstance(content_file, list):
            return None
        return content_file.decoded_content.decode("utf-8")
    except Exception:
        return None


def build_review_context(
    repo: Repository,
    *,
    owner: str,
    repo_name: str,
    pull_number: int,
    base_branch: str,
    head_branch: str,
    head_sha: str,
    changed_files: list[ChangedFile],
    context_budget: int,
) -> ReviewContext:
    metadata = RepoMetadata(
        owner=owner,
        repo=repo_name,
        pull_number=pull_number,
        base_branch=base_branch,
        head_branch=head_branch,
        head_sha=head_sha,
    )

    token_budget = context_budget
    changed_file_contents: list[FileContent] = []
    imported_file_contents: list[FileContent] = []
    fetched_paths: set[str] = set()

    for file in changed_files:
        if file.status == "removed":
            continue

        content = _fetch_file_content(repo, file.path, head_sha)
        if not content:
            continue

        tokens = estimate_tokens(content)
        if tokens > token_budget:
            continue
        token_budget -= tokens

        language = _get_language(file.path)
        changed_file_contents.append(FileContent(path=file.path, content=content, language=language))
        fetched_paths.add(file.path)

    for fc in changed_file_contents:
        import_paths = extract_imports(fc.content, fc.language)

        for import_path in import_paths:
            candidates = resolve_import_path(import_path, fc.path, fc.language)

            for candidate in candidates:
                if candidate in fetched_paths:
                    break

                content = _fetch_file_content(repo, candidate, head_sha)
                if not content:
                    continue

                tokens = estimate_tokens(content)
                if tokens > token_budget:
                    break
                token_budget -= tokens

                imported_file_contents.append(
                    FileContent(path=candidate, content=content, language=_get_language(candidate))
                )
                fetched_paths.add(candidate)
                break

    return ReviewContext(
        changed_files=changed_file_contents,
        imported_files=imported_file_contents,
        repo_metadata=metadata,
        total_token_estimate=context_budget - token_budget,
    )
