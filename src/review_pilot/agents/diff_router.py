"""File classification and routing — port of src/agents/diff-router.ts."""

from __future__ import annotations

from ..models import (
    CategoryClassificationConfig,
    ChangedFile,
    DiffRoutingResult,
    FileClassification,
    FileKind,
    PolicyBundle,
    RoutedFile,
    SpecialistName,
)
from .language_detector import detect_language

DEFAULT_CLASSIFICATION: dict[str, CategoryClassificationConfig] = {
    "generated": CategoryClassificationConfig(
        paths=["/generated/", "/gen/", "/biz/model/", "biz/model/"],
        extensions=["_gen.go", "router_gen.go"],
    ),
    "handler": CategoryClassificationConfig(
        paths=["/handler/", "/handlers/", "/api/"],
    ),
    "service": CategoryClassificationConfig(
        paths=["/service/", "/services/"],
    ),
    "dal": CategoryClassificationConfig(
        paths=["/dal/", "/repository/", "/repos/"],
    ),
    "model": CategoryClassificationConfig(
        paths=["/model/", "/models/"],
    ),
    "config": CategoryClassificationConfig(
        paths=["/config/"],
        extensions=["config.ts", "config.go"],
    ),
    "test": CategoryClassificationConfig(
        paths=["/test/", "/tests/"],
        extensions=[".test.ts", "_test.go"],
    ),
    "other": CategoryClassificationConfig(),
}

KIND_ORDER: list[FileKind] = [
    "generated",
    "handler",
    "service",
    "dal",
    "model",
    "config",
    "test",
]

DEFAULT_SPECIALIST_ROUTING: dict[str, list[SpecialistName]] = {
    "test": ["security", "reliability"],
    "generated": ["security", "architecture-boundary"],
    "handler": [
        "security",
        "logging-error",
        "reliability",
        "architecture-boundary",
        "api-contract",
        "data-access",
    ],
    "service": ["security", "logging-error", "reliability", "architecture-boundary", "data-access"],
    "dal": ["security", "logging-error", "reliability", "architecture-boundary"],
    "config": ["security", "logging-error", "reliability"],
    "model": [
        "security",
        "logging-error",
        "reliability",
        "architecture-boundary",
        "data-access",
        "api-contract",
    ],
    "other": [
        "security",
        "logging-error",
        "reliability",
        "architecture-boundary",
        "data-access",
        "api-contract",
    ],
}


def _build_effective_classification(
    user_config: dict[str, CategoryClassificationConfig],
) -> dict[str, CategoryClassificationConfig]:
    result: dict[str, CategoryClassificationConfig] = {}
    for kind, default_entry in DEFAULT_CLASSIFICATION.items():
        base_paths = list(default_entry.paths)
        base_exts = list(default_entry.extensions)
        user_entry = user_config.get(kind)
        if user_entry:
            base_paths.extend(user_entry.paths)
            base_exts.extend(user_entry.extensions)
        result[kind] = CategoryClassificationConfig(paths=base_paths, extensions=base_exts)
    # Add any user-defined kinds not in defaults
    for kind, user_entry in user_config.items():
        if kind not in result:
            result[kind] = user_entry
    return result


def _matches_category(path: str, config: CategoryClassificationConfig) -> bool:
    for path_fragment in config.paths:
        if path_fragment in path:
            return True
    for ext in config.extensions:
        if path.endswith(ext):
            return True
    return False


def _classify_path(
    path: str,
    effective_config: dict[str, CategoryClassificationConfig],
) -> FileKind:
    p = path.lower()
    for kind in KIND_ORDER:
        entry = effective_config.get(kind)
        if entry and _matches_category(p, entry):
            return kind
    return "other"


def _specialists_for_kind(
    kind: str,
    routing_overrides: dict[str, list[str]],
) -> list[str]:
    if kind in routing_overrides:
        return routing_overrides[kind]
    return list(DEFAULT_SPECIALIST_ROUTING.get(kind, []))


SPECIALIST_NAMES: list[SpecialistName] = [
    "security",
    "logging-error",
    "architecture-boundary",
    "api-contract",
    "data-access",
    "reliability",
]


def _build_empty_route_map() -> dict[str, list[RoutedFile]]:
    return {name: [] for name in SPECIALIST_NAMES}


def route_diff(
    changed_files: list[ChangedFile],
    policy: PolicyBundle | None = None,
) -> DiffRoutingResult:
    effective_config = _build_effective_classification(
        policy.file_classification if policy else {}
    )
    routing_overrides = policy.specialist_routing if policy else {}

    by_specialist = _build_empty_route_map()
    generated_touched: list[RoutedFile] = []

    for file in changed_files:
        kind = _classify_path(file.path, effective_config)
        language = detect_language(file.path)

        classification = FileClassification(path=file.path, kind=kind, language=language)
        routed = RoutedFile(file=file, classification=classification)

        if kind == "generated":
            generated_touched.append(routed)

        for specialist_name in _specialists_for_kind(kind, routing_overrides):
            if specialist_name in by_specialist:
                by_specialist[specialist_name].append(routed)

    return DiffRoutingResult(by_specialist=by_specialist, generated_touched=generated_touched)
