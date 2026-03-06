"""Reliability specialist — port of src/agents/specialists/reliability.ts."""

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

PANIC_PATTERN = LanguageTaggedPattern(pattern=re.compile(r"\bpanic\("), languages=["go"])
CONTEXT_PATTERN = LanguageTaggedPattern(
    pattern=re.compile(r"context\.Background\(|context\.TODO\("), languages=["go"]
)
TODO_PATTERN = LanguageTaggedPattern(pattern=re.compile(r'panic\("implement me"\)|TODO|FIXME'))


def _check_built_in_reliability(inp: SpecialistInput) -> list[Finding]:
    findings: list[Finding] = []

    for routed_file in inp.routed_files:
        if routed_file.classification.kind == "test":
            continue

        path = routed_file.file.path
        language = routed_file.classification.language
        lower = path.lower()

        for line in routed_file.file.added_lines:
            if pattern_applies_to(PANIC_PATTERN, language) and PANIC_PATTERN.pattern.search(line.content):
                findings.append(
                    create_finding(
                        rule_id="reliability-panic-in-runtime",
                        severity="warning",
                        file=path,
                        line=line.line_number,
                        title="panic introduced in runtime path",
                        explanation=(
                            "panic should be avoided in request/runtime paths; "
                            "prefer returning errors and structured logging."
                        ),
                        suggestion="Return an error and let caller handle it with standard error flow.",
                        category="reliability",
                        agent="reliability-agent",
                        evidence=line.content.strip(),
                    )
                )

            if (
                pattern_applies_to(CONTEXT_PATTERN, language)
                and CONTEXT_PATTERN.pattern.search(line.content)
                and re.search(r"/biz/|/handler/|/service/", lower)
            ):
                findings.append(
                    create_finding(
                        rule_id="reliability-background-context",
                        severity="info",
                        file=path,
                        line=line.line_number,
                        title="Background/TODO context used in request/business path",
                        explanation=(
                            "Business/request paths should propagate caller context "
                            "for cancellation, deadlines, and tracing."
                        ),
                        suggestion="Thread context from the caller instead of creating a new background context.",
                        category="reliability",
                        agent="reliability-agent",
                        evidence=line.content.strip(),
                    )
                )

            if pattern_applies_to(TODO_PATTERN, language) and TODO_PATTERN.pattern.search(line.content):
                findings.append(
                    create_finding(
                        rule_id="reliability-todo-runtime",
                        severity="info",
                        file=path,
                        line=line.line_number,
                        title="Runtime code contains TODO/FIXME placeholder",
                        explanation="Placeholders in production paths can cause incomplete behavior and regressions.",
                        category="reliability",
                        agent="reliability-agent",
                        evidence=line.content.strip(),
                    )
                )

    return findings


@specialist("reliability")
def run_reliability_agent(inp: SpecialistInput) -> list[Finding]:
    findings = [*_check_built_in_reliability(inp), *apply_hard_rules(inp)]
    return limit_findings(findings, inp.policy, "reliability")
