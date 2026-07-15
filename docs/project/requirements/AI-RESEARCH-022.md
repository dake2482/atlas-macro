---
schema_version: 1
id: AI-RESEARCH-022
project_id: AI-RESEARCH
title: Treasury HQM 与 Fed SLOOS 信用页面族严格公开合同
status: REVIEW
priority: P1
executor: codex
task_id: atlas-credit-official-v1-alignment-20260715
branch: main
worktree: local
dependencies:
- AI-RESEARCH-021
updated_at: '2026-07-15T19:43:41+08:00'
next_action: Review the completed credit evidence together with draft PR #1, which carries the subsequent volatility and Treasury v2 product patch. Production deployment remains separately authorized.
evidence:
- Current `/credit/`, `/credit/spreads/`, `/credit/cds/` and `/credit/stress/` routes return HTTP 200; retired `/credit/issuance/` and `/credit/events/` correctly return 410.
- The current database has three published revisions each for `credit`, `credit-spreads` and `credit-stress`, but their latest snapshots are unversioned generic publications with no dedicated selector, append-only lineage or exact-set contract. `credit-cds` has no published snapshot.
- The current generic builder can select observations from different ingestion batches, so a partial new source run could silently combine new and old rows.
- A live Federal Reserve SLOOS fetch on 2026-07-15 returned 848 observations across all six required quarterly series, with 139 common dates and latest values dated 2026-06-30.
- A live U.S. Treasury HQM fetch on 2026-07-15 returned 2,040 observations across 2Y/5Y/10Y/30Y, 510 observations per tenor from 1984-01-31 through 2026-06-30.
- Both current providers parse real official files, but neither result retains exact raw response bytes, and current credit runs therefore cannot prove immutable ZIP/XLS acquisition evidence.
- Static registry descriptions still imply IG/HY/rating-bucket OAS, NFCI and a five-factor stress score although those datasets are not licensed for this public product.
- ICE BofA OAS, CDX/single-name CDS, TRACE-derived stress inputs and licensed ETF/market proxies remain explicit PURCHASE_REQUIRED gaps. Chicago Fed NFCI/ANFCI remains LICENSE_REVIEW and is not eligible for public publication without written permission.
- Independent pre-implementation review resolved five P0 contract ambiguities: canonical SLOOS public keys, selected-series exactness, base-valid retained parent semantics, prose-only CDS rendering, and private capability-token publication. It also fixed freshness instants, change quality, archive safety and period controls before product code was written.
- Credit Official v1 now has dedicated HQM/SLOOS raw replay, child and parent publishers/selectors, exact MetricSnapshot reconciliation, failure retention, no-number CDS rendering, GET controls and explicit purchase/licence gaps.
- The final correction review found and resolved four P1 issues: all nine exact table schemas, the HQM tenor chart axis, future/invalid acquisition chronology, and transaction locks for RawArtifact, Observation, child snapshot and child metric rows. The final independent result was P0=0 and P1=0.
- Focused credit, route, refresh and assets-FX suites passed; the complete repository pytest suite, Ruff, Django system check, migration drift, `git diff --check` and changed-file secret scan all passed. The only pytest warning is the intentional duplicate-SLOOS-member rejection fixture.
- Product commit `88508bc` is retained on local `main`. The patch-identical public snapshot commit `d67908a127a2b3e9421b1457153ef30f385a833e` is published on `dake2482/atlas-macro-platform` `main`; internal `docs/project` files are not part of that public snapshot.
- An isolated 2026-07-15 live refresh created exactly two successful official runs and 2,888 normalized observations: 2,040 Treasury HQM rows and 848 Federal Reserve SLOOS rows. Both official files replayed byte-for-byte from private content-addressed artifacts (`a083d61df24bef951c96a779106c7cbb03dd5b1681c99e8ed6020199d07c2aad`, 75,776 bytes; `d8621f78335b1aa8ccdde7786e2cacad81d0b20261a82c632675be17befa6300`, 241,829 bytes).
- The same refresh atomically published exactly three strict dashboards (`credit-spreads`, `credit-stress`, `credit`) and 14 `MetricSnapshot` rows under one `credit_refresh_id`, with zero failed/partial runs, zero fallback events and no `credit-cds` snapshot.
- Live route smoke returned 200 for all four current credit routes and 410 for both retired issuance/event routes. Desktop 1440x900 and mobile 390x844 browser acceptance covered every GET period/tab combination, invalid-value normalization, exact chart row/series counts, metric units, table schemas, canonical URLs, fixed/hidden navigation and internal table scrolling with no page-level overflow.
- Final browser evidence showed exactly one nonzero ECharts canvas on each numeric route and zero metrics/charts/canvases on `credit-cds`. The CDS page now renders exact 3-row and 8-row structured contracts plus its purchase ledger, rejects a deliberately published rogue numeric snapshot, and leaves the console error/warning log empty.
- After the CDS presentation hardening, the complete pytest suite, Ruff, Django system check, migration drift and `git diff --check` all passed. The only pytest warning remains the intentional duplicate-SLOOS-member rejection fixture.
started_at: '2026-07-15T12:36:57+08:00'
---

