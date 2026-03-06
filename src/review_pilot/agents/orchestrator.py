"""Specialist orchestration — port of src/agents/orchestrator.ts."""

from __future__ import annotations

from ..models import AnalysisResult, DiffRoutingResult, FileContent, PolicyBundle, SpecialistName
from .review_synthesizer import synthesize_findings
from .specialists import registry  # noqa: F401 — import triggers registration
from .specialists.common import SpecialistInput
from .specialists.registry import get_specialist

SPECIALIST_ORDER: list[SpecialistName] = [
    "security",
    "logging-error",
    "architecture-boundary",
    "api-contract",
    "data-access",
    "reliability",
]


def run_orchestrator(
    *,
    routing: DiffRoutingResult,
    policy: PolicyBundle,
    changed_file_contents: list[FileContent],
) -> AnalysisResult:
    file_content_by_path: dict[str, FileContent] = {f.path: f for f in changed_file_contents}
    all_findings = []

    for specialist_name in SPECIALIST_ORDER:
        settings = policy.agents.specialists.get(specialist_name)
        if not settings or not settings.enabled:
            continue

        fn = get_specialist(specialist_name)
        if fn is None:
            continue

        specialist_input = SpecialistInput(
            specialist=specialist_name,
            routed_files=routing.by_specialist.get(specialist_name, []),
            file_content_by_path=file_content_by_path,
            policy=policy,
        )
        all_findings.extend(fn(specialist_input))

    return synthesize_findings(
        specialist_findings=all_findings,
        pass_count=len(SPECIALIST_ORDER),
    )
