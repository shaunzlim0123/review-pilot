"""Tests for context_resolver — port of tests/context-resolver.test.ts."""

from review_pilot.context_resolver import estimate_tokens, extract_imports, resolve_import_path


class TestEstimateTokens:
    def test_basic_estimation(self) -> None:
        assert estimate_tokens("hello world") == 3  # 11 / 4 = 2.75 → 3
        assert estimate_tokens("") == 0
        assert estimate_tokens("a") == 1


class TestExtractImportsTypescript:
    def test_es_module_imports(self) -> None:
        code = (
            'import { foo } from "./foo";\n'
            'import bar from "../bar";\n'
            'import * as baz from "./utils/baz";\n'
            'import { something } from "lodash";\n'
        )
        imports = extract_imports(code, "typescript")
        assert imports == ["./foo", "../bar", "./utils/baz"]

    def test_require_calls(self) -> None:
        code = (
            'const foo = require("./foo");\n'
            'const bar = require("express");\n'
            'const baz = require("../utils/baz");\n'
        )
        imports = extract_imports(code, "typescript")
        assert imports == ["./foo", "../utils/baz"]

    def test_no_imports(self) -> None:
        code = "const x = 42;\nconsole.log(x);"
        assert extract_imports(code, "typescript") == []


class TestExtractImportsPython:
    def test_relative_imports(self) -> None:
        code = (
            "from .models import User\n"
            "from ..utils import helper\n"
            "import .config\n"
            "import os\n"
            "from fastapi import FastAPI\n"
        )
        imports = extract_imports(code, "python")
        assert imports == [".models", "..utils", ".config"]


class TestExtractImportsGo:
    def test_single_import(self) -> None:
        code = 'import "fmt"'
        imports = extract_imports(code, "go")
        assert imports == ["fmt"]

    def test_grouped_imports(self) -> None:
        code = (
            "import (\n"
            '  "context"\n'
            '  "fmt"\n'
            '  "github.com/user/repo/pkg"\n'
            ")"
        )
        imports = extract_imports(code, "go")
        assert imports == ["context", "fmt", "github.com/user/repo/pkg"]


class TestResolveImportPath:
    def test_relative_ts_extensions(self) -> None:
        candidates = resolve_import_path("./utils", "src/index.ts", "typescript")
        assert "src/utils.ts" in candidates
        assert "src/utils.tsx" in candidates
        assert "src/utils.js" in candidates
        assert "src/utils/index.ts" in candidates

    def test_parent_directory_imports(self) -> None:
        candidates = resolve_import_path("../shared/types", "src/services/auth.ts", "typescript")
        assert "src/shared/types.ts" in candidates

    def test_python_relative_imports(self) -> None:
        candidates = resolve_import_path(".models", "app/services/auth.py", "python")
        assert "app/services/models" in candidates
