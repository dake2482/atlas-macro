---
schema_version: 1
id: AI-RESEARCH-024
project_id: AI-RESEARCH
title: Treasury 原始 XML 重放、年度批次 append-only 与利率页面严格合同
status: IN_PROGRESS
priority: P1
executor: codex
task_id: atlas-treasury-curve-v2-20260715
branch: main
worktree: local
dependencies:
- AI-RESEARCH-009
- AI-RESEARCH-023
updated_at: '2026-07-15T19:43:41+08:00'
next_action: Run the isolated live 2021-2026 Treasury backfill, verify 12 private artifacts and a second current-year append-only revision, complete route smoke plus 1440/390 browser acceptance, then promote AI-RESEARCH-024 to REVIEW. Draft PR #1 is open; production deployment remains separately authorized.
evidence:
- The live 2026 nominal and real Treasury feeds are Atom XML with 133 entries, explicit feed titles and update timestamps; the official source is public and already licensed for Atlas display, derived display and historical storage.
- Current TreasuryRatesProvider decodes XML to text and only records a URL/hash/size pointer, so ProviderResult has no exact raw bytes and old runs cannot be replayed.
- Current annual persistence updates existing series/date observations in place and transfers their batch_id to the newest run; local successful historic runs therefore retain row_count but can have zero exact-batch observations.
- Current Treasury page publication uses the generic writer and the public route uses the generic selector. Neither independently rechecks raw bytes, run state, observations, MetricSnapshot rows, payload integrity or latest-attempt semantics.
- The every-two-hour generic official job currently fetches current-year Treasury curves. Append-only storage would create excessive duplicate annual batches, so the curve refresh must move to a dedicated once-daily job; six-year history remains an explicit backfill/recovery operation.
- Independent route and Treasury audits agree that this is the highest-impact next milestone because it secures yield-curve, real-rates, rates overview, bonds and the asset overview, and is a prerequisite for any transparent Treasury yield-change realized-volatility proxy.
- Treasury v2 now persists exact XML bytes to one private content-addressed RawArtifact per annual run, replays normalized rows, preserves observation batches append-only and makes exact-input retries idempotent.
- Dedicated append-only publishers and strict selectors now cover `yield-curve`, `real-rates` and the Fed Funds-linked `rates` parent; generic publication, legacy contracts, rogue rows, tampered artifacts/metrics and revoked licences fail closed.
- Bonds, the asset overview and inflation expectations consume only strict Treasury children. Unsupported volatility pages remain number-free, while the volatility coverage ledger marks Treasury only as an input for a later transparent yield-change RV requirement.
- Transition, retained-failure, mixed-child, successful-supersession and one-hour RUNNING timeout behavior now have deterministic tests. Presentation clones hide superseded failure markers without mutating the stored audit marker.
- Full-suite seed isolation normalizes the `internal` and Treasury licence decisions before strict contract tests; the final repository run passed all 863 tests. Ruff, Django check, migration drift and diff checks also passed; the sole warning is the deliberate duplicate-SLOOS-member fixture.
- Independent correction review ended at P0=0 and P1=0. Local product commit `a54f60f99eb7925a634f3820217d195af5c24768` is mirrored as stable-patch-identical public commit `37b8aaecc0f016f1bdfed14e3956aae1cb80aa8d` in draft PR #1 on `dake2482/atlas-macro-platform`.
started_at: '2026-07-15T18:16:46+08:00'
---

# 目标

把 U.S. Treasury 名义与实际 Par Yield 曲线从“可显示但不可从原始响应独立重验”的 v1 链路升级为严格 v2：每个年度响应保留 exact HTTP bytes，每次成功抓取产生不可变 observation 批次，发布物只能由专用 publisher 写入，公开 selector 必须从私有 XML 一路重放到页面组件和 MetricSnapshot。

本项只升级现有利率数据链和消费页面，不发布 Treasury 波动率数字。MOVE、债券价格波动率、期权隐含波动率与 Treasury yield-change realized volatility 仍是不同口径；后者只能在本项完成后另立 requirement。

