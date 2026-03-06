"""Tests for architecture_boundary specialist — port of tests/agents/specialists/architecture-boundary.test.ts."""

from review_pilot.agents.specialists.architecture_boundary import run_architecture_boundary_agent
from review_pilot.agents.specialists.common import SpecialistInput
from tests.conftest import make_file_content, make_policy, make_routed_file


class TestRunArchitectureBoundaryAgent:
    def test_flags_handler_dal_imports(self) -> None:
        routed = make_routed_file("src/handler/list.go", "handler", ["func List() {}"])
        contents = {
            routed.file.path: make_file_content(
                routed.file.path,
                'import dal "project/biz/dal"\nfunc List() {}',
                "go",
            )
        }
        findings = run_architecture_boundary_agent(
            SpecialistInput(
                specialist="architecture-boundary",
                routed_files=[routed],
                file_content_by_path=contents,
                policy=make_policy(),
            )
        )
        assert any(f.rule_id == "arch-handler-direct-data-access" for f in findings)

    def test_no_flag_handler_service_only(self) -> None:
        routed = make_routed_file("src/handler/list.go", "handler", ["func List() {}"])
        contents = {
            routed.file.path: make_file_content(
                routed.file.path,
                'import svc "project/biz/service"\nfunc List() {}',
                "go",
            )
        }
        findings = run_architecture_boundary_agent(
            SpecialistInput(
                specialist="architecture-boundary",
                routed_files=[routed],
                file_content_by_path=contents,
                policy=make_policy(),
            )
        )
        assert len(findings) == 0