# 目标

把信用页面族从弱校验的 generic 快照升级为独立、可复算、失败可见的 `Credit Official v1`：

1. `/credit/spreads/` 只发布 U.S. Treasury HQM 高质量企业债月均 Par Yield 曲线。
2. `/credit/stress/` 只发布 Federal Reserve SLOOS 银行贷款标准与需求调查。
3. `/credit/` 只原子组合上述两个严格子快照，不再查询裸 `Observation`。
4. `/credit/cds/` 不发布任何 CDX/CDS 数字，清楚解释采购原因、代理边界和采购后的字段合同。

HQM 不是国债利差、不是 ICE BofA OAS、没有 IG/HY/BBB/BB/B/CCC 评级桶。SLOOS 是季度银行调查，不是市场报价、NFCI、信用压力综合分或交易信号。页面不得用免费代理冒充商业指数或 composite 报价。

# 官方输入与原始证据

## Treasury HQM

- source：`us-treasury-hqm`。
- dataset：`monthly-average-par-yields`。
- official XLS：`hqm_qh_pars.xls`。
- required exact series：`HQM-PAR-2Y`、`HQM-PAR-5Y`、`HQM-PAR-10Y`、`HQM-PAR-30Y`。
- 口径：高质量企业债月均 par yield，单位 percent，日期为 reference month end。
- 最新值不可为未来；四期限必须来自同一成功、非空、未 supersede 的 exact ingestion batch。
- 需要至少 120 个四期限共同有效月份；不插值、不前值填充。
- freshness deadline date 为 `latest reference month end + 62 calendar days`；公开有效截止时间固定为该 deadline date 后一个自然日的 `00:00 America/New_York` exclusive instant，并以带时区 ISO timestamp 保存。

## Federal Reserve SLOOS

- source：`federal-reserve-sloos`。
- dataset：`quarterly-series`。
- official ZIP/member：DDP ZIP / `SLOOS_data.xml`。
- required exact series：
  - `SUBLPDMBS_XWB_N.Q` → `sloos-business-standards-weighted`：企业贷款标准，贷款余额加权，正值表示净收紧。
  - `SUBLPDMBD_XWB_N.Q` → `sloos-business-demand-weighted`：企业贷款需求，贷款余额加权，正值表示净需求增强。
  - `SUBLPDMHS_XWB_N.Q` → `sloos-household-standards-weighted`：家庭贷款标准，贷款余额加权，正值表示净收紧。
  - `SUBLPDMHD_XWB_N.Q` → `sloos-household-demand-weighted`：家庭贷款需求，贷款余额加权，正值表示净需求增强。
  - `SUBLPDCILS_N.Q` → `sloos-ci-large-standards`：大中企业 C&I 贷款标准，正值表示净收紧。
  - `SUBLPDCISS_N.Q` → `sloos-ci-small-standards`：小企业 C&I 贷款标准，正值表示净收紧。
- 左侧 Board series ID 只作为 acquisition/Observation lineage；右侧 canonical public metric key 是 payload、MetricSnapshot、parent projection 和测试的唯一页面 key。
- 原始官方 XML 可以包含其他 Board series；provider 必须只请求、发现和持久化上述六条。`requested_series`、`found_required_series` 与该 run 的 persisted Observation series exact set 必须一致，六条中的重复 identity、缺失或持久化额外 series 才 fail closed。
- 六系列必须来自同一成功、非空、未 supersede 的 exact ingestion batch。
- 需要至少 80 个标准组共同有效季度与 80 个需求组共同有效季度；不插值、不前值填充。
- freshness deadline date 为 `latest survey quarter end + 150 calendar days`；公开有效截止时间固定为该 deadline date 后一个自然日的 `00:00 America/New_York` exclusive instant，并以带时区 ISO timestamp 保存。
- Board DDP `Prepared` 只保存为 `file_prepared_at`，不冒充每条 observation 的发布日期。v1 分别保存 `value_date`、`fetched_at` 与 `file_prepared_at`；只有以后找到官方 release timestamp 才新增 `published_at`。

