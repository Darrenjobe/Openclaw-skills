# Openclaw Skills

A collection of skills for the **Openclaw** system running on a Raspberry Pi 5.

## Repository Structure

```
Openclaw-skills/
├── skills/                  # One directory per skill
│   ├── x-research/          # Research X (Twitter) for trends & news
│   └── <future-skill>/
├── shared/                  # Utilities shared across skills
│   └── utils.py
└── docs/
    ├── adding-a-skill.md    # Guide for adding new skills
    └── skill-spec.md        # skill.yaml specification
```

## Available Skills

| Skill | Description | Status |
|-------|-------------|--------|
| [x-research](skills/x-research/) | Research X for trends & latest news on topics | ✅ Active |

## Quick Start

Each skill is self-contained. Navigate into the skill directory and follow its own README:

```bash
cd skills/x-research
pip install -r requirements.txt
cp config.example.yaml config.yaml
# Edit config.yaml with your settings
python src/main.py --topic "raspberry pi" --topic "AI"
```

## Adding a New Skill

See [docs/adding-a-skill.md](docs/adding-a-skill.md) for the step-by-step guide and conventions.

## Platform

- Device: Raspberry Pi 5
- Python: 3.11+
- Storage: SQLite per skill (no external database required)
