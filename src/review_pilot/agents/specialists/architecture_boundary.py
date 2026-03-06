"""Architecture boundary specialist — port of src/agents/specialists/architecture-boundary.ts."""

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

_IMPORT_LINE_RE = re.compile(r"^\s*import\s+.*$", re.MULTILINE)

HANDLER_DATA_ACCESS_PATTERNS: list[LanguageTaggedPattern] = [
    LanguageTaggedPattern(
        pattern=re.compile(r"/dal\b|/repository\b|config\.MysqlCli|gorm\."),
        languages=["go"],
    ),
    LanguageTaggedPattern(
        pattern=re.compile(r"/dal\b|/repository\b|knex\b|sequelize\b|typeorm\b"),
        languages=["typescript"],
    ),
]


def _check_built_in_architecture(inp: SpecialistInput) -> list[Finding]:
    findings: list[Finding] = []

    for routed_file in inp.routed_files:
        path = routed_file.file.path
        language = routed_file.classification.language
        fc = inp.file_content_by_path.get(path)
        content = fc.content if fc else ""
        imports = _IMPORT_LINE_RE.findall(content)

        if routed_file.classification.kind == "handler":
            for line in imports:
                triggered = any(
                    pattern_applies_to(p, language) and p.pattern.search(line)
                    for p in HANDLER_DATA_ACCESS_PATTERNS
                )
                if triggered:
                    findings.append(
                        create_finding(
                            rule_id="arch-handler-direct-data-access",
                            severity="warning",
                            file=path,
                            line=1,
                            title="Handler appears to depend directly on DAL/DB concerns",
                            explanation=(
                                "Handlers should stay thin and delegate business/data access "
                                "through service boundaries."
                            ),
                            suggestion=(
                                "Move DAL/DB operations behind a service layer and "
                                "call that service from the handler."
                            ),
                            category="architecture-boundary",
                            agent="architecture-boundary-agent",
                            evidence=line.strip(),
                        )
                    )

        if routed_file.classification.kind == "model":
            for line in imports:
                if re.search(r"/service\b|/handler\b", line):
                    findings.append(
                        create_finding(
                            rule_id="arch-model-upward-dependency",
                            severity="warning",
                            file=path,
                            line=1,
                            title="Model layer imports service/handler layer",
                            explanation=(
                                "Model/data structures should not depend on "
                                "higher-level application layers."
                            ),
                            category="architecture-boundary",
                            agent="architecture-boundary-agent",
                            evidence=line.strip(),
                        )
                    )

    return findings


@specialist("architecture-boundary")
def run_architecture_boundary_agent(inp: SpecialistInput) -> list[Finding]:
    findings = [*_check_built_in_architecture(inp), *apply_hard_rules(inp)]
    return limit_findings(findings, inp.policy, "architecture-boundary")
