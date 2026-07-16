---
schema_version: 1
id: AI-RESEARCH-025
project_id: AI-RESEARCH
title: BEA/BLS/DOL/Census 宏观五页 append-only 严格公开合同
status: IN_PROGRESS
priority: P1
executor: codex
task_id: atlas-macro-official-v2-20260715
branch: codex/volatility-treasury-v2
worktree: local
dependencies:
- AI-RESEARCH-002
- AI-RESEARCH-003
- AI-RESEARCH-004
- AI-RESEARCH-006
- AI-RESEARCH-008
- AI-RESEARCH-024
updated_at: '2026-07-16T13:30:00+08:00'
next_action: Separate the consumer publication-postcondition freshness boundary from the macro refresh abort path so a stale-but-replayable Census release workbook can be retained/marked stale without aborting GDP and Inflation publication; then complete the isolated live dual-refresh acceptance and 1440/390 browser gate before moving to strict Fed Funds and Liquidity contracts.
evidence:
- The five routes already render substantial official BEA, BLS, DOL, Census, Federal Reserve and New York Fed data, but they still fall through the generic public snapshot selector.
- A newer permitted rogue snapshot can therefore outrank the intended GDP, employment, inflation, consumer or economy publication without replaying its raw inputs, normalized observations, MetricSnapshot rows, required component sets or payload hash.
- The initial acquisition audit found no end-to-end exact private response retention. The current v2 providers and callbacks now build byte-replayable private bundles and append-only batches, both production refresh orchestrators are wired to them, and retry idempotency, chronology, successful-run-only watermarks, coverage, schema and unit gates are implemented.
- Migration 0018 extends BEA release-vintage identity with `batch_id`, preserving old rows while allowing the same official release identity to be retained in a later immutable acquisition batch.
- Migration 0019 expands `IngestionRun.dataset` to 512 characters so the exact 24-series BLS request identity is not truncated; preliminary BLS rows are retained as `estimated` and participate in exact postconditions.
- The economy parent already has a partial component envelope, but it reads weak child snapshots and cannot prove each child through acquisition, normalized storage and publication layers.
- The official source and licence ledger marks the underlying government sources as displayable and storable. Consumer sentiment, complete historical release vintages and any commercial microdata remain separate source or purchase boundaries.
started_at: '2026-07-15T20:14:42+08:00'
---

# 目标

把 `/economy/`、`/economy/gdp/`、`/economy/employment/`、`/economy/inflation/` 与 `/economy/consumer/` 从“已有真实官方数值但公开读取仍是通用快照选择”的状态升级为端到端严格合同：每个发布组件可由私有原始响应独立重放，每个成功抓取保留不可变 observation 批次，每个页面只能由专用 publisher 写入并由专用 selector 公开。

本项不把采购缺口改造成免费代理。消费者信心、商业调查、付费市场预期和未取得完整历史的 release vintage 继续显示结构化来源或采购状态，不发布合成数字。

# 页面合同

## GDP

- 来源以 BEA GDP official release HTML/workbook 为准，保留 GDP、GDI、PCE、主要分项增速、贡献和发布轮次。
- 页面必须冻结 exact metric、chart 与 vintage section 集合；Advance、Second、Third 与后续 Revised 不得因同一经济季度而相互覆盖。
- 当前值与历史修订路径分别保留 observation date、release date、release round、source revision、fetch time、batch 和原始 artifact witness。

Exact metrics（11）：`bea-a191rl`、`bea-dpcerl`、`bea-gdp-nominal-saar`、`bea-gdi-real-growth-saar`、`bea-pce-goods-growth`、`bea-pce-services-growth`、`bea-gpdi-growth`、`bea-pce-contribution`、`bea-gpdi-contribution`、`bea-net-exports-contribution`、`bea-government-contribution`。

Exact charts：`gdp-growth-history`、`gdp-vintage-trail`。Exact sections：`gdp-vintage-ledger`。`gdp-growth-history` 必须同时具备 A191RL 与 DPCERL，不再接受单序列 fallback。

## 就业

