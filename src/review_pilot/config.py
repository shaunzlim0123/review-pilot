"""YAML config loading with Pydantic validation — port of src/config.ts."""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC
from typing import Any

import yaml

from .models import (
    AgentRuntimeSettings,
    AgentSettings,
    AllowlistEntry,
    CategoryClassificationConfig,
    ConfigSettings,
    EnforcementSettings,
    HardRule,
    LearnedRule,
    LearnedRulesStore,
    PolicySnapshot,
    ReviewPilotConfig,
    Rule,
    Severity,
)

logger = logging.getLogger(__name__)

VALID_SEVERITIES: set[str] = {"critical", "warning", "info"}
VALID_SPECIALIST_NAMES: set[str] = {
    "security",
    "logging-error",
    "architecture-boundary",
    "api-contract",
    "data-access",
    "reliability",
}
VALID_FILE_KINDS: set[str] = {
    "generated", "handler", "service", "dal", "model", "config", "test", "other",
}

DEFAULT_SPECIALIST_SETTINGS: dict[str, AgentRuntimeSettings] = {
    name: AgentRuntimeSettings(enabled=True, max_findings=50)
    for name in VALID_SPECIALIST_NAMES
}


def _to_severity(s: Any, fallback: Severity = "warning") -> Severity:
    if isinstance(s, str) and s in VALID_SEVERITIES:
        return s  # type: ignore[return-value]
    return fallback


def _to_rule(raw: dict[str, Any], source: str) -> Rule:
    return Rule(
        id=raw["id"],
        description=raw["description"],
        scope=raw["scope"],
        pattern=raw["pattern"],
        severity=_to_severity(raw.get("severity")),
        source=source,
    )


def _to_hard_rule(raw: dict[str, Any], source: str) -> HardRule:
    category = raw.get("category", "any")
    if category not in VALID_SPECIALIST_NAMES and category != "any":
        category = "any"

    mode = raw.get("mode", "forbid_regex")
    if mode not in ("forbid_regex", "require_regex"):
        mode = "forbid_regex"

    target = raw.get("target", "added_lines")
    if target not in ("added_lines", "file_content"):
        target = "added_lines"

    return HardRule(
        id=raw["id"],
        description=raw["description"],
        scope=raw["scope"],
        pattern=raw["pattern"],
        severity=_to_severity(raw.get("severity"), "critical"),
        source=source,
        category=category,
        mode=mode,
        target=target,
        message=raw.get("message"),
        new_code_only=raw.get("new_code_only", True),
    )


def _normalize_file_classification(
    raw: dict[str, Any] | None,
) -> dict[str, CategoryClassificationConfig]:
    if not raw:
        return {}
    result: dict[str, CategoryClassificationConfig] = {}
    for k, v in raw.items():
        if k not in VALID_FILE_KINDS or not isinstance(v, dict):
            continue
        paths = [p for p in v.get("paths", []) if isinstance(p, str)]
        extensions = [e for e in v.get("extensions", []) if isinstance(e, str)]
        result[k] = CategoryClassificationConfig(paths=paths, extensions=extensions)
    return result


def _normalize_specialist_routing(
    raw: dict[str, Any] | None,
) -> dict[str, list[str]]:
    if not raw:
        return {}
    result: dict[str, list[str]] = {}
    for k, v in raw.items():
        if k not in VALID_FILE_KINDS or not isinstance(v, list):
            continue
        result[k] = [s for s in v if s in VALID_SPECIALIST_NAMES]
    return result


def _normalize_agent_settings(raw: dict[str, Any] | None) -> AgentSettings:
    merged = dict(DEFAULT_SPECIALIST_SETTINGS)
    if not raw or "specialists" not in raw:
        return AgentSettings(specialists=merged)

    for k, v in raw["specialists"].items():
        if k not in VALID_SPECIALIST_NAMES or not isinstance(v, dict):
            continue
        base = merged.get(k, AgentRuntimeSettings())
        merged[k] = AgentRuntimeSettings(
            enabled=v.get("enabled", base.enabled),
            max_findings=v.get("max_findings", base.max_findings),
        )

    return AgentSettings(specialists=merged)