## 不可变原始文件

两个 provider 都必须返回 exact `raw_bytes`，并在 metadata 保存：

- endpoint/download URL、content type、byte length、SHA-256。
- SLOOS ZIP member 名、未压缩字节数与 member SHA-256。
- HQM workbook 的文件类型与工作表/表头验证结果。

每次成功 run 在规范化事务中写入一个 private content-addressed `RawArtifact`。发布与 selector 必须重新读取并验证原始 bytes、artifact URI、hash、size、run/batch 归属，以及由该文件重建的 exact observations。空 bytes、伪 URI、重复/额外 artifact、hash/size/member 不一致均 fail closed。

原始文件重放必须使用安全边界：SLOOS ZIP 限制 archive/member 最大字节数、拒绝加密 member、拒绝绝对路径或 `..` 路径、要求唯一精确 `SLOOS_data.xml`、只允许安全压缩类型并限制压缩比；HQM 限制 XLS 最大字节数、拒绝异常 workbook/sheet/header/tenor 集。selector 使用同一严格解析器重建 required observations，不允许测试专用捷径。

同一刷新命令生成一个 `credit_refresh_id`，写入 HQM 与 SLOOS 两个 run metadata。子页各自只要求自身 run；父页新发布必须引用同一 refresh cycle 内两个成功子 revision，禁止把本轮 HQM 与历史 SLOOS 静默拼接成“最新完整批次”。

# `credit-spreads v1`（公开标题：HQM 企业债收益率代理）

## Exact metrics

精确四项：

1. `hqm-par-2y`
2. `hqm-par-5y`
3. `hqm-par-10y`
4. `hqm-par-30y`

主值为 Treasury official direct/fresh par yield。每项同时保存相对前一共同有效月份的变化：

`change_bp = 100 × (Y_t − Y_previous)`

其中输入收益率单位为 percent，变化单位为 bp。主 MetricSnapshot 行使用 `quality_status=fresh`、`unit=%` 和 Treasury direct source；`change` 是 Atlas Macro transparent derived/estimated，只在 payload/metadata 保存 `change_unit=bp`、`change_quality_status=estimated`、公式、前值/当前值与日期、exact input lineage、calculation owner。当前许可必须同时允许 public display、derived display 与 historical storage。

## Exact charts

1. `hqm-latest-par-yield-curve`：最新共同月份的 2Y/5Y/10Y/30Y 四个期限点。
2. `hqm-par-yield-history`：最近 120 个四期限共同有效月份，四条曲线，不插值。

每个点都携带 source、value date、fetched-at、input run/batch、RawArtifact、quality、licence 与 fallback。

## Exact sections

1. `recent-hqm-observations`：最近 24 个共同月份，四期限值与行级 batch/artifact lineage。
2. `hqm-source-freshness-methodology`：source/dataset/run/batch、fetched、latest month、fresh-until、XLS hash/size、row count、licence、fallback 与公式。
3. `licensed-spread-data-gaps`：ICE BofA IG/HY/评级桶 OAS、TRACE bond pricing、licensed all-in yield/ETF proxies，精确标记 PURCHASE_REQUIRED 或 LICENSE_REVIEW，不填伪数值。

三张表 exact column key 顺序：

- `recent-hqm-observations`：`date, hqm-2y, hqm-5y, hqm-10y, hqm-30y, quality, batch, artifact`。
- `hqm-source-freshness-methodology`：`source-dataset, run-batch, fetched, latest-month, fresh-until, artifact-sha-size, rows, licence, fallback`。
- `licensed-spread-data-gaps`：`market-data, status, public-value, provider-guidance`。

# `credit-stress v1`

页面公开名称与语义改为“银行信贷压力代理”，不得显示“五因子综合压力”或 `0–100` 总分。

## Exact metrics

精确六项，对应六条 SLOOS required series。主值为 Board official direct/fresh net percentage；`change` 为相对上一共同有效季度的百分点变化：

`change_pp = V_t − V_previous`

主 MetricSnapshot 行使用 `quality_status=fresh`、`unit=%` 和 Board direct source；变化为 Atlas Macro transparent derived/estimated，只在 payload/metadata 保存 `change_unit=pp`、`change_quality_status=estimated`、公式、方向解释、前值/当前值、日期、exact input lineage 与 calculation owner。当前许可必须同时允许 public display、derived display 与 historical storage。