- BLS CES/CPS/JOLTS 与 DOL ETA weekly claims 分为独立 acquisition components，再原子发布到同一页面。
- 必需指标至少覆盖非农新增及 3M 均值、时薪同比、失业率、参与率、职位空缺、离职率、初请、四周均值、续请和 insured unemployment rate。
- 月度、周度和季度口径不伪造同日；每个组件单独显示有效日和新鲜度。

Exact metrics（11）：`nonfarm-payroll-change`、`nonfarm-payroll-change-3m`、`average-hourly-earnings-yoy`、`lns14000000`、`lns11300000`、`jts000000000000000jol`、`jts000000000000000qur`、`dol-ui-initial-claims-sa`、`dol-ui-initial-claims-sa-4wk`、`dol-ui-continued-claims-sa`、`dol-ui-iur-sa`。

Exact charts：`payroll-change`、`average-hourly-earnings-yoy`、`labor-slack`、`jolts-rates`、`initial-claims`、`continued-claims`。Exact sections：`jolts-official-levels`、`employment-methodology`。

## 通胀

- BLS CPI/PPI 与 BEA PIO PCE price indexes 进入同一严格子页；季调指数只用于环比和短期年化，未季调指数只用于同比。
- CPI/PPI/PCE 的 headline、core、shelter、core goods、services less energy 以及最终需求 PPI 指标和历史图必须冻结 exact sets。
- 5Y/10Y 市场预期只复用通过 Treasury v2 strict selector 的 nominal-minus-real par-yield 代理；明确不是可交易 breakeven 或 5Y5Y。
- 完整历史 release vintage 未具备前保持 `NEEDS_SOURCE`，不能把当前响应批次冒充完整修订轨迹。

Strict base snapshot 的 exact metrics 为 8 个前缀各 4 个周期变换，共 32 项：`headline-cpi`、`core-cpi`、`shelter-cpi`、`core-goods-cpi`、`services-less-energy-cpi`、`final-demand-ppi`、`pce-price-index`、`core-pce-price-index` 分别配 `mom`、`yoy`、`3m-annualized`、`6m-annualized`。

Exact base charts：`headline-cpi-rates`、`core-cpi-rates`、`shelter-cpi-rates`、`core-goods-cpi-rates`、`services-less-energy-cpi-rates`、`final-demand-ppi-rates`、`pce-price-rates`、`core-pce-price-rates`。Exact base sections：`inflation-methodology`、`inflation-coverage-gaps`。

Treasury overlay 不写入 inflation child revision，由路由从 strict `real-rates` 组合 `market-5y-bei`、`market-10y-bei`、`market-breakeven-inflation` 与 `market-breakeven-methodology`，并保存该 child 的 id、batch、fingerprint 和 payload hash。

## 消费

- Census MARTS、BEA PIO、Federal Reserve G.19 与 New York Fed Household Debt and Credit 各自保留精确来源批次，再在页面层组合。
- 零售、实际 PCE、实际可支配收入、储蓄率、消费者信贷、家庭债务与逾期率必须保留各自频率、单位和许可边界。
- Census 当前发布工作簿和完整历史 API 是不同组件；缺少 `CENSUS_API_KEY` 时只能显示已验证的发布工作簿覆盖，不得声称完整历史。
- 消费者信心在取得公开再发布许可前保持 `PURCHASE_REQUIRED` 或 `LICENSE_REVIEW`。

Exact metrics（14）：`census-mrts-44x72-sm-sa`、`census-mrts-44x72-sm-sa-mom`、`census-mrts-44x72-sm-sa-yoy`、`bea-real-pce-mom`、`bea-personal-saving-rate`、`bea-real-dpi-mom`、`g19-consumer-credit-outstanding-sa`、`g19-consumer-credit-growth-saar`、`g19-revolving-credit-growth-saar`、`g19-nonrevolving-credit-growth-saar`、`hhdc-total-debt-balance`、`hhdc-credit-card-balance`、`hhdc-all-90d-delinquent`、`hhdc-credit-card-90d-delinquent`。

Exact charts：`retail-sales`、`real-consumption-income-momentum`、`personal-saving-rate`、`consumer-credit-composition`、`household-debt-composition`、`household-debt-delinquency`。Exact sections 为空。

