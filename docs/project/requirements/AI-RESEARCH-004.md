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
updated_at: '2026-07-13T16:05:00+08:00'
next_action: PCE inflation, Treasury/TIPS BEI proxy, and BLS CPI component follow-ups are deployed; remaining inflation gaps are real traded breakeven or 5Y5Y feeds and full release vintage.
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
- '2026-07-13 PCE follow-up: commit 7816d24 extends BEA PIO Section 2 parsing to T20804-M
  DPCERG and DPCCRG, adds PCE and core PCE price-index MoM, YoY and 3M/6M annualized metrics
  to the inflation page, and changes the inflation publication gate from BLS-only to BLS plus
  bea-pio-release. The data catalogue now marks bea-pce-inflation as LIVE.'
- 'Mina release 7816d24 was deployed on port 3080 after backup
  /srv/atlasmacro/backups/pre-7816d2479b62-20260713T065025Z.dump, SHA-256
  be302ebe5ae99ed3f40f27caa37972299945a41f86a0bb3c8ce7b8d54c007ead. Production
  sync_data_requirements moved live from 33 to 34 and needs_source from 15 to 14; refresh_official_data
  completed with BEA PIO success row_count=6,702 and published inflation.'
- 'Production inflation snapshot 133 has five charts: headline CPI, core CPI, final-demand PPI,
  PCE price and core PCE price. Public /economy/inflation/?tab=pce returns 200 and displays
  PCE +4.1% YoY and core PCE +3.4% YoY from U.S. Bureau of Economic Analysis Personal Income and Outlays.'
- '2026-07-13 BEI proxy follow-up: commit 5ff9adf reuses the audited real-rates Treasury
  nominal and TIPS par-curve snapshot on the inflation page, adds a shareable expectations tab,
  publishes market-5y-bei and market-10y-bei metrics with component snapshot lineage, and marks
  inflation-market-expectations LIVE while preserving real traded breakeven and 5Y5Y as separate
  source gaps.'
- 'Mina release 5ff9adf was deployed on port 3080 after backup
  /srv/atlasmacro/backups/pre-5ff9adf0d90c-20260713T070513Z.dump, SHA-256
  68079fb969060fb197ca60467482fefb62e17d760b78b34253e318d6dea9c32b. Production
  sync_data_requirements now reports live=35, needs_source=13, license_review=3 and
  purchase_required=36.'
- 'Production inflation snapshot 136 has six charts including market-breakeven-inflation.
  Public /economy/inflation/?tab=expectations returns 200 and displays Treasury 曲线派生
  盈亏平衡通胀, 5Y BEI 2.28%, 10Y BEI 2.24%, and the explicit not-traded-breakeven label.
  GitHub public repository created at https://github.com/dake2482/atlas-macro and main is
  tracking origin/main.'
- '2026-07-13 BLS component follow-up: commit 335fc99 freezes seasonally adjusted and
  not-seasonally-adjusted pairs for Shelter (SAH1), commodities less food and energy
  commodities (SACL1E), and services less energy services (SASLE). The page publishes
  MoM, YoY, 3M and 6M annualized rates from exact calendar months and explicitly states
  that SASLE still includes Shelter and is not supercore inflation.'
- 'The exact production BLS request returned all 24 requested series and 1,552 rows with
  no missing series. Mina release 335fc99 was deployed after the validated backup
  /srv/atlasmacro/backups/pre-335fc995f580-20260713T075721Z.dump (9,253,455 bytes),
  SHA-256 7344016ec50c2d03d63648bb40121f3a32b93e1ff5592d8ba9302c9e9944c8a2.'
- 'Production inflation snapshot 138 contains nine charts, including three component
  charts and the Treasury BEI proxy. The component tab returns HTTP 200 and displays
  May 2026 Shelter +0.3% MoM/+3.4% YoY, core goods -0.1% MoM/+1.1% YoY, and services
  less energy +0.3% MoM/+3.4% YoY, all bound to BLS batch
  c62e7a25-e503-47f3-81f5-8018aaaa85b3. The catalogue now reports live=36 and
  needs_source=12.'
started_at: '2026-07-12T23:24:28+08:00'
---

# 目标

用 BLS 官方季调与未季调配对价格指数发布可复算的 CPI、核心 CPI 与最终需求 PPI 环比、同比和短期年化动能，不再把指数水平冒充通胀率。

## Acceptance criteria

- [x] CPI、核心 CPI 与最终需求 PPI 的环比只使用季调序列、同比只使用未季调序列，并且只在精确相邻自然月与 t-12 存在时计算，缺月不跨期补算。
- [x] 3M/6M 年化动能使用明确的几何年化公式，保留输入序列、数值日、批次、来源、许可与 preliminary 状态。
- [x] 通胀页按总体、核心与生产者价格分组图表，支持可分享的 1y/3y/5y GET 时间窗口，不展示不兼容单位。
- [x] 通胀页使用独立 BLS 同批发布门；与通胀无关的 Treasury/Fed/DOL 失败不阻断新快照，BLS 必需输入失败则保留上版并标 stale。
- [x] BLS 官方 Shelter、核心商品与不含能源服务的服务 CPI 分项已使用季调/未季调配对序列发布，服务口径明示仍含 Shelter，不冒充“超级核心”。
- [x] 真实交易 breakeven、5Y5Y 和完整修订 vintage 继续保持明确的数据源/采购状态，不用演示数值填充。
- [x] 后续补齐：PCE 与核心 PCE 价格指数使用 BEA PIO Section 2 官方工作簿发布；5Y/10Y 市场预期使用 Treasury/TIPS 官方曲线派生代理发布；剩余未覆盖层只保留真实交易 breakeven、5Y5Y 与完整 vintage。
- [x] 公式、精度、缺月、批次、stale 保留、路由、血缘、响应式和生产刷新验收通过。

## Verification plan

- Add deterministic exact-month ratio and annualization tests, including zero/negative denominator and missing-month failures.
- Run BLS provider, page-specific publication-gate, stale-retention, GET-filter, lineage and route tests.
- Run Ruff, the complete pytest suite, Django checks, production refresh and desktop/390px browser verification on Mina port 3080.
