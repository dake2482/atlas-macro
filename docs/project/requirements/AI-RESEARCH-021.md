---
schema_version: 1
id: AI-RESEARCH-021
project_id: AI-RESEARCH
title: 联储 H.10 外汇参考序列严格公开合同
status: REVIEW
priority: P1
executor: codex
task_id: atlas-assets-fx-h10-alignment-20260715
branch: main
worktree: local
dependencies:
- AI-RESEARCH-019
updated_at: '2026-07-15T16:50:22+08:00'
next_action: AI-RESEARCH-021 product changes are included in local commit `88508bc` and public snapshot commit `d67908a`; continue AI-RESEARCH-022 live and browser acceptance. Production deployment remains separately authorized.
evidence:
- Current live truth returns HTTP 200 at `/assets/fx/`, but snapshot 111 is unversioned, stale, dated 2026-07-02 and contains only four metrics with no versioned charts or sections.
- The current registry still embeds prototype DXY, EUR/USD, USD/JPY and USD/CNH values and describes offshore funding pressure even though no ICE DXY, CNH, forward, NDF or cross-currency-basis source is licensed.
- The latest local Federal Reserve H.10 run is successful with 37,303 normalized observations and one immutable private ZIP artifact, so the immediate gap is publication integrity rather than source availability.
- AI-RESEARCH-019 already validates H.10 archive/member hashes, exact observations, quote conventions, release freshness and four required Board series. Assets FX must share that acquisition truth without depending on or copying the global-dollar parent snapshot.
- The proposed v1 contract publishes four official reference levels, two transparent historical views and three rendered source/method/gap sections. Commercial executable FX and derivatives stay explicitly PURCHASE_REQUIRED.
- The dedicated implementation passed 15 assets-fx contract tests and 198 adjacent H.10, global-dollar, refresh, transmission and route tests; the focused final Sol review reported P0=0, P1=0 and P2=0.
- A clean temporary SQLite database fetched the live H.10 archive in 23.68 seconds, stored 37,323 exact observations and one 2,072,667-byte private artifact, published one strict v1 snapshot with four MetricSnapshots, and returned HTTP 200 for both `/assets/fx/` and `/assets/`.
- Full canonical validation passed 790 tests, Ruff, Django system checks, migration drift and `git diff --check`.
- >-
  Browser Plugin 26.707.72221 completed the deferred visual and interaction gate against the isolated live H.10 snapshot: 1440x900 and 390x844 had no horizontal overflow, rendered four metric cards and three tables, Major FX GET navigation and chart selection worked, the mobile drawer and theme toggle worked, and browser console errors were empty.
- A final presentation-only fix now rounds the one-observation percentage changes to signed two-decimal strings without altering the persisted exact numeric `change` or the assets-fx payload hash contract; 15 focused tests, Ruff and `git diff --check` passed, and the browser confirmed the raw long float is no longer visible.
started_at: '2026-07-15T10:30:14+08:00'
---

# 目标

把 `/assets/fx/` 从无版本、弱校验的 generic H.10 快照升级为独立、可复算、失败可见的 `assets-fx v1` 公开合同。

页面只展示 Federal Reserve H.10 的 Nominal Broad Dollar Index 和三条日频参考汇率，以及 Atlas Macro 对同一精确批次做的透明变化与重基准计算。H.10 Broad Dollar 不是 ICE DXY，H.10 参考汇率不是可执行即期、CNH、远期/NDF 或 cross-currency basis。页面不生成离岸美元压力分数、交易信号或行动建议。

# v1 输入合同

唯一必需输入是当前最新成功的 `federal-reserve / h10` exact run。必须复用中性的 H.10 严格验证器，而不是从 `global-dollar` 父快照复制 JSON。

必需 Board series：

- `JRXWTFB_N.B`：Nominal Broad Dollar Index，January 2006 = 100。
- `RXI$US_N.B.EU`：U.S. dollars per euro。
- `RXI_N.B.CH`：Chinese yuan per U.S. dollar。
- `RXI_N.B.JA`：Japanese yen per U.S. dollar。

必须同时验证：