## Exact charts

1. `sloos-lending-standards-history`：最近 80 个共同季度，企业余额加权、家庭余额加权、大中企业 C&I、小企业 C&I 四条贷款标准序列。
2. `sloos-loan-demand-history`：最近 80 个共同季度，企业与家庭余额加权需求两条序列。

## Exact sections

1. `latest-sloos-survey-table`：六行，最新值、上一值、变化、正值含义、value date 和行级血缘。
2. `sloos-source-freshness-methodology`：source/dataset/run/batch、DDP Prepared、fetched、latest quarter、fresh-until、ZIP/member hash/size、row count、licence 与 fallback。
3. `licensed-credit-stress-gaps`：NFCI/ANFCI 为 LICENSE_REVIEW；ICE OAS、TRACE、CDX/CDS、完整五因子压力历史和授权 ETF 行情为 PURCHASE_REQUIRED；不生成压力分数。

三张表 exact column key 顺序：

- `latest-sloos-survey-table`：`metric, value, previous, change-pp, positive-meaning, value-date, quality, batch`。
- `sloos-source-freshness-methodology`：`source-dataset, run-batch, file-prepared, fetched, latest-quarter, fresh-until, archive-sha-size, member-sha-size, rows, licence, fallback`。
- `licensed-credit-stress-gaps`：`market-data, status, public-value, provider-guidance`。

# `credit v1` 父页

父页只能组合同一 `credit_refresh_id` 下当前有效的 `credit-spreads v1` 与 `credit-stress v1`，不得重新查询裸 Observation。

父级重验必须分成两层：`child_base_valid(snapshot, embedded_run)` 重放 embedded run/artifact/observations/hash/MetricSnapshot/licence，但不要求 embedded run 仍为 latest；`child_public_state` 才比较 latest attempts。当前 refresh cycle 不完整时，上一 parent 只要两个 embedded child 仍 base-valid 就可进入 `retained_failure`，即使其中一个 dataset 已产生新的 current child。不得因禁止跨 cycle 新组装而让上一完整 parent 消失。

## Exact metrics

精确四项，值与完整 lineage 从 child MetricSnapshot 原样复制：

1. `overview-hqm-10y` ← `credit-spreads / hqm-par-10y`。
2. `overview-hqm-30y` ← `credit-spreads / hqm-par-30y`。
3. `overview-sloos-business-standards` ← `credit-stress / sloos-business-standards-weighted`。
4. `overview-sloos-business-demand` ← `credit-stress / sloos-business-demand-weighted`。

父页 `as_of = min(child.as_of)`、`fetched_at = max(child.fetched_at)`、`fresh_until = min(child.fresh_until)`，同时逐组件展示各自日期，不能用一个父时间掩盖月频与季频差异。

## Exact charts

1. `credit-overview-hqm-history`：复制并绑定 child `hqm-par-yield-history`。
2. `credit-overview-sloos-standards-history`：复制并绑定 child `sloos-lending-standards-history`。

## Exact sections

1. `credit-component-ledger`：精确两行，列出 child snapshot/batch/hash、run/batch/artifact、dates、quality、licence 与 fallback。
2. `credit-semantic-boundary`：HQM 与 SLOOS 可陈述的事实、不可推导的 OAS/CDS/综合压力语义。
3. `licensed-credit-market-gaps`：合并 OAS、TRACE、NFCI、CDX/CDS、发行、评级/违约事件与授权 ETF 行情采购台账。

三张表 exact column key 顺序：

- `credit-component-ledger`：`component, snapshot-batch, payload-hashes, input-run-batch, value-date, fetched, fresh-until, artifact, quality, licence, fallback`。
- `credit-semantic-boundary`：`evidence, can-state, cannot-state, status, source`。
- `licensed-credit-market-gaps`：`market-data, status, public-value, provider-guidance`。

# `credit-cds` 无数字合同

