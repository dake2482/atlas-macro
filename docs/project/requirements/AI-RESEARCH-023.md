---
schema_version: 1
id: AI-RESEARCH-023
project_id: AI-RESEARCH
title: H.10 外汇实现波动率与六路由零伪数合同
status: REVIEW
priority: P1
executor: codex
task_id: atlas-volatility-h10-rv-alignment-20260715
branch: main
worktree: local
dependencies:
- AI-RESEARCH-009
- AI-RESEARCH-021
- AI-RESEARCH-022
updated_at: '2026-07-15T19:43:41+08:00'
next_action: Review draft PR #1 together with the completed AI-RESEARCH-023 evidence. The product patch is committed locally and published to the independent public snapshot branch; production deployment remains separately authorized.
evidence:
- All six volatility routes currently have no strict real-data snapshot; the overview, panorama and VIX registry entries still carry prototype VIX, MOVE, VIX9D, VXTLT and 30-index-map values.
- The H.10 acquisition chain already retains a private content-addressed ZIP, validates the unique XML member, preserves observation batches and independently replays exact observations.
- The latest local H.10 run contains the four required official series and enough history to calculate transparent 20-day and 60-day realized volatility without interpolation.
- Current Treasury annual curve ingestion records a response hash but does not retain private XML bytes, and same-year refreshes update prior Observation batch lineage. It therefore cannot yet support retained strict yield-volatility snapshots.
- VIX-family, CFE term structure, ICE MOVE, FX ATM IV/risk reversal/butterfly and cross-asset IV-RV products require explicit storage, derived-display and public website-display rights.
- The dedicated fx-vol v1 publisher, selector and coordinator now replay the exact H.10 ZIP/member/Observation batch, validate four metrics, two 260-point charts, three tables, four MetricSnapshot rows, title/summary, licence decisions and payload hashes, and fail closed for malformed or unreadable artifacts.
- An isolated live H.10 acceptance ingested 37,323 official observations from a 2,072,667-byte content-addressed archive, published snapshot as-of 2026-07-10 with four metrics and two 260-point charts, and served all six volatility routes with no demo or fallback data.
- Exact-320 common-level input, natural expiry, transition pending, terminal failure retention, marker chronology, append-only same-value refresh, rogue payloads and raw/parser errors have deterministic regression coverage.
- Five unsupported routes now ignore rogue database snapshots, render zero metrics and zero charts, and expose structured source/licence/purchase contracts. Static LIVE claims were replaced by CONTRACT_READY because actual availability belongs to the strict child selector.
- Browser acceptance at 1440x900 and 390x844 passed chart/filter rendering, wide-table containment, drawer state, mobile footers, no page overflow and an empty warning/error console; route tests additionally verify VIX/panorama navigation state and the internal FX child link.
- Independent final review reported P0=0 and P1=0; both remaining P2 observations were subsequently corrected with display-copy marker cleanup and complete H.10 replay exception handling.
- Ruff, the complete 863-test pytest suite, Django system check, migration drift, diff whitespace and changed-file secret gates pass. Local product commit `a54f60f99eb7925a634f3820217d195af5c24768` is mirrored as patch-identical public commit `37b8aaecc0f016f1bdfed14e3956aae1cb80aa8d` in draft PR #1 on `dake2482/atlas-macro-platform`; internal governance files are excluded.
started_at: '2026-07-15T17:20:36+08:00'
---

# 目标

把 `/volatility/`、`/volatility/dashboard/`、`/volatility/vix/`、`/volatility/move/`、`/volatility/fx-vol/` 与 `/volatility/implied-vs-realized/` 从原型或泛化空态升级为明确的数据合同。

v1 只在 `/volatility/fx-vol/` 发布可由 Federal Reserve H.10 精确重放的外汇参考序列实现波动率。其余五页保持 HTTP 200、canonical、导航、sitemap 与结构化采购说明，但无任何指标卡、图表、fallback 或静态原型数字。页面不得把实现波动率命名为隐含波动率，不得把财政部收益率变化命名为 MOVE，也不得从 ETF、新闻或终端可见值拼装专有指数。

# 六路由合同

## `/volatility/fx-vol/`：唯一数值页

输入为 latest successful non-empty `federal-reserve / h10` exact run，复用 AI-RESEARCH-019/021 的 ZIP、member、series、Observation、许可和 freshness 验证。精确四系列：

- `h10-broad-dollar`：Nominal Broad Dollar Index。
- `h10-eurusd`：U.S. dollars per euro。
- `h10-usdcny`：Chinese yuan per U.S. dollar。
- `h10-usdjpy`：Japanese yen per U.S. dollar。

