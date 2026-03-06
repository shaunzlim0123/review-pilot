"""Tests for diff_parser — port of tests/diff-parser.test.ts."""

from review_pilot.diff_parser import (
    extract_changed_lines,
    parse_hunks,
    parse_pr_files,
    should_ignore_file,
)


class TestParseHunks:
    def test_single_hunk(self) -> None:
        patch = (
            "@@ -1,4 +1,5 @@\n"
            " line1\n"
            " line2\n"
            "+added line\n"
            " line3\n"
            " line4"
        )
        hunks = parse_hunks(patch)
        assert len(hunks) == 1
        assert hunks[0].old_start == 1
        assert hunks[0].old_lines == 4
        assert hunks[0].new_start == 1
        assert hunks[0].new_lines == 5

    def test_multiple_hunks(self) -> None:
        patch = (
            "@@ -1,3 +1,4 @@\n"
            " line1\n"
            "+added1\n"
            " line2\n"
            " line3\n"
            "@@ -10,3 +11,4 @@\n"
            " line10\n"
            "+added2\n"
            " line11\n"
            " line12"
        )
        hunks = parse_hunks(patch)
        assert len(hunks) == 2
        assert hunks[0].new_start == 1
        assert hunks[1].new_start == 11

    def test_single_line_hunk(self) -> None:
        patch = "@@ -1 +1 @@\n-old\n+new"
        hunks = parse_hunks(patch)
        assert len(hunks) == 1
        assert hunks[0].old_lines == 1
        assert hunks[0].new_lines == 1

    def test_empty_patch(self) -> None:
        assert parse_hunks("") == []


class TestExtractChangedLines:
    def test_added_and_removed_lines(self) -> None:
        patch = (
            "@@ -5,4 +5,5 @@\n"
            " context\n"
            "-removed line\n"
            "+added line 1\n"
            "+added line 2\n"
            " context\n"
            " context"
        )
        hunks = parse_hunks(patch)
        added, removed = extract_changed_lines(hunks)

        assert len(added) == 2
        assert added[0].line_number == 6
        assert added[0].content == "added line 1"
        assert added[1].line_number == 7
        assert added[1].content == "added line 2"

        assert len(removed) == 1
        assert removed[0].line_number == 6
        assert removed[0].content == "removed line"


class TestShouldIgnoreFile:
    def test_lock_files(self) -> None:
        assert should_ignore_file("package-lock.json") is True
        assert should_ignore_file("yarn.lock") is True
        assert should_ignore_file("pnpm-lock.yaml") is True

    def test_image_files(self) -> None:
        assert should_ignore_file("assets/logo.png") is True
        assert should_ignore_file("img/photo.jpg") is True

    def test_minified_files(self) -> None:
        assert should_ignore_file("dist/bundle.min.js") is True
        assert should_ignore_file("styles/main.min.css") is True

    def test_source_files_not_ignored(self) -> None:
        assert should_ignore_file("src/index.ts") is False
        assert should_ignore_file("app/services/auth.py") is False

    def test_extra_ignore_patterns(self) -> None:
        assert should_ignore_file("src/generated/types.ts", ["**/generated/**"]) is True
        assert should_ignore_file("src/index.ts", ["**/generated/**"]) is False


class TestParsePRFiles:
    def test_parses_files_with_patches(self) -> None:
        files = [
            {
                "filename": "src/handler.ts",
                "status": "modified",
                "patch": (
                    "@@ -1,3 +1,4 @@\n"
                    " import { foo } from './foo';\n"
                    "+import { bar } from './bar';\n"
                    "\n"
                    " export function handler() {"
                ),
            },
        ]
        result = parse_pr_files(files)
        assert len(result) == 1
        assert result[0].path == "src/handler.ts"
        assert result[0].status == "modified"
        assert len(result[0].added_lines) == 1
        assert result[0].added_lines[0].content == "import { bar } from './bar';"

    def test_filters_ignored_files(self) -> None:
        files = [
            {"filename": "src/index.ts", "status": "modified", "patch": "@@ -1 +1 @@\n-a\n+b"},
            {"filename": "package-lock.json", "status": "modified", "patch": "@@ -1 +1 @@\n-a\n+b"},
        ]
        result = parse_pr_files(files)
        assert len(result) == 1
        assert result[0].path == "src/index.ts"

    def test_skips_files_without_patches(self) -> None:
        files = [
            {"filename": "logo.png", "status": "added"},
            {"filename": "src/index.ts", "status": "modified", "patch": "@@ -1 +1 @@\n-a\n+b"},
        ]
        result = parse_pr_files(files)
        assert len(result) == 1