## 经济总览

- parent 固定引用 GDP、employment、inflation 和 consumer 四个通过严格 selector 的 child snapshot id、publication batch、payload hash、状态和新鲜度。
- parent 不从散乱 Observation 或 generic snapshot 重新拼装。
- 任一必需 child 新成功未发布、刷新中、失败或不可重放时，保留上一完整 parent 并准确标记 transition、retained failure 或 natural expiry；不得跨批次混装。

Exact metrics：`bea-a191rl`、`lns14000000`、`core-cpi-yoy`、`bea-real-pce-mom`。Exact charts：`gdp-growth-history`、`labor-slack`、`core-cpi-rates`、`real-consumption-income-momentum`。Exact sections 为空。

每个 `component_snapshots` 引用固定包含 child page key、snapshot id、publication batch、fingerprint、payload hash、contract/formula version、所选 MetricSnapshot id、metric/chart key、source roles 与 fresh-until。

# Acquisition v2

- BLS JSON、BEA GDP/PIO HTML 与 workbooks、DOL claims 年度 XML、当前 PDF 与不可变 archive PDF、Census MARTS/API、Federal Reserve G.19 和 NY Fed household-credit 响应必须保存 exact HTTP bytes、content type、SHA-256、size、canonical URL、retrieval time 和上游 release identity。
- 每个成功 run 保存一个 content-addressed private evidence-bundle artifact；bundle 内 response role 与 unique blob 数量必须精确符合来源合同，数据库 witness 与 RAW_ARTIFACT_ROOT bytes 必须一致。
- provider、persist 与 selector 共用每种格式的 byte parser。normalized records 必须与 raw replay 精确相等；只保存 URL/hash/size 指针不能满足本合同。
- Observation 和 release-vintage storage 使用 append-only batch identity；同值新 run 不修改旧 batch，同一 run 安全重试幂等。
- 对未来日期、错误 release identity、字段/单位漂移、重复或非有限值、缺少必需系列、尾部回退与 source watermark 回退 fail closed。

## 当前实现证据（2026-07-16）