- latest attempt 为 SUCCESS、非空、未 supersede，source/dataset 精确匹配。
- 真实 H.10 ZIP private artifact、archive SHA-256、字节数、唯一 `H10_data.xml` member 与 member SHA-256。
- Prepared/fetched/value-date 非未来、不回退，周度发布时效逻辑通过。
- 四个 series 的序列唯一性、报价方向、A/ND 状态、exact Observation batch 和当前 public/derived/storage licence。
- H.10 Observation 按 batch 追加保存；新 run 不得覆盖旧 batch 的同日 observation，确保 retained snapshot 能重验其 embedded batch。
- 不允许 demo、fallback、PARTIAL、非有限数、silent skip、未知序列或伪造 artifact pointer。

# 指标、图表与表格

## Exact metrics

精确四项：

1. `h10-broad-dollar`
2. `h10-eurusd`
3. `h10-usdcny`
4. `h10-usdjpy`

每项保存最新有效官方 level，以及相对同序列上一有效观察的变化：

`change_pct = 100 × (V_t / V_previous_valid − 1)`

主 level 为 official direct/fresh；对应 `MetricSnapshot.source/quality_status` 仅描述主 level。change 为 Atlas transparent derived/estimated，保存在同一指标的 `change` 字段，并在 metadata 精确保存 `change_formula`、`change_quality_status=estimated`、`change_calculation_owner=Atlas Macro`、前值/当前值及其日期和 lineage；`source_keys` 同时包含 `federal-reserve` 与 `internal`。每项单独保存 `value_date/as_of/fetched_at/fresh_until`、报价方向、当前与前值日期、run/batch/artifact lineage。不强迫四条序列的最新日期完全一致；父快照 `as_of = min(metric value_dates)`。

## Exact charts

1. `fx-broad-dollar-history`：最近 260 个有效 Broad Dollar 观察，不插值、不前值填充。
2. `fx-major-reference-rates-usd-strength-rebased`：EUR/USD、USD/CNY、USD/JPY 最近 120 个共同有效日期，共同起点重基准为 100；EUR leg 使用 `1 / EURUSD` 统一为美元走强方向。

每个图点都继承精确 observation、batch、artifact、许可、质量与 fallback 字段。
v1 发布要求 exact 260/120 个图点以及 recent 表 exact 20 个共同日期；历史不足时 fail closed，不缩短、不填充。`period=3y` 是展示上限而非完整三年历史承诺，仍只展示 v1 已发布的 260/120 点，并在图表方法说明中明确 available window。

## Exact sections

1. `recent-h10-reference-observations`：最近 20 个共同有效日期，列出 Broad Dollar、EUR/USD、USD/CNY、USD/JPY 和行级血缘。
2. `source-freshness-methodology`：source/dataset/run/batch、Prepared、fetched、四序列最新日期、fresh-until、ZIP/member hash、行数、许可与 fallback。
3. `licensed-fx-market-gaps`：精确列出 ICE DXY、可执行 spot、CNH、forward/NDF、cross-currency basis 和 order-book/dealer 微观数据，全部使用 `PURCHASE_REQUIRED` 或 `LICENSE_REVIEW`，不填伪数值。

三张表必须实际渲染 `cells_list`，不得把内部字段名泄漏到页面文本。

# 发布与选择合同

新增：

- `ASSETS_FX_CONTRACT_VERSION = 1`
- `ASSETS_FX_FORMULA_VERSION = "federal-reserve-h10-reference-v1"`
- dedicated coordinator/publisher/selector
- registry `snapshot_contract_version = 1`

`assets-fx` 从 `H10_PUBLICATION_KEYS` 和 generic dashboard definitions 移除，加入独立发布集合。generic publisher 在显式 key、`keys=None` 和内部 core 调用中都必须硬拒绝写入该 key。

payload 至少包含：

- exact metric/chart/section sets、contract/formula version、formula map、semantic boundary。
- input run、component batch/date、private ZIP/member artifact refs、source keys、licence decisions、fresh-until 和 publication batch。
- semantic fingerprint 与 exact payload integrity hash；顶层 `refresh_failure` 不进 exact hash，嵌套血缘不得递归排除。

