---
schema_version: 1
id: AI-RESEARCH-020
project_id: AI-RESEARCH
title: 六层官方证据传导链原子组合公开合同
status: REVIEW
priority: P0
executor: codex
task_id: atlas-transmission-chain-official-alignment-20260714
branch: main
worktree: local
dependencies:
- AI-RESEARCH-014
- AI-RESEARCH-015
- AI-RESEARCH-016
- AI-RESEARCH-017
- AI-RESEARCH-018
- AI-RESEARCH-019
updated_at: '2026-07-15T10:30:14+08:00'
next_action: Run the deferred 1440/390 Browser Plugin visual and console gate when its locked-runtime import regression is fixed; optionally refine mixed transition wording so terminal failures remain more specific than RUNNING layers. Commit, push and deployment remain separately authorized.
evidence:
- The dedicated transmission-chain v1 coordinator now composes only the six strict 014–019 child revisions and publishes the exact 12 metrics, 6 copied charts and 3 rendered evidence/reconciliation/gap sections; generic core publication is capability-guarded from writing this key.
- Parent-facing validation rebuilds reserves and reserves-rate-spreads from referenced exact Observation batches, reconciles all child MetricSnapshot rows, hashes, current licences and acquisition evidence, and rejects payload-only self-consistency.
- Parent semantic identity excludes run, batch, URI and artifact-row identity while the exact payload hash retains them; same-value recovery therefore preserves semantic identity but creates a new immutable child and parent lineage revision.
- The selector now proves current_candidate, retained_failure, transition_pending and natural_expiry separately, including markerless RUNNING direct successors, terminal-marker plus unrelated RUNNING mixed transitions, repeated failures, same-value recovery and poisoned-parent regression baselines.
- Failure reason codes are bound to attempt status semantics; latest-attempt-incomplete requires a terminal incomplete attempt, while component/shared/regression/postcondition failures require success-only attempts. Hashed child envelopes and evidence ledgers remain immutable.
- Presentation overlays mark only failed, changed or naturally expired layers. Final Sol review reported P0=0 and P1=0; one non-blocking P2 remains because a mixed terminal-failure/RUNNING transition uses the generic waiting text for both stale layers.
- An isolated temporary database retained live official runs including H.4.1 7,380 rows, H.8 2,792, PRATES 1,813, H.10 37,323, SOFR 800, ON RRP 951, SRF 1,320, SOMA 2,340, USD swaps 2,622, TGA 100 and 13-week bills 382. Re-publication produced one current parent with 12 exact MetricSnapshots and 6 shared-input reconciliations.
- Real-data acquisition evidence reconciled as 11 PRIVATE_BYTES, 6 HASH_POINTER_ONLY and 1 NOT_AVAILABLE_UNDER_CHILD_V1 across 24 RawArtifact rows. The final route returned HTTP 200, rendered all three exact tables, and did not leak the internal cells_list field name.
- Final validation passed 43 transmission-chain tests, 110 parent-plus-strict-child tests, 133 adjacent component/refresh tests and 771 full-suite tests. Ruff, Django check, migration drift and git diff checks are clean.
- Browser Plugin 26.707.71524 still fails its supported locked-runtime import by attempting to redefine the non-configurable process global. The 1440/390 visual and console gate is explicitly unexecuted; no alternate harness is counted as evidence.
started_at: '2026-07-14T16:56:47+08:00'
---

# 目标

把 `/liquidity/transmission-chain/` 从无版本、跨来源、跨批次的 generic 拼装页升级为独立、可复算、失败可见的 `transmission-chain v1` 公开合同。

页面保留“六层传导链”导航名与现有 URL，但公开语义改为“六层官方证据传导链”：原子组合 014–019 已审计的六个组件快照，逐层展示官方直接值和 Atlas Macro 透明派生值。页面不是压力指数、不是 Federal Reserve 官方指标、不是完整金融条件指数，也不是交易信号。

本里程碑不发布总分、层级分数、`normal/tight/stress` 状态、共振结论、行动建议或 demo fallback。旧“能源、离岸美元、Repo、银行负债表、中介能力、资产反应”评分框架不做数值反推；缺失部分进入许可与方法缺口台账。

# v1 六层证据合同

## 必需组件

父页不得直接查询最新裸 `Observation`。它只能组合以下六个当前有效、可独立重验的严格子快照：

