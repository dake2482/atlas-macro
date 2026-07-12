---
schema_version: 1
id: AI-RESEARCH-006
project_id: AI-RESEARCH
title: 修正经济总览的官方变化率组合
status: DONE
priority: P1
executor: codex
task_id: atlas-economy-overview-20260713
branch: main
worktree: local
dependencies:
- AI-RESEARCH-002
- AI-RESEARCH-003
- AI-RESEARCH-004
updated_at: '2026-07-13T02:23:17+08:00'
next_action: Audit the next highest-impact public dashboard whose metric semantics or source batches still diverge from the clean-room contract.
evidence:
- Production economy still labels the BLS total nonfarm employment level as nonfarm payrolls and publishes
  seasonally adjusted CPI/core CPI index levels instead of the rate metrics expected by a macro overview.
- The economy definition remains inside CORE_PUBLICATION_KEYS, so unrelated Treasury, NY Fed or RSS outcomes can
  control publication even though the intended inputs are GDP, employment, inflation and consumer releases.
- 'The four component pages already publish official, traceable metrics suitable for reuse: BEA-A191RL real GDP
  growth, LNS14000000 unemployment, core-cpi-yoy and BEA-REAL-PCE-MOM.'
- Commit cb1872b replaces the raw BLS economy definition with a contract-v1 snapshot-of-snapshots coordinator,
  exact four-metric selection, component-level licence/freshness/batch gates, latest-successful-source checks,
  same-value lineage refresh, component failure display and queryset-level legacy isolation.
- All 320 deterministic tests pass, including 14 economy-overview tests for exact semantics, mixed frequency,
  normalized MetricSnapshot reconciliation, missing/demo/stale/licence/latest-batch failures, same-value recovery,
  value changes, dual refresh entrypoints, contract routing and safe GET controls.
- Production release cb1872b refreshed all 15 main official datasets successfully, including 1,168 BLS rows and
  1,437 DOL rows, then refreshed five macro-release sources with 18,861 rows and zero failed or partial runs.
- Production economy snapshot 94 uses publication batch 8082bf61-d2a6-405d-b59b-8165aa4be0ea and fingerprint
  120a779edbfc1a7fe8a0229dc52c532669b31e03789b1faddc1e0cac7823578a. It contains exactly four metrics,
  four charts, four component references and no refresh failure.
- Production values are real GDP SAAR 2.10% for 2026Q1, unemployment 4.20% for 2026-06, core CPI YoY +2.9%
  for 2026-05 and real PCE MoM 0.30% for 2026-05. Their latest relevant source batches are respectively
  fe5f7473-2505-43b4-b016-2abf73af6586, f1f31941-7d76-4a7d-a2a0-c9e10306cd84 and
  673d59a9-76b8-4018-8055-75b18f6de450; all are present in the selected component lineage.
- A second identical five-source macro refresh retained the same single DashboardSnapshot id, publication batch
  and fingerprint while updating GDP and PCE component batches plus all four public MetricSnapshot rows in place.
- Public desktop and 390px CDP QA found four metric cards, four/one selected chart containers, no horizontal
  overflow and no page JavaScript errors; scrolling the mobile labor view rendered one ECharts canvas. Default
  economy response transferred 22,269 gzip bytes with 0.38 second TTFB, while all economy child routes and
  sitemap returned HTTP 200.
- The validated pre-release PostgreSQL backup is
  /srv/atlasmacro/backups/pre-cb1872b-20260712T181008Z.dump, size 7,595,515 bytes, SHA-256
  94c864811894f1520c11a98de517843dea29122f6792b818323df0657cda69c6; pg_restore catalog validation succeeded.
- Mina serves cb1872b on HTTP 3080. All six Compose services are running with zero restarts and no OOM; production
  checks only retain the expected HSTS/SSL-redirect warnings for the deliberately non-TLS origin, and host port
  3003 remains an unrelated untouched service.
started_at: '2026-07-13T01:33:17+08:00'
---

# 目标

将经济总览改为由四个已完成官方数据页原子组合的可追溯快照，不再把就业总量或价格指数水平冒充宏观变化率，也不受无关来源失败控制。

## Acceptance criteria

- [x] 总览指标卡和图表数值只展示实际 GDP 季调年化增速、失业率、核心 CPI 同比和实际 PCE 环比；禁止 CES 就业总水平、CPI/核心 CPI 原始指数作为总览指标，公式与输入血缘仍保留官方序列标识以支持复算。
- [x] 每个总览指标完整继承组件快照的来源、许可、有效日、抓取时间、输入批次、公式、质量和 fallback，并记录四个组件快照 ID、publication batch 与 fingerprint。
- [x] 经济总览使用独立四组件协调器；任一被选指标、对应图表或相关来源缺失、stale、error、demo、未授权、未继承最新成功批次或合同不完整时保留上一完整总览并标明具体失败组件，不发布部分组合；子页内未被总览复用的来源或指标不单独使组合失效。
- [x] 官方 BLS/DOL 主刷新以及 BEA/Census/Board/NY Fed 宏观刷新都触发协调；Treasury、NY Fed Markets、Fed RSS 等无关失败不得阻断。
- [x] 同值重发不新增 DashboardSnapshot，但必须刷新组件批次和 MetricSnapshot 血缘；任何组件数值变化才创建新的完整总览快照。
- [x] 指标语义、来源许可、混批、stale/恢复、双入口触发、路由、响应式和生产刷新测试通过。

## Verification plan

- Add deterministic component-snapshot fixtures that prove raw index and payroll-level metrics cannot enter the overview.
- Test missing, stale, revoked, demo and mismatched component snapshots plus same-value recovery and changed-value publication.
- Run Ruff, the complete pytest suite, Django checks, an immutable Mina deployment, database lineage audit and desktop/390px browser verification on port 3080.
