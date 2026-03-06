"""Pytest fixtures replacing tests/helpers.ts factories."""

from __future__ import annotations

from review_pilot.agents.language_detector import detect_language
from review_pilot.models import (
    AgentRuntimeSettings,
    AgentSettings,
    ChangedFile,
    ChangedLine,
    ConfigSettings,
    EnforcementSettings,
    FileClassification,
    FileContent,
    PolicyBundle,
    RoutedFile,
)

SPECIALIST_NAMES = [
    "security",
    "logging-error",
    "architecture-boundary",
    "api-contract",
    "data-access",
    "reliability",
]


def make_changed_file(path: str, added: list[str] | None = None) -> ChangedFile:
    added = added or []
    return ChangedFile(
        path=path,
        status="modified",
        hunks=[],
        added_lines=[
            ChangedLine(type="add", line_number=idx + 1, content=content)
            for idx, content in enumerate(added)
        ],
        removed_lines=[],
        patch="",
    )


def make_routed_file(
    path: str,
    kind: str,
    added: list[str] | None = None,
    language: str | None = None,
) -> RoutedFile:
    return RoutedFile(
        file=make_changed_file(path, added),
        classification=FileClassification(
            path=path,
            kind=kind,  # type: ignore[arg-type]
            language=language or detect_language(path),
        ),
    )


def make_file_content(path: str, content: str, language: str = "typescript") -> FileContent:
    return FileContent(path=path, content=content, language=language)


def make_default_agents() -> AgentSettings:
    return AgentSettings(
        specialists={
            name: AgentRuntimeSettings(enabled=True, max_findings=100)
            for name in SPECIALIST_NAMES
        }
    )


def make_policy(**overrides: object) -> PolicyBundle:
    defaults: dict[str, object] = dict(
        soft_rules=[],
        hard_rules=[],
        allowlist=[],
        ignore=[],
        settings=ConfigSettings(
            max_inline_comments=3,
            model="claude-sonnet-4-5-20250929",
            context_budget=50000,
        ),
        enforcement=EnforcementSettings(
            mode="warn",
            block_on=["critical"],
            new_code_only=True,
            max_comments=3,
        ),
        agents=make_default_agents(),
        file_classification={},
        specialist_routing={},
    )
    defaults.update(overrides)
    return PolicyBundle(**defaults)  # type: ignore[arg-type]
