"""Tests for security specialist — port of tests/agents/specialists/security.test.ts + security-extra.test.ts."""

from review_pilot.agents.specialists.common import SpecialistInput
from review_pilot.agents.specialists.security import run_security_agent
from tests.conftest import make_policy, make_routed_file


class TestRunSecurityAgent:
    def test_detects_hardcoded_secret(self) -> None:
        routed = [make_routed_file("src/service/foo.ts", "service", ['const token = "abcdefghi123";'])]
        findings = run_security_agent(
            SpecialistInput(
                specialist="security",
                routed_files=routed,
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert any(f.rule_id == "security-hardcoded-secret-assignment" for f in findings)

    def test_no_flag_safe_assignment(self) -> None:
        routed = [make_routed_file("src/service/foo.ts", "service", ["const token = getToken();"])]
        findings = run_security_agent(
            SpecialistInput(
                specialist="security",
                routed_files=routed,
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert len(findings) == 0

    def test_flags_generated_files(self) -> None:
        findings = run_security_agent(
            SpecialistInput(
                specialist="security",
                routed_files=[make_routed_file("biz/model/data_copilot_api.go", "generated", [])],
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert any(f.rule_id == "security-generated-file-edit" for f in findings)
