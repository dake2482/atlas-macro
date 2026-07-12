---
schema_version: 1
id: AI-RESEARCH-004
project_id: AI-RESEARCH
title: 发布官方通胀变化率与短期动能
status: DONE
priority: P1
executor: codex
task_id: atlas-inflation-official-20260712
branch: main
worktree: local
dependencies: []
updated_at: '2026-07-13T00:10:00+08:00'
next_action: Start AI-RESEARCH-005 to align the Fed Funds policy corridor on one common effective date.
evidence:
- Production currently publishes headline CPI, core CPI and final-demand PPI index levels, which are not the
  month-over-month or year-over-year inflation rates expected by the page contract.
- The shared BLS refresh already retains more than five years of monthly official index observations, but
  inflation has no page-specific same-batch gate or exact-month derived-series tests.
- BLS publication semantics require seasonally adjusted CPI/PPI series for month-over-month and short-term
  annualized momentum, and matching not-seasonally-adjusted series for the official 12-month change.
- Production 114d75b publishes 12 BLS-derived percentage metrics and three unit-matched charts from one
  complete 1,168-row BLS batch; the latest reference month is 2026-05 and PPI preliminary status remains visible.
- The production snapshot binds every formula input to BLS batch 7fb24661-237b-4169-9151-21484593771d,
  stores 12 MetricSnapshot rows, and lists PCE, components, expectations and vintage as explicit source gaps.
- A DOL legacy XML failure during the full refresh did not block inflation publication; employment retained its
  previous snapshot and recovered after a separate successful 1,437-row DOL retry.
- Desktop 1440px and mobile 390px Chromium QA rendered three/one selected ECharts canvases with no horizontal
  overflow or application errors; the only console notice is the expected ignored COOP header on raw HTTP.
- Gzip reduced the default inflation response to 39,050 bytes and repeated public TTFB measurements were
  0.44-0.47 seconds. All public route smokes returned HTTP 200 and port 3080 remains the only host listener.
- The validated pre-release PostgreSQL backup is
  `/srv/atlasmacro/backups/pre-114d75b-20260712T155837Z.dump` with SHA-256 sidecar and container pg_restore listing check.
- Portfolio closeout passed on commit 64da0f3 with Ruff, the complete pytest suite, Django checks, strict
  portfolio validation and the explicitly local-only Git delivery boundary verified.
started_at: '2026-07-12T23:24:28+08:00'
---

# 目标

用 BLS 官方季调与未季调配对价格指数发布可复算的 CPI、核心 CPI 与最终需求 PPI 环比、同比和短期年化动能，不再把指数水平冒充通胀率。

## Acceptance criteria

- [x] CPI、核心 CPI 与最终需求 PPI 的环比只使用季调序列、同比只使用未季调序列，并且只在精确相邻自然月与 t-12 存在时计算，缺月不跨期补算。
- [x] 3M/6M 年化动能使用明确的几何年化公式，保留输入序列、数值日、批次、来源、许可与 preliminary 状态。
- [x] 通胀页按总体、核心与生产者价格分组图表，支持可分享的 1y/3y/5y GET 时间窗口，不展示不兼容单位。
- [x] 通胀页使用独立 BLS 同批发布门；与通胀无关的 Treasury/Fed/DOL 失败不阻断新快照，BLS 必需输入失败则保留上版并标 stale。
- [x] 官方序列未覆盖的通胀分项、PCE 或修订 vintage 保持明确的数据源/采购状态，不用演示数值填充。
- [x] 公式、精度、缺月、批次、stale 保留、路由、血缘、响应式和生产刷新验收通过。

## Verification plan

- Add deterministic exact-month ratio and annualization tests, including zero/negative denominator and missing-month failures.
- Run BLS provider, page-specific publication-gate, stale-retention, GET-filter, lineage and route tests.
- Run Ruff, the complete pytest suite, Django checks, production refresh and desktop/390px browser verification on Mina port 3080.
