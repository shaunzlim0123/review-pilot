"""Data access specialist — port of src/agents/specialists/data-access.ts."""

from __future__ import annotations

import re

from ...models import Finding
from .common import (
    LanguageTaggedPattern,
    SpecialistInput,
    apply_hard_rules,
    create_finding,
    limit_findings,
    pattern_applies_to,
)
from .registry import specialist

DATA_ACCESS_PATTERNS: list[LanguageTaggedPattern] = [
    LanguageTaggedPattern(
        pattern=re.compile(r"config\.MysqlCli|gorm\.|sql\.Open\(|RedisCli|redis\.NewClient"),
        languages=["go"],
    ),
    LanguageTaggedPattern(
        pattern=re.compile(r"db\.Query\(|db\.Exec\("),
        languages=["go"],
    ),
    LanguageTaggedPattern(
        pattern=re.compile(r"\bsequelize\b|\bknex\b"),
        languages=["typescript"],
    ),
    LanguageTaggedPattern(
        pattern=re.compile(r"\bpsycopg2\b|\bpymysql\b|\bSQLAlchemy\b"),
        languages=["python"],
    ),
    LanguageTaggedPattern(
        pattern=re.compile(r"executeQuery\(|EntityManager|\.createQuery\("),
        languages=["java"],
    ),
]


def _check_built_in_data_access(inp: SpecialistInput) -> list[Finding]:
    findings: list[Finding] = []

    for routed_file in inp.routed_files:
        path = routed_file.file.path
        language = routed_file.classification.language

        if routed_file.classification.kind in ("dal", "config"):
            continue

        for line in routed_file.file.added_lines:
            triggered = any(
                pattern_applies_to(p, language) and p.pattern.search(line.content)
                for p in DATA_ACCESS_PATTERNS
            )

            if triggered:
                findings.append(
                    create_finding(
                        rule_id="data-access-outside-dal",
                        severity="warning",
                        file=path,
                        line=line.line_number,
                        title="Direct data-access usage outside DAL/config layer",
                        explanation=(
                            "Direct database/cache access in non-DAL files increases coupling "
                            "and makes review harder. Keep data access behind DAL/repository boundaries."
                        ),
                        suggestion="Move this access into DAL/repository and call it from service/handler.",
                        category="data-access",
                        agent="data-access-agent",
                        evidence=line.content.strip(),
                    )
                )

    return findings


@specialist("data-access")
def run_data_access_agent(inp: SpecialistInput) -> list[Finding]:
    findings = [*_check_built_in_data_access(inp), *apply_hard_rules(inp)]
    return limit_findings(findings, inp.policy, "data-access")
