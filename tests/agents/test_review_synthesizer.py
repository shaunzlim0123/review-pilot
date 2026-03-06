"""Tests for review_synthesizer — port of tests/agents/review-synthesizer.test.ts."""

from review_pilot.agents.review_synthesizer import synthesize_findings
from review_pilot.models import Finding


class TestSynthesizeFindings:
    def test_dedupes_keeps_higher_severity(self) -> None:
        result = synthesize_findings(
            specialist_findings=[
                Finding(rule_id="r1", severity="warning", file="a.ts", line=10, title="same", explanation="warn"),
                Finding(rule_id="r1", severity="critical", file="a.ts", line=10, title="same", explanation="critical"),
            ],
            pass_count=6,
        )
        assert len(result.findings) == 1
        assert result.findings[0].severity == "critical"
        assert result.pass_count == 6

    def test_ranks_by_severity_then_file_then_line(self) -> None:
        result = synthesize_findings(
            specialist_findings=[
                Finding(rule_id="i", severity="info", file="b.ts", line=2, title="i", explanation="i"),
                Finding(rule_id="c", severity="critical", file="z.ts", line=9, title="c", explanation="c"),
                Finding(rule_id="w", severity="warning", file="a.ts", line=1, title="w", explanation="w"),
            ],
        )
        assert [f.rule_id for f in result.findings] == ["c", "w", "i"]
        assert "1 critical" in result.summary
        assert "1 warning" in result.summary
        assert "1 info" in result.summary
