"""Review formatting and GitHub posting — port of src/reviewer.ts."""

from __future__ import annotations

import logging

from github.PullRequest import PullRequest

from .models import (
    AnalysisResult,
    ChangedFile,
    Finding,
    InlineComment,
    RepoMetadata,
    ReviewOutput,
    Severity,
)

logger = logging.getLogger(__name__)

SEVERITY_EMOJI: dict[str, str] = {
    "critical": "\U0001f534",  # red circle
    "warning": "\U0001f7e1",   # yellow circle
    "info": "\U0001f535",       # blue circle
}

BOT_SIGNATURE = "<!-- review-pilot-review -->"


def line_to_diff_position(
    changed_files: list[ChangedFile],
    file_path: str,
    line_number: int,
) -> int | None:
    file = next((f for f in changed_files if f.path == file_path), None)
    if not file:
        return None

    position = 0
    for hunk in file.hunks:
        position += 1  # hunk header
        current_line = hunk.new_start

        for line in hunk.content.split("\n"):
            position += 1
            if line.startswith("-"):
                continue
            if current_line == line_number:
                return position
            current_line += 1

    return None


def _format_inline_comment(finding: Finding) -> str:
    emoji = SEVERITY_EMOJI.get(finding.severity, "")
    body = f"{emoji} **{finding.title}**\n\n{finding.explanation}"
    if finding.suggestion:
        body += f"\n\n**Suggestion:** {finding.suggestion}"
    agent_part = f" | Agent: `{finding.agent}`" if finding.agent else ""
    body += f"\n\n<sub>Rule: `{finding.rule_id}`{agent_part}</sub>"
    return body


def _format_summary_body(result: AnalysisResult) -> str:
    findings = result.findings
    critical = [f for f in findings if f.severity == "critical"]
    warnings = [f for f in findings if f.severity == "warning"]
    infos = [f for f in findings if f.severity == "info"]

    body = f"{BOT_SIGNATURE}\n## Review Pilot\n\n"
    body += f"{result.summary}\n\n"

    if not findings:
        body += "No semantic issues found. The changes look consistent with the policy.\n"
    else:
        body += "### Findings\n\n"
        body += "| Severity | Count |\n|----------|-------|\n"
        if critical:
            body += f"| {SEVERITY_EMOJI['critical']} Critical | {len(critical)} |\n"
        if warnings:
            body += f"| {SEVERITY_EMOJI['warning']} Warning | {len(warnings)} |\n"
        if infos:
            body += f"| {SEVERITY_EMOJI['info']} Info | {len(infos)} |\n"

        body += "\n### Details\n\n"
        for finding in findings:
            emoji = SEVERITY_EMOJI.get(finding.severity, "")
            body += f"#### {emoji} {finding.title}\n"
            body += f"`{finding.file}:{finding.line}` | Rule: `{finding.rule_id}`"
            if finding.category:
                body += f" | Category: `{finding.category}`"
            if finding.agent:
                body += f" | Agent: `{finding.agent}`"
            body += "\n\n"
            body += f"{finding.explanation}\n"
            if finding.suggestion:
                body += f"\n> **Suggestion:** {finding.suggestion}\n"
            body += "\n---\n\n"

    tu = result.token_usage
    body += f"<sub>Passes: {result.pass_count} | Tokens: {tu.input_tokens} in / {tu.output_tokens} out</sub>"
    return body


def _choose_review_event(
    findings: list[Finding],
    *,
    mode: str = "enforce",
    block_on: list[Severity] | None = None,
) -> str:
    if not findings:
        return "APPROVE"

    if mode == "warn":
        return "COMMENT"

    effective_block_on = block_on or ["critical"]
    should_block = any(f.severity in effective_block_on for f in findings)
    return "REQUEST_CHANGES" if should_block else "COMMENT"


def build_review_output(
    result: AnalysisResult,
    changed_files: list[ChangedFile],
    max_inline_comments: int,
    opts: dict[str, object] | None = None,
) -> ReviewOutput:
    body = _format_summary_body(result)
    opts = opts or {}

    inline_findings = result.findings[:max_inline_comments]
    comments: list[InlineComment] = []

    for finding in inline_findings:
        position = line_to_diff_position(changed_files, finding.file, finding.line)
        if position is None:
            continue

        comments.append(
            InlineComment(
                path=finding.file,
                line=position,
                body=_format_inline_comment(finding),
            )
        )

    event = _choose_review_event(
        result.findings,
        mode=str(opts.get("mode", "enforce")),
        block_on=opts.get("block_on"),  # type: ignore[arg-type]
    )

    return ReviewOutput(body=body, comments=comments, event=event)


def _find_existing_review(pr: PullRequest) -> int | None:
    for review in pr.get_reviews():
        if review.body and BOT_SIGNATURE in review.body:
            return review.id
    return None


def post_review(
    pr: PullRequest,
    metadata: RepoMetadata,
    review: ReviewOutput,
) -> None:
    existing_id = _find_existing_review(pr)

    if existing_id is not None:
        logger.info("Dismissing existing Review Pilot review #%d", existing_id)
        try:
            pr.get_review(existing_id).dismiss("Superseded by updated Review Pilot review")
        except Exception:
            logger.warning("Could not dismiss previous review (may lack permissions)")

    logger.info("Posting review with %d inline comments", len(review.comments))

    pr.create_review(
        commit=pr.get_commits().reversed[0],
        body=review.body,
        event=review.event,
        comments=[
            {
                "path": c.path,
                "position": c.line,
                "body": c.body,
            }
            for c in review.comments
        ],
    )

    logger.info("Review posted successfully (event: %s)", review.event)