1. `fed-balance-sheet v1`：资产负债表供给与净流动性透明代理。
2. `operations v1`：ON RRP、SRF 与 Desk 操作设施。
3. `reserves-rate-spreads v1`：SOFR、IORB 与 13 周 T-bill 共同日利差。
4. `subsurface v1`：SOFR 尾部分位、成交量与官方设施见证。
5. `reserves v1`：准备金相对商业银行资产的覆盖代理。
6. `global-dollar v1`：H.10 美元参考序列与央行美元互换后盾。

六个组件可以有不同 observation/as-of/fetched/fresh-until，不强迫异频输入同日或同一 refresh cycle，不做前值填充。父页：

- `as_of = min(component.as_of)`，明确表示最老组件日期，不冒充统一市场时点。
- `fetched_at = max(component.fetched_at)`，另存父页 `generated_at/published_at`，不得把抓取时间与发布时间混为一谈。
- `fresh_until = min(component.fresh_until)`。
- 每层分别显示自身 observation/as-of/fetched/fresh-until、quality、stale 和 refresh-failure 状态。
- 只有 6/6 组件均通过 embedded strict validation、当前许可允许、无 fallback 且共享输入对账一致时，才发布新父快照。

## 必需指标

父快照 exact metric set 为十二项。数值不在父页重新计算，而是从通过复验的 child metric 原样复制，并保存 child snapshot、child MetricSnapshot、child publication hash、input run，以及该 child v1 实际具备的 acquisition evidence：

1. `balance-sheet-net-liquidity` ← `fed-balance-sheet / net-liquidity`。
2. `balance-sheet-total-assets` ← `fed-balance-sheet / walcl`。
3. `operations-onrrp-regular` ← `operations / onrrp-non-small-value-total`。
4. `operations-srf-regular` ← `operations / srf-non-small-value-total`。
5. `money-market-sofr-iorb` ← `reserves-rate-spreads / reserves-sofr-iorb-spread`。
6. `money-market-sofr-tbill` ← `reserves-rate-spreads / reserves-sofr-tbill-spread`。
7. `repo-tail-p99-iorb` ← `subsurface / sofr-p99-minus-iorb`。
8. `repo-volume-z60` ← `subsurface / sofr-volume-z60`。
9. `bank-reserve-coverage` ← `reserves / reserve-commercial-bank-assets-ratio`。
10. `bank-reserve-8w-change` ← `reserves / reserve-ratio-8w-change`。
11. `global-dollar-5d-change` ← `global-dollar / h10-broad-dollar-5d-change-pct`。
12. `global-swap-regular-outstanding` ← `global-dollar / fxswap-usd-outstanding-non-small-value`。

必须保持并重验子合同的透明公式。下列是展示式；字符串校验必须引用现有 child 常量，不能用排版差异另造公式：

- `balance-sheet-net-liquidity` 原样继承 `FED_BALANCE_SHEET_NET_FORMULA = "WALCL - ONRRP - TGA"`。
- `operations-onrrp-regular` 独立继承 `ONRRP - ONRRP-SMALL-VALUE-TOTAL`；它与前项共享 ON RRP acquisition run，但不是同一 scalar field。
- `operations-srf-regular`：`SRP - SRP-SMALL-VALUE-TOTAL`。
- `money-market-sofr-iorb`：`100 * (SOFR - IORB)`。
- `money-market-sofr-tbill`：`100 * (SOFR - 13W Coupon Equivalent)`。
- `repo-tail-p99-iorb`：`100 * (SOFR_99P - IORB)`。
- `repo-volume-z60`：`(V_t - mean(V_t..V_t-59)) / population_std(V_t..V_t-59)`。
- `bank-reserve-coverage`：`100 * WRBWFRBL / H8-B1151NCBA`。
- `bank-reserve-8w-change`：`ratio(t) - ratio(t-56 calendar days)`。
- `global-dollar-5d-change`：`100 * (V_t / V_t-5 - 1)`。
- `global-swap-regular-outstanding`：`sum(active amount_i / 1,000,000 where isSmallValue = false)`。

