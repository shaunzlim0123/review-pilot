"""All Pydantic models — faithful port of src/types.ts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Literal unions (replaces TS string unions)
# ---------------------------------------------------------------------------

Severity = Literal["critical", "warning", "info"]
RuleSource = Literal["seed", "learned", "policy"]
SpecialistName = Literal[
    "security",
    "logging-error",
    "architecture-boundary",
    "api-contract",
    "data-access",
    "reliability",
]
FileKind = Literal[
    "generated",
    "handler",
    "service",
    "dal",
    "model",
    "config",
    "test",
    "other",
]

# ---------------------------------------------------------------------------
# Diff parsing
# ---------------------------------------------------------------------------


class DiffHunk(BaseModel):
    header: str
    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    content: str


class ChangedLine(BaseModel):
    type: Literal["add", "delete", "context"]
    line_number: int
    content: str


class ChangedFile(BaseModel):
    path: str
    status: Literal["added", "modified", "removed", "renamed"]
    hunks: list[DiffHunk]
    added_lines: list[ChangedLine]
    removed_lines: list[ChangedLine]
    patch: str


# ---------------------------------------------------------------------------
# Context resolution
# ---------------------------------------------------------------------------


class FileContent(BaseModel):
    path: str
    content: str
    language: str


class RepoMetadata(BaseModel):
    owner: str
    repo: str
    pull_number: int
    base_branch: str
    head_branch: str
    head_sha: str


class ReviewContext(BaseModel):
    changed_files: list[FileContent]
    imported_files: list[FileContent]
    repo_metadata: RepoMetadata
    total_token_estimate: int


# ---------------------------------------------------------------------------
# Rules and policy
# ---------------------------------------------------------------------------


class Rule(BaseModel):
    id: str
    description: str
    scope: str
    pattern: str
    severity: Severity
    source: RuleSource


class HardRule(BaseModel):
    id: str
    description: str
    scope: str
    severity: Severity
    source: RuleSource
    category: SpecialistName | Literal["any"]
    mode: Literal["forbid_regex", "require_regex"]
    pattern: str
    target: Literal["added_lines", "file_content"]
    message: str | None = None
    new_code_only: bool = True


class AllowlistEntry(BaseModel):
    path: str
    rule_ids: list[str] | None = None
    reason: str | None = None


class EnforcementSettings(BaseModel):
    mode: Literal["warn", "enforce"] = "warn"
    block_on: list[Severity] = ["critical"]
    new_code_only: bool = True
    max_comments: int = 3


class AgentRuntimeSettings(BaseModel):
    enabled: bool = True
    max_findings: int = 50


class AgentSettings(BaseModel):
    specialists: dict[str, AgentRuntimeSettings]


class CategoryClassificationConfig(BaseModel):
    paths: list[str] = []
    extensions: list[str] = []


class ReviewPilotConfig(BaseModel):
    rules: list[Rule] = []
    soft_rules: list[Rule] = []
    hard_rules: list[HardRule] = []
    ignore: list[str] = []
    allowlist: list[AllowlistEntry] = []
    settings: ConfigSettings = None  # type: ignore[assignment]
    enforcement: EnforcementSettings = None  # type: ignore[assignment]
    agents: AgentSettings = None  # type: ignore[assignment]
    file_classification: dict[str, CategoryClassificationConfig] = {}
    specialist_routing: dict[str, list[str]] = {}


class ConfigSettings(BaseModel):
    max_inline_comments: int = 3
    model: str = "claude-sonnet-4-5-20250929"
    context_budget: int = 50000


class LearnedRule(BaseModel):
    id: str
    description: str
    scope: str
    pattern: str
    severity: Severity
    source: Literal["learned"] = "learned"
    learned_from: LearnedFrom
    confidence: float


class LearnedFrom(BaseModel):
    pr_number: int
    merged_at: str


class LearnedRulesStore(BaseModel):
    version: int = 1
    rules: list[LearnedRule] = []
    last_updated: str = ""


class PolicySnapshot(BaseModel):
    version: int
    generated_at: str
    soft_rules: list[Rule] = []
    hard_rules: list[HardRule] = []


class PolicyBundle(BaseModel):
    soft_rules: list[Rule] = []
    hard_rules: list[HardRule] = []
    allowlist: list[AllowlistEntry] = []
    ignore: list[str] = []
    settings: ConfigSettings = ConfigSettings()
    enforcement: EnforcementSettings = EnforcementSettings()
    agents: AgentSettings = AgentSettings(specialists={})
    file_classification: dict[str, CategoryClassificationConfig] = {}
    specialist_routing: dict[str, list[str]] = {}


# ---------------------------------------------------------------------------
# Diff routing
# ---------------------------------------------------------------------------


class FileClassification(BaseModel):
    path: str
    kind: FileKind
    language: str


class RoutedFile(BaseModel):
    file: ChangedFile
    classification: FileClassification


class DiffRoutingResult(BaseModel):
    by_specialist: dict[str, list[RoutedFile]]
    generated_touched: list[RoutedFile] = []


# ---------------------------------------------------------------------------
# Analysis and review output
# ---------------------------------------------------------------------------


class Finding(BaseModel):
    rule_id: str
    severity: Severity
    file: str
    line: int
    title: str
    explanation: str
    suggestion: str | None = None
    category: str | None = None
    agent: str | None = None
    evidence: str | None = None


class AnalysisResult(BaseModel):
    findings: list[Finding]
    summary: str
    pass_count: int = 1
    token_usage: TokenUsage = None  # type: ignore[assignment]


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0


class InlineComment(BaseModel):
    path: str
    line: int
    body: str


class ReviewOutput(BaseModel):
    body: str
    comments: list[InlineComment]
    event: Literal["COMMENT", "REQUEST_CHANGES", "APPROVE"]
