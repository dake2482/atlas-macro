---
schema_version: 1
id: AI-RESEARCH-007
project_id: AI-RESEARCH
title: 流动性快照原子协调与净流动性同日化
status: IN_PROGRESS
priority: P1
executor: codex
task_id: atlas-liquidity-alignment-20260713
branch: main
worktree: local
dependencies:
- AI-RESEARCH-005
updated_at: '2026-07-13T02:32:47+08:00'
next_action: Replace the latest-per-series liquidity proxy with an exact-batch common-date coordinator for H.4.1, ON RRP, TGA and the validated Fed Funds component.
evidence:
- Production liquidity snapshot 86 publishes net liquidity as 5.990427 USD tn with value_date 2026-07-08,
  but the formula actually combines WALCL from 2026-07-08, TGA from 2026-07-09 and ON RRP from 2026-07-10.
- The latest exact common date is 2026-07-08; its official inputs are WALCL 6,735,609 USD mn, TGA
  749,244 USD mn and ON RRP 3,347 USD mn, yielding 5.983018 USD tn rather than the published mixed-date value.
- The current derived metric stores a comma-joined batch string and formula only; it omits input_value_dates,
  per-input values and full input_lineage, so the public value cannot be independently reproduced from its label.
- Liquidity remains in both the global core gate and H.4.1 publication set. Unrelated BLS/RSS failures can block
  publication, while H.4.1 or PRATES refreshes can republish against older Treasury/NY Fed components without an
  independent page contract.
- The liquidity chart contains only TGA and ON RRP but inherits six unrelated page batches; the transmission-chain
  chart similarly inherits unrelated H.4.1, Treasury and FX-swap batches instead of chart-local lineage.
started_at: '2026-07-13T02:32:47+08:00'
---

# 目标

把流动性总览改为由 H.4.1、NY Fed ON RRP、Treasury TGA 与已验证 Fed Funds 快照独立协调的原子页面；净流动性代理只用最新非未来共同有效日，所有卡片和图表保存可复算的组件血缘。

## Acceptance criteria

- [ ] 净流动性代理只使用 WALCL、ON RRP 与 TGA 的最新非未来共同有效日；不得各取最新后把最早日期冒充组合日期。
- [ ] 净流动性当前值、前值和历史图完整保存每个输入的 value、value_date、as_of、fetched_at、batch、source、license、quality 与 fallback，并明确标记为 Atlas Macro 代理计算而非官方 LPI。
- [ ] 流动性总览使用独立页面协调器和 contract version；H.4.1、ON RRP、TGA 或 Fed Funds 任一必需组件失败、过期、未授权、混批或回退时保留上一完整快照并标明具体组件。
- [ ] 主官方刷新、H.4.1 刷新与 PRATES/Fed Funds 刷新都在组件状态落库后触发协调；BLS、DOL、Fed RSS、拍卖或其他无关数据集失败不得阻断。
- [ ] 页面指标与图表只声明其实际使用的批次和来源；同值重抓不新增 DashboardSnapshot，但必须刷新 MetricSnapshot、图表及组件引用血缘。
- [ ] 同日公式、非未来截止、失败保留、最新批次、许可撤销、同值恢复、双/三入口、路由、响应式和生产刷新测试通过。

## Verification plan

- Build deterministic H.4.1, ON RRP, TGA and Fed Funds fixtures with deliberately different latest dates and one
  exact common date; prove the old mixed-date answer is rejected.
- Test missing/failed/stale/revoked/mismatched components, unrelated source failures, same-value lineage refresh and
  changed common-date values.
- Run Ruff, the complete pytest suite, Django checks, an immutable Mina deployment, a production common-date audit
  and desktop/390px browser verification on port 3080.