每项 outer `MetricSnapshot` 必须 exact match label、value、display、change、unit、source、value date、as-of、fetched-at、quality、licence、fallback、formula、calculation owner、input lineage、child snapshot 与 child MetricSnapshot 引用。normalized key 固定为 `transmission-chain-{outer_metric_key}`；row 的 `batch_id` 必须等于父 publication batch，child publication batch 存入 `metadata.component_metric_snapshot_batch_id`，child input batches 存入 `metadata.input_batch_ids`。dataset、upstream field、run 和 artifact evidence 放入专属 metadata；派生值不得伪造单一 dataset/upstream field，必须保存有序的 exact input datasets/fields。

## 必需图表

父快照 exact chart set 为六项，复制相应 child chart 的完整 data 和 point lineage：

- `fed-balance-sheet-net-liquidity-history`
- `operations-standing-tools-history`
- `reserves-funding-levels`
- `subsurface-sofr-tail-history`
- `reserve-ratio-history`
- `global-dollar-swap-drawdowns`

每张父图必须记录 `component_page_key`、`component_chart_key`、`component_contract_version`、`component_snapshot_id`、`component_publication_batch_id`、`component_fingerprint`、`component_payload_integrity_hash`、数据日期范围、input runs 和 child 实际具备的 artifact evidence。父 selector 必须验证 chart data 与 referenced child 完全一致，不能只相信复制后的 JSON。

## 必需表格

section exact set 为三项，所有行都必须生成并实际渲染 `cells_list`：

1. `layer-evidence-ledger`：精确六行。逐层列出 claim scope、两项指标、component as-of/fetched/fresh-until、quality、stale、snapshot/batch/hash、source、dataset、licence、fallback 与语义边界。
2. `shared-input-reconciliation`：精确六行。对账 H.4.1、ON RRP、SOFR、IORB、SRF 和 USD swaps 的跨组件共享输入。
3. `methodology-and-licensing-gaps`：明确列出 `LIVE / PROXY / NEEDS_SOURCE / PURCHASE_REQUIRED / LICENSE_REVIEW`，不得用空白或伪数值代替缺口。

# 共享输入对账

以下重复输入必须在相关 child snapshots 中引用相同 `(source, dataset, run_id, batch_id)`；任何一项不一致都不得发布新父快照。对账对象是 acquisition identity，不要求两个 child 的公开 metric 数值相等；每行同时保存双方 component、series/field、source、dataset、run、batch 及可用 artifact identity：

- H.4.1：`fed-balance-sheet = reserves`。
- ON RRP：`fed-balance-sheet = operations`。
- SOFR：`reserves-rate-spreads = subsurface`。
- IORB：`reserves-rate-spreads = subsurface`。
- SRF：`operations = subsurface`。
- USD swaps：`subsurface = global-dollar`。

若同值重采集改变 run、batch 或 artifact lineage，父协调器必须重新执行对账并生成可审计的新父血缘；不得因值未变化而吞掉恢复事件。

六个 child 暴露给父页的 publication revision 必须 append-only。semantic fingerprint 相同但 exact payload hash、run、batch 或 artifact lineage 改变时，必须创建新 child revision、新 publication batch 和新 `MetricSnapshot` rows；不得原地覆盖已被父页引用的 revision。可使用等价的 immutable component revision，但父页引用必须不可变。该行为必须是六个 component key 的 scoped 改造，例如 `append_on_exact_lineage_change`，不得全局改变无关 generic dashboard 的 semantic dedupe。

revision 的 hashed payload、`MetricSnapshot` rows 和 publication lineage 不可变。唯一允许原地变化的是顶层、且被 exact payload hash 明确排除的 `refresh_failure`，由失败或自然过期确定性派生的 `DashboardSnapshot.quality_status`，以及 `updated_at`。component envelope 保存不可变的 `publication_quality_status`；当前 stale/failure 状态只通过父级 presentation overlay 展示。

父页自身同样采用 append-only revision：任何 child exact lineage 变化，即使十二个数值和父 semantic fingerprint 相同，也必须生成新父 revision 与新父 publication batch；不得走 generic same-fingerprint 原地更新。

# 完整性与选择合同

新增：

- `TRANSMISSION_CHAIN_CONTRACT_VERSION = 1`。
- `TRANSMISSION_CHAIN_FORMULA_VERSION = "official-evidence-chain-v1"`。
- 独立 coordinator/publisher/selector 与 parent-facing embedded component validators。
- registry `snapshot_contract_version = 1`。

