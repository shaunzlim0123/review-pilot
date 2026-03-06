"""Shared specialist utilities — port of src/agents/specialists/common.ts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from wcmatch import fnmatch

from ...models import (
    FileContent,
    Finding,
    PolicyBundle,
    RoutedFile,
    Severity,
    SpecialistName,
)


@dataclass
class LanguageTaggedPattern:
    pattern: re.Pattern[str]
    languages: list[str] | None = None


def pattern_applies_to(p: LanguageTaggedPattern, language: str) -> bool:
    if not p.languages:
        return True
    return language in p.languages


@dataclass
class SpecialistInput:
    specialist: SpecialistName
    routed_files: list[RoutedFile]
    file_content_by_path: dict[str, FileContent]
    policy: PolicyBundle


def create_finding(
    *,
    rule_id: str,
    severity: Severity,
    file: str,
    line: int,
    title: str,
    explanation: str,
    suggestion: str | None = None,
    category: str,
    agent: str,
    evidence: str | None = None,
) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        file=file,
        line=line,
        title=title,
        explanation=explanation,
        suggestion=suggestion,
        category=category,
        agent=agent,
        evidence=evidence,
    )


def is_allowlisted(path: str, rule_id: str, policy: PolicyBundle) -> bool:
    for entry in policy.allowlist:
        if not fnmatch.fnmatch(path, entry.path, flags=0):
            continue
        if not entry.rule_ids or len(entry.rule_ids) == 0:
            return True
        if rule_id in entry.rule_ids:
            return True
    return False


def _find_line_by_regex_in_added_lines(routed_file: RoutedFile, regex: re.Pattern[str]) -> int:
    for line in routed_file.file.added_lines:
        if regex.search(line.content):
            return line.line_number
    if routed_file.file.added_lines:
        return routed_file.file.added_lines[0].line_number
    return 1


def _find_line_by_regex_in_file(content: str, regex: re.Pattern[str]) -> int:
    for i, line in enumerate(content.split("\n")):
        if regex.search(line):
            return i + 1
    return 1


def _get_text_target(rule_target: str, routed_file: RoutedFile, file_content: str | None) -> str:
    if rule_target == "file_content":
        return file_content or ""
    return get_added_lines_text(routed_file)


def _get_line_target(
    rule_target: str,
    regex: re.Pattern[str],
    routed_file: RoutedFile,
    file_content: str | None,
) -> int:
    if rule_target == "file_content":
        return _find_line_by_regex_in_file(file_content or "", regex)
    return _find_line_by_regex_in_added_lines(routed_file, regex)


def apply_hard_rules(inp: SpecialistInput) -> list[Finding]:
    findings: list[Finding] = []
    rules = [
        r
        for r in inp.policy.hard_rules
        if r.category == "any" or r.category == inp.specialist
    ]

    for routed_file in inp.routed_files:
        file_path = routed_file.file.path
        fc = inp.file_content_by_path.get(file_path)
        file_content = fc.content if fc else None

        for rule in rules:
            if not fnmatch.fnmatch(file_path, rule.scope, flags=0):
                continue
            if is_allowlisted(file_path, rule.id, inp.policy):
                continue

            try:
                regex = re.compile(rule.pattern, re.MULTILINE)
            except re.error:
                continue

            target_text = _get_text_target(rule.target, routed_file, file_content)
            matched = bool(regex.search(target_text))
            violated = matched if rule.mode == "forbid_regex" else not matched

            if not violated:
                continue

            line = _get_line_target(rule.target, regex, routed_file, file_content)
            findings.append(
                create_finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    file=file_path,
                    line=line,
                    title=rule.description,
                    explanation=rule.message or f"Hard rule violated: {rule.id}",
                    category=inp.specialist,
                    agent=f"{inp.specialist}-agent",
                    evidence=rule.pattern,
                )
            )

    return findings


def limit_findings(
    findings: list[Finding],
    policy: PolicyBundle,
    specialist_name: str,
) -> list[Finding]:
    settings = policy.agents.specialists.get(specialist_name)
    if not settings:
        return findings
    return findings[: settings.max_findings]


def get_added_lines_text(routed_file: RoutedFile) -> str:
    return "\n".join(line.content for line in routed_file.file.added_lines)
