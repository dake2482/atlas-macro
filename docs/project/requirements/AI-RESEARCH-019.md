---
schema_version: 1
id: AI-RESEARCH-019
project_id: AI-RESEARCH
title: 联储官方美元参考与央行互换后盾精确双源公开合同
status: REVIEW
priority: P1
executor: codex
task_id: atlas-global-dollar-official-alignment-20260714
branch: main
worktree: local
dependencies:
- AI-RESEARCH-017
- AI-RESEARCH-018
updated_at: '2026-07-14T16:40:54+08:00'
next_action: Run the deferred 1440/390 browser visual and console gate after the official Browser Plugin runtime regression is fixed; commit, push and deployment remain separately authorized.
evidence:
- The current `/liquidity/global-dollar/` route accepts an unversioned generic snapshot with no payload hash or immutable swap artifact and still returns HTTP 200 as fresh.
- The generic publisher exposes only total and small-value swap balances and can publish same-named series from the wrong dataset; the existing regression test explicitly permits that bypass.
- The page registry still describes cross-currency basis and contains legacy basis-shaped values and an action recommendation even though no licensed basis source is connected.
- Federal Reserve H.10 provides the official nominal broad dollar index and three daily reference FX series; these are reference data, not ICE DXY, executable spot, forward points or cross-currency basis.
- The New York Fed Markets API provides individual U.S.-dollar liquidity-swap operations, including settlement, maturity, counterparty, amount, rate and small-value status, from which Atlas can transparently calculate current outstanding balances.
- Two independent read-only audits agreed that H.10 and New York Fed swaps are the only mandatory v1 inputs; H.4.1 SWPT is an optional weekly witness, while BIS GLI, IMF COFER and Treasury TIC belong in a later structural component.
- The dedicated v1 implementation now publishes only two exact official inputs, nine metrics, three charts and three rendered sections; the generic publisher and wrong-dataset aliases cannot publish this key.
- A clean temporary database fetched the live H.10 archive with 38,896 observations (37,323 valid A and 1,573 ND) and 1,540 New York Fed swap operations, stored two immutable private artifacts, wrote nine exact MetricSnapshots and returned HTTP 200 through the dedicated selector.
- Full canonical validation passed with 720 tests; the adjacent publication-chain review passed 128 tests and reported P0=0, P1=0 and P2=0. Ruff, Django system check, migration drift and git diff checks are clean.
- The Browser Plugin 26.707.71524 fails during its official import because it attempts to redefine the runtime's non-configurable process property. The 1440/390 visual and console gate remains explicitly unexecuted; no substitute browser harness is counted as acceptance evidence.
started_at: '2026-07-14T15:36:09+08:00'
---

# 目标

把 `/liquidity/global-dollar/` 从无版本、跨批次的通用拼装页升级为独立、可复算、失败可见的 v1 公开合同。页面保留“全球美元”导航名，但语义收窄为“联储官方美元参考与央行互换后盾”：只发布 Federal Reserve H.10 参考序列、New York Fed 美元流动性互换直接字段，以及 Atlas Macro 可从精确原始批次复算的透明派生值。

本页面不得声称完整衡量离岸美元融资压力，不生成压力分数、交易信号或行动建议。H.10 不是 ICE DXY、可交易现货或远期；央行互换使用量不是 cross-currency basis 或市场融资价格。

# 页面合同

## 必需输入

两个输入分别使用各自最新 attempt 和最新成功 exact batch，不强迫同一刷新周期或同一 value date：

- `federal-reserve / h10`：必须包含且只按合同使用 `JRXWTFB_N.B`、`RXI$US_N.B.EU`、`RXI_N.B.CH`、`RXI_N.B.JA` 四个 Board series。
- `ny-fed-markets / fx-swaps:usdollar`：必须来自 USD liquidity-swap search 响应，保留完整操作字段和明确的检索覆盖窗口，不再依赖会饱和的 `last/500` 作为完整性证明。

每个成功 run 必须各保存且只保存一个内容寻址的私有 `RawArtifact`。H.10 artifact 是实际 ZIP bytes，而不是会变化的 latest URL 加哈希指针；其 SHA-256、字节数、content type、唯一 `H10_data.xml` member 及 member SHA 均可重新校验。NY Fed artifact 是经过校验的精确 JSON response bytes。

## 必需指标

指标 exact set 为九项：

- `h10-broad-dollar`：Nominal Broad Dollar Index，January 2006 = 100。
- `h10-broad-dollar-5d-change-pct`：最近 5 个有效观察间隔的百分比变化。
- `h10-eurusd`：U.S. dollars per euro。
- `h10-usdcny`：Chinese yuan per U.S. dollar。
- `h10-usdjpy`：Japanese yen per U.S. dollar。
- `fxswap-usd-outstanding`：当前全部在途美元互换。
- `fxswap-usd-outstanding-non-small-value`：剔除 small-value 技术测试后的在途额。
- `fxswap-usd-outstanding-small-value`：仅技术测试在途额，至少保留两位小数，不能把 0.05 USD mn 显示成 0。
- `fxswap-active-counterparties`：当前非技术测试在途操作涉及的唯一央行数。

