"""Tests for api_contract specialist — port of tests/agents/specialists/api-contract.test.ts."""

from review_pilot.agents.specialists.api_contract import run_api_contract_agent
from review_pilot.agents.specialists.common import SpecialistInput
from tests.conftest import make_file_content, make_policy, make_routed_file


class TestRunApiContractAgent:
    def test_flags_endpoint_without_validation(self) -> None:
        routed = make_routed_file("src/handler/list_session.go", "handler", ["func ListSession() {}"])
        content = (
            '// @router /manage/list_session [GET]\n'
            'func ListSession(ctx context.Context, c *app.RequestContext) {\n'
            '  c.JSON(200, map[string]string{"ok":"1"})\n'
            '}'
        )
        findings = run_api_contract_agent(
            SpecialistInput(
                specialist="api-contract",
                routed_files=[routed],
                file_content_by_path={routed.file.path: make_file_content(routed.file.path, content, "go")},
                policy=make_policy(),
            )
        )
        assert any(f.rule_id == "api-missing-request-validation" for f in findings)

    def test_no_flag_when_validation_exists(self) -> None:
        routed = make_routed_file("src/handler/list_session.go", "handler", ["func ListSession() {}"])
        content = (
            '// @router /manage/list_session [GET]\n'
            'func ListSession(ctx context.Context, c *app.RequestContext) {\n'
            '  err := binding.BindAndValidate(c, &req)\n'
            '  _ = err\n'
            '}'
        )
        findings = run_api_contract_agent(
            SpecialistInput(
                specialist="api-contract",
                routed_files=[routed],
                file_content_by_path={routed.file.path: make_file_content(routed.file.path, content, "go")},
                policy=make_policy(),
            )
        )
        assert len(findings) == 0