# 数据输入合同

## Feed identity

- Endpoint: U.S. Treasury `interest-rates/pages/xml`。
- Nominal dataset: `daily_treasury_yield_curve:{year}`，feed title `DailyTreasuryYieldCurveRateData`。
- Real dataset: `daily_treasury_real_yield_curve:{year}`，feed title `DailyTreasuryRealYieldCurveRateData`。
- 支持年度范围不早于 1990，且不得晚于抓取时所在年份。
- v2 首次生产发布需要重新抓取当前年及前五年，共 12 个 feed；旧 URL/hash 指针不能伪造成私有 artifact。

## Exact XML validation

provider、persist 和 selector 共用一个 byte parser，并严格验证：

1. 原始响应非空，根节点为 Atom `feed`，content type 为 XML。
2. feed title、updated time、曲线类型、请求年份和 endpoint identity 精确匹配。
3. `updated`、observation date 不得在未来；所有 observation 必须属于请求年份。
4. entry/content/properties 结构存在，`NEW_DATE` 为 `Edm.DateTime`；所用曲线字段为 `Edm.Double`。
5. 数值必须有限；同一日期/期限不允许重复或冲突。
6. feed 非空，最新有效日必须具备该年度官方已发布的全部必需期限；历史年度尚不存在的期限允许为空，但不可伪造或插值。
7. metadata 保存 endpoint、content type、byte length、SHA-256、feed title、updated time、entry count、row count、series coverage、latest value date、curve 和 requested year。

# 持久化合同

- source、dataset、curve、year、run identity 必须一致。
- 从 `raw_bytes` 重放的标准化 tuple 必须与 ProviderResult records 精确相等。
- 每个成功 run 恰有一个 `private://us-treasury-rates/...` content-addressed RawArtifact；数据库 hash、size、content type 和磁盘 bytes 均一致。
- Observation 以 `batch_id` 作为身份的一部分，使用 append-only 语义；新 run 即使原始 bytes 或值完全相同，也不得修改或删除旧批次。
- 同一个 run 的安全重试幂等；新 run 必须保留自己的完整 exact-batch rows。
- 拒绝年度尾部回退、source release watermark 回退、superseded run、许可失效、重复标准化 identity 与原始/标准化对账失败。
- 所有 raw artifact、run metadata 与 observations 在一个数据库事务中通过后置检查。

# Treasury Curve v2 页面合同

## `/rates/yield-curve/` 与 `/assets/bonds/`

- 只接受 `yield-curve` v2 专用快照。
- Exact metrics: UST 2Y、5Y、10Y、30Y、2s10s、3m10s、5s30s，共 7 项；四个直接收益率指标各自保存相邻有效日变化。
- Exact charts: nominal curve comparison 与 2s10s/3m10s/5s30s history，共 2 张。
- Exact section: 当前名义曲线 13 行，期限集合与顺序固定。

## `/rates/real-rates/`

- 只接受 `real-rates` v2 专用快照。
- Exact metrics: TIPS 5Y、TIPS 10Y、5Y BEI 近似、10Y BEI 近似，共 4 项。
- Exact chart: 实际利率与同期限 nominal-minus-real BEI history，共 1 张。
- Exact section: 当前实际曲线 5 行，期限集合与顺序固定。

BEI 是 Atlas 用同日同期限 Treasury nominal par yield 减 real par yield 的透明近似，不冒充 Federal Reserve 官方 breakeven、zero-coupon inflation swap 或 5Y5Y。

## `/rates/` parent

- `rates` v2 必须是 dedicated composite，只能引用通过严格 selector 的 Treasury nominal/real children 与严格 Fed Funds child。
- parent 自身保存 child snapshot id、publication batch、payload hash、状态和新鲜度；任一必需 child 不可验证时保留上一完整 parent 或显示缺口，不可混装。

# 发布与选择合同