透明公式：

- `5D change % = 100 × (V_t / V_t−5 − 1)`，只用同一 H.10 exact batch 的有效 A 状态观察值，不填周末或 ND/NA。
- `Outstanding(as_of) = Σ amount_i / 1,000,000`，其中 `settlementDate_i ≤ as_of < maturityDate_i`。
- `Regular outstanding = Σ active_i[isSmallValue=false]`。
- `Technical-test outstanding = Σ active_i[isSmallValue=true]`。
- `Total outstanding = Regular outstanding + Technical-test outstanding` 必须精确对账。
- `Active counterparties = count(distinct counterparty_i)`，只纳入 active non-small-value operations。

H.10 四项直接值标记为官方 direct/fresh；5D 变化和全部互换余额/计数标记为 Atlas Macro transparent derived/estimated，并保留 formula、calculation owner、全部 input lineage 和 acquisition artifact hash。

## 图表与表格

图表 exact set 为三项：

- `global-dollar-broad-dollar-history`：同一 H.10 batch 的最近 260 个有效观察日。
- `global-dollar-major-fx-usd-strength-rebased`：最近 120 个共同有效日期、基期 100；EUR leg 使用 `1 / EURUSD`，CNY 与 JPY 使用直接 USD quote，明确只是 H.10 参考序列的方向统一比较。
- `global-dollar-swap-drawdowns`：按 settlement date 展示 non-small-value 与 small-value drawdown，不把每次刷新时重算的 current outstanding 拼成伪官方历史。

section exact set 为三项，且表格必须实际渲染 `cells_list`：

- `active-usd-liquidity-swap-operations`：当前 active 操作的 counterparty、trade、settlement、maturity、term、rate、USD mn amount 与 technical-test 状态；regular 与 small-value 明确分区。
- `source-freshness-methodology`：逐组件显示 observation/prepared/as-of/fetched/fresh-until、batch、artifact、quality、licence 和 fallback，不用单一 page timestamp 掩盖异频。
- `licensed-market-data-gaps`：九行 `EUR/USD`、`USD/JPY`、`USD/CNH` × `1M/3M/1Y` basis 采购矩阵，全部为 `PURCHASE_REQUIRED`，不显示伪数值；同时说明 executable dealer quotes、forward points、implied funding、ICE DXY 与 order book 的授权边界。

# 完整性、时效与失败保留

- H.10 provider 必须拒绝 duplicate archive member、duplicate series、duplicate series/date、缺少必需 series、畸形/未来 observation、错误状态或 quote convention、Prepared future/regression、ZIP bomb、hash/size/member hash 不一致。历史 ND/NA 可保留，但四个 series 的最新有效观察必须齐全。
- H.10 新鲜度按 Board 每周发布节奏计算，至少同时检查 fetch age、Prepared 和每个 series 的 latest valid observation age；不能继续套用 generic `value_date + 4 days`。
- NY Fed provider 必须拒绝非 mapping 行、错误 operation type/currency、空 counterparty、非规范日期、`trade > settlement`、`settlement ≥ maturity`、term 不一致、非有限或负金额/利率、未知 small-value 标记和自然键重复；任何坏行整批失败，不得 silent skip。
- 生产刷新使用官方 search endpoint 的显式完整历史窗口，保存 start/end/dateType/returned count；页面从同一 raw batch 重算 active set、partition、counterparty totals 和 drawdowns。无 coverage proof 不发布。
- NY Fed 每日轮询；fresh-until 使用 fetched_at 加有限 grace。旧 raw 在上游失败后不得每天重新滚动 as_of 冒充新鲜。
- 两组件各自最新 attempt 必须为 success、非空、未 supersede、当前 licence 允许 public display；派生值还要求 derived display，artifact 要求 historical storage。禁止 demo、fallback、partial 和未知 source。
- 任一必需源 timeout、latest failure、partial、schema drift、coverage failure、artifact 丢失/篡改、future/regression、许可撤销、公式/表格/hash/MetricSnapshot 篡改时，不发布半成品；上一版完整快照仅在 embedded contract 可独立重验后以 stale 保留，并写结构化 `refresh_failure`。
- 无关 BLS、BEA、Treasury、RSS 等 source 的成败不得阻塞本页面。

# 发布与选择合同

新增 `GLOBAL_DOLLAR_CONTRACT_VERSION = 1`、独立 coordinator/publisher/selector，并将 `global-dollar` 从 generic `CORE_PUBLICATION_KEYS` 移除、加入 `INDEPENDENT_PUBLICATION_KEYS`。generic publisher 无法写入该 key；wrong dataset 的同名 series 无法发布。