发布批次只包含四条 `assets-fx-{metric_key}` MetricSnapshot，精确匹配 label/value/display/change/unit/source/dates/quality/licence/fallback/formula/input lineage、semantic fingerprint 和 payload hash。

旧无版本快照保留审计但永不进公开选择，不允许原地升级。`/assets/` 总览中的 FX 分组只能投影该严格快照，不得再查询裸 `Instrument/Observation`。

# 失败、并发与时效

- 仅评估 H.10 latest attempt。FAILED/PARTIAL/零行、artifact/hash/member 不一致、Observation 篡改、许可撤销、future/regression 或 required-set 错误时不发布半成品。
- 上一完整快照只有在 embedded run/artifact/observation/hash/MetricSnapshot 仍可独立重验时才能 stale 保留。
- RUNNING 直接后继是无伪失败 marker 的 `transition_pending`；terminal failure 必须写结构化 marker；自然过期不得伪造 ingestion failure。
- 同一 run 重试幂等。新 run 即使数值不变，也必须 append-only 创建新 revision、publication batch 和四条 MetricSnapshot。
- 锁定 source、licence、latest run、上一快照与新 rows，提交前复验 still-latest 和 dedicated selector postcondition。
- main official/H.10 management command/Celery task 都调用 assets-fx coordinator；主 official 当前不重复采集 H.10，因此对同一 latest run 必须幂等，无法发布或合法保留时 fail loudly。

# 参数与数据边界

保留可分享 GET 参数：

- `period=3m|1y|3y`
- `tab=broad-dollar|major-fx`

非法值安全归一化；v1 不新增公开数据 API。

官方免费源：Federal Reserve H.10 Data Download Program。商业增强项：

- ICE DXY：ICE Data Services。
- 可执行机构 spot/forwards/NDF：CME EBS、Cboe FX、LSEG 或 Bloomberg Enterprise。
- cross-currency basis/FX swap implied funding：LSEG/Bloomberg 或具有公开派生展示权的授权供应商。

未获得 public/derived display 与 historical storage 权利前，不得将这些数据接入公开页面。

# Acceptance criteria

- [x] 抽取可中性复用的 H.10 exact run/artifact/Observation validator，与 global-dollar 共享 acquisition truth 但保持独立 publication lineage。
- [x] 建立 assets-fx v1 dedicated coordinator/publisher/selector，generic writer 和旧无版本快照无法进公开选择。
- [x] 四项 metrics、两张 charts、三张 rendered sections 满足 exact set、公式、日期、血缘、许可、质量与无 fallback 合同。
- [x] 四条 normalized MetricSnapshot、semantic fingerprint、exact payload hash、ZIP/member hashes 和 exact observations 可独立重验。
- [x] latest failure/partial/zero-row/RUNNING、自然过期、同值恢复、并发 supersede、旧 replay 与所有 tamper 路径 fail closed 且正确 stale/transition。
- [x] registry 删除 DXY/CNH/离岸压力原型数值与语义；数据台账将 H.10 标 LIVE，将商业 DXY、spot、forward/NDF、basis 与微观行情标 PURCHASE_REQUIRED。
- [x] `/assets/` 总览 FX 投影、`period/tab` 参数、空态、旧快照拒绝和 `/assets/fx/` 路由有合同测试。
- [x] Ruff、完整 pytest、Django check、migration drift、`git diff --check`、隔离临时库真实 H.10 刷新与路由 smoke 通过。
- [x] 1440/390 Browser Plugin 视觉、交互与 console 验收通过；四张指标卡、三张表、筛选导航、移动抽屉、主题切换、无横向溢出和空错误控制台均有真实 H.10 页面证据。

# Verification plan

- Canonical: `.venv/bin/ruff check .`, `.venv/bin/pytest -q`, `.venv/bin/python manage.py check`。
- Additional: `git diff --check`、migration drift、H.10 raw ZIP/member/hash replay、exact metric/chart/table and MetricSnapshot tests、latest-attempt/failure/recovery/concurrency matrix、global-dollar shared-acquisition reconciliation、isolated live H.10 refresh、route smoke 与 desktop/mobile Browser Plugin gate。
