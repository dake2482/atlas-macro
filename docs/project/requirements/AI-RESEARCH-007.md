---
schema_version: 1
id: AI-RESEARCH-007
project_id: AI-RESEARCH
title: 流动性快照原子协调与净流动性同日化
status: DONE
priority: P1
executor: codex
task_id: atlas-liquidity-alignment-20260713
branch: main
worktree: local
dependencies:
- AI-RESEARCH-005
updated_at: '2026-07-13T03:24:00+08:00'
next_action: Define the next reviewed requirement to replace the lagging Census retail workbook tail with the current official release and full historical series.
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
- Commit e35d4dd removes liquidity from the generic core and H.4.1 publication sets, adds a contract-v1 coordinator
  keyed by exact source and dataset, aligns WALCL, reserve balances, ON RRP and TGA to one non-future common date,
  inherits four normalized Fed Funds metrics, and rejects fallback, stale, mixed-cycle, unlicensed or tampered lineage.
- All 332 deterministic tests pass. The 12 liquidity-overview tests cover the production mixed-date bait value,
  future-date exclusion, current and previous input lineage, chart-local batches, failed component retention,
  same-value recovery, changed values, licence revocation, legacy isolation, all three refresh entrypoints,
  mismatched cycles, fallback on the actual common date and tampered Fed child lineage.
- Mina release e35d4dd refreshed H.4.1 successfully with 7,380 rows. The first main refresh demonstrated that an
  unrelated DOL failure does not stale liquidity; a retry completed all 15 datasets, including 1,168 BLS and 1,437
  DOL rows, and cleared the temporary employment and economy failure states without changing liquidity content.
- Production liquidity snapshot 97 is the only contract-v1 row. It retains publication batch
  c7bd6d64-c52b-4a4c-bac7-41ffaf2a012f and fingerprint
  3f367fa4278853a1ed5ca6f5b57b4f3b70260f36c3d146aeb8e8a3d078705ad3 after repeated same-value refreshes,
  while its component batches and normalized MetricSnapshot lineage were updated in place and refresh_failure is absent.
- The production common date is 2026-07-08; WALCL 6,735,609, ON RRP 3,347 and TGA 749,244 USD millions produce
  exactly 5.983018 USD trillion. The old mixed-date 5.990427 value is absent. The 21-point chart ends on the same
  date and declares only the H.4.1, ON RRP and TGA batches plus their four actual sources including internal derivation.
- Sitemap now has 266 canonical locations under the production origin and none omit the origin's port. Public home,
  liquidity, all checked liquidity children, Fed Funds, economy, robots and sitemap routes return HTTP 200;
  liquidity TTFB was 0.026 seconds and its response size was 135,496 bytes in the final local-origin smoke.
- Desktop 1280px and mobile 390px CDP checks each found nine cards, one chart container, no horizontal overflow,
  the exact 5.983018 value and proxy disclaimer, no old mixed value, and one ECharts canvas after scrolling. The only
  browser warning is the expected COOP warning for the deliberately bare-HTTP origin, not a page JavaScript failure.
- The validated pre-release PostgreSQL backup is /srv/atlasmacro/backups/20260712T191302Z.dump, size 7,696,693
  bytes, SHA-256 3119a323e8cd91e386717cfb95fe99575247ba9557228102912788e83d02808b; pg_restore catalog validation succeeded.
- Mina serves e35d4dd on HTTP 3080. Web and worker are healthy; all six Compose services are running with zero
  restarts and no OOM, recent web/worker logs contain no traceback, and unrelated host listener 3003 remains untouched.
started_at: '2026-07-13T02:32:47+08:00'
---

# 目标

把流动性总览改为由 H.4.1、NY Fed ON RRP、Treasury TGA 与已验证 Fed Funds 快照独立协调的原子页面；净流动性代理只用最新非未来共同有效日，所有卡片和图表保存可复算的组件血缘。

## Acceptance criteria

- [x] 净流动性代理只使用 WALCL、ON RRP 与 TGA 的最新非未来共同有效日；不得各取最新后把最早日期冒充组合日期。
- [x] 净流动性当前值、前值和历史图完整保存每个输入的 value、value_date、as_of、fetched_at、batch、source、license、quality 与 fallback，并明确标记为 Atlas Macro 代理计算而非官方 LPI。
- [x] 流动性总览使用独立页面协调器和 contract version；H.4.1、ON RRP、TGA 或 Fed Funds 任一必需组件失败、过期、未授权、混批或回退时保留上一完整快照并标明具体组件。
- [x] 主官方刷新、H.4.1 刷新与 PRATES/Fed Funds 刷新都在组件状态落库后触发协调；BLS、DOL、Fed RSS、拍卖或其他无关数据集失败不得阻断。
- [x] 页面指标与图表只声明其实际使用的批次和来源；同值重抓不新增 DashboardSnapshot，但必须刷新 MetricSnapshot、图表及组件引用血缘。
- [x] 同日公式、非未来截止、失败保留、最新批次、许可撤销、同值恢复、双/三入口、路由、响应式和生产刷新测试通过。

## Verification plan

- Build deterministic H.4.1, ON RRP, TGA and Fed Funds fixtures with deliberately different latest dates and one
  exact common date; prove the old mixed-date answer is rejected.
- Test missing/failed/stale/revoked/mismatched components, unrelated source failures, same-value lineage refresh and
  changed common-date values.
- Run Ruff, the complete pytest suite, Django checks, an immutable Mina deployment, a production common-date audit
  and desktop/390px browser verification on port 3080.
