"""CLI entry point for skill-grade."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Optional

from skill_grade import __version__
from skill_grade.checker import (
    ERROR,
    WARNING,
    INFO,
    GRADE_ORDER,
    SkillResult,
    check_skill,
    grade_threshold_to_score,
)


# ANSI color codes
class Color:
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


def _use_color() -> bool:
    return sys.stdout.isatty() and os.environ.get("NO_COLOR", "") == ""


def _c(text: str, *codes: str) -> str:
    if not _use_color():
        return text
    return "".join(codes) + text + Color.RESET


def _severity_color(severity: str) -> str:
    if severity == ERROR:
        return Color.RED
    if severity == WARNING:
        return Color.YELLOW
    return Color.BLUE


def _severity_symbol(severity: str) -> str:
    if severity == ERROR:
        return "E"
    if severity == WARNING:
        return "W"
    return "I"


def _grade_color(grade: str) -> str:
    if grade in ("A+", "A"):
        return Color.GREEN
    if grade == "B":
        return Color.BLUE
    if grade in ("C", "D"):
        return Color.YELLOW
    return Color.RED


def _collect_skill_files(path_str: str) -> list[Path]:
    """Return list of SKILL.md paths for a file path, directory, or '-' for stdin."""
    if path_str == "-":
        return [Path("-")]

    path = Path(path_str)
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.rglob("SKILL.md"))
    # Maybe it's a glob or just doesn't exist
    sys.stderr.write(f"skill-grade: path not found: {path_str}\n")
    sys.exit(1)


def _format_single_result(
    result: SkillResult,
    errors_only: bool,
    show_header: bool,
) -> list[str]:
    """Format a single SkillResult for terminal output. Returns list of lines."""
    lines: list[str] = []

    if show_header:
        lines.append(_c(f"skill-grade v{__version__}", Color.BOLD))
        lines.append(_c("\u2501" * 43, Color.DIM))

    grade_colored = _c(result.grade, _grade_color(result.grade), Color.BOLD)
    score_colored = _c(f"{result.score}/100", Color.BOLD)
    token_total = result.token_estimate_description + result.token_estimate_body

    lines.append(f"Skill: {_c(result.name, Color.BOLD)}")
    lines.append(f"Score: {score_colored}  Grade: {grade_colored}")
    lines.append(
        f"Tokens: ~{token_total} "
        f"(description: {result.token_estimate_description}, body: {result.token_estimate_body})"
    )
    lines.append("")

    displayed_issues = result.issues
    if errors_only:
        displayed_issues = [i for i in result.issues if i.severity == ERROR]

    if displayed_issues:
        for issue in displayed_issues:
            sym = _severity_symbol(issue.severity)
            sym_colored = _c(sym, _severity_color(issue.severity), Color.BOLD)
            code_colored = _c(issue.code, Color.BOLD)
            lines.append(f"  {sym_colored}  {code_colored}  {issue.message}")
        lines.append("")

    if result.passed_checks:
        passed_str = "  ".join(
            _c(f"{c} \u2713", Color.GREEN) for c in result.passed_checks
        )
        lines.append(f"Passed: {passed_str}")
        lines.append("")

    # Tip
    if result.score < 90:
        if result.error_count > 0:
            lines.append(
                _c(
                    "Tip: Fix errors first (S001-S003 penalties are largest).",
                    Color.DIM,
                )
            )
        else:
            lines.append(
                _c(
                    "Tip: A+ skills include explicit trigger phrases and concrete examples.",
                    Color.DIM,
                )
            )

    return lines


def _format_multi_results(
    results: list[SkillResult],
    threshold_score: int,
) -> list[str]:
    """Format a summary table for multiple results."""
    lines: list[str] = []
    lines.append(_c(f"skill-grade v{__version__}", Color.BOLD))
    lines.append(_c("\u2501" * 43, Color.DIM))

    # Determine column width for skill name
    max_name = max((len(r.name) for r in results), default=20)
    max_name = max(max_name, 10)

    for result in results:
        grade_col = _c(f"{result.grade:<3}", _grade_color(result.grade), Color.BOLD)
        score_col = _c(f"{result.score:>3}/100", Color.BOLD)
        name_col = result.name.ljust(max_name)

        # Issue summary
        issue_parts: list[str] = []
        if result.error_count:
            issue_parts.append(
                _c(f"{result.error_count} error{'s' if result.error_count != 1 else ''}", Color.RED)
            )
        if result.warning_count:
            issue_parts.append(
                _c(
                    f"{result.warning_count} warning{'s' if result.warning_count != 1 else ''}",
                    Color.YELLOW,
                )
            )
        if not issue_parts:
            issue_parts.append(_c("\u2713", Color.GREEN))

        issue_str = ", ".join(issue_parts)
        lines.append(f"  {name_col}  {grade_col}  {score_col}  {issue_str}")

    lines.append("")
    passing = sum(1 for r in results if r.score >= threshold_score)
    total = len(results)
    ratio = _c(f"{passing}/{total}", Color.GREEN if passing == total else Color.YELLOW)
    lines.append(f"{ratio} skills pass (\u2265{threshold_score}/100)")

    return lines


def _result_to_dict(result: SkillResult) -> dict:
    return {
        "filename": result.filename,
        "name": result.name,
        "score": result.score,
        "grade": result.grade,
        "tokens": {
            "description": result.token_estimate_description,
            "body": result.token_estimate_body,
            "total": result.token_estimate_description + result.token_estimate_body,
        },
        "issues": [
            {
                "code": i.code,
                "severity": i.severity,
                "message": i.message,
                "penalty": i.penalty,
            }
            for i in result.issues
        ],
        "passed_checks": result.passed_checks,
        "error_count": result.error_count,
        "warning_count": result.warning_count,
    }


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="skill-grade",
        description="Grade Claude Code SKILL.md files for quality.",
    )
    parser.add_argument(
        "path",
        help="Path to SKILL.md file, directory, or '-' for stdin.",
    )
    parser.add_argument(
        "--errors-only",
        action="store_true",
        help="Show only errors, suppress warnings and info.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON.",
    )
    parser.add_argument(
        "--threshold",
        default="B",
        metavar="GRADE",
        help="Exit code 1 if any skill scores below this grade (default: B). "
        "Valid: A+, A, B, C, D, F.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"skill-grade {__version__}",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> None:
    args = _parse_args(argv)

    # Validate threshold
    threshold_grade = args.threshold.upper().replace("A PLUS", "A+")
    # Allow "a+" or "A+" etc.
    if threshold_grade not in GRADE_ORDER:
        sys.stderr.write(
            f"skill-grade: invalid threshold '{args.threshold}'. "
            f"Valid grades: {', '.join(GRADE_ORDER)}\n"
        )
        sys.exit(2)

    threshold_score = grade_threshold_to_score(threshold_grade)

    # Collect files
    skill_files = _collect_skill_files(args.path)

    if not skill_files:
        sys.stderr.write(f"skill-grade: no SKILL.md files found in '{args.path}'\n")
        sys.exit(0)

    # Grade each file
    results: list[SkillResult] = []
    for path in skill_files:
        if str(path) == "-":
            content = sys.stdin.read()
            filename = "stdin"
        else:
            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                sys.stderr.write(f"skill-grade: cannot read {path}: {exc}\n")
                sys.exit(1)
            filename = str(path)

        results.append(check_skill(content, filename=filename))

    # Output
    if args.json_output:
        output = (
            _result_to_dict(results[0])
            if len(results) == 1
            else [_result_to_dict(r) for r in results]
        )
        print(json.dumps(output, indent=2))
    elif len(results) == 1:
        lines = _format_single_result(results[0], errors_only=args.errors_only, show_header=True)
        print("\n".join(lines))
    else:
        lines = _format_multi_results(results, threshold_score=threshold_score)
        print("\n".join(lines))

    # Exit code
    any_failed = any(r.score < threshold_score for r in results)
    sys.exit(1 if any_failed else 0)
