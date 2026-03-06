"""Convention mining from merged PRs — port of src/agents/convention-miner.ts."""

from __future__ import annotations

import json
import logging
import re

import anthropic
from github.PullRequest import PullRequest
from github.Repository import Repository

from ..config import load_learned_rules, save_learned_rules
from ..models import LearnedFrom, LearnedRule

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are a coding convention extractor. Given a merged pull request diff \
and review comments, extract implicit semantic coding conventions.

Focus on high-signal conventions only:
- security/compliance checks
- error logging patterns
- architecture boundaries
- API validation and response contracts
- data-access separation

## PR Diff
{diff}

## Review Comments
{comments}

Return JSON array only. Schema:
[
  {{
    "id": "kebab-case-id",
    "description": "convention description",
    "scope": "glob/pattern/**",
    "pattern": "natural language review rule",
    "severity": "critical|warning|info",
    "confidence": 0.0
  }}
]

If no clear conventions, return []"""


def mine_conventions_from_merged_pr(
    repo: Repository,
    pr: PullRequest,
    *,
    api_key: str,
    model: str,
    learned_rules_path: str,
) -> None:
    if not pr.merged:
        logger.info("PR is not merged; skipping convention mining")
        return

    pull_number = pr.number

    files = pr.get_files()
    diff = "\n\n".join(
        f"### {f.filename}\n{f.patch or ''}"
        for f in files
        if f.patch
    )

    comments = list(pr.get_review_comments())
    comment_text = (
        "\n".join(f"- {c.path}:{c.line or '?'} {c.body}" for c in comments)
        if comments
        else "No review comments."
    )

    prompt = EXTRACTION_PROMPT.replace("{diff}", diff).replace("{comments}", comment_text)

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    text_block = next((b for b in response.content if b.type == "text"), None)
    if not text_block:
        return

    try:
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text_block.text)
        raw_text = fenced.group(1) if fenced else text_block.text
        extracted: list[dict[str, object]] = json.loads(raw_text.strip())
    except (json.JSONDecodeError, AttributeError) as err:
        logger.warning("Convention mining parse failure: %s", err)
        return

    if not extracted:
        return

    existing = load_learned_rules(learned_rules_path)
    existing_ids = {r.id for r in existing}

    new_rules: list[LearnedRule] = []
    for e in extracted:
        eid = str(e.get("id", ""))
        if eid in existing_ids:
            continue
        new_rules.append(
            LearnedRule(
                id=eid,
                description=str(e.get("description", "")),
                scope=str(e.get("scope", "")),
                pattern=str(e.get("pattern", "")),
                severity=str(e.get("severity", "info")),
                source="learned",
                learned_from=LearnedFrom(
                    pr_number=pull_number,
                    merged_at=pr.merged_at.isoformat() if pr.merged_at else "",
                ),
                confidence=float(str(e.get("confidence", 0.0))),
            )
        )

    if not new_rules:
        return

    save_learned_rules(learned_rules_path, [*existing, *new_rules])
    logger.info("Convention miner added %d learned rule(s)", len(new_rules))
