"""Policy merging logic — port of src/policy/merge-policy.ts."""

from __future__ import annotations

from typing import Literal

from ..models import (
    EnforcementSettings,
    HardRule,
    PolicyBundle,
    PolicySnapshot,
    ReviewPilotConfig,
    Rule,
)


def _merge_rules_by_id(*rule_sets: list[Rule]) -> list[Rule]:
    merged: dict[str, Rule] = {}
    for rule_set in rule_sets:
        for rule in rule_set:
            merged[rule.id] = rule
    return list(merged.values())


def _merge_hard_rules_by_id(*rule_sets: list[HardRule]) -> list[HardRule]:
    merged: dict[str, HardRule] = {}
    for rule_set in rule_sets:
        for rule in rule_set:
            merged[rule.id] = rule
    return list(merged.values())


def _unique_strings(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _merge_enforcement(
    base: EnforcementSettings,
    override_mode: Literal["warn", "enforce"] | None = None,
) -> EnforcementSettings:
    if not override_mode:
        return base
    return base.model_copy(update={"mode": override_mode})


def merge_policy(
    config: ReviewPilotConfig,
    learned_rules: list[Rule],
    snapshot: PolicySnapshot | None,
    override_mode: Literal["warn", "enforce"] | None = None,
) -> PolicyBundle:
    soft_rules = _merge_rules_by_id(
        snapshot.soft_rules if snapshot else [],
        learned_rules,
        config.soft_rules,
    )

    hard_rules = _merge_hard_rules_by_id(
        snapshot.hard_rules if snapshot else [],
        config.hard_rules,
    )

    return PolicyBundle(
        soft_rules=soft_rules,
        hard_rules=hard_rules,
        allowlist=config.allowlist,
        ignore=_unique_strings(config.ignore),
        settings=config.settings,
        enforcement=_merge_enforcement(config.enforcement, override_mode),
        agents=config.agents,
        file_classification=config.file_classification,
        specialist_routing=config.specialist_routing,
    )
