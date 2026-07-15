---
schema_version: 1
id: AI-RESEARCH-018
project_id: AI-RESEARCH
title: 纽约联储公开市场操作精确批次公开合同
status: REVIEW
priority: P1
executor: codex
task_id: atlas-open-market-operations-alignment-20260714
branch: main
worktree: local
dependencies:
- AI-RESEARCH-014
- AI-RESEARCH-017
updated_at: '2026-07-14T15:21:47+08:00'
next_action: Re-run the 1440/390 browser visual acceptance after the Browser Plugin runtime regression is fixed; keep commit, push and deployment separately authorized.
evidence:
- The route `/liquidity/operations/` currently has no contract version or dedicated public selector and is rebuilt by the generic publisher from latest rows across unrelated batches.
- The current generic page exposes only ON RRP, legacy SRP/SRP rate and SOMA total with one SOMA chart; it omits Treasury outright purchases, 30-day totals and recent-operation tables promised by the page family.
- The legacy SRP headline can include small-value technical exercises even though the exact Standing Repo provider now exposes separately reconciled non-small-value series.
- The generic core publisher can republish operations whenever any unrelated core run succeeds, without requiring the page's own latest attempts, one refresh cycle, immutable raw artifacts or a complete required metric/chart/table set.
- New York Fed Markets API provides public official Treasury outright purchase results, fixed-rate ON RRP results, full-allotment Standing Repo results and weekly SOMA summaries. The result feed does not reliably identify RMP-only versus agency-principal reinvestment purchases.
- Two independent read-only audits selected operations ahead of global-dollar because all core operations inputs can be closed with free official data, while cross-currency basis remains a commercial-data requirement.
- A clean temporary SQLite database and independent artifact root completed the four live New York Fed runs with 100 / 955 / 1320 / 2340 rows and exactly one immutable RawArtifact per run.
- The live coordinator published one strict operations v1 snapshot with 10 metrics, 3 charts, 2 sections, 20 + 20 rendered operation rows and 10 exact normalized MetricSnapshot records; the strict selector passed and the route returned HTTP 200.
- Final verification passed 697 tests, Ruff, Django system checks, migration drift and `git diff --check`. The 1440/390 browser visual acceptance remains unexecuted because Browser Plugin 26.707.71524 fails during its supported runtime import.
started_at: '2026-07-14T14:31:50+08:00'
---

# 目标

把 `/liquidity/operations/` 从跨批次通用拼装页升级为独立、可复算、失败可见的 v1 公开合同：展示纽约联储国债二级市场购买、ON RRP、剔除技术测试后的 Standing Repo Facility（SRF）和 SOMA 周度持仓，只发布官方直接值与 Atlas Macro 透明派生值。

# 页面合同

## 必需输入

四个输入必须来自同一次 `refresh_cycle_id`，且每个数据集的最新 attempt 都是当前成功 exact batch：

- `ny-fed-markets / treasury:purchases`
- `ny-fed-markets / repo:reverse-repo-fixed-results`
- `ny-fed-markets / repo:standing-repo-full-allotment-results`
- `ny-fed-markets / soma:summary`

四个成功 run 必须各保存且只保存一个内容寻址的私有 `RawArtifact`，其 SHA-256、字节数与 provider 验证过的原始响应完全一致。不同频率的 value date 不强行对齐；页面和每个组件分别显示 value/as-of/fetch time。

## 必需指标

- 最新国债二级市场购买接受额（官方结果合计，可能包含操作准备测试）。
- 最近 30 个自然日国债二级市场购买接受额（同一官方口径）。
- ON RRP 非 small-value 接受额、操作利率和参与交易对手数。
- SRF 非 small-value 接受额、唯一操作利率和最近 30 个自然日激活天数。
- SOMA 总持仓及相邻两个官方周度观察值的变化。

## 透明公式与分类

- `Latest Treasury purchases = Σ accepted`，取最新官方操作日、`operationDirection=P` 且 `auctionStatus=Results` 的全部操作。
- `30D Treasury purchases = Σ accepted(d)`，`d ∈ [latest operation date−29d, latest operation date]`。
- `ON RRP regular accepted = Σ non-small-value totalAmtAccepted / 1,000,000`。
- `SRF regular accepted = Σ non-small-value totalAmtAccepted / 1,000,000`。
- `SRF active days 30D = Σ 1[daily non-small-value accepted > 0]`，窗口以最新 SRF 官方操作日截止。
- `SOMA weekly change = SOMA_TOTAL(t) − SOMA_TOTAL(t−1 official release)`。

金额统一规范化为 USD millions 后再展示。周末、节假日与无操作日不填充；缺失值不补零。ON RRP 与 SRF 的 small-value 技术测试必须在 provider、序列、公式、图表、表格和血缘中独立分区并完成 `total = regular + small-value` 对账。多个非技术测试场次若报告不一致利率，合同失败，不取第一条冒充唯一利率。