- 保持 `/credit/cds/` HTTP 200、canonical、导航和 sitemap。
- 不创建任何带 CDX/CDS 数字的 snapshot、metric、chart 或 fallback。
- registry 删除银行代理、主权代理、HY 保护代理等静态原型值与“Yahoo 代理”暗示。
- 不创建假“数据快照”。`dashboard_page` 对 `credit-cds` 使用专属 prose-only 空态，并安全保留只含文字/采购表的静态 sections；无快照状态必须使用页面专属说明，解释：
  - composite 报价与单笔 SEF/SDR 成交不是同一口径；
  - ETF/银行股/国债变化只能作为方向代理，不能命名为 CDX/CDS；
  - 采购候选为 S&P Global/Markit、ICE settlement、LSEG/Bloomberg 等具 public/derived display 与历史存储权的产品；
  - 采购后的字段至少包括 reference entity/index, series/version, tenor, currency, restructuring clause, bid/mid/ask, timestamp, contributor/composite method, source licence, value/fetch/batch/quality/fallback。
- prose-only section exact column key 顺序：`quote-type, what-it-is, why-not-substitute, required-licence` 与 `field, requirement, reason`。
- 页面底部 DataRequirement 保留采购产品、原因与代理限制；不得把 FRED 中受 ICE 约束的序列误判为可再分发。

# 发布、选择与完整性合同

新增：

- `CREDIT_CONTRACT_VERSION = 1`。
- `CREDIT_FORMULA_VERSION = "treasury-hqm-fed-sloos-v1"`。
- dedicated child publishers/coordinators/selectors 与 parent publisher/coordinator/selector。
- registry 三个数值页 `snapshot_contract_version = 1`。

`credit`、`credit-spreads`、`credit-stress` 从 generic dashboard definitions 和 generic publication keys 移除，加入 `INDEPENDENT_PUBLICATION_KEYS`。generic publisher 在显式 key、`keys=None` 和无 capability 的内部 core 调用中均硬拒绝写入这三个 key；三个 dedicated publisher 分别持有不可导出的私有 capability token 调用 core，不允许外部复用该 bypass。

每个 child/parent payload 至少包含：

- exact metric/chart/section sets、contract/formula version、formula map、semantic boundary。
- publication batch、refresh cycle、input run/batch、component dates、private artifact refs、source keys、licence decisions、fresh-until、demo/fallback state。child direct source 分别为 `us-treasury-hqm` 或 `federal-reserve-sloos`；`internal` 只作为 derived change 与 parent projection 的 calculation owner/source-key 成员。所有页面明确保存 ordered exact direct/derived source sets，selector 不允许二者混淆。
- semantic fingerprint 与 exact payload integrity hash；仅顶层 `refresh_failure` 和自身 hash 字段可从 exact hash 排除，嵌套 lineage 不得递归忽略。

每个页面使用独立 publication batch，只写精确 required `MetricSnapshot` rows。outer rows 必须匹配 label/value/display/change/unit/source/dates/quality/licence/fallback/formula/input lineage、semantic fingerprint 和 payload hash。旧无版本快照保留审计但永不进入公开选择，不允许原地补版本冒充 v1。

同一 exact input run 重试幂等。新的、仍在 freshness deadline 内的成功 run 即使值不变，也必须 append-only 创建新 revision、publication batch 和 MetricSnapshot rows，保留 semantic fingerprint 但更新 exact lineage hash；已经自然过期的同值新 run不得创建声称 direct/fresh 的 revision。published hashed core、child refs 与 MetricSnapshot rows 不可原地改写。

# 失败、并发与恢复

- 仅评估每个 dataset 的 latest attempt。FAILED、PARTIAL、RUNNING、零行、missing required series、required series 重复、该 run 持久化了 required set 之外的 Observation series、raw artifact/hash/member 不一致、Observation batch 缺失/篡改、许可撤销、future/regression 或 required set 错误时不得发布半成品。原始官方 ZIP/XML 含其他未请求 Board series 本身不是错误。
- 子页各自允许保留其上一完整 v1；父页只在两个 embedded child refs 仍可独立重验时保留上一完整 parent。
- RUNNING 直接后继为 `transition_pending`，不伪造 terminal failure marker；terminal failure 可更新被 exact hash 明确排除的顶层 `refresh_failure` 与 presentation quality overlay；自然过期只在展示层标 stale，不伪造 ingestion failure。hashed core 和嵌套 lineage 始终 immutable。
- 恢复成功创建一个不带 marker 的新 immutable revision，不清除或改写旧 revision 的历史 marker。重复 terminal failure 必须推进 attempt/audit time。
- 在单一事务中按稳定顺序锁现有 Source、current licences、latest runs、artifacts、observations、candidate/previous child/parent snapshots 与已有 MetricSnapshot rows；随后创建新 rows，并在提交前复验 still-latest 与 dedicated selector postcondition。
- 刷新命令和 Celery task 在新数据无法发布且上一版也不能合法 retained 时 fail loudly，并返回 `stale_dashboard_keys`；不得打印“成功”后静默留下不完整信用页。

