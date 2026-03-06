"""Tests for merge_policy — port of tests/policy/merge-policy.test.ts."""

from review_pilot.models import (
    ConfigSettings,
    EnforcementSettings,
    HardRule,
    PolicySnapshot,
    ReviewPilotConfig,
    Rule,
)
from review_pilot.policy.merge_policy import merge_policy
from tests.conftest import make_default_agents


def _make_config() -> ReviewPilotConfig:
    return ReviewPilotConfig(
        rules=[],
        soft_rules=[
            Rule(
                id="dup-soft",
                description="from config",
                scope="src/**",
                pattern="config-pattern",
                severity="warning",
                source="seed",
            ),
            Rule(
                id="config-only",
                description="config only",
                scope="src/services/**",
                pattern="service-pattern",
                severity="info",
                source="seed",
            ),
        ],
        hard_rules=[
            HardRule(
                id="dup-hard",
                description="hard from config",
                scope="src/**",
                severity="critical",
                source="seed",
                category="any",
                mode="forbid_regex",
                pattern="secret",
                target="added_lines",
                new_code_only=True,
            ),
        ],
        ignore=["**/*.snap", "**/*.snap"],
        allowlist=[],
        settings=ConfigSettings(
            max_inline_comments=3,
            model="claude-sonnet-4-5-20250929",
            context_budget=50000,
        ),
        enforcement=EnforcementSettings(
            mode="warn",
            block_on=["critical"],
            new_code_only=True,
            max_comments=3,
        ),
        agents=make_default_agents(),
        file_classification={},
        specialist_routing={},
    )


class TestMergePolicy:
    def test_precedence_snapshot_learned_config(self) -> None:
        config = _make_config()

        learned_rules = [
            Rule(
                id="dup-soft",
                description="from learned",
                scope="src/**",
                pattern="learned-pattern",
                severity="critical",
                source="learned",
            ),
        ]

        snapshot = PolicySnapshot(
            version=1,
            generated_at="2026-01-01T00:00:00Z",
            soft_rules=[
                Rule(
                    id="dup-soft",
                    description="from snapshot",
                    scope="src/**",
                    pattern="snapshot-pattern",
                    severity="info",
                    source="policy",
                ),
            ],
            hard_rules=[
                HardRule(
                    id="dup-hard",
                    description="hard from snapshot",
                    scope="src/**",
                    severity="warning",
                    source="policy",
                    category="any",
                    mode="forbid_regex",
                    pattern="password",
                    target="added_lines",
                    new_code_only=True,
                ),
            ],
        )

        merged = merge_policy(config, learned_rules, snapshot)

        soft = next((r for r in merged.soft_rules if r.id == "dup-soft"), None)
        assert soft is not None
        assert soft.description == "from config"
        assert any(r.id == "config-only" for r in merged.soft_rules)

        hard = next((r for r in merged.hard_rules if r.id == "dup-hard"), None)
        assert hard is not None
        assert hard.description == "hard from config"

        assert merged.ignore == ["**/*.snap"]

    def test_overrides_enforcement_mode(self) -> None:
        config = _make_config()
        merged = merge_policy(config, [], None, "enforce")
        assert merged.enforcement.mode == "enforce"
        assert merged.enforcement.block_on == ["critical"]