`transmission-chain` 必须从 `CORE_PUBLICATION_KEYS`、`PRATES_PUBLICATION_KEYS`、generic dashboard definitions 和所有 generic 发布路径中移除，并加入 `INDEPENDENT_PUBLICATION_KEYS`。generic publisher 在显式 key、`keys=None` 或内部直接调用时都必须硬拒绝写入该 key。

旧无版本快照只保留审计历史，立即退出公开选择；不得通过补写 contract version、hash 或字段把旧 JSON 冒充 v1。无合法 v1 时，路由显示清晰空状态，而不是继续展示现有 legacy snapshot。

父 payload 至少包含：

- contract/formula version、required exact sets、publication batch、as-of/fetched/fresh-until。
- 六个 component snapshot 的 key、contract version、snapshot/batch、semantic fingerprint、payload hash、MetricSnapshot refs、runs、dates、publication quality、licence 与 fallback。每个 envelope 保存按 input run 粒度的 `artifact_evidence[]`；每项绑定 `input_role/source/dataset/run_id/batch_id`，状态只能是 `PRIVATE_BYTES`、`HASH_POINTER_ONLY` 或 `NOT_AVAILABLE_UNDER_CHILD_V1`，单个 run 可有零到多个 artifact rows。不得把 mixed child 压成一个 artifact 状态。已哈希的 envelope 不保存会在失败后被回写的动态状态。
- 共享输入对账结果、六层 evidence ledger 和 gap ledger。
- semantic fingerprint、exact payload integrity hash、structured refresh failure。

两类 publication hash 必须分离：

1. semantic fingerprint 覆盖页面语义、十二项指标、六张图、三张表、六个 child semantic fingerprints 及共享输入对账。parent canonicalizer 只排除明确列出的父级顶层 volatile 字段；不得递归删除 child envelope 内的 semantic fingerprint、component identity 或 reconciliation 内容，禁止直接复用 generic `_dashboard_content_fingerprint`。
2. exact payload integrity hash 覆盖嵌套 `{"title", "summary", "data"}` 完整内容，只排除顶层自身 hash 与顶层 `refresh_failure`；不得递归忽略嵌套同名字段。

父 selector 不得只调用现有 public selector 后盲信 child JSON。它必须调用能在父事务中运行的 embedded strict validators，并明确区分四种模式：

- `current_candidate`：用于创建新父 revision；latest attempts 全部 SUCCESS、非空、fresh，并与六个 current immutable child revisions 一致。
- `retained_failure`：旧 parent 的 immutable refs 可独立重验；latest terminal attempts 与父级顶层 `refresh_failure` 精确对应。
- `transition_pending`：至少一个 latest attempt 或严格 child revision 已不同于旧 parent，但 parent coordinator 尚未完成。旧 refs 必须仍可独立重验；新 attempt 必须是数据库中的真实直接后继，SUCCESS 时必须已有严格有效的 immutable child revision。marker 可以不存在，或仍指向紧邻的前一失败 attempt。selector 只把旧 parent 作为 stale 展示，不回写 hashed envelope。
- `natural_expiry`：referenced runs 仍是 latest SUCCESS，且无 `refresh_failure`；仅 freshness deadline 自然经过。使用 child 的 `allow_natural_expiry` 路径重验，并只在 presentation 层标 stale。

四种模式都重新核对：

- child contract version、required sets、source/dataset、run status 和 supersede 状态；只有 `current_candidate` 与 `natural_expiry` 要求 referenced run 仍是 latest attempt，其余模式按上述 failure/transition 规则验证真实后继，不把历史 referenced run 的非 latest 身份本身当作篡改。
- current public/derived/historical-storage licence、无 demo/fallback。
- referenced observations、formulas、tables、charts 与 child 已声明的 acquisition contract。逐 input run 处理 `artifact_evidence[]`：存在私有内容寻址 bytes 时必须复验 bytes/hash/size；只有 URL+hash pointer 时复验 artifact row、run metadata 与 pointer hash；child v1 完全未提供 artifact 时必须记录 `NOT_AVAILABLE_UNDER_CHILD_V1` 并进入 gap ledger，不得伪造 artifact 或声称已完成 bytes 复验。
- child payload/semantic hashes与 exact MetricSnapshot rows。
- parent copied values/charts/sections、shared inputs、parent hashes 与 outer MetricSnapshot rows。