- `TREASURY_CURVE_CONTRACT_VERSION = 2`，独立公式版本固定。
- `yield-curve`、`real-rates` 与 `rates` 加入 independent/append-only 集合；generic publisher 明确拒绝写入。
- 相同 exact run set 重试为 no-op；任一新成功年度 run 即使值相同，也产生新 revision 与新的 exact MetricSnapshot rows。
- payload 嵌入 6/12 个 annual run witness、private artifact witness、exact component sets、公式、licence decisions、publication batch、semantic fingerprint 和 integrity hash。
- selector 从 private bytes 重放并逐层校验 artifact、run metadata、exact Observation batch、页面 metrics/charts/sections、MetricSnapshot、licence、fingerprint/hash。
- selector 状态区分 `current_candidate`、`natural_expiry`、`transition_pending`、`retained_failure`；存在 newer successful input 且尚未发布时，旧版不能继续冒充 current。
- structured `refresh_failure` 是唯一允许添加到既有 revision 的失败标记；必须绑定新 attempt 与严格时间线，不能把自然过期伪装成 ingestion failure。

# 消费面

以下入口必须统一调用 strict selector，不得各自复制弱筛选：

- `/rates/yield-curve/`
- `/rates/real-rates/`
- `/rates/`
- `/assets/bonds/`
- `/assets/` 的债券区
- 通胀页面的 Treasury market-expectations 子组件

volatility coverage ledger 只可把 Treasury 输入状态更新为 `INPUT_READY` 或 `CONTRACT_READY`，并注明后续 requirement 才会计算 Atlas Treasury yield-change RV；不得在本项渲染 MOVE 或 Treasury volatility 数字。

# 调度与运维

- 从每两小时的 generic official job 中移除 current-year nominal/real curve 抓取。
- 新增 once-daily Treasury curve task，在财政部日度数据通常完成更新后的时段抓取当前年 nominal/real 并原子发布。
- `refresh_treasury_curve_data --start-year ... --end-year ...` 仅用于首次回填、年度切换和恢复；不能由高频 beat 自动执行六年回填。
- 不使用 `row_count=0` 或 partial 表示“上游未变化”。每次成功 HTTP 响应均是一个完整 exact run；调度频率负责控制重复量。

# Acceptance criteria

- [x] Treasury provider 返回 exact XML bytes，并通过 feed identity、type、时间、年份、重复、有限值和 coverage 测试。
- [x] 每个成功 annual run 恰有一个私有可重放 RawArtifact，normalized rows 与 exact bytes 完全一致。
- [x] Observation 按 batch append-only；同值新 run 不覆盖旧 run，旧批次仍可独立重验。
- [x] yield-curve、real-rates、rates 使用专用 append-only publisher 和 strict selector；generic writer、v1、demo、fallback 与 rogue snapshot 全部被拒绝。
- [x] selector 对 raw file、artifact、run、Observation、payload、MetricSnapshot、licence 的逐层篡改均 fail closed。
- [x] current、自然过期、刷新中、失败保留、新成功未发布的状态语义有确定性测试。
- [x] yield/real/rates/bonds/assets/inflation 的下游入口只消费 strict snapshot。
- [x] generic 2h 任务不再抓 Treasury curves，daily 专用 task 和显式 backfill 命令有测试。
- [x] volatility 只更新输入覆盖状态，MOVE 等未授权页面继续零数字。
- [x] Ruff、完整 pytest、Django check、migration drift、diff 与 secret gate 通过。
- [ ] 隔离临时库重新抓取 2021–2026 共 12 个官方 feed，验证 12 个 private artifacts、exact-batch observations、v2 页面与第二次 same-value/current-year append-only revision，并完成 1440/390 浏览器验收。

# Verification plan

- Canonical: `.venv/bin/ruff check .`, `.venv/bin/pytest -q`, `.venv/bin/python manage.py check`。
- Additional: `git diff --check`、`.venv/bin/python manage.py makemigrations --check --dry-run`、provider/persist/coordinator/selector tamper matrix、isolated 12-feed live backfill、same-value second current-year refresh、route smoke、1440/390 browser/console。
