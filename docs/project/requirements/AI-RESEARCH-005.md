---
schema_version: 1
id: AI-RESEARCH-005
project_id: AI-RESEARCH
title: 修正 Fed Funds 政策走廊的同日对齐
status: IN_PROGRESS
priority: P1
executor: codex
task_id: atlas-fed-funds-alignment-20260713
branch: main
worktree: local
dependencies: []
updated_at: '2026-07-13T00:10:00+08:00'
next_action: Audit NY Fed and PRATES effective-date semantics and design the two-source publication coordinator.
evidence:
- Production snapshot 65 subtracts 2026-07-13 IORB 3.65% from 2026-07-09 SOFR 3.53% and publishes
  SOFR-IORB as -12bp while labeling the result with the earlier date.
- The generic derived metric helper independently selects each series latest observation and then uses the
  minimum value date, so weekends, holidays and announced future-effective policy rates can create false spreads.
- NY Fed reference-rate observations already retain the target range, percentile distribution and volume in
  metadata; Federal Reserve PRATES already supplies official IORB, so no paid source is required.
started_at: '2026-07-13T00:10:00+08:00'
---

# 目标

将 EFFR、SOFR、IORB 与联邦基金目标区间严格对齐到最新共同有效日，补齐分位与成交量，并把 Fed Funds 页面从宽泛全局发布门中拆出，消除跨日期政策走廊计算。

## Acceptance criteria

- [ ] EFFR、SOFR、IORB 及所有相互差值只使用最新共同有效日；未来生效或缺少配对日期的观测不得参与当前指标。
- [ ] 目标区间上下限、SOFR/EFFR 分位与成交量直接使用 NY Fed 官方字段，并保留有效日、抓取时间、批次、来源、许可和修订状态。
- [ ] SOFR−EFFR、SOFR−IORB 及相对走廊位置为透明 Atlas 计算，输入日期和批次可复算，不再调用“各取最新”的通用 helper。
- [ ] 页面使用 NY Fed reference-rate 与 Federal Reserve PRATES 的独立双源发布协调器；无关 Treasury、DOL 或 RSS 失败不阻断，任一必需输入失败则保留上版并标 stale。
- [ ] 页面按同单位图表展示政策走廊、市场利率与分布，支持可分享的 1y/3y GET 时间窗口，不混入未来值。
- [ ] 周末、假日、未来生效 IORB、缺共同日、混批、stale 恢复、血缘、路由、响应式及生产刷新测试通过。

## Verification plan

- Add deterministic effective-date intersection tests including the observed 2026-07-09/2026-07-13 production mismatch.
- Test target-range and percentile metadata normalization, two-source publication coordination, stale retention and recovery.
- Run Ruff, the complete pytest suite, Django checks, an immutable Mina deployment, database lineage audit and desktop/390px browser verification on port 3080.
