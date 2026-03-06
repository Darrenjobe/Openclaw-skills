# Adding a New Skill

Follow these conventions so all skills remain consistent and maintainable.

## 1. Create the Skill Directory

```bash
mkdir -p skills/<skill-name>/{src,tests,data}
```

Use `kebab-case` for the directory name (e.g. `weather-monitor`, `home-automation`).

## 2. Required Files

Every skill **must** include:

| File | Purpose |
|------|---------|
| `skill.yaml` | Skill metadata (see spec below) |
| `README.md` | Usage guide, config reference, examples |
| `requirements.txt` | Python dependencies (pin versions) |
| `config.example.yaml` | Template config — **never** commit real credentials |
| `src/main.py` | Entry point; must accept `--help` |

## 3. skill.yaml Fields

```yaml
name: my-skill          # matches directory name
version: 0.1.0
description: One-line description
author: Openclaw
language: python        # python | bash | node
entry_point: src/main.py
requires_config: true   # whether config.yaml is needed
tags:                   # free-form tags for discovery
  - research
  - social-media
```

## 4. Directory Layout

```
skills/<skill-name>/
├── skill.yaml
├── README.md
├── requirements.txt
├── config.example.yaml      # template only — no secrets
├── src/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   └── *.py                 # additional modules
├── tests/
│   └── test_*.py
└── data/                    # gitignored — created at runtime
```

## 5. Config Pattern

Skills read their config from `config.yaml` in the skill's root directory.
Use `config.example.yaml` as the source-of-truth template.

```python
# In your skill:
from pathlib import Path
import yaml

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
```

## 6. Shared Utilities

Common helpers live in `shared/`. Import them using a relative path adjustment or
by adding the repo root to `PYTHONPATH`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3]))  # repo root
from shared.utils import setup_logging, ensure_dir
```

## 7. Coding Standards

- Python 3.11+
- Pin dependency versions in `requirements.txt`
- Store runtime data under `data/` (gitignored)
- Log to `data/logs/` not stdout, unless running interactively
- No hard-coded secrets — always read from `config.yaml` or environment vars
- Prefer stdlib + lightweight deps (the host is a Raspberry Pi 5)

## 8. Checklist Before Committing

- [ ] `skill.yaml` filled out completely
- [ ] `README.md` has usage examples
- [ ] `config.example.yaml` has all keys (no real values)
- [ ] `requirements.txt` with pinned versions
- [ ] `data/` directory is gitignored
- [ ] Tests added under `tests/`
