"""Tests for reviewer — port of tests/reviewer.test.ts."""

from review_pilot.models import (
    AnalysisResult,
    ChangedFile,
    ChangedLine,
    DiffHunk,
    Finding,
    TokenUsage,
)
from review_pilot.reviewer import build_review_output, line_to_diff_position

CHANGED_FILES: list[ChangedFile] = [
    ChangedFile(
        path="src/api/users.ts",
        status="modified",
        hunks=[
            DiffHunk(
                header="@@ -5,4 +5,6 @@",
                old_start=5,
                old_lines=4,
                new_start=5,
                new_lines=6,
                content=(
                    " context line\n"
                    "-removed\n"
                    "+added line 1\n"
                    "+added line 2\n"
                    "+added line 3\n"
                    " context end"
                ),
            ),
        ],
        added_lines=[
            ChangedLine(type="add", line_number=6, content="added line 1"),
            ChangedLine(type="add", line_number=7, content="added line 2"),
            ChangedLine(type="add", line_number=8, content="added line 3"),
        ],
        removed_lines=[ChangedLine(type="delete", line_number=6, content="removed")],
        patch="",
    ),
]


class TestLineToDiffPosition:
    def test_maps_line_to_position(self) -> None:
        pos = line_to_diff_position(CHANGED_FILES, "src/api/users.ts", 6)
        assert pos is not None
        assert isinstance(pos, int)

    def test_undefined_for_missing_file(self) -> None:
        pos = line_to_diff_position(CHANGED_FILES, "src/other.ts", 1)
        assert pos is None

    def test_undefined_for_line_not_in_hunk(self) -> None:
        pos = line_to_diff_position(CHANGED_FILES, "src/api/users.ts", 1)
        assert pos is None


class TestBuildReviewOutput:
    def test_approve_when_no_findings(self) -> None:
        result = AnalysisResult(
            findings=[],
            summary="All clear",
            pass_count=3,
            token_usage=TokenUsage(input_tokens=100, output_tokens=50),
        )
        review = build_review_output(result, CHANGED_FILES, 3)
        assert review.event == "APPROVE"
        assert "No semantic issues found" in review.body
        assert len(review.comments) == 0

    def test_request_changes_for_critical(self) -> None:
        result = AnalysisResult(
            findings=[
                Finding(
                    rule_id="require-auth",
                    severity="critical",
                    file="src/api/users.ts",
                    line=6,
                    title="Missing auth check",
                    explanation="Endpoint has no authentication",
                ),
            ],
            summary="Found critical issues",
            pass_count=3,
            token_usage=TokenUsage(input_tokens=200, output_tokens=100),
        )
        review = build_review_output(result, CHANGED_FILES, 3)
        assert review.event == "REQUEST_CHANGES"
        assert "Critical" in review.body

    def test_comment_for_warnings_only(self) -> None:
        result = AnalysisResult(
            findings=[
                Finding(
                    rule_id="require-logging",
                    severity="warning",
                    file="src/api/users.ts",
                    line=6,
                    title="Missing error logging",
                    explanation="Error is caught but not logged",
                ),
            ],
            summary="Minor issues found",
            pass_count=3,
            token_usage=TokenUsage(input_tokens=150, output_tokens=75),
        )
        review = build_review_output(result, CHANGED_FILES, 3)
        assert review.event == "COMMENT"

    def test_limits_inline_comments(self) -> None:
        f = "src/api/users.ts"
        result = AnalysisResult(
            findings=[
                Finding(rule_id="r1", severity="critical", file=f, line=6, title="Issue 1", explanation="..."),
                Finding(rule_id="r2", severity="critical", file=f, line=7, title="Issue 2", explanation="..."),
                Finding(rule_id="r3", severity="warning", file=f, line=8, title="Issue 3", explanation="..."),
                Finding(rule_id="r4", severity="info", file=f, line=6, title="Issue 4", explanation="..."),
            ],
            summary="Multiple issues",
            pass_count=3,
            token_usage=TokenUsage(input_tokens=300, output_tokens=150),
        )
        review = build_review_output(result, CHANGED_FILES, 2)
        assert len(review.comments) <= 2
        # Summary should still mention all findings
        assert "Issue 1" in review.body
        assert "Issue 4" in review.body
