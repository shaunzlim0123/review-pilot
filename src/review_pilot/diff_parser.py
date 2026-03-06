"""Hunk parsing and line tracking — port of src/diff-parser.ts."""

from __future__ import annotations

import re
from typing import Any

from wcmatch import fnmatch

from .models import ChangedFile, ChangedLine, DiffHunk

DEFAULT_IGNORE_PATTERNS = [
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "**/*.min.js",
    "**/*.min.css",
    "**/*.map",
    "**/*.png",
    "**/*.jpg",
    "**/*.gif",
    "**/*.ico",
    "**/*.woff",
    "**/*.woff2",
    "**/*.ttf",
    "**/*.eot",
    "**/*.svg",
    "**/*.pdf",
]

_HUNK_HEADER_RE = re.compile(r"^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@(.*)")


def parse_hunks(patch: str) -> list[DiffHunk]:
    hunks: list[DiffHunk] = []
    current: DiffHunk | None = None

    for line in patch.split("\n"):
        m = _HUNK_HEADER_RE.match(line)
        if m:
            if current is not None:
                hunks.append(current)
            current = DiffHunk(
                header=line,
                old_start=int(m.group(1)),
                old_lines=int(m.group(2)) if m.group(2) else 1,
                new_start=int(m.group(3)),
                new_lines=int(m.group(4)) if m.group(4) else 1,
                content="",
            )
        elif current is not None:
            current.content += ("\n" if current.content else "") + line

    if current is not None:
        hunks.append(current)
    return hunks


def extract_changed_lines(
    hunks: list[DiffHunk],
) -> tuple[list[ChangedLine], list[ChangedLine]]:
    added_lines: list[ChangedLine] = []
    removed_lines: list[ChangedLine] = []

    for hunk in hunks:
        new_line_num = hunk.new_start
        old_line_num = hunk.old_start

        for line in hunk.content.split("\n"):
            if line.startswith("+"):
                added_lines.append(
                    ChangedLine(type="add", line_number=new_line_num, content=line[1:])
                )
                new_line_num += 1
            elif line.startswith("-"):
                removed_lines.append(
                    ChangedLine(type="delete", line_number=old_line_num, content=line[1:])
                )
                old_line_num += 1
            else:
                new_line_num += 1
                old_line_num += 1

    return added_lines, removed_lines


def _normalize_status(status: str) -> str:
    if status in ("added", "removed", "renamed"):
        return status
    return "modified"


def should_ignore_file(
    path: str,
    extra_ignore_patterns: list[str] | None = None,
) -> bool:
    all_patterns = DEFAULT_IGNORE_PATTERNS + (extra_ignore_patterns or [])
    return any(fnmatch.fnmatch(path, pattern) for pattern in all_patterns)


def parse_pr_files(
    files: list[dict[str, Any]],
    ignore_patterns: list[str] | None = None,
) -> list[ChangedFile]:
    changed_files: list[ChangedFile] = []

    for file_data in files:
        filename: str = file_data["filename"]
        if should_ignore_file(filename, ignore_patterns):
            continue
        patch: str | None = file_data.get("patch")
        if not patch:
            continue

        hunks = parse_hunks(patch)
        added_lines, removed_lines = extract_changed_lines(hunks)

        changed_files.append(
            ChangedFile(
                path=filename,
                status=_normalize_status(file_data.get("status", "modified")),
                hunks=hunks,
                added_lines=added_lines,
                removed_lines=removed_lines,
                patch=patch,
            )
        )

    return changed_files