四系列必须有至少 320 个共同有效日期。周末和节假日按相邻有效观察计算；不插值、不前值填充、不补零。FX level 必须有限且严格大于零。

对窗口 `N=20` 或 `N=60`：

`RV_N = 100 × sqrt(252) × sample_std(ln(P_t / P_{t-1}))`

每个 RV 点精确使用 `N+1` 个 level 和 `N` 个 log return，sample standard deviation 分母为 `N-1`。Broad Dollar 与三个 reference pair 分别计算；EUR/USD 报价方向保持官方语义，倒数只改变 return 符号而不改变 sample standard deviation，不得将其标签改成 USD/EUR。

### Exact metrics

四项当前 20D 年化实现波动率：

1. `h10-broad-dollar-rv20`
2. `h10-eurusd-rv20`
3. `h10-usdcny-rv20`
4. `h10-usdjpy-rv20`

主值单位为 `% annualized`、`quality_status=estimated`、`source_key=internal`；change 为相对前一共同有效日期的 `RV20_t - RV20_t-1`，单位 pp。metadata 必须保存公式、窗口、年化因子、sample standard deviation、当前/前一窗口日期、exact input run/batch/artifact、四系列官方报价方向、Federal Reserve 与 internal licence，以及 `fallback_source=None`。

### Exact charts

1. `h10-fx-realized-volatility-20d`：最近 260 个共同日期的四系列 20D RV。
2. `h10-fx-realized-volatility-60d`：最近 260 个共同日期的四系列 60D RV。

每个点保存 series、window start/end、sample count、run/batch、ZIP/member hash、source keys、licence、quality、fetched/fresh-until 与 fallback。图表可以使用 compact window lineage，但 selector 必须从嵌入 run 重新计算全部 520×4 数值。

### Exact sections

1. `latest-h10-realized-volatility`：四行，列顺序 `reference, rv-20d, rv-60d, change-20d-pp, value-date, quote-convention, quality, batch`。
2. `h10-rv-source-methodology`：一行，列顺序 `source-dataset, run-batch, prepared, fetched, common-latest-date, fresh-until, archive, member, common-observations, formula, licence, fallback`。
3. `licensed-fx-volatility-gaps`：列顺序 `market-data, status, public-value, purchase-guidance`；列出 ATM IV、25Δ risk reversal、butterfly、可执行 spot/forward/NDF 与授权历史行情。

GET 参数：`period=3m|1y`、`tab=20d|60d`。非法值归一化；参数只裁剪已发布 260 点，不改变公式窗口。

## `/volatility/vix/`：prose-only

零指标、零图表。结构表解释 VIX index close、VIX9D/VIX3M/VXTLT、CFE VX futures、SPX option-derived IV 与 SPX/SPY realized volatility不是同一口径。采购候选为 Cboe Global Indices Feed、Cboe DataShop 与 CFE market data，合同必须覆盖历史存储、网站展示和派生展示。

## `/volatility/move/`：prose-only

零指标、零图表。ICE MOVE 是授权的 Treasury option implied-volatility index。Treasury par-yield change RV 只能在 Treasury 原始 XML 私有存储、年度 observation append-only 和 strict retained selector 完成后作为 Atlas 自有代理发布，并明确“不是 MOVE、不是债券价格波动率、不是隐含波动率”。

## `/volatility/implied-vs-realized/`：prose-only

零指标、零图表。没有授权 IV 或 option chain 时不计算 `IV-RV`、variance risk premium、skew 或 percentile。标的行情和期权链必须同批次、同日历、同 tenor，并具有历史存储及公开派生展示权。

## `/volatility/` 与 `/volatility/dashboard/`：coverage-only

零指标、零图表，不显示“风险低/中高”“升温/降温”“30 Index Map”或跨资产判断。两页用结构化 coverage ledger 展示：

- H.10 FX realized volatility：LIVE，链接 `/volatility/fx-vol/`。
- Treasury yield-change RV：NEEDS_SOURCE，先完成 strict Treasury acquisition upgrade。
- VIX/CFE、MOVE、FX IV、option IV-RV：PURCHASE_REQUIRED。

在至少两个异资产严格 child snapshot 可独立重验前，不发布跨资产分数、状态或 parent composite。

# 发布与选择合同

新增 `FX_VOL_CONTRACT_VERSION = 1` 与 `FX_VOL_FORMULA_VERSION = "federal-reserve-h10-realized-vol-v1"`。

`fx-vol` 使用 dedicated builder/coordinator/publisher/selector，并加入 generic publication 排除集合。旧无版本、demo、fallback、legacy 或 rogue snapshot 永不进入公开选择。发布为 append-only：同一 run 重试幂等；新的成功 run 即使数值相同也创建新 revision 和四条 MetricSnapshot；不可原地升级旧快照。

