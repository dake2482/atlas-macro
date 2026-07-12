---
schema_version: 1
id: AI-RESEARCH-006
project_id: AI-RESEARCH
title: 修正经济总览的官方变化率组合
status: IN_PROGRESS
priority: P1
executor: codex
task_id: atlas-economy-overview-20260713
branch: main
worktree: local
dependencies:
- AI-RESEARCH-002
- AI-RESEARCH-003
- AI-RESEARCH-004
updated_at: '2026-07-13T01:33:17+08:00'
next_action: Build a page-specific economy coordinator from the latest complete GDP, employment, inflation and consumer snapshots.
evidence:
- Production economy still labels the BLS total nonfarm employment level as nonfarm payrolls and publishes
  seasonally adjusted CPI/core CPI index levels instead of the rate metrics expected by a macro overview.
- The economy definition remains inside CORE_PUBLICATION_KEYS, so unrelated Treasury, NY Fed or RSS outcomes can
  control publication even though the intended inputs are GDP, employment, inflation and consumer releases.
- 'The four component pages already publish official, traceable metrics suitable for reuse: BEA-A191RL real GDP
  growth, LNS14000000 unemployment, core-cpi-yoy and BEA-REAL-PCE-MOM.'
started_at: '2026-07-13T01:33:17+08:00'
---

# 目标

将经济总览改为由四个已完成官方数据页原子组合的可追溯快照，不再把就业总量或价格指数水平冒充宏观变化率，也不受无关来源失败控制。

## Acceptance criteria

- [ ] 总览只展示实际 GDP 季调年化增速、失业率、核心 CPI 同比和实际 PCE 环比；禁止 CES 就业总水平、CPI/核心 CPI 原始指数再次进入总览。
- [ ] 每个总览指标完整继承组件快照的来源、许可、有效日、抓取时间、输入批次、公式、质量和 fallback，并记录四个组件快照 ID、publication batch 与 fingerprint。
- [ ] 经济总览使用独立四组件协调器；任一被选指标、对应图表或相关来源缺失、stale、error、demo、未授权、未继承最新成功批次或合同不完整时保留上一完整总览并标明具体失败组件，不发布部分组合；子页内未被总览复用的来源或指标不单独使组合失效。
- [ ] 官方 BLS/DOL 主刷新以及 BEA/Census/Board/NY Fed 宏观刷新都触发协调；Treasury、NY Fed Markets、Fed RSS 等无关失败不得阻断。
- [ ] 同值重发不新增 DashboardSnapshot，但必须刷新组件批次和 MetricSnapshot 血缘；任何组件数值变化才创建新的完整总览快照。
- [ ] 指标语义、来源许可、混批、stale/恢复、双入口触发、路由、响应式和生产刷新测试通过。

## Verification plan

- Add deterministic component-snapshot fixtures that prove raw index and payroll-level metrics cannot enter the overview.
- Test missing, stale, revoked, demo and mismatched component snapshots plus same-value recovery and changed-value publication.
- Run Ruff, the complete pytest suite, Django checks, an immutable Mina deployment, database lineage audit and desktop/390px browser verification on port 3080.