`reserves` 与 `reserves-rate-spreads` 现有公开 guard 不足以供父页复验；020 必须补足 parent-facing strict embedded validation，不能以 `reconcile_metric_snapshots=False` 绕过 normalized rows。

# 原子发布、时效与失败保留

- 在单一数据库事务中按稳定顺序先 `select_for_update` 锁定全部 required `Source` rows 作为并发插入栅栏，再锁当前 licences、六个 immutable child revisions、所选 child `MetricSnapshot` rows、对应 latest attempts 和上一父快照；提交前重新执行 still-latest 检查。
- 任一 child 缺失、partial/failed/superseded、source/dataset 错误、shared batch 不一致、artifact/hash/公式/table/chart/MetricSnapshot 被篡改、许可撤销、fallback、未来时间或 as-of 回退时，不写半成品。
- 父发布批次只包含十二个 transmission-chain outer MetricSnapshot，不与其他 dashboard 共用 publication batch。
- 写入 payload 与十二个 rows 后，在提交前运行 dedicated selector postcondition；失败则整体回滚。
- 旧父快照只有在 embedded 六组件引用仍可独立重验且许可仍有效时，才能以 `retained_failure`、`transition_pending` 或 `natural_expiry` stale 展示。failure marker 在存在时必须合法；`natural_expiry` 与合法的无失败 `transition_pending` 不要求伪造 marker。
- 最新 attempt 失败必须推进结构化 failure marker；重复失败更新审计时间和 attempt，不得永久停在第一次失败。
- 自然过期可在 presentation 层标 stale，但不得伪造 ingestion failure。
- 恢复成功必须清除 failure marker 并更新 lineage。若 child 同值恢复发生在 parent coordinator 之前，上一完整父快照不得在安全过渡窗口内瞬间消失；但 forged future references 或不存在的 child refs 必须拒绝。
- published component envelopes、layer ledger 和 shared reconciliation 一经发布均不可变。失败时只推进父级顶层 `refresh_failure`；UI 的逐层 stale/failure 状态由该 marker 覆盖展示，不回写嵌套 hashed 内容。恢复后用新的父 revision 清除 marker。

main official、H.4.1、H.8、PRATES 和 H.10 刷新入口必须在各自 child coordinator 完成后触发 transmission coordinator。Celery task 与对应 management commands 必须在无法发布或合法 retained-stale 时 fail loudly；无关 source failure 不阻塞本页。

# 数据来源与缺口边界

## v1 可发布证据

- Federal Reserve H.4.1、H.8、PRATES 与 H.10。
- New York Fed SOFR、ON RRP、SRF、Treasury purchases、SOMA 与 USD liquidity swaps。
- Treasury FiscalData TGA 与 U.S. Treasury 13-week bill coupon-equivalent rate。
- 净流动性、准备金覆盖、60 日成交量 Z-score 等只标 `PROXY/estimated`，保留 Atlas Macro calculation owner 和公式，不冒充官方指标。

## 明确不在 v1 假装可用

- 原总压力分、六层分、阈值、紧松状态和共振判断：`NEEDS_SOURCE`。
- 石油/天然气“能源层”：EIA exact series、方法与再展示权利完成审核前为 `NEEDS_SOURCE / LICENSE_REVIEW`；CME/ICE 可执行曲线为 `PURCHASE_REQUIRED`。
- 1M/3M/1Y cross-currency basis、forward points、dealer implied funding：`PURCHASE_REQUIRED`。
- AOCI/HTM/AFS、资本/LCR/放贷能力解释：FFIEC 聚合合同完成前为 `NEEDS_SOURCE`。
- 中介能力：NY Fed Primary Dealer positions/financing/fails、SCOOS 与 OFR repo 是候选代理，均为 `NEEDS_SOURCE / LICENSE_REVIEW`；dealer books、haircuts、specials、bid/ask、basis inventory 与 market impact 为 `PURCHASE_REQUIRED`。
- 完整资产反应：Treasury/H.10 只能提供部分官方参考；ICE OAS/CDX、VIX/MOVE、权益、商品与可交易 FX 为 `PURCHASE_REQUIRED`。

