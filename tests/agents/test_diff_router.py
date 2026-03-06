"""Tests for diff_router — port of tests/agents/diff-router.test.ts."""

from review_pilot.agents.diff_router import route_diff
from tests.conftest import make_changed_file, make_policy


class TestRouteDiff:
    def test_routes_generated_files(self) -> None:
        files = [make_changed_file("biz/model/data_copilot_api.go")]
        routed = route_diff(files)

        assert len(routed.generated_touched) == 1
        assert len(routed.by_specialist["security"]) == 1
        assert len(routed.by_specialist["architecture-boundary"]) == 1
        assert len(routed.by_specialist["api-contract"]) == 0

    def test_routes_handler_and_service_files(self) -> None:
        files = [
            make_changed_file("src/handler/list_session.go"),
            make_changed_file("src/service/session.go"),
            make_changed_file("src/service/session_test.go"),
        ]
        routed = route_diff(files)

        handler_in_api = any(
            r.file.path == "src/handler/list_session.go"
            for r in routed.by_specialist["api-contract"]
        )
        service_in_api = any(
            r.file.path == "src/service/session.go"
            for r in routed.by_specialist["api-contract"]
        )
        test_in_api = any(
            r.file.path == "src/service/session_test.go"
            for r in routed.by_specialist["api-contract"]
        )

        assert handler_in_api is True
        assert service_in_api is False
        assert test_in_api is False

        test_in_reliability = any(
            r.file.path == "src/service/session_test.go"
            for r in routed.by_specialist["reliability"]
        )
        assert test_in_reliability is True

    def test_detects_language(self) -> None:
        files = [
            make_changed_file("src/service/foo.go"),
            make_changed_file("src/handler/bar.ts"),
        ]
        routed = route_diff(files)

        go_file = next(
            (r for r in routed.by_specialist["security"] if r.file.path == "src/service/foo.go"),
            None,
        )
        ts_file = next(
            (r for r in routed.by_specialist["security"] if r.file.path == "src/handler/bar.ts"),
            None,
        )

        assert go_file is not None
        assert go_file.classification.language == "go"
        assert ts_file is not None
        assert ts_file.classification.language == "typescript"

    def test_user_configured_paths(self) -> None:
        from review_pilot.models import CategoryClassificationConfig

        policy = make_policy(
            file_classification={"handler": CategoryClassificationConfig(paths=["/views/"])}
        )
        files = [make_changed_file("src/views/main.py")]
        routed = route_diff(files, policy)

        assert len(routed.by_specialist["api-contract"]) == 1
        assert routed.by_specialist["api-contract"][0].classification.kind == "handler"

    def test_specialist_routing_override(self) -> None:
        policy = make_policy(specialist_routing={"model": ["security"]})
        files = [make_changed_file("src/model/user.ts")]
        routed = route_diff(files, policy)

        assert len(routed.by_specialist["security"]) == 1
        assert len(routed.by_specialist["architecture-boundary"]) == 0

    def test_unknown_language_for_no_extension(self) -> None:
        files = [make_changed_file("Makefile")]
        routed = route_diff(files)
        all_files = [r for specialists in routed.by_specialist.values() for r in specialists]
        assert all_files[0].classification.language == "unknown"
