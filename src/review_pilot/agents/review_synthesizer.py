"""Finding synthesis — port of src/agents/review-synthesizer.ts."""

from __future__ import annotations

from ..models import AnalysisResult, Finding, TokenUsage

SEVERITY_RANK: dict[str, int] = {
    "critical": 3,
    "warning": 2,
    "info": 1,
}


def _dedupe_findings(findings: list[Finding]) -> list[Finding]:
    merged: dict[str, Finding] = {}
    for finding in findings:
        key = f"{finding.rule_id}|{finding.file}|{finding.line}|{finding.title}"
        existing = merged.get(key)
        if not existing or SEVERITY_RANK.get(finding.severity, 0) > SEVERITY_RANK.get(existing.severity, 0):
            merged[key] = finding
    return list(merged.values())


def _rank_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda f: (
            -SEVERITY_RANK.get(f.severity, 0),
            f.file,
            f.line,
        ),
    )


def _build_summary(findings: list[Finding]) -> str:
    if not findings:
        return "No semantic issues found by the multi-agent review pipeline."

    critical = sum(1 for f in findings if f.severity == "critical")
    warning = sum(1 for f in findings if f.severity == "warning")
    info = sum(1 for f in findings if f.severity == "info")

    return (
        f"Multi-agent review found {len(findings)} issue(s): "
        f"{critical} critical, {warning} warning, {info} info."
    )


def synthesize_findings(
    *,
    specialist_findings: list[Finding],
    pass_count: int = 1,
) -> AnalysisResult:
    deduped = _dedupe_findings(specialist_findings)
    ranked = _rank_findings(deduped)

    return AnalysisResult(
        findings=ranked,
        summary=_build_summary(ranked),
        pass_count=pass_count,
        token_usage=TokenUsage(input_tokens=0, output_tokens=0),
    )
