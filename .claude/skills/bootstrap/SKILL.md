---
name: bootstrap
description: "Initialize a new project — detect stack, fill PROJECT.md"
---

# /bootstrap — Project Initialization

## Workflow

### Step 1: Detect Project
1. Scan directory for package.json, requirements.txt, go.mod, Cargo.toml, etc.
2. Identify language, framework, package manager
3. Identify existing test/lint/build tooling

### Step 2: Fill PROJECT.md
Update `PROJECT.md` with detected information:
- Product name, tech stack table
- Available commands (install, dev, build, test, lint, typecheck)
- Directory structure, file conventions
- Architecture pattern

### Step 3: Verify
1. Run detected install command
2. Run detected build/lint/test commands
3. Confirm everything works

### Step 4: Report
```
## Bootstrap Complete
- **Project**: name
- **Stack**: language + framework
- **Commands verified**: install, build, test, lint
- **PROJECT.md**: updated
```
