---
name: generate-eval
description: "Generate eval.json assertions for a skill"
argument-hint: "<skill-name>"
---

# /generate-eval — Generate Evaluation File

### Step 1: Analyze Skill
Read SKILL.md — identify expected output format, sections, content requirements.

### Step 2: Create Assertions
Binary (pass/fail) assertions in categories:
- **structure** — headings, bullet lists, code blocks
- **content** — required keywords, topics, sections
- **format** — line length, markdown, frontmatter
- **length** — word count, section count
- **forbidden** — no TODOs, no placeholders, no secrets

### Step 3: Write eval.json
Save to `.claude/skills/<skill-name>/eval.json`

### Step 4: Validate
- Minimum 5 assertions per test case
- Minimum 2 test cases per skill
- All assertions must be binary (automatable)
- Non-automatable checks marked `"needs_ai": true`

### Assertion Types
`contains`, `not_contains`, `min_words`, `max_words`, `has_heading`, `has_code_block`, `has_bullet_list`, `min_sections`, `max_line_length`, `first_line_contains`, `last_line_contains`, `matches_regex`