payload 至少包含 contract version、formula version、input runs、component batches/dates、private artifact refs、required metric/chart/section sets、component source keys、publication batch、semantic fingerprint、exact payload integrity hash 和 refresh failure。两层 publication hash 与两个 acquisition hash 分开：

1. semantic fingerprint 覆盖可复算页面语义和组件血缘；
2. payload integrity hash 覆盖完整 payload，只排除顶层自身字段与顶层 `refresh_failure`，不得递归忽略同名嵌套字段；
3. raw JSON/ZIP 及 H.10 member SHA 覆盖采集原件。

所有九项 `MetricSnapshot` 必须 exact match label、value、display、change、unit、source、dates、quality、licence、fallback、input lineage、两个 publication hashes 和 component acquisition hash。selector 必须从 referenced DB runs、private bytes 和 exact observations 重新验证 required sets、公式、图表、表格、notice、hash 和 normalized rows，不能只相信 JSON 自述。

# 数据源与边界

- H.10：[Federal Reserve H.10 Foreign Exchange Rates](https://www.federalreserve.gov/releases/h10/about.htm) 与 [Data Download Program](https://www.federalreserve.gov/datadownload/Choose.aspx?rel=H10)。
- 美元央行互换：[New York Fed Central Bank Swap Arrangements](https://www.newyorkfed.org/markets/international-market-operations/central-bank-swap-arrangements)、[Markets API](https://markets.newyorkfed.org/static/docs/markets-api.html) 与 [Terms of Use](https://www.newyorkfed.org/privacy/termsofuse)。
- H.4.1 `SWPT` 仅作为 v1.1 可选周三核验项；若公开数值，必须先升级成私有 exact artifact，并按同一周三重算 NY Fed total 后以约 0.5 USD mn 的取整容差对账。
- BIS GLI、IMF COFER 与 Treasury TIC 是后续低频结构性组件，不是 basis 或实时融资价格，不阻塞 019。
- 1M/3M/1Y cross-currency basis、FX swap implied USD funding、forward points、dealer bid/ask、depth/order book 与 ICE DXY 保持 `PURCHASE_REQUIRED`，候选为 LSEG/Bloomberg Enterprise、CME EBS、Cboe FX 或 ICE，并须取得 public/derived display rights。
- 不复制比较站 HTML/CSS、文案、私有 API、历史库、不透明评分或交易建议。

# Acceptance criteria

- [x] H.10 四序列严格校验并保存真实 private ZIP artifact、archive/member hashes 和完整 exact batch；部分/畸形/回退 release 失败关闭。
- [x] NY Fed USD swap 使用完整 search coverage，坏行整批失败，并保存一个 private raw JSON artifact；total/regular/small/counterparty/active boundary 全部可复算。
- [x] 建立 global-dollar v1 独立 coordinator，generic publisher 与 wrong-dataset same-name series 无法写入该 key。
- [x] 九项指标、三张图、三张表满足 exact set、公式、精度、异频时效、血缘、许可、fallback 和 PURCHASE_REQUIRED 合同。
- [x] 建立专属 public selector，重验 latest attempts、artifact bytes、required sets、公式、双 publication hash、acquisition hash、normalized MetricSnapshot 和 embedded stale lineage。
- [x] 任一输入失败、partial、schema 漂移、过期、许可撤销、fallback、混批、未来/回退、覆盖不足或篡改时，只保留可独立重验的上一完整 stale 快照；同值恢复也更新 run/batch/artifact lineage。
- [x] H.10 与 main official refresh、Celery task 和 management command 分别触发 coordinator，并在 global-dollar v1 无法发布或保留时 fail loudly；无关 source failure 不阻塞。
- [x] registry 删除 legacy basis 数字和行动建议；页面明确显示“不是 ICE DXY/不是跨币种基差”、small-value 技术测试与授权数据缺口。
- [x] 数据覆盖台账拆分 H.10 LIVE、央行互换 LIVE、H.4.1 witness NEEDS_SOURCE、BIS/COFER/TIC 后续结构组件和商业 basis/微观数据 PURCHASE_REQUIRED。
- [x] Ruff、720 项完整 pytest、Django check、迁移漂移、`git diff --check`、干净临时库真实刷新与路由 smoke 通过。
- [ ] 1440/390 浏览器视觉、交互与 console 验收通过；当前被官方 Browser Plugin 运行时回归阻断，未以其他工具冒充通过。

# Verification plan

- Canonical: `.venv/bin/ruff check .`, `.venv/bin/pytest -q`, `.venv/bin/python manage.py check`。
- Additional: `git diff --check`、migration drift、provider raw-byte/hash/member tests、search coverage 与 partition tests、latest-attempt failure/recovery/concurrency tests、双 hash 与 exact MetricSnapshot tamper matrix、clean temporary official refresh、rendered table route smoke、desktop/mobile browser and console inspection。
