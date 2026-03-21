---
name: release
description: "Prepare and execute a release — changelog, version bump, tag"
argument-hint: "<version> [major|minor|patch]"
---

# /release — Release Management

### Step 1: Pre-release Checks
1. Run `/validate` — all checks must pass
2. Verify all PRD acceptance criteria are met
3. Check for uncommitted changes

### Step 2: Changelog
1. Read git log since last tag/release
2. Group commits by type (features, fixes, chores)
3. Generate CHANGELOG entry

### Step 3: Version Bump
1. Update version in package.json / pyproject.toml / etc.
2. Update any version references in docs

### Step 4: Tag & Commit
1. Commit version bump and changelog
2. Create git tag: `v<version>`
3. Present summary and ask before pushing

### Output
```
## Release v<version>
- Features: N
- Fixes: M
- Breaking changes: K
- Tag: v<version>
- Ready to push: yes/no
```
