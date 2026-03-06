"""Tests for logging_error specialist — port of tests/agents/specialists/logging-error.test.ts."""

from review_pilot.agents.specialists.common import SpecialistInput
from review_pilot.agents.specialists.logging_error import run_logging_error_agent
from tests.conftest import make_policy, make_routed_file


class TestRunLoggingErrorAgent:
    def test_detects_legacy_logger(self) -> None:
        findings = run_logging_error_agent(
            SpecialistInput(
                specialist="logging-error",
                routed_files=[make_routed_file("src/service/foo.go", "service", ['log.V1.CtxError(ctx, "oops")'])],
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert any(f.rule_id == "logging-legacy-v1" for f in findings)

    def test_no_flag_in_test_files(self) -> None:
        findings = run_logging_error_agent(
            SpecialistInput(
                specialist="logging-error",
                routed_files=[make_routed_file("tests/foo.test.ts", "test", ["console.log('test only')"])],
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert len(findings) == 0

    def test_no_flag_go_pattern_on_typescript(self) -> None:
        findings = run_logging_error_agent(
            SpecialistInput(
                specialist="logging-error",
                routed_files=[make_routed_file("src/service/foo.ts", "service", ['log.V1.CtxError(ctx, "oops")'])],
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert not any(f.rule_id == "logging-legacy-v1" for f in findings)

    def test_no_flag_console_log_on_go(self) -> None:
        findings = run_logging_error_agent(
            SpecialistInput(
                specialist="logging-error",
                routed_files=[make_routed_file("src/service/foo.go", "service", ["console.log('something')"])],
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert not any(f.rule_id == "logging-console-usage" for f in findings)
