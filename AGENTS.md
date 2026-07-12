# Atlas Macro Repository Guidelines

## Shared Policy

- Also follow `/Users/dake/Documents/AGENT_POLICY.md`.
- This file only adds Atlas Macro architecture, provenance, publication, and validation rules.

## Purpose

Atlas Macro is a clean-room Django macro-research and AI supply-chain intelligence platform. It uses original presentation, traceable public sources, explicit data-quality labels, and first-party calculations. It is not a trading or order-entry system.

## Repository Structure

- `atlasmacro/` contains Django settings, URLs, ASGI/WSGI, and Celery configuration.
- `research/` contains data contracts, source adapters, calculations, models, views, and management commands.
- `tests/` contains deterministic contract, route, source-lineage, and publication-safety tests.
- `assets/` contains public contract artifacts; `staticfiles/` and local runtime databases are generated output.
- `docs/project/` contains project state, requirements, decisions, and generated status.

## Data And Publication Safety

- Keep third-party content to permitted metadata, links, and original summaries. Do not copy protected pages, private APIs, proprietary reports, or restricted datasets.
- Every published numerical observation must preserve source, observation time, fetch time, quality state, licence scope, and fallback state.
- Demo or offline seed data must never appear as official public data. Production publication must retain the last complete snapshot when a required source fails.
- Keep `.env`, databases, credentials, API keys, runtime data, logs, generated static output, and dependency directories out of Git.

## Canonical Validation

Run from the repository root with the local virtual environment:

```bash
.venv/bin/ruff check .
.venv/bin/pytest -q
.venv/bin/python manage.py check
```

For deployment-facing changes, also run the documented production checks, route smoke tests, and browser verification appropriate to the changed surface.
