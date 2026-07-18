---
schema_version: 1
id: AI-RESEARCH-015
project_id: AI-RESEARCH
title: 准备金页 SOFR-13周国库券与 SOFR-IORB 官方日频利差组件
status: REVIEW
priority: P1
executor: codex
task_id: atlas-reserves-rate-spreads-alignment-20260714
branch: main
worktree: local
dependencies:
- AI-RESEARCH-014
updated_at: '2026-07-14T12:07:35+08:00'
next_action: Re-run the 1440/390 browser and console acceptance after the Browser Plugin process-shim compatibility regression is fixed. Production deployment and production data refresh remain separately authorized actions.
evidence:
- >-
  The comparison route is currently unavailable, so the implementation uses the previously captured public-page contract: current SOFR and 3M T-bill values plus 60-day SOFR-minus-T-bill and SOFR-minus-IORB histories.
- The U.S. Treasury Daily Treasury Bill Rates feed identifies the official 13-week bill and publishes both Bank Discount and Coupon Equivalent quotations. Coupon Equivalent is selected because Treasury explicitly defines it as the investment/bond-equivalent yield suitable for yield comparison.
- The exact Treasury XML field is ROUND_B1_YIELD_13WK_2; ROUND_B1_CLOSE_13WK_2 is retained only as source metadata and is never substituted into the displayed spread.
- SOFR remains sourced directly from the New York Fed Markets API and IORB directly from the Federal Reserve PRATES DDP archive; no FRED or comparison-site value is used.
- >-
  Architecture decision: retain reserves v1 as the independent weekly H.4.1/H.8 component, publish reserves-rate-spreads v1 as an independent daily three-source component, and merge only validated component snapshots in the public view with component-level timestamps and stale state.
- The captured comparison page also labels an opaque bank-intermediation status, but does not disclose its threshold or method. Atlas will publish the raw spread and keep the status method as NEEDS_SOURCE rather than inventing a normal/tight classification.
- Implementation now publishes an independent reserves-rate-spreads v1 component, retains the weekly reserves v1 contract, rechecks current SourceLicense rights in the public selector, and propagates retained stale state to presentation copies without mutating stored snapshots.
- Fourteen deterministic rate-spread tests pass. They cover Treasury field drift, exact-date publication, latest-failure retention, date regression, duplicate triggers, same-value recovery, mixed-batch pollution, licence revocation, fewer than 30 common observations, publication-postcondition rollback, legacy weekly compatibility, missing-component state and stale presentation.
- A clean temporary SQLite database completed live official refreshes from Federal Reserve H.4.1/H.8/PRATES, the New York Fed Markets API and U.S. Treasury XML feeds. The weekly reserves contract used the exact 2026-07-01 common date; the daily spread contract used 2026-07-10 and 41 exact common dates in the closed 60-calendar-day window starting 2026-05-12.
- The live daily component published SOFR 3.55%, 13-week Coupon Equivalent 3.80%, IORB 3.65%, SOFR-minus-T-bill -25.00bp and SOFR-minus-IORB -10.00bp from three exact batches, with five normalized metrics, three equal-date charts, zero fallback observations and zero demo snapshots.
- The two Treasury XML raw artifacts retained SHA-256 e05421b6cf9629946f034a292c35f2453a7bb563b1f71f2c9af450e1919abd9c and 81d4c8ed3bc9a766afe9f8fd4b7150de5167fdf7f6939b17e53cc32409759c4. The displayed field was ROUND_B1_YIELD_13WK_2; ROUND_B1_CLOSE_13WK_2 remained lineage-only metadata.
- An HTTP route smoke against the isolated database returned 200 and rendered all five daily values, three chart payloads, source notices and the weekly recent-20 table without a missing-source state.
- The official Browser Plugin 26.707.71524 cannot currently be imported in the trusted Node runtime because the bundle overwrites a non-configurable process facade at browser-client.mjs:33. The 1440/390 visual and console gate remains explicitly unexecuted; HTTP/Django checks are not counted as a browser substitute.
- >-
  Repository gates passed before the final test additions: full Ruff, complete pytest, Django check, migration drift check and git diff whitespace validation. The expanded 14-test slice and targeted Ruff/diff checks also pass; final repository-wide gates are rerun with the next milestone changes.
started_at: '2026-07-14T11:10:45+08:00'
---

# 目标

把准备金页剩余的 `SOFR−3M T-bill` 与 `SOFR−IORB` 从来源缺口升级为可追溯的官方日频组件，同时保留原有 H.4.1/H.8 周度准备金合同的独立失败边界。

# 口径与边界

- “3M T-bill”明确实现为财政部最新发行 13 周国库券的 Coupon Equivalent / Investment Yield，不使用 3M Treasury constant maturity，也不使用 Bank Discount 报价。
- SOFR、13 周 T-bill 与 IORB 只按完全相同的美国市场有效日求交集，不做周末、节假日或缺失日的前值填充。
- 利差单位为基点：`100 × (SOFR% − rate%)`。
- 图表窗口为 `[最新共同有效日 − 59 天, 最新共同有效日]` 的 60 个自然日闭区间；页面必须明确该窗口包含的只是实际共同有效日。
- 周度准备金核心和日频利差组件分别原子发布。任一日频源失败时保留上一版完整利差组件并标记 stale，不重写或降级周度准备金快照。
- 不复制比较站点的 HTML、CSS、文案、私有接口或历史数据库。

# Acceptance criteria

- [x] Treasury provider 严格解析 13 周 Coupon Equivalent，保留 Bank Discount、CUSIP、到期日、feed 更新时间与原始响应 SHA-256。
- [x] 三源协调器只接受 SOFR 与 Treasury 同一刷新周期的最新成功精确批次，以及最新成功 PRATES 精确批次。
- [x] 当前值和 60 自然日历史只使用无回退、许可有效、非未来的共同有效日，并保留逐点 input lineage。
- [x] 直接指标和两项利差均有可复算公式、来源、value date、fetch time、batch、质量、许可与 fallback 状态。
- [x] 日频组件失败、日期回退、重复触发、批次混装、许可撤销、报价口径漂移、样本不足及发布后置条件失败均保留上一完整组件并显示 stale。
- [x] 准备金页面合并两个独立组件，新增资金利差标签页；缺失日频组件时继续显示周度核心并明确显示组件缺失。
- [x] 数据台账把该项改为 LIVE，并继续把严格同口径准备金充裕度方法保留为 NEEDS_SOURCE。
- [x] 原页未披露的“银行中介意愿”阈值方法单独登记为 NEEDS_SOURCE；页面不生成伪精确状态。
- [ ] Ruff、完整 pytest、Django check、真实官方源临时库刷新以及 1440/390 浏览器验收通过。

# Verification plan

- Canonical: `.venv/bin/ruff check .`, `.venv/bin/pytest -q`, `.venv/bin/python manage.py check`.
- Additional: `git diff --check`, migration drift check, clean temporary SQLite live refresh, exact-batch/lineage inspection, desktop/mobile browser and console inspection.
- Public GitHub publication is authorized in the current user turn. Production deployment, production refresh, and migration remain separately authorized actions.
