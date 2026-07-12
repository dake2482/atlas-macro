# Project Decisions

## 2026-07-12 - Register Atlas Macro as AI-RESEARCH

- Atlas Macro is the canonical project at `/Users/dake/Documents/AI投研`.
- The project is an active research application, not an untriaged workspace.
- Public data lineage, licensing, and clean-room boundaries are durable product requirements.
- The repository currently has no canonical remote and remains explicitly local-only until the user chooses otherwise.

## 2026-07-12 - Separate current observations from release vintages

- `Observation` remains the normalized current-value contract used by public metrics and historical trend charts.
- `ReleaseVintageObservation` preserves values exactly as published in an identifiable official release, keyed by series, economic period, release date, estimate round, and source.
- A refresh may publish GDP only when the current observations and required vintage series were stored under the same successful BEA ingestion batch.
- Public revision charts use the latest complete workbook batch; older raw artifacts and hashes remain the immutable audit trail.
