---
schema_version: 1
id: AI-RESEARCH-002
project_id: AI-RESEARCH
title: 发布可追溯的 GDP 修订轨迹
status: DONE
priority: P1
executor: codex
task_id: atlas-gdp-vintage-20260712
branch: main
worktree: local
dependencies: []
updated_at: '2026-07-12T22:19:38+08:00'
next_action: Start AI-RESEARCH-003 to correct the employment page with BLS and DOL official data.
evidence:
- The official GDP/GDI Vintage History workbook is already downloaded and fingerprinted by the production
  macro refresh.
- The existing parser retains only the first estimate row for each quarter, so later rows cannot be queried
  independently.
- Production 0850cf2 stores 3,953 BEA vintage observations across 1,052 release rounds, publishes two
  GDP charts plus an eight-quarter revision table, and passed desktop/390px browser QA on port 3080.
- portfolio closeout AI-RESEARCH passed on commit 9e9179e with Ruff, the complete pytest suite, Django
  checks, strict portfolio validation, and the local-only Git boundary verified.
started_at: '2026-07-12T21:43:47+08:00'
---

# 目标

将 BEA GDP/GDI Vintage History 工作簿中的 Advance、Second、Third、Revised 等每轮估算作为独立、可查询且有完整血缘的数据保存，并在 GDP 页面展示修订路径。

## Acceptance criteria

- [x] 独立 vintage 数据模型保存序列、观察期、发布日期、估算轮次、数值、抓取批次、来源、许可、质量与 fallback 状态。
- [x] BEA 解析器保留工作簿中的全部有效轮次，同时现行 GDP 指标继续只发布每季度最新轮次。
- [x] GDP 页面展示最新季度轮次图和最近季度修订表，并保留组件级来源、截至时间与更新时间。
- [x] `bea-gdp-vintage-trail` 数据需求状态仅在真实数据、页面和测试闭环后变更为 `live`。
- [x] 上游失败或不完整时保留上一版完整快照，不发布半成品轨迹。
- [x] 规范验证、生产迁移、真实刷新、3080 路由与桌面/移动浏览器验收通过。

## Verification plan

- Run parser, persistence, uniqueness, lineage, publication, route, stale/failure and migration tests.
- Run Ruff, the complete pytest suite and Django system checks.
- Refresh official macro data in the immutable Mina release and verify database counts, source lineage, page content and chart initialization.
