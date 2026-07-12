---
schema_version: 1
id: AI-RESEARCH-004
project_id: AI-RESEARCH
title: 发布官方通胀变化率与短期动能
status: IN_PROGRESS
priority: P1
executor: codex
task_id: atlas-inflation-official-20260712
branch: main
worktree: local
dependencies: []
updated_at: '2026-07-12T23:58:00+08:00'
next_action: Implement six-series BLS inflation derivations and the independent same-batch publication gate.
evidence:
- Production currently publishes headline CPI, core CPI and final-demand PPI index levels, which are not the
  month-over-month or year-over-year inflation rates expected by the page contract.
- The shared BLS refresh already retains more than five years of monthly official index observations, but
  inflation has no page-specific same-batch gate or exact-month derived-series tests.
- BLS publication semantics require seasonally adjusted CPI/PPI series for month-over-month and short-term
  annualized momentum, and matching not-seasonally-adjusted series for the official 12-month change.
started_at: '2026-07-12T23:24:28+08:00'
---

# 目标

用 BLS 官方季调与未季调配对价格指数发布可复算的 CPI、核心 CPI 与最终需求 PPI 环比、同比和短期年化动能，不再把指数水平冒充通胀率。

## Acceptance criteria

- [ ] CPI、核心 CPI 与最终需求 PPI 的环比只使用季调序列、同比只使用未季调序列，并且只在精确相邻自然月与 t-12 存在时计算，缺月不跨期补算。
- [ ] 3M/6M 年化动能使用明确的几何年化公式，保留输入序列、数值日、批次、来源、许可与 preliminary 状态。
- [ ] 通胀页按总体、核心与生产者价格分组图表，支持可分享的 1y/3y/5y GET 时间窗口，不展示不兼容单位。
- [ ] 通胀页使用独立 BLS 同批发布门；与通胀无关的 Treasury/Fed/DOL 失败不阻断新快照，BLS 必需输入失败则保留上版并标 stale。
- [ ] 官方序列未覆盖的通胀分项、PCE 或修订 vintage 保持明确的数据源/采购状态，不用演示数值填充。
- [ ] 公式、精度、缺月、批次、stale 保留、路由、血缘、响应式和生产刷新验收通过。

## Verification plan

- Add deterministic exact-month ratio and annualization tests, including zero/negative denominator and missing-month failures.
- Run BLS provider, page-specific publication-gate, stale-retention, GET-filter, lineage and route tests.
- Run Ruff, the complete pytest suite, Django checks, production refresh and desktop/390px browser verification on Mina port 3080.
