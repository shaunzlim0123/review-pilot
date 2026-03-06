"""API contract specialist — port of src/agents/specialists/api-contract.ts."""

from __future__ import annotations

import re

from ...models import Finding
from .common import SpecialistInput, apply_hard_rules, create_finding, limit_findings
from .registry import specialist

_VALIDATION_RE = re.compile(
    r"BindAndValidate\(|schema\.parse\(|z\.object\(|Joi\.|validator\.|pydantic|validate\("
)
_ENDPOINT_RE = re.compile(
    r"@router\s+|\.GET\(|\.POST\(|\.PUT\(|\.DELETE\(|func\s+[A-Z][A-Za-z0-9_]*\s*\(.*RequestContext"
)


def _check_built_in_api_contract(inp: SpecialistInput) -> list[Finding]:
    findings: list[Finding] = []

    for routed_file in inp.routed_files:
        if routed_file.classification.kind != "handler":
            continue

        path = routed_file.file.path
        fc = inp.file_content_by_path.get(path)
        content = fc.content if fc else ""

        if not _ENDPOINT_RE.search(content):
            continue

        if not _VALIDATION_RE.search(content):
            line = routed_file.file.added_lines[0].line_number if routed_file.file.added_lines else 1
            findings.append(
                create_finding(
                    rule_id="api-missing-request-validation",
                    severity="warning",
                    file=path,
                    line=line,
                    title="Request validation pattern not detected",
                    explanation=(
                        "Handler-like endpoint code should validate incoming request payloads "
                        "using the project standard validation flow."
                    ),
                    suggestion="Add request binding/validation before executing business logic.",
                    category="api-contract",
                    agent="api-contract-agent",
                )
            )

    return findings


@specialist("api-contract")
def run_api_contract_agent(inp: SpecialistInput) -> list[Finding]:
    findings = [*_check_built_in_api_contract(inp), *apply_hard_rules(inp)]
    return limit_findings(findings, inp.policy, "api-contract")