- 通用 raw-evidence schema v1 使用 canonical manifest 与确定性 ZIP，保存 credential-free canonical HTTPS URL、request/response witness、response role、SHA-256 与 size；重复响应 bytes 去重，未声明 entry、未引用 blob、凭据键、hash/size 或 witness 篡改均拒绝。
- BLS 保留 exact POST JSON response；registration key 不进入 witness。纯 byte parser、private content-addressed artifact、append-only Observation、value-date watermark 与 normalized/transport tamper tests 已实现。
- BEA GDP bundle 固定 `release-page`、`vintage-workbook`、`comparison-workbook`；PIO 固定 `release-page`、`summary-workbook`、`section2-workbook`。动态 workbook URL 从 exact HTML 重新发现，records、GDP supplemental vintages 与 replay metadata 在落库前逐项对账。
- DOL bundle 保存连续年度 `history-xml-YYYY`、`current-release-pdf` 与 `archive-release-pdf`；当前和归档 PDF exact bytes 必须一致，并由 release date 重新推导 archive URL。
- Census API 保存无 API key 的 canonical request witness 和 exact JSON；release workbook 使用互斥的 current-workbook 或 archive-index/archive-workbook 合同。G.19 保存 choose-page/output-csv，HHDC 保存 databank-page/household-debt-workbook。
- 五类 v2 persistence callback 均执行 source/licence/latest-attempt lock、bundle replay、append-only batch、private artifact、watermark及数据库 postcondition；`refresh_official_data()` 与 `refresh_macro_official_data()` 已切换到这些 callbacks。
- GDP 是首个完成的 strict child：11 个 metrics、2 个 charts、1 个 vintage ledger 由显式 BEA run 重建；generic writer 被硬拒绝，专用 selector 支持 current、natural-expiry、transition 与 retained-failure。
- GDP focused tests 覆盖同 run 幂等、同值新 run 新 revision、rogue newer snapshot，以及 raw bytes、Observation、ReleaseVintageObservation、MetricSnapshot、payload 与 licence 任一篡改 fail closed；终审报告 P1/P2 均为零。
- Employment v2 现由一个 exact 24-series BLS JSON run 和一个 DOL XML/PDF evidence-bundle run 原子发布，冻结 11 个 metrics、6 个 charts、2 个 sections 与 CES/CPS/JOLTS/claims 四个逻辑角色。generic core/wrapper 均硬拒绝写入，路由和 economy adapter 只消费专用 selector。
- 14 个 Employment focused tests 与随后完整 suite 已通过，覆盖 raw replay、preliminary `estimated` rows、same-run 幂等、同值新 run 追加 revision、PostgreSQL 安全锁、exact 24-series dataset、rogue snapshot、raw tamper、四种公开状态、GET controls 与 Economy 继承；终审无剩余 P1/P2。
- 严格 BEA PIO postcondition 暴露并修复两条价格指数 series definition 缺口：`BEA-PCE-PRICE-INDEX` 与 `BEA-CORE-PCE-PRICE-INDEX` 现在声明为月频 chain-type price index，不再回退为默认日频。
- Inflation v2 现把 exact canonical 24-series BLS JSON run 与独立节奏的 BEA PIO 三证据包 run 绑定为一个 append-only revision；基础合同冻结 32 metrics、8 charts、2 keyed sections 和 8 个逻辑组件，generic core/wrapper 均拒绝写入。
- Inflation static replay 会逐层校验 raw bytes/hash/role、完整 24-series BLS 与 9-series PIO Observation 批次、OPEN licence、32 条 MetricSnapshot、payload integrity 与 exact run pair；同 pair 幂等，任一新 run id 即使同值也追加 revision。
- Inflation selector 已覆盖 `current_candidate`、`natural_expiry`、`transition_pending`、`retained_failure` 与两小时 transition timeout；精确 dataset 的 DB latest-attempt 查询不会被 unrelated BLS、legacy、demo 或不可重放快照抢占。
- Treasury 5Y/10Y BEI 不再进入 Inflation hashed child；route 只动态叠加 strict real-rates，并携带 child id、batch、fingerprint、payload hash、contract/formula version、component roles 和 annual source roles，字段缺失即不展示。
- 18 个 Inflation focused tests及 Inflation/Economy/refresh wiring 合计 33 个 tests 已通过，覆盖 SA/NSA/PCE-SA 公式、preliminary、tamper matrix、append-only pair、四状态、GET controls、动态 overlay 不落库、Economy strict current-only 与两个 refresh 入口。Consumer 与 strict four-child Economy parent 仍待迁移。
- Correction round 1 发现并关闭四类 P2：strict-looking snapshot 的非 dict 容器可触发异常、publisher 的 run→Source 反向锁序、success selector 后置校验位于发布事务之外，以及 Inflation overlay 未要求 Treasury `current_candidate` 且会被基础页 stale 状态一刀切。相同 rogue-container、锁序和原子发布模式已同步修到 GDP 与 Employment。
- GDP、Employment、Inflation publisher 现在先按 PK 锁 input/internal Source，再按 PK 锁 IngestionRun；Observation 与 GDP release-vintage 使用无 nullable join 的 base-table `FOR UPDATE`。三条 success coordinator 都以外层原子事务覆盖 publish 和 strict selector/current-candidate 后置校验，失败 revision 与 MetricSnapshot 一并回滚。
- retained marker 现区分 `latest-attempt-incomplete`（精确 failed/partial attempts）与 `publication-postcondition`（精确全 SUCCESS attempts）。若已有上一可重放 revision，成功输入因自然过期或 candidate 校验失败不能成为 current，上一版会以可重放 stale marker 保留；后续新成功输入先进入 transition，再原子恢复 current。首轮无上一版时继续 fail closed。
- Inflation route 只组合 `treasury_publication_state=current_candidate` 且组件自身未过期的 real-rates overlay；基础 Inflation 非 current 时仅把严格 32/8/2 标 stale，当前 overlay 保留自身 quality，overlay 过期或 provenance 不完整则整体不展示。
- Correction focused 六文件共 119 tests 通过，新增三合同 malformed-container 回退、Source→run 锁序、PostgreSQL nullable-lock shape、自然过期成功发布回滚/retained/recovery、Inflation 32/8/2 cardinality、registry 零 demo、October exact-month 空档、1Y slicing、全部 tab、导航 GET 参数和 GET 零写入回归。双刷新入口的真实全链 live fixture 仍留待隔离部署验收；Consumer 与 strict four-child Economy parent 仍待迁移。
- Final P2 correction makes same-target natural expiry a true read-only idempotent result for GDP、Employment 与 Inflation：coordinator 在 publisher/`ensure_source` 前确认 exact input target 与 `natural_expiry`，返回 stale key 且不写 Source、revision、MetricSnapshot 或 failure marker；新 target 仍走原子发布或 retained-failure 流程。
- Inflation 与 Employment coordinator 现在对任意非 system publication/builder exception 统一回滚整版，再以 exact latest-success attempts 写入 `publication-postcondition` marker；若旧版不能静态重放则不制造 marker，并原样抛出最初异常。GDP 的普通发布异常继续由 acquisition operational wrapper 转换为 durable FAILED attempt、retained marker 并重抛，保持既有分层契约。
- 所有带 `select_related(source)` 的 IngestionRun/DashboardSnapshot `FOR UPDATE` 均限定 `of=("self",)`；确需 Source 锁的 publisher 仍先按 Source PK，再锁 self-only run，消除 PostgreSQL 隐式 Source 锁与反向锁序。Employment 对 FAILED/PARTIAL 与 RUNNING 混合状态新增同一两小时 timeout：超时 RUNNING fail closed，全部未超时时保持 `transition_pending`。
- Final P2 targeted regression 10/10 与 GDP/Employment/Inflation 三份 focused files 107/107 通过，覆盖三合同 same-target expiry 零写入、Inflation/Employment builder RuntimeError 回滚/retained/recovery、GDP operational exception、joined-lock `of` 形状及 Employment mixed RUNNING timeout。隔离 live 双刷新仍是发布前待办。
- Consumer v2 现已由 Census MARTS release、BEA PIO、Federal Reserve G.19 与 New York Fed HHDC 四个必需 exact run 原子发布，冻结 14 metrics、6 charts、0 sections 和 `official-consumer-four-source-v2` 公式版本；通用 core/wrapper publisher 均硬拒绝 `consumer`。
- Consumer selector 从私有 evidence bundle 重放 provider records，再验证 append-only Observation、MetricSnapshot、OPEN licence、fingerprint、payload hash 与 exact run identity。状态覆盖 `current_candidate`、`natural_expiry`、`transition_pending` 与 `retained_failure`；两小时 RUNNING 边界、terminal+新鲜 RUNNING 混合态、marker 状态突变与原子回滚/恢复均有确定性回归。
- Census API 只在 1992-01 起连续历史与 release 尾部三序列逐项一致时升级为 `complete_history`；同一四源 revision 上 full history 对失败、partial 或语义无效的后续 optional attempt 保持单调，不降级已审计公开版。
- Census release 的当前工作簿失败后保留最多四个按 UTC 月份推导的连续 probe witness；只有 404/410 可继续，403、网络失败、redirect、非 XLSX 200、月份/时间链不匹配均 fail closed。四次 terminal probe 后才可使用 directory index，standalone archive 仅允许诊断重放而被正式持久化拒绝。
- Migration 0020 将旧 Census API 三序列与 Observation/run lineage 转换为 `CENSUS-API-*` 独立身份，保留 parser 大写 `input_series/input_series_id` 与 lineage 小写口径。真实 0019→0020 E2E 证明旧 raw bundle、PK/FK、artifact hash 与 Observation batch 不变，旧 metadata 缺 `retrieved_at` 时仍必须由 raw witness 严格等于 run `fetched_at`才能进入 `complete_history`。
- Consumer route 在 current 与 retained 态都保持 exact 14/6/0 容器与组件级新鲜度；registry 只提供空卡，消费者信心仍为 `PURCHASE_REQUIRED`，不从总量序列推断收入群体压力。Economy parent 只接受 Consumer `current_candidate` 并固定该 child 的完整 revision identity。
- Economy v2 现只从 GDP、Employment、Inflation 与 Consumer 四个 strict selector 组合 4 metrics、4 charts、0 sections；parent 固定完整 child identity、所选 MetricSnapshot、根新鲜度、精确 source/batch union、fingerprint 与 payload hash，不从散乱 Observation 或 generic snapshot 重组。
- Economy 历史重放只读取 reference 固定的 child snapshot；动态状态独立覆盖 current、natural expiry、transition 与 retained failure。strict int/UUID、canonical JSON、marker `reason_sha256`、internal derived/storage licence、实际物化的 MetricSnapshot 行锁及提交边界重选均有确定性测试。
- Economy 已从 generic core、wrapper、bulk publisher 三层硬拒绝，并删除旧 v1 builder、unused coordinator 与 `prepared_economy_data` 旁路；路由 GET 只消费 dedicated selector 且保持零写入。
- Daily Evidence v2 固定 Economy 2 / Liquidity 1 / Rates 2，使用 canonical 三组件、三证据、exact parent/reference/evidence-item schema 与固定 Economy/Treasury 公式身份；历史 Daily v1 与已发布 Thesis 继续按 v1 验证。
- 首页、日报详情、研究任务 dataset/metadata/prompt 已切换到验证后的 daily-evidence v2，同时 UI 仍能按实际验证结果显示历史 v1 标签。真实 Economy v2 parent 经过 production selector 冻结到 Daily v2 的集成接缝已通过。
- 两轮独立终审已关闭 Economy 的伪行锁、数值类型走私、marker 篡改、derived licence 与死代码问题，以及 Daily 的非 canonical 列表、任意公式、宽松 ID 和 dataset 命名问题；最终 Economy 与 Daily 均为 P0/P1/P2 零残余。
- 稳定代码上的 focused 306/306 回归与完整 1,063/1,063 suite 均通过；Ruff、Django check、migration drift、diff check 与 changed-file secret scan 同步全绿。完整 suite 首轮暴露的 3 个失败只是 session demo seed 被绝对计数，断言收窄到 `internal + Economy v2` 后，带 seed 的复现组合与第二次全套均通过。
- HHDC live 精度与历史覆盖修正把 Page 3 Excel 浮点值归一到 15 位有效数字、把 Page 12 `0.00` 比率按 ROUND_HALF_UP 保存，并强制两张表从 `2003:Q1` 到最新季度拥有相同且连续的 93 季集合。Consumer 相关 98 项测试、1302 行 live provider 与临时 SQLite byte-replay/persistence 均通过。
- HHDC 修正后的完整 suite 通过 1,115/1,115 项，Ruff、Django check、migration drift 与 diff check 同步通过。最近一次隔离宏观刷新已证明 GDP、PIO、G.19 与 HHDC 可成功持久化，其中 HHDC 为 1,302 行；Census recent archive 的 rank-1 请求发生一次 20 秒 read timeout，随后 provider-only 立即重试 3/3 成功，说明下一步是同一候选 URL 的有界瞬时 transport retry，而不是放宽 403、redirect、malformed 200 或 404/410 顺序证明。隔离 live/browser gate 仍待本 milestone 最终验收。
- Census MARTS release transport retry 已实现：瞬时 `httpx.TransportError`（超时、连接重置）与瞬时状态集合 {429, 500, 502, 503, 504} 在同一 URL 上有界重试，上限三次总尝试、单调退避（1s/3s）。成功 200 与证明链终态 403/404/410 为精确 evidence 状态，立即返回、不重试，因此重试循环不会改变持久化状态或削弱 fail-closed 证明链；只有最终尝试的 bytes 与 `retrieved_at` 被持久化。13 个确定性重试测试覆盖瞬时状态恢复、read/connect 超时恢复、重试后 probe 回退、耗尽即 fail-closed、终态零重试与有界单调退避。
- 隔离 live 宏观刷新确认 Census release provider 现可从瞬时 transport 故障恢复（retail_release 到达 success），且 GDP 发布为 fresh。同一隔离运行复现了一个 pre-existing 的 consumer publication-postcondition 失败，该失败为上游数据缺口而非回归：2026-07-16 唯一已发布的 Census MARTS 工作簿为 `rs2605.xlsx`（2026 年 5 月数据），其月度 fresh-until 窗口（5 月底 + 46 天）在 2026-07-15 到期，因此首次 consumer 发布正确 fail-closed，不发布过期数据。此 live 数据新鲜度边界及其导致的 macro 刷新在 consumer 协调前中止，与 Census retry 工作分离，未被掩盖。
- 完整 suite 在本批改动后通过 1,128/1,128 项（基线 1,115 + 13 个新增 Census retry 测试），Ruff、Django check、migration drift 与 diff check 同步通过。本地服务 11 个必需路由（healthz、首页、四个 economy 子页与父页、data-sources、search、manifest、offline）全部返回 200，页面在无已发布快照时正确渲染 needs_source/stale/transition 缺口状态而不产生 500。隔离 live/browser gate 的最终完整闭环仍受上述 consumer 新鲜度边界约束。

