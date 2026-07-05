# skill-grade

**73% of community Claude Code skills score below 60/100.**

Nobody graded them before shipping. Now you can.

`skill-grade` is a static quality checker for Claude Code `SKILL.md` files — the same role ESLint plays for JavaScript, but for AI agent skills. It catches missing trigger phrases, scope creep, missing examples, and token bloat before they degrade agent behavior in production.

```
pip install skill-grade
```

---

## Quick start

```bash
# Grade a single skill
skill-grade path/to/SKILL.md

# Grade all skills in a directory (recursive)
skill-grade ./skills/

# Grade via stdin
cat SKILL.md | skill-grade -

# JSON output for CI pipelines
skill-grade SKILL.md --json

# Fail CI below a threshold
skill-grade SKILL.md --threshold A
```

## Example output

```
skill-grade v0.1.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Skill: my-skill
Score: 65/100  Grade: C
Tokens: ~847 (description: 312, body: 535)

  W  S006  No trigger phrases detected. Add "Use when...", "Triggers include...",
           or "Use for..." so Claude knows when to invoke this skill.
  W  S013  No code examples (no markdown code blocks). Agents learn better from
           concrete examples than prose descriptions.
  W  S014  No structure detected (no ## headers or numbered lists). Structured
           instructions are easier for agents to follow.

Passed: S001 ✓  S002 ✓  S003 ✓  S004 ✓  S010 ✓  S011 ✓

Tip: A+ skills include explicit trigger phrases and concrete examples.
```

For multiple files:

```
skill-grade v0.1.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  browser-automation  A+   97/100  ✓
  code-review         B    78/100  1 warning
  deployment          F    35/100  3 errors, 2 warnings

2/3 skills pass (≥70/100)
```

---

## Checks

### Frontmatter

| Code | Severity | Description | Penalty |
|------|----------|-------------|---------|
| S001 | error | No YAML frontmatter found (`---` delimiters missing) | -70 |
| S002 | error | Missing `name` field | -30 |
| S003 | error | Missing `description` field | -40 |
| S004 | warning | Description too short (<50 chars) — unreliable trigger matching | -20 |
| S005 | warning | Description too long (>500 chars) — loads into context on every match | -10 |
| S006 | warning | No trigger phrases ("Use when", "Triggers include", "Use for", "when the user") | -20 |
| S007 | warning | Vague trigger language ("help with", "assist with", "various", "manage", "handle") | -15 |
| S008 | info | No `allowed-tools` field | -5 |
| S009 | warning | Skill name contains spaces (use hyphens or underscores) | -10 |

### Body

| Code | Severity | Description | Penalty |
|------|----------|-------------|---------|
| S010 | error | No body content — stub skill | -30 |
| S011 | warning | Body too short (<100 chars) | -20 |
| S012 | warning | Body too long (>8000 chars) — increases context usage | -10 |
| S013 | warning | No code examples (no markdown code blocks) | -15 |
| S014 | warning | No structure (no `##` headers or numbered lists) | -10 |
| S015 | warning | Scope creep — 4+ "and" connectors in description | -15 |

### Grades

| Grade | Score |
|-------|-------|
| A+ | ≥ 90 |
| A | ≥ 80 |
| B | ≥ 70 |
| C | ≥ 60 |
| D | ≥ 50 |
| F | < 50 |

---

## GitHub Action

```yaml
- uses: 0-co/skill-grade@main
  with:
    path: '.'
    threshold: 'B'
```

Or install directly:

```yaml
- run: pip install skill-grade
- run: skill-grade ./skills/ --threshold B
```

---

## Why this exists

Claude Code skills are loaded into context when triggered. A skill with a vague description triggers too broadly (wasted tokens) or not at all (the skill gets ignored). A skill with no examples produces worse agent behavior than one with three concrete command invocations.

These are fixable problems. `skill-grade` makes them visible before they ship.

---

## Zero dependencies

Pure Python stdlib. No PyYAML, no third-party packages. Works anywhere Python 3.9+ is installed.

---

`pip install skill-grade`
