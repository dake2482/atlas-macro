---
schema_version: 1
id: AI-RESEARCH-012
project_id: AI-RESEARCH
title: Fed 官方描述与 Atlas 分析 provenance 公开安全门
status: REVIEW
priority: P1
executor: codex
task_id: atlas-fed-document-provenance-20260713
branch: main
worktree: local
dependencies:
- AI-RESEARCH-008
updated_at: '2026-07-13T18:31:16+08:00'
next_action: Design and provision the scheduled evidence-binding and human-review pipeline; after future explicit deployment authorization, back up and migrate production through 0017, run a real official RSS refresh, deploy, and repeat post-deploy route and browser QA.
evidence:
- Federal Reserve RSS description now has a dedicated official_description field. Atlas summary is blank for new RSS rows and is never inferred from official metadata.
- Hawkish score is nullable and constrained to -5..5. Draft, rejected and incomplete-provenance enrichment cannot appear as a public Atlas analysis or score.
- Analysis states cover draft, AI generated, reviewed and rejected, with model, prompt version, generation time, evidence, reviewer and review time available for audit.
- Migration 0017 moves typical legacy RSS descriptions out of summary and nulls their default zero score. Other legacy enrichment is retained as legacy_unverified draft; an out-of-range legacy score is preserved in migration evidence before the public score is nulled.
- RSS refresh updates official fields and official_description while retaining every analysis and review field.
- Hub, fixed lists, detail and hawkish pages distinguish official metadata from Atlas analysis. Search covers title, speaker and official_description for every public Fed row, but only lets provenance-complete public analysis summaries influence results; the type filter is only shown where it is active.
- Public analysis evidence is a non-empty list of mappings with a stable non-empty id or source_id. Optional evidence links must be absolute HTTPS URLs without embedded credentials; model validation, public properties and templates all fail closed for bypassed malformed rows.
- The hub and hawkish aggregate includes only provenance-complete, explicitly reviewed, non-null scores. AI generated records are clearly labelled unreviewed and excluded from that aggregate.
- Data coverage records official Fed documents as LIVE and the scheduled hawkish/dovish analysis loop as NEEDS_SOURCE. No protected page, full document body or fabricated analysis was ingested.
- Independent directed verification passed all 123 Fed ingestion, migration, publication-hygiene, route, filter, hidden-search and evidence-safety tests; the full pytest suite also passed.
- Independent Ruff, Django check, migration-drift, production check and diff-whitespace checks all passed. A fresh SQLite database migrated successfully from 0001 through 0017.
- Independent browser QA passed `/fed/`, `/fed/news/`, reviewed detail, malformed-provenance detail and `/fed/hawkish-dovish/`; hidden summary searches failed closed. At 390px there was no horizontal overflow and the mobile drawer opened successfully.
- No network RSS refresh, production migration or deployment was performed; those remain future explicitly authorized operations.
started_at: '2026-07-13T18:00:00+08:00'
---

# 目标

将 Federal Reserve 官方 RSS 元数据和 Atlas 自有分析彻底分离，并以 fail-closed 规则约束所有公开摘要和鹰鸽评分。官方 description 可以独立展示；Atlas 分析只有在状态与 provenance 同时完整时才可见。

## 边界

- 只保存 Federal Reserve 官方 RSS 元数据、外链和 Atlas 自有分析，不抓取或复制受保护正文。
- 本需求不生成真实 AI 研判，不制造评分，也不声称已建立生产定时任务。
- AI generated 可以公开但必须明确标记“未人工审核”；只有 reviewed 评分进入综合平均。
- legacy enrichment 保留供人工复核，默认 draft，不能凭旧 summary 或默认 0 自动进入公开分析。

## Acceptance criteria

- [x] official_description 与 summary 分字段，provider 与 store 使用官方字段且刷新保留分析。
- [x] hawkish_score 可空、无默认值并限制为 -5..5；分析状态与 provenance 可在模型和 Admin 审计。
- [x] 0017 对典型旧 RSS 行保守拆分，对其他旧 enrichment 失败关闭且不删除内容。
- [x] Fed hub/list/detail/hawkish 页面统一使用公开安全门，q/type 筛选生效；隐藏 summary 不影响搜索结果，固定类型页不显示伪筛选。
- [x] 每条公开证据都有稳定 id/source_id；可选链接仅允许安全绝对 HTTPS URL，绕过 model clean 的无效记录仍保持隐藏。
- [x] reviewed-only 平均分、未审核标签、缺 provenance 隐藏、重复 refresh 和迁移规则有确定性测试。
- [x] data catalog 和 route requirement mapping 同时暴露官方 LIVE 与分析 NEEDS_SOURCE 状态。

## Independent verification evidence

- Fed 定向命令：`.venv/bin/pytest -q tests/test_fed_documents.py tests/test_content_ingestion.py tests/test_public_data_hygiene.py tests/test_routes.py tests/test_migrations.py`，结果 `123 passed`。
- 全量命令：`.venv/bin/pytest -q`，结果通过；`.venv/bin/ruff check .`，结果通过。
- Django 与仓库检查：`.venv/bin/python manage.py check`、`.venv/bin/python manage.py makemigrations --check --dry-run`、Django production `check --deploy`、`git diff --check` 均通过，迁移无漂移。
- 全新临时 SQLite 数据库从 `research.0001` 迁移至 `research.0017` 成功。
- 浏览器检查通过 `/fed/`、固定 news list、reviewed detail、malformed-provenance detail 与 `/fed/hawkish-dovish/`；隐藏 draft/rejected/malformed summary 搜索均为空。
- 390px 视口无水平溢出，移动端抽屉可正常打开。
- REVIEW 状态继续保留：生产前仍需设计并配置定时证据绑定/人工审核闭环，取得显式授权后再执行生产备份、0017 迁移、真实 RSS refresh、部署及上线后复验。