payload 保存 exact metric/chart/section sets、formula map、input run、ZIP/member artifact、component dates、source/license decisions、publication batch、semantic boundary、content fingerprint 与 exact payload integrity hash。只有顶层 structured `refresh_failure` 可以排除在 immutable hash 外。

selector 必须重新验证 embedded H.10 run、私有原始 bytes、ZIP/member hashes、exact observations、公式结果、MetricSnapshot rows、current licences 与 payload hash。latest attempt 状态语义：

- same successful run：`current_candidate`。
- newer RUNNING：上一完整版本仅作为 `transition_pending`。
- newer FAILED/PARTIAL/zero-row：上一完整版本可作为 `retained_failure` 并显示组件级失败。
- newer successful run：旧版本不得继续被选为 current；coordinator 必须发布新 revision 或 loudly fail。
- 自然过期只标 stale，不伪造 ingestion failure。

# Treasury 前置缺口

利率实现波动率启用前必须另立 requirement 完成：

1. `TreasuryRatesProvider` 返回 exact raw XML bytes。
2. 每个 annual run 保存 private content-addressed RawArtifact，URI/hash/size 可重放。
3. 年度 Observation 使用 preserve-batches append-only 语义；同年重抓不覆盖旧 batch。
4. XML 重放与 normalized rows exact 对账。
5. Treasury page 与未来 yield-change RV 均使用 dedicated strict selector。

完成前，Treasury 公式可以进入测试与文档，但不能进入公开数字页。

# 数据采购边界

- VIX/VIX9D/VIX3M/VXTLT 与 VX futures：Cboe Global Indices Feed、Cboe DataShop、CFE market data。
- MOVE：ICE Data Indices。
- FX ATM IV、risk reversal、butterfly、forward/NDF：LSEG、Bloomberg、CME FX/CVOL 或其他具外部展示权的产品。
- 跨资产期权 IV/Greeks：OPRA/Cboe 或授权 consolidated feed，加具缓存、历史存储与 derived display 权的 underlying bars。

网页可见、FRED 转载、媒体引用、终端席位或单笔公开成交都不自动授予批量存储和公开再分发权。

# Acceptance criteria

- [x] 删除六路由全部 VIX/MOVE/VIX9D/VXTLT/30-index prototype 数字与风险判断。
- [x] `fx-vol v1` 从 exact H.10 run 计算四项 RV20、两张 260 点 RV chart 和三张 exact section table。
- [x] 20D/60D sample standard deviation、年化、相邻有效观察与无插值公式测试通过。
- [x] H.10 raw ZIP/member/Observation/licence、payload/hash 和四条 MetricSnapshot 可独立重验，所有篡改 fail closed。
- [x] generic publisher、旧/rogue snapshot、demo、fallback 与无版本快照不能写入或进入 `fx-vol` 公开选择。
- [x] VIX、MOVE、IV-RV、overview、dashboard 五页均为结构化 prose/coverage-only，零 metric、零 chart、零 ECharts canvas。
- [x] 六路由、GET 归一化、canonical、sitemap、数据覆盖台账和采购说明有合同测试。
- [x] Ruff、完整 pytest、Django check、migration drift、diff 与 secret gate 通过。
- [x] 隔离临时库重用 live H.10 原始链发布严格 `fx-vol v1`，并完成 1440/390 Browser Plugin 验收。

# Verification plan

- Canonical: `.venv/bin/ruff check .`, `.venv/bin/pytest -q`, `.venv/bin/python manage.py check`。
- Additional: `git diff --check`、`.venv/bin/python manage.py makemigrations --check --dry-run`、公式向量测试、H.10 raw replay、tamper/failure/recovery matrix、generic-writer bypass、isolated live H.10 route smoke、1440/390 browser and console checks。

# 验收结果

- Live run: `federal-reserve / h10`, run `1`, batch `83a95084-bfa5-442e-911c-f8d7cabd5cc5`, 37,323 observations, latest common value date `2026-07-10`.
- Raw artifact: SHA-256 `e914d23476f4ab36749f5faf239e731bbb48fbcad5918615861a0d7d008ac995`, 2,072,667 bytes; private file size and digest matched the database record.
- Publication: snapshot id `2`, four MetricSnapshot rows, two charts × 260 points, exact tables with 4/1/5 rows, no fallback and no stale dashboard key.
- UI: six HTTP 200 routes; 3m/1y and 20d/60d controls; desktop/mobile no page overflow; table-local horizontal scroll; mobile drawer and console checks passed.
- Validation: complete pytest suite passed; Ruff, Django check, no migration drift, `git diff --check`, and changed-file secret scan passed.
