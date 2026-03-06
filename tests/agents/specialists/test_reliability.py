"""Tests for reliability specialist — port of tests/agents/specialists/reliability.test.ts."""

from review_pilot.agents.specialists.common import SpecialistInput
from review_pilot.agents.specialists.reliability import run_reliability_agent
from tests.conftest import make_policy, make_routed_file


class TestRunReliabilityAgent:
    def test_flags_panic_in_runtime(self) -> None:
        findings = run_reliability_agent(
            SpecialistInput(
                specialist="reliability",
                routed_files=[make_routed_file("src/service/foo.go", "service", ['panic("boom")'])],
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert any(f.rule_id == "reliability-panic-in-runtime" for f in findings)

    def test_no_flag_panic_in_test(self) -> None:
        findings = run_reliability_agent(
            SpecialistInput(
                specialist="reliability",
                routed_files=[make_routed_file("src/service/foo_test.go", "test", ['panic("boom")'])],
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert len(findings) == 0

    def test_no_flag_panic_on_typescript(self) -> None:
        findings = run_reliability_agent(
            SpecialistInput(
                specialist="reliability",
                routed_files=[make_routed_file("src/service/foo.ts", "service", ['panic("something went wrong")'])],
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert not any(f.rule_id == "reliability-panic-in-runtime" for f in findings)
