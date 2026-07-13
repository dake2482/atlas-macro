---
schema_version: 1
id: AI-RESEARCH-013
project_id: AI-RESEARCH
title: Treasury 拍卖与发行结算日历原子公开合同
status: REVIEW
priority: P1
executor: codex
task_id: atlas-treasury-auction-calendar-20260713
branch: main
worktree: local
dependencies:
- AI-RESEARCH-008
updated_at: '2026-07-13T19:43:00+08:00'
next_action: After future explicit deployment authorization, back up production, run one complete same-cycle official Treasury/NY Fed refresh, deploy, then repeat post-deploy route and browser verification.
evidence:
- FiscalDataProvider fetches explicit auction_date [ET today-90d, ET today+14d) and issue_date [ET today, ET today+14d) windows with fields, sort and page-size contracts. Hyphenated meta counts, official empty zero-page windows, rejected rows and single-page coverage are fail-closed.
- Duplicate CUSIP and auction_date rows collapse only when non-empty values do not conflict; a more complete complementary result wins. Conflicting non-empty values fail the whole provider result.
- One ProviderResult fetched_at and one run batch are used for every stored row. A complete bounded refresh reconciles removed or rescheduled rows in the covered union so stale future records cannot remain as ghost calendar entries.
- Auctions v1 publishes future formal auctions, future issue/settlement rows and recent 90-day results from one current exact batch. Same-day completed results do not remain in the formal table, while completed auctions with a future issue date stay visible in the settlement table.
- Seven- and fourteen-day aggregates use half-open ET windows. Zero is published only when both official slices prove complete. offering_amount is always labelled gross announced face amount, never actual cash, net financing, a TGA forecast or a net-liquidity forecast.
- RRP/TGA v1 requires exact current ON RRP, TGA and auction batches from one refresh cycle. It preserves exact-batch official balance history and adds the same auction batch issue calendar without combining different effective dates into a forecast net drain.
- Every metric, chart point and table row payload retains value/event date, fetch time, source, licence, quality, batch and explicit no-fallback state. The UI exposes metric/table lineage and each chart's aggregate source, batch, licence and fallback state; point-level lineage remains in the SSR chart payload. Derived totals retain reproducible input_lineage and use the internal calculation source.
- Both page families are removed from CORE_PUBLICATION_KEYS. Only their source-locked coordinators can publish v1; failed, partial, mixed-cycle, future-fetched, unlicensed or invalid attempts retain the previous complete snapshot as stale. An old replay is a no-op and same-value recovery updates lineage without duplicating the snapshot.
- The page registry, data catalog and UI remove the former 21-day and net-drain claims, expose v1 contracts and distinguish LIVE gross settlement calendar data from NEEDS_SOURCE future net financing, TGA cash flow and net-liquidity impact.
- A read-only live API check on 2026-07-13 returned 111 complete auction-window rows and 9 complete issue-window rows on one page each using the exact new fields and filters. It was not persisted and no production refresh or deployment was performed.
- Current exact TreasuryAuction rows use the existing unique CUSIP and auction_date schema, so a later refresh replaces the normalized current row. Published snapshots embed their component lineage, but durable historical row-level auction vintages would require a future additive model migration.
- An independent read-only final review found no P0 or P1 findings. Status remains REVIEW/YELLOW because production refresh and deployment still require separate explicit authorization.
- Final local gates passed: full pytest 509 tests, targeted pytest 140 tests, Ruff, Django system check, migration-drift check, production deployment check and `git diff --check`.
- Local browser acceptance at 1440px and 390px passed for `/rates/auctions/` and `/liquidity/rrp-tga/`: neither route has horizontal overflow, long batch UUID and licence text remain readable after the metric-card fix, the mobile navigation drawer works, and the console has no warnings or errors.
started_at: '2026-07-13T18:35:00+08:00'
---

# 目标

以 Treasury FiscalData 官方拍卖数据构建可复核的正式拍卖、发行/结算与近期结果页面，并把同批发行/结算公告总面值安全加入 RRP/TGA 页面。所有公开值必须来自当前完整窗口或明确保留的上一完整快照，且不得把公告发行额表述为实际财政现金流或未来净流动性。

## 边界

- `record_date` 是官方数据发布日期语义，不替代事件日期、`as_of` 或实际 `fetched_at`。
- 正式拍卖与发行/结算窗口均使用 America/New_York 日期和半开区间；凌晨、周末或上游未形成当前 ET 日完整批次时保留 stale，不从旧成功批次静默重建“新”页面。
- Bid-to-Cover 和 high yield 是官方拍卖结果；真实 when-issued yield/Tail 仍需授权市场数据，公告总面值不是替代品。
- 不执行交易，不预测税收、支出、最终结算、TGA 方向、净融资或资金来源。
- 本地实现不授权生产刷新、数据库变更、部署或发布。

## Acceptance criteria

- [x] 双窗口 provider 明确字段、边界、排序、分页与 meta 完整性；空窗、截断、坏行和冲突均有确定性测试。
- [x] 存储统一 fetched_at/batch，完整窗口对账撤销或改期记录；来源许可使用官方 Web API Terms、归因和非背书声明。
- [x] Auctions v1 的五个指标、三张表和发行日图表严格来自一个当前完整批次，日期、金额、零值和同日结果规则有后置条件。
- [x] RRP/TGA v1 只接受 ON RRP、TGA 和 auctions 的同一刷新周期精确批次，并保留直接指标、历史、发行总面值与组件血缘。
- [x] generic publisher 无法绕过两个独立协调器；失败保留、old replay、same-value recovery、许可撤销和 route HTML 有测试。
- [x] 页面和数据目录不再声称未来 14/21 天净抽水，并明确列出实际净融资、TGA 现金流和净流动性影响的数据缺口。

## Verification plan

- Canonical local commands: `.venv/bin/ruff check .`, `.venv/bin/pytest -q`, `.venv/bin/python manage.py check`.
- Additional gates: migration drift, production Django check, `git diff --check`, route HTML and 1440/390 browser inspection.
- Production requires a fresh complete same-cycle official run and post-refresh checks for exact component batches, stale/failure visibility, required notices and no demo/fallback data.
