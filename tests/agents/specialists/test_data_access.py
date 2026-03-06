"""Tests for data_access specialist — port of tests/agents/specialists/data-access.test.ts."""

from review_pilot.agents.specialists.common import SpecialistInput
from review_pilot.agents.specialists.data_access import run_data_access_agent
from tests.conftest import make_policy, make_routed_file

DB_LINE = "config.MysqlCli.WithContext(ctx).Find(&rows)"


class TestRunDataAccessAgent:
    def test_flags_direct_db_outside_dal(self) -> None:
        findings = run_data_access_agent(
            SpecialistInput(
                specialist="data-access",
                routed_files=[make_routed_file("src/service/foo.go", "service", [DB_LINE])],
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert any(f.rule_id == "data-access-outside-dal" for f in findings)

    def test_no_flag_in_dal(self) -> None:
        findings = run_data_access_agent(
            SpecialistInput(
                specialist="data-access",
                routed_files=[make_routed_file("src/dal/foo.go", "dal", [DB_LINE])],
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert len(findings) == 0

    def test_no_flag_go_patterns_on_typescript(self) -> None:
        findings = run_data_access_agent(
            SpecialistInput(
                specialist="data-access",
                routed_files=[
                    make_routed_file("src/service/foo.ts", "service", ["gorm.Open()", "sql.Open(db)"])
                ],
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert not any(f.rule_id == "data-access-outside-dal" for f in findings)

    def test_flags_sequelize_on_typescript(self) -> None:
        knex_line = "const result = await knex('users').select()"
        findings = run_data_access_agent(
            SpecialistInput(
                specialist="data-access",
                routed_files=[make_routed_file("src/service/foo.ts", "service", [knex_line])],
                file_content_by_path={},
                policy=make_policy(),
            )
        )
        assert any(f.rule_id == "data-access-outside-dal" for f in findings)