# 发布与选择

- 五个 key 加入 independent 与 append-only publication 集合；generic publisher 明确拒绝写入。
- 四个 child 各自冻结 contract version、formula version、exact metric/chart/section keys、component runs、artifact witnesses、semantic manifest、fingerprint 与 payload-integrity hash。
- selector 从私有 bytes 逐层重验 run、append-only observations、页面组件、MetricSnapshot、许可、fingerprint 和 hash。
- selector 状态区分 `current_candidate`、`natural_expiry`、`transition_pending` 与 `retained_failure`；新成功输入尚未发布时旧版不能继续冒充 current。
- `daily-evidence`、首页与每日研判只消费 strict economy parent，不绕过 selector 读取 generic child。

# 数据源与采购边界

- 已有免费官方源：BEA GDP/PIO、BLS CES/CPS/JOLTS/CPI/PPI、DOL ETA claims、Census MARTS、Federal Reserve G.19、New York Fed Household Debt and Credit。
- Treasury 5Y/10Y BEI 继续作为透明政府曲线代理；真实交易 breakeven、inflation swaps 和 5Y5Y 另行找源或采购。
- 消费者信心建议向 Conference Board 或 University of Michigan 核对公开网站展示与历史存储授权；未授权前保持零数字采购合同。
- 完整 CPI/PPI vintage 优先评估 BLS release archive、ALFRED 可覆盖部分与自建 release-time archive；当前通用 Observation 不能替代该能力。

