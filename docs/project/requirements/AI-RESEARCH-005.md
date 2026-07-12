---
schema_version: 1
id: AI-RESEARCH-005
project_id: AI-RESEARCH
title: 修正 Fed Funds 政策走廊的同日对齐
status: DONE
priority: P1
executor: codex
task_id: atlas-fed-funds-alignment-20260713
branch: main
worktree: local
dependencies: []
updated_at: '2026-07-13T01:28:35+08:00'
next_action: Start AI-RESEARCH-006 to replace raw index and employment levels on the economy overview with gated official rate metrics.
evidence:
- Production snapshot 65 subtracts 2026-07-13 IORB 3.65% from 2026-07-09 SOFR 3.53% and publishes
  SOFR-IORB as -12bp while labeling the result with the earlier date.
- The generic derived metric helper independently selects each series latest observation and then uses the
  minimum value date, so weekends, holidays and announced future-effective policy rates can create false spreads.
- NY Fed reference-rate observations already retain the target range, percentile distribution and volume in
  metadata; Federal Reserve PRATES already supplies official IORB, so no paid source is required.
- Commit f334af0 deploys an independent three-dataset coordinator, New York calendar cutoff, same-cycle NY Fed
  gate, three-year coverage check, effective-date regression guard, stale retention and same-value lineage refresh.
- Production release f334af0 publishes 13 metrics and three unit-matched charts from 796 common dates. Snapshot
  91 and all 13 MetricSnapshot rows use 2026-07-09; EFFR/SOFR/IORB are 3.62%/3.53%/3.65%, with transparent
  -9bp, -12bp and -3bp pairwise spreads and a 48% EFFR corridor position.
- The production snapshot binds NY Fed batches 2522a286-63ba-4515-b774-2d697996a1ae and
  c7a9a3ac-8446-4c6d-931e-399e966687a4 to PRATES batch dfcce0c6-c7fe-4b1a-8756-7adf42ea2e4e;
  the NY pair shares refresh cycle fe46db05-248e-4f4f-9c8d-ef560f87ff2d and no refresh failure remains.
- A first production refresh isolated a transient DOL XML failure while Fed Funds still published; the retry
  stored all 1,437 DOL rows, restored employment to estimated and left no stale dashboard keys.
- Compact series-batch chart lineage reduces the complete 796-day dashboard JSON to 396,136 bytes and 21,625
  gzip bytes. Public default/3y responses transferred 14,790/12,408 bytes with 0.44/0.37 second TTFB.
- Desktop 1280px and mobile 390px browser QA rendered three/one selected ECharts canvases, 13 metric cards,
  the New York Fed notice and synchronized source catalog with no horizontal overflow or console errors.
- The validated pre-release PostgreSQL backup is
  `/srv/atlasmacro/backups/pre-f334af0-20260712T171531Z.dump`; SHA-256 is
  6e3aecfcd2b24bc63595e8f6a51c41dfc3a0dbc16414a560b01e4026683b28a1 and `pg_restore -l` succeeded.
- Mina serves release f334af0 through the existing HTTP 3080 origin; all six Compose services run with zero
  restarts and no OOM. Production deploy checks only retain the two expected HSTS/SSL-redirect warnings for
  the deliberately non-TLS origin.
started_at: '2026-07-13T00:10:00+08:00'
---

# 目标

将 EFFR、SOFR、IORB 与联邦基金目标区间严格对齐到最新共同有效日，补齐分位与成交量，并把 Fed Funds 页面从宽泛全局发布门中拆出，消除跨日期政策走廊计算。

## Acceptance criteria

- [x] EFFR、SOFR、IORB 及所有相互差值只使用最新共同有效日；未来生效或缺少配对日期的观测不得参与当前指标。
- [x] 目标区间上下限、SOFR/EFFR 分位与成交量直接使用 NY Fed 官方字段，并保留有效日、抓取时间、批次、来源、许可和修订状态。
- [x] SOFR−EFFR、SOFR−IORB、EFFR−IORB 及相对走廊位置为透明 Atlas 计算，输入日期和批次可复算，不再调用“各取最新”的通用 helper。
- [x] 页面使用 NY Fed reference-rate 与 Federal Reserve PRATES 的独立双源发布协调器；无关 Treasury、DOL 或 RSS 失败不阻断，任一必需输入失败则保留上版并标 stale。
- [x] 页面按同单位图表展示政策走廊、市场利率与分布，支持可分享的 1y/3y GET 时间窗口，不混入未来值。
- [x] 周末、假日、未来生效 IORB、缺共同日、混批、stale 恢复、血缘、路由、响应式及生产刷新测试通过。

## Verification plan

- Add deterministic effective-date intersection tests including the observed 2026-07-09/2026-07-13 production mismatch.
- Test target-range and percentile metadata normalization, two-source publication coordination, stale retention and recovery.
- Run Ruff, the complete pytest suite, Django checks, an immutable Mina deployment, database lineage audit and desktop/390px browser verification on port 3080.
