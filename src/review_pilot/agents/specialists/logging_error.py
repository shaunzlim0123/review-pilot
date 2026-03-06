"""Logging/error specialist — port of src/agents/specialists/logging-error.ts."""

from __future__ import annotations

import re

from ...models import Finding
from .common import (
    LanguageTaggedPattern,
    SpecialistInput,
    apply_hard_rules,
    create_finding,
    get_added_lines_text,
    limit_findings,
    pattern_applies_to,
)
from .registry import specialist

LEGACY_LOG_PATTERNS: list[LanguageTaggedPattern] = [
    LanguageTaggedPattern(pattern=re.compile(r"\blog\.V1\."), languages=["go"]),
    LanguageTaggedPattern(pattern=re.compile(r"\bconsole\.(log|error|warn)\("), languages=["typescript"]),
]


def _check_built_in_logging(inp: SpecialistInput) -> list[Finding]:
    findings: list[Finding] = []

    for routed_file in inp.routed_files:
        if routed_file.classification.kind == "test":
            continue

        path = routed_file.file.path
        language = routed_file.classification.language
        added_text = get_added_lines_text(routed_file)

        for line in routed_file.file.added_lines:
            if (
                pattern_applies_to(LEGACY_LOG_PATTERNS[0], language)
                and LEGACY_LOG_PATTERNS[0].pattern.search(line.content)
            ):
                findings.append(
                    create_finding(
                        rule_id="logging-legacy-v1",
                        severity="warning",
                        file=path,
                        line=line.line_number,
                        title="Legacy logging API used in new code",
                        explanation=(
                            "New code should not introduce legacy logging APIs. "
                            "Use the structured logging convention required by the repository."
                        ),
                        suggestion="Replace legacy logger usage with the preferred structured logging API.",
                        category="logging-error",
                        agent="logging-error-agent",
                        evidence=line.content.strip(),
                    )
                )

            if (
                pattern_applies_to(LEGACY_LOG_PATTERNS[1], language)
                and LEGACY_LOG_PATTERNS[1].pattern.search(line.content)
            ):
                findings.append(
                    create_finding(
                        rule_id="logging-console-usage",
                        severity="warning",
                        file=path,
                        line=line.line_number,
                        title="Console logging in application code",
                        explanation=(
                            "Application code should use structured logging for "
                            "observability and consistent error context."
                        ),
                        suggestion="Replace console logging with the project logging abstraction.",
                        category="logging-error",
                        agent="logging-error-agent",
                        evidence=line.content.strip(),
                    )
                )

        if re.search(r"\bcatch\s*\(", added_text) and not re.search(
            r"\blog(?:ger)?\.|\bthrow\b|\.Error\(|\.error\(", added_text
        ):
            catch_line = next(
                (
                    line.line_number
                    for line in routed_file.file.added_lines
                    if re.search(r"\bcatch\s*\(", line.content)
                ),
                1,
            )
            findings.append(
                create_finding(
                    rule_id="logging-catch-no-log",
                    severity="warning",
                    file=path,
                    line=catch_line,
                    title="Catch block appears to miss error logging/propagation",
                    explanation=(
                        "New catch blocks should either log with context or "
                        "rethrow to avoid silent failures."
                    ),
                    suggestion="Add structured error logging and/or rethrow after handling.",
                    category="logging-error",
                    agent="logging-error-agent",
                )
            )

    return findings


@specialist("logging-error")
def run_logging_error_agent(inp: SpecialistInput) -> list[Finding]:
    findings = [*_check_built_in_logging(inp), *apply_hard_rules(inp)]
    return limit_findings(findings, inp.policy, "logging-error")