# Acceptance criteria

- [x] 五页 exact metric/chart/section、source component、formula 和 freshness 合同已冻结并有确定性测试。
- [x] 所有必需官方 acquisition 保存 exact private bytes，能够从 artifact 独立重放 normalized records。
- [x] macro observations 与 GDP release vintages append-only；同值新 run 不覆盖旧 batch，安全重试幂等。
- [x] 四个 child 与 economy parent 使用 dedicated append-only publisher 和 strict selector；generic、legacy、demo、fallback 与 rogue snapshots 被拒绝。
- [x] raw file、artifact、run、Observation、payload、MetricSnapshot、licence、fingerprint 和 hash 的篡改均 fail closed。
- [x] current、自然过期、刷新中、失败保留和新成功未发布状态有确定性测试。
- [x] economy parent 只引用四个 strict child；daily-evidence 与首页/日报不绕过 parent。
- [x] 所有找不到或未获公开权的数据在对应页面和总台账显示 `NEEDS_SOURCE`、`LICENSE_REVIEW` 或 `PURCHASE_REQUIRED`，无合成数字。
- [ ] 隔离临时库完成全套 live 官方刷新、第二次 append-only revision、五路由 smoke 与 1440/390 浏览器验收。
- [x] Ruff、完整 pytest、Django check、migration drift、diff 和 secret gate 通过。

# Verification plan

- Canonical: `.venv/bin/ruff check .`, `.venv/bin/pytest -q`, `.venv/bin/python manage.py check`。
- Additional: `git diff --check`、`.venv/bin/python manage.py makemigrations --check --dry-run`、source-specific replay fixtures、same-value second refresh、tamper matrix、rogue snapshot tests、daily-evidence tests、isolated live refresh、route smoke、1440/390 browser/console。
