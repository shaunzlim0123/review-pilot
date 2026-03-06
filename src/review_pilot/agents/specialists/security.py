"""Security specialist — port of src/agents/specialists/security.ts."""

from __future__ import annotations

import re

from ...models import Finding
from .common import SpecialistInput, apply_hard_rules, create_finding, limit_findings
from .registry import specialist

SECRET_PATTERNS: list[dict[str, str | re.Pattern[str]]] = [
    {
        "id": "security-hardcoded-secret-assignment",
        "regex": re.compile(r'(?:api[_-]?key|secret|token|password)\s*[:=]\s*["\'][^"\']{8,}["\']', re.IGNORECASE),
        "title": "Possible hardcoded secret in code",
    },
    {
        "id": "security-long-hex-literal",
        "regex": re.compile(r"\b[a-fA-F0-9]{32,}\b"),
        "title": "Long hex literal detected",
    },
    {
        "id": "security-aws-access-key",
        "regex": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "title": "AWS-style access key detected",
    },
    {
        "id": "security-private-key-material",
        "regex": re.compile(r"-----BEGIN\s+(?:RSA|EC|OPENSSH|PRIVATE)\s+KEY-----"),
        "title": "Private key material detected",
    },
]


def _check_built_in_security(inp: SpecialistInput) -> list[Finding]:
    findings: list[Finding] = []

    for routed_file in inp.routed_files:
        path = routed_file.file.path

        if routed_file.classification.kind == "generated":
            findings.append(
                create_finding(
                    rule_id="security-generated-file-edit",
                    severity="critical",
                    file=path,
                    line=1,
                    title="Generated file modified",
                    explanation=(
                        "This file appears generated and should not be manually edited. "
                        "Regenerate from source definitions instead."
                    ),
                    category="security",
                    agent="security-agent",
                )
            )

        for line in routed_file.file.added_lines:
            for pat in SECRET_PATTERNS:
                regex: re.Pattern[str] = pat["regex"]  # type: ignore[assignment]
                if not regex.search(line.content):
                    continue

                findings.append(
                    create_finding(
                        rule_id=str(pat["id"]),
                        severity="critical",
                        file=path,
                        line=line.line_number,
                        title=str(pat["title"]),
                        explanation=(
                            "Sensitive values should be loaded from secure runtime "
                            "config/secrets management, not committed in code."
                        ),
                        suggestion="Move the secret to configuration or secret manager and reference it at runtime.",
                        category="security",
                        agent="security-agent",
                        evidence=line.content.strip(),
                    )
                )

    return findings


@specialist("security")
def run_security_agent(inp: SpecialistInput) -> list[Finding]:
    findings = [*_check_built_in_security(inp), *apply_hard_rules(inp)]
    return limit_findings(findings, inp.policy, "security")