纽约联储的 Treasury operation results 同时可能覆盖 reserve-management purchases、agency-principal reinvestment purchases 与 operational-readiness small-value exercises；公开结果行没有稳定的逐场用途或 small-value 字段，近期测试结果的 `note` 也可能为空。因此页面统一命名为“国债二级市场购买（官方结果合计）”，不得称为精确 RMP-only，也不得根据金额或 operation ID 猜测并剔除测试。

## 图表与表格

- `operations-treasury-purchases-history`：每日官方购买接受额与滚动 30 个自然日合计，明确可能包含操作准备测试。
- `operations-standing-tools-history`：ON RRP 非测试接受额与 SRF 非测试接受额。
- `operations-soma-history`：SOMA 总额以及 Bills、Notes/Bonds、TIPS、FRN、MBS 等官方分项。
- `recent-treasury-purchase-operations`：最近 20 场操作的 operation ID、日期、类型、提交额、接受额、结算日、期限范围与“官方结果未提供测试标记”状态。
- `recent-repo-reverse-repo-operations`：最近 20 个操作日/场次的 ON RRP 或 SRF、接受额、利率、参与方/抵押品与技术测试标记。

每个图点和表格行必须保留来源、value date、fetched_at、batch ID、质量、许可与 fallback 状态；表格必须实际渲染 `cells_list`，不能只在 JSON 中存在。

# 数据源与边界

- 官方数据：[New York Fed Markets Data APIs](https://markets.newyorkfed.org/static/docs/markets-api.html)、[Treasury Securities Operations](https://www.newyorkfed.org/markets/desk-operations/treasury-securities)、[Repo and Reverse Repo Operations](https://www.newyorkfed.org/markets/desk-operations/repo) 与 [SOMA Holdings](https://www.newyorkfed.org/markets/soma-holdings)。
- 强制归属与许可声明：[New York Fed Terms of Use](https://www.newyorkfed.org/privacy/termsofuse)。
- “实际 RMP-only 接受额”标记 `NEEDS_SOURCE`，等待官方逐场用途字段或建立有原始计划证据、人工复核的 schedule mapping。
- 交易商级报价、订单簿、实时相对价值、市场冲击与低延迟成交数据标记 `PURCHASE_REQUIRED`；候选为 Bloomberg、LSEG、Tradeweb 或 CME BrokerTec，并须取得公开展示与派生分析权。
- 不复制比较站 HTML/CSS、文案、私有 API、历史库、不透明打分或其已知错误。

# Acceptance criteria

- [x] 新增 Treasury purchases provider，严格验证官方 JSON envelope、结果状态、方向、规范日期、唯一 operation ID 与非负金额，并保存精确原始字节；不得伪造官方未提供的 small-value 分类。
- [x] Reverse Repo、Standing Repo、SOMA 与 Treasury purchases 均输出可分区、可对账的 exact series；四个 run 各有一个 immutable RawArtifact。
- [x] 建立 `operations v1` 独立协调器，通用 publisher 无法写入该 key，且只接受同 cycle 的四个最新成功批次。
- [x] 上述 10 项指标、3 张图和 2 张表满足公式、血缘、许可、质量、fallback 与组件级日期合同。
- [x] 建立专属 public selector，重新验证 contract version、required sets、最新 attempts、当前许可、artifact、cycle、公式、双哈希、规范化 MetricSnapshot 和 embedded lineage。
- [x] 任一输入失败、部分响应、schema 漂移、过期、许可撤销、fallback、混批、未来日期、重复、未知序列、公式/指纹/表格篡改时，上一完整快照只在重新验证后以 stale 状态保留。
- [x] 旧 writer、superseded run、重复触发、同值恢复和 PostgreSQL 锁定路径有确定性回归；主刷新命令和 Celery 任务在 operations v1 无法保留或发布时 fail loudly。
- [x] 数据覆盖台账拆分四个官方 LIVE 输入、透明派生值、RMP-only NEEDS_SOURCE 与交易商微观数据 PURCHASE_REQUIRED。
- [ ] Ruff、完整 pytest、Django check、迁移漂移、`git diff --check`、干净临时库真实刷新、路由 smoke 与 1440/390 浏览器验收通过。

# Verification plan

- Canonical: `.venv/bin/ruff check .`, `.venv/bin/pytest -q`, `.venv/bin/python manage.py check`.
- Additional: `git diff --check`, migration drift, provider raw-byte/hash tests, exact formula/partition tests, latest-attempt/failure/recovery/concurrency tests, clean temporary official refresh, rendered-table route smoke, desktop/mobile browser and console inspection.