Primary Dealer 明确拆到后续独立里程碑：必须先实现官方 provider、`*` suppression/null 处理、不可变 artifact、许可声明、exact-set、独立 selector 和失败保留。即使完成，也只能命名为“交易商活动与结算摩擦”，不能直接升级成“中介能力分数”。

# 页面与迁移

- 保留 `/liquidity/transmission-chain/`、导航、canonical、sitemap 和历史外链兼容。
- eyebrow 改为 `Six-Layer Official Evidence Chain`。
- description 明确“官方证据链，不是压力指数或交易信号”。
- 删除 registry 中 `5.6 / 10`、`4 / 10`、`6 / 10`、`偏紧`、`缓冲下降`、`收缩`、`正常`、`共振` 等 legacy prototype。
- 术语库同步删除“分层评分”暗示，改为组件化证据、口径和缺口说明。
- 页面逐层显示 component freshness；不得用一个父页更新时间掩盖混合频率。
- 表格实际输出 `cells_list`，不得把内部序列化字段名泄漏为页面文本。
- 不复制比较站 HTML/CSS、原创文案、私有 API、历史库、不透明评分或研判。

# Acceptance criteria

- [x] 建立 transmission-chain v1 独立 coordinator；generic publisher 在所有调用形态下均无法发布该 key。
- [x] 六个 014–019 child snapshots 全部经 parent-facing strict embedded validation；`reserves` 与 `reserves-rate-spreads` 不再绕过 normalized-row 复验。
- [x] 十二项指标、六张图、三张表满足 exact set、copy-and-reconcile、lineage、公式、异频时效、许可和无 fallback 合同。
- [x] 六项共享输入按 exact source/dataset/run/batch 对账，任一 mismatch、wrong dataset、partial、旧 replay 或 forged ref 都失败关闭。
- [x] 六个 versioned child 采用 key-scoped append-only，父 revision 也 append-only：同值但 exact lineage 改变时创建新 revision/batch/rows，历史 parent 引用不被原地覆盖；只允许顶层 failure、派生 quality 与 updated-at 原地变化。
- [x] 父 semantic fingerprint、exact payload hash、十二个 outer `MetricSnapshot` 与 child refs 可从数据库和 child 已声明的 acquisition evidence 独立复验；私有 bytes、hash pointer 与 unavailable 三种状态不混称。
- [x] `current_candidate / retained_failure / transition_pending / natural_expiry` 四态均有对抗测试；任一 child 失败、过期、篡改、许可撤销或恢复时，只保留可重验的上一完整 stale 父快照，failure marker 和 recovery lineage 正确推进。
- [x] main/H.4.1/H.8/PRATES/H.10、Celery 与 management commands 在 child 协调后触发父协调器并 fail loudly。
- [x] registry、术语和页面删除所有 legacy 分数/状态/共振/行动文案，显示六层 evidence ledger、shared-input reconciliation 和完整缺口台账。
- [x] 数据目录将已审核官方证据标为 LIVE/PROXY，将能源方法、中介候选、AOCI 和完整资产响应标为 NEEDS_SOURCE/LICENSE_REVIEW，将商业 basis、微观市场与完整行情标为 PURCHASE_REQUIRED。
- [x] 对抗测试覆盖 exact-set 删除/重复/增加、arbitrary v1 shell、wrong dataset/source/run、mixed batch、hash/MetricSnapshot/artifact/licence/table/chart tamper、未来/回退、重复失败、同值恢复、并发 supersede 与 legacy rejection。
- [x] Ruff、771 项完整 pytest、Django check、migration drift、`git diff --check`、隔离临时数据库真实组件组合与路由 smoke 通过。
- [ ] 1440/390 浏览器视觉、交互与 console 验收通过；若官方 Browser Plugin 回归仍存在，必须明确记录为未执行，不以替代 harness 冒充通过。

# Verification plan

- Canonical: `.venv/bin/ruff check .`, `.venv/bin/pytest -q`, `.venv/bin/python manage.py check`。
- Additional: `git diff --check`、`manage.py makemigrations --check --dry-run`、exact-set and cross-child lineage tests、parent/child hash and MetricSnapshot tamper matrix、licence revocation、latest-attempt failure/recovery/concurrency tests、clean temporary official component composition、rendered-table route smoke、desktop/mobile browser and console inspection。