# 页面与交互

- 保留四个信用 URL、导航、canonical、sitemap 和 GET 分享能力。
- `credit-spreads` 支持 `period=3y|5y|10y`、`tab=curve|history`；v1 历史最多 120 月，GET period 只是展示上限。
- `credit-stress` 支持 `period=10y|20y`、`tab=standards|demand`；v1 payload 固定最近 80 个季度，非法值归一化。现有 period renderer 的 `months` 均使用整数，不提供与 20 年重复的 `full`。
- `credit` 支持 `tab=hqm|sloos`，展示两个 child 的独立 freshness。
- 三个表格必须实际渲染 `cells_list`，不得泄漏内部字段名。
- 组件级显示 value date、fetched-at、batch、quality、licence 与 fallback。

# 数据采购边界

## v1 可公开

- Federal Reserve SLOOS DDP 六条季度调查序列。
- U.S. Treasury HQM 2Y/5Y/10Y/30Y 月均高质量企业债 par yield。
- Atlas Macro 对前值变化、图表重排和 parent 组合的透明计算。

## 明确缺口

- ICE BofA IG/HY 与评级桶 OAS：`PURCHASE_REQUIRED`，候选 ICE Data Indices，需历史存储、公开展示和 derived-data 权利。
- CDX IG/HY 与单名 CDS composite：`PURCHASE_REQUIRED`，候选 S&P Global/Markit、ICE settlement、LSEG/Bloomberg。
- FINRA TRACE 全量与派生流动性/压力：`PURCHASE_REQUIRED / LICENSE_REVIEW`；公开查询不等于批量存储和再分发许可。
- Chicago Fed NFCI/ANFCI：`LICENSE_REVIEW`，取得商业公开再发布书面许可前不入公开 snapshot。
- HYG/LQD/银行 ETF/股指代理：`PURCHASE_REQUIRED`，需行情缓存、派生与网站展示权。
- 信用发行数据库、评级变化与违约事件：保持 410，直到取得 Bloomberg/LSEG/Dealogic/Moody's/S&P/Fitch 等结构化许可。

# Acceptance criteria

- [x] HQM 与 SLOOS providers 返回并持久化 exact private raw bytes、hash/size/member evidence；真实官方文件可重放。
- [x] `credit-spreads v1` 精确四 metrics、两 charts、三 rendered sections，固定一个 HQM run/batch，不冒充 spread/OAS。
- [x] `credit-stress v1` 精确六 metrics、两 charts、三 rendered sections，固定一个 SLOOS run/batch，不生成综合压力分。
- [x] `credit v1` 只原子组合同一 refresh cycle 的两个严格 child revisions，精确四 metrics、两 charts、三 rendered sections。
- [x] dedicated selectors 重验 source/licence/run/artifact/Observation/hash/MetricSnapshot；旧 unversioned、demo、fallback 与 tamper 全部拒绝。
- [x] failure/partial/zero/RUNNING、自然过期、同值新 run、恢复、并发 supersede 与 repeated failure 行为有完整测试。
- [x] generic publisher 无法写入三个数值页；新 run append-only，旧 revision 不原地修改。
- [x] registry 删除 OAS/NFCI/五因子/CDS 代理原型语义；`credit-cds` 无数字页面清楚展示采购原因、代理边界和字段合同。
- [x] 数据台账准确标记 HQM PROXY、SLOOS LIVE、NFCI LICENSE_REVIEW、OAS/CDX/CDS/TRACE/行情 PURCHASE_REQUIRED。
- [x] 四个信用路由保持 200，两个 retired 路由保持 410；筛选参数、空态、旧快照拒绝和 cells_list 渲染有合同测试。
- [x] Ruff、完整 pytest、Django check、migration drift、`git diff --check`、隔离临时库真实 HQM/SLOOS 刷新、路由 smoke 和 1440/390 Browser gate 全部通过。

# Verification plan

- Canonical：`.venv/bin/ruff check .`、`.venv/bin/pytest -q`、`.venv/bin/python manage.py check`。
- Additional：`git diff --check`、migration drift、raw ZIP/XLS replay、exact metric/chart/table/MetricSnapshot tests、latest-attempt/failure/recovery/concurrency matrix、isolated live two-source refresh、four-route smoke、retired 410 checks 与 desktop/mobile Browser Plugin gate。