DEFAULT_CONFIG = ReviewPilotConfig(
    settings=ConfigSettings(),
    enforcement=EnforcementSettings(),
    agents=AgentSettings(specialists=dict(DEFAULT_SPECIALIST_SETTINGS)),
)


def load_config(config_path: str) -> ReviewPilotConfig:
    if not os.path.exists(config_path):
        logger.info("No config file found at %s, using defaults", config_path)
        return DEFAULT_CONFIG

    with open(config_path) as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    legacy_rules = [_to_rule(r, "seed") for r in raw.get("rules", [])]
    soft_rules_new = [_to_rule(r, "seed") for r in raw.get("soft_rules", [])]
    soft_rules = soft_rules_new if soft_rules_new else legacy_rules

    hard_rules = [_to_hard_rule(r, "seed") for r in raw.get("hard_rules", [])]

    raw_settings = raw.get("settings", {}) or {}
    max_inline_comments = raw_settings.get(
        "max_inline_comments", DEFAULT_CONFIG.settings.max_inline_comments
    )

    raw_enforcement = raw.get("enforcement", {}) or {}
    block_on_raw = raw_enforcement.get("block_on", ["critical"])
    block_on: list[Severity] = [
        s for s in block_on_raw if isinstance(s, str) and s in VALID_SEVERITIES  # type: ignore[misc]
    ]

    allowlist = [
        AllowlistEntry(
            path=a["path"],
            rule_ids=a.get("rule_ids"),
            reason=a.get("reason"),
        )
        for a in raw.get("allowlist", [])
    ]

    return ReviewPilotConfig(
        rules=soft_rules,
        soft_rules=soft_rules,
        hard_rules=hard_rules,
        ignore=raw.get("ignore", []),
        allowlist=allowlist,
        settings=ConfigSettings(
            max_inline_comments=max_inline_comments,
            model=raw_settings.get("model", DEFAULT_CONFIG.settings.model),
            context_budget=raw_settings.get("context_budget", DEFAULT_CONFIG.settings.context_budget),
        ),
        enforcement=EnforcementSettings(
            mode="enforce" if raw_enforcement.get("mode") == "enforce" else "warn",
            block_on=block_on,
            new_code_only=raw_enforcement.get("new_code_only", True),
            max_comments=raw_enforcement.get("max_comments", max_inline_comments),
        ),
        agents=_normalize_agent_settings(raw.get("agents")),
        file_classification=_normalize_file_classification(raw.get("file_classification")),
        specialist_routing=_normalize_specialist_routing(raw.get("specialist_routing")),
    )


def load_learned_rules(learned_path: str) -> list[LearnedRule]:
    if not os.path.exists(learned_path):
        return []
    try:
        with open(learned_path) as f:
            data = json.load(f)
        store = LearnedRulesStore(**data)
        return store.rules
    except Exception as err:
        logger.warning("Failed to parse learned rules at %s: %s", learned_path, err)
        return []


def save_learned_rules(learned_path: str, rules: list[LearnedRule]) -> None:
    from datetime import datetime

    store = LearnedRulesStore(
        version=1,
        rules=rules,
        last_updated=datetime.now(UTC).isoformat(),
    )
    with open(learned_path, "w") as f:
        f.write(store.model_dump_json(indent=2))


def load_policy_snapshot(policy_path: str) -> PolicySnapshot | None:
    if not os.path.exists(policy_path):
        return None
    try:
        with open(policy_path) as f:
            data = json.load(f)
        parsed = PolicySnapshot(**data)
        if not isinstance(parsed.soft_rules, list) or not isinstance(parsed.hard_rules, list):
            return None
        return parsed
    except Exception as err:
        logger.warning("Failed to parse policy snapshot at %s: %s", policy_path, err)
        return None
