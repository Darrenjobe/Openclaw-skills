# skill.yaml Specification

Every skill declares its metadata in a `skill.yaml` at the skill root.

## Full Schema

```yaml
# --- Required ---
name: string          # Unique skill identifier, matches directory name (kebab-case)
version: string       # Semantic version: MAJOR.MINOR.PATCH
description: string   # One-sentence description shown in skill listings
author: string        # Author or team name
language: string      # Runtime: python | bash | node
entry_point: string   # Relative path to the main executable/script

# --- Optional ---
requires_config: bool       # Default: false. If true, config.yaml must exist before running
schedule: string            # Cron expression for automated runs, e.g. "0 */6 * * *"
tags: list[string]          # Discovery tags
dependencies:               # Other skills this one depends on (name only)
  - other-skill-name
env_vars: list[string]      # Environment variable names the skill reads (no values)
min_python: string          # Minimum Python version, e.g. "3.11"
```

## Version Bumping Rules

| Change type | Version bump |
|-------------|-------------|
| Bug fix, no config change | PATCH (0.1.0 → 0.1.1) |
| New feature, backwards-compatible config | MINOR (0.1.0 → 0.2.0) |
| Breaking config change or interface change | MAJOR (0.1.0 → 1.0.0) |
