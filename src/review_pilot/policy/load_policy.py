"""Policy loading orchestrator — port of src/policy/load-policy.ts."""

from __future__ import annotations

from typing import Literal

from ..config import load_config, load_learned_rules, load_policy_snapshot
from ..models import PolicyBundle, Rule
from .merge_policy import merge_policy


def load_policy(
    *,
    config_path: str,
    learned_rules_path: str,
    policy_path: str,
    mode: Literal["warn", "enforce"] | None = None,
) -> PolicyBundle:
    config = load_config(config_path)
    learned = load_learned_rules(learned_rules_path)

    learned_as_rules: list[Rule] = [
        Rule(
            id=rule.id,
            description=rule.description,
            scope=rule.scope,
            pattern=rule.pattern,
            severity=rule.severity,
            source="learned",
        )
        for rule in learned
        if rule.confidence >= 0.5
    ]

    snapshot = load_policy_snapshot(policy_path)
    return merge_policy(config, learned_as_rules, snapshot, mode)
