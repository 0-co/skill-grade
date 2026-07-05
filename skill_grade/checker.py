"""Core checks for SKILL.md quality analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


GRADE_THRESHOLDS: list[tuple[str, int]] = [
    ("A+", 90),
    ("A", 80),
    ("B", 70),
    ("C", 60),
    ("D", 50),
    ("F", 0),
]

GRADE_ORDER = ["A+", "A", "B", "C", "D", "F"]

# Severity levels
ERROR = "error"
WARNING = "warning"
INFO = "info"


@dataclass
class Issue:
    code: str
    severity: str
    message: str
    penalty: int


@dataclass
class SkillResult:
    filename: str
    name: str
    score: int
    grade: str
    issues: list[Issue]
    passed_checks: list[str]
    token_estimate_description: int
    token_estimate_body: int

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == INFO)


def _estimate_tokens(text: str) -> int:
    return len(text) // 4


def _parse_frontmatter(content: str) -> tuple[Optional[dict[str, str]], str]:
    """Parse YAML frontmatter using simple string parsing (no PyYAML)."""
    stripped = content.lstrip()
    if not stripped.startswith("---"):
        return None, content

    # Find the closing ---
    rest = stripped[3:]
    # Allow optional \r
    if rest.startswith("\r\n"):
        rest = rest[2:]
    elif rest.startswith("\n"):
        rest = rest[1:]
    else:
        # --- not followed by newline, not valid frontmatter
        return None, content

    # Search for closing ---
    end_match = re.search(r"\n---[ \t]*(\r?\n|$)", rest)
    if not end_match:
        return None, content

    fm_text = rest[: end_match.start()]
    body = rest[end_match.end() :]

    # Parse simple key: value pairs (single-level only)
    parsed: dict[str, str] = {}
    current_key: Optional[str] = None
    current_lines: list[str] = []

    for line in fm_text.split("\n"):
        # Check for key: value
        key_match = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)", line)
        if key_match:
            if current_key is not None:
                parsed[current_key] = "\n".join(current_lines).strip()
            current_key = key_match.group(1)
            current_lines = [key_match.group(2)]
        elif current_key is not None and (line.startswith("  ") or line.startswith("\t")):
            # Continuation line (indented)
            current_lines.append(line.strip())

    if current_key is not None:
        parsed[current_key] = "\n".join(current_lines).strip()

    return parsed, body


def _score_to_grade(score: int) -> str:
    for grade, threshold in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "F"


def grade_threshold_to_score(grade: str) -> int:
    """Return the minimum score for a given grade string."""
    for g, threshold in GRADE_THRESHOLDS:
        if g == grade:
            return threshold
    raise ValueError(f"Unknown grade: {grade}")


def check_skill(content: str, filename: str = "SKILL.md") -> SkillResult:
    """Analyze a SKILL.md string and return a SkillResult with issues and score."""
    issues: list[Issue] = []
    passed: list[str] = []
    score = 100

    def add_issue(code: str, severity: str, message: str, penalty: int) -> None:
        nonlocal score
        issues.append(Issue(code=code, severity=severity, message=message, penalty=penalty))
        score = max(0, score - penalty)

    def mark_passed(code: str) -> None:
        passed.append(code)

    # --- Parse frontmatter ---
    frontmatter, body = _parse_frontmatter(content)

    if frontmatter is None:
        add_issue("S001", ERROR, "No YAML frontmatter found (--- delimiters missing).", 70)
        # Without frontmatter, S002-S009 cannot be evaluated meaningfully
        skill_name = filename
        description = ""
    else:
        mark_passed("S001")
        skill_name = frontmatter.get("name", "").strip()
        description = frontmatter.get("description", "").strip()
        allowed_tools = frontmatter.get("allowed-tools", "").strip()

        # S002: Missing name
        if not skill_name:
            add_issue("S002", ERROR, "Missing `name` field in frontmatter.", 30)
        else:
            mark_passed("S002")

        # S003: Missing description
        if not description:
            add_issue("S003", ERROR, "Missing `description` field in frontmatter.", 40)
        else:
            mark_passed("S003")

            # S004: Description too short
            if len(description) < 50:
                add_issue(
                    "S004",
                    WARNING,
                    f"Description too short ({len(description)} chars). "
                    "Add at least 50 chars for reliable trigger matching.",
                    20,
                )
            else:
                mark_passed("S004")

            # S005: Description too long
            if len(description) > 500:
                add_issue(
                    "S005",
                    WARNING,
                    f"Description too long ({len(description)} chars). "
                    "Descriptions load into context on every skill match — keep under 500 chars.",
                    10,
                )
            else:
                mark_passed("S005")

            # S006: No trigger phrases
            trigger_patterns = ["use when", "triggers include", "use for", "when the user"]
            desc_lower = description.lower()
            if not any(pat in desc_lower for pat in trigger_patterns):
                add_issue(
                    "S006",
                    WARNING,
                    'No trigger phrases detected. Add "Use when...", "Triggers include...", '
                    'or "Use for..." so Claude knows when to invoke this skill.',
                    20,
                )
            else:
                mark_passed("S006")

            # S007: Vague trigger language
            vague_terms = ["help with", "assist with", "various", "manage", "handle"]
            vague_found = [t for t in vague_terms if t in desc_lower]
            if vague_found:
                add_issue(
                    "S007",
                    WARNING,
                    f"Vague trigger language: {', '.join(repr(t) for t in vague_found)}. "
                    "Replace with specific actions (e.g., 'create', 'deploy', 'parse').",
                    15,
                )
            else:
                mark_passed("S007")

        # S008: No allowed-tools
        if not allowed_tools:
            add_issue(
                "S008",
                INFO,
                "No `allowed-tools` field. Consider specifying which tools this skill may invoke.",
                5,
            )
        else:
            mark_passed("S008")

        # S009: Skill name contains spaces
        if skill_name and " " in skill_name:
            add_issue(
                "S009",
                WARNING,
                f"Skill name '{skill_name}' contains spaces. Use hyphens or underscores instead.",
                10,
            )
        elif skill_name:
            mark_passed("S009")

    # --- Body checks ---
    body_stripped = body.strip()

    # S010: No body content
    if not body_stripped:
        add_issue("S010", ERROR, "No body content — skill is just a frontmatter stub.", 30)
    else:
        mark_passed("S010")

        # S011: Body too short
        if len(body_stripped) < 100:
            add_issue(
                "S011",
                WARNING,
                f"Body too short ({len(body_stripped)} chars). "
                "Stub skills don't give the agent enough guidance.",
                20,
            )
        else:
            mark_passed("S011")

        # S012: Body too long
        if len(body_stripped) > 8000:
            add_issue(
                "S012",
                WARNING,
                f"Body too long ({len(body_stripped)} chars). "
                "Large skill bodies increase context usage on every invocation. "
                "Consider splitting into focused sub-skills.",
                10,
            )
        else:
            mark_passed("S012")

        # S013: No code examples
        if not re.search(r"```", body_stripped):
            add_issue(
                "S013",
                WARNING,
                "No code examples (no markdown code blocks). "
                "Agents learn better from concrete examples than prose descriptions.",
                15,
            )
        else:
            mark_passed("S013")

        # S014: No structure
        has_headers = bool(re.search(r"^##\s", body_stripped, re.MULTILINE))
        has_numbered = bool(re.search(r"^\d+\.", body_stripped, re.MULTILINE))
        if not has_headers and not has_numbered:
            add_issue(
                "S014",
                WARNING,
                "No structure detected (no ## headers or numbered lists). "
                "Structured instructions are easier for agents to follow.",
                10,
            )
        else:
            mark_passed("S014")

    # S015: Scope creep (checked against description if available)
    check_text = description if frontmatter and description else ""
    if check_text:
        and_count = len(re.findall(r"\band\b", check_text, re.IGNORECASE))
        if and_count >= 4:
            add_issue(
                "S015",
                WARNING,
                f"Scope creep: description contains {and_count} instances of 'and'. "
                "Broad-scope skills trigger unpredictably — split into focused skills.",
                15,
            )
        else:
            mark_passed("S015")
    else:
        mark_passed("S015")

    # Token estimates
    token_desc = _estimate_tokens(description) if frontmatter else 0
    token_body = _estimate_tokens(body_stripped)

    return SkillResult(
        filename=filename,
        name=skill_name if (frontmatter and skill_name) else filename,
        score=max(0, score),
        grade=_score_to_grade(max(0, score)),
        issues=issues,
        passed_checks=passed,
        token_estimate_description=token_desc,
        token_estimate_body=token_body,
    )
