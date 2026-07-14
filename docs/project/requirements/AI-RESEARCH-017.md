---
schema_version: 1
id: AI-RESEARCH-017
project_id: AI-RESEARCH
title: 流动性次表层资金压力精确多源公开合同
status: REVIEW
priority: P1
executor: codex
task_id: atlas-liquidity-subsurface-alignment-20260714
branch: main
worktree: local
dependencies:
- AI-RESEARCH-015
- AI-RESEARCH-016
updated_at: '2026-07-14T14:18:51+08:00'
next_action: Re-run the recorded 1440/390 browser acceptance when the Browser Plugin runtime is fixed; production deployment remains separately authorized.
evidence:
- The route `/liquidity/subsurface/` exists, but currently resolves through the generic dashboard publisher and selector with no page contract version or required metric/chart set.
- The registry still contains demo-shaped values for an opaque 4.2/10 pressure score, SOFR 99P minus IORB, volume Z-score and 30-day SRF activation. The public empty-state masks them with dashes, but the configuration and requirements remain non-contractual.
- Current real publication exposes SOFR volume and percentiles, IORB, SOFR spreads, aggregate SRF acceptance/rate and one SOFR history chart. It lacks Z60, 30-day non-test activation, USD swaps, exact recent tables, component cycles and a dedicated selector.
- Current SRF aggregation can include small-value technical exercises in accepted volume, which would mislabel a test as market stress. Current NY Fed JSON inputs also lack immutable RawArtifact hashes.
- Official/free inputs are the New York Fed SOFR and Markets API, Federal Reserve PRATES DDP, New York Fed Standing Repo results and New York Fed USD liquidity-swap operations. Opaque composite scoring and dealer-level books remain NEEDS_SOURCE or PURCHASE_REQUIRED.
- The dedicated v1 coordinator, strict selector, fail-loud refresh wiring, immutable artifacts, 11 metrics, four charts and two rendered tables are implemented. The legacy generic publisher path was removed.
- Independent adversarial review found and closed empty table rendering, incomplete swap partitioning, incomplete SRF classification/collateral/rate checks, retained-stale cycle bypass and normalized swap-evidence reconciliation.
- Canonical verification passed with 674 deterministic tests, repository-wide Ruff, Django check, migration drift and `git diff --check` all green.
- A clean temporary SQLite database refreshed live PRATES, SOFR, Standing Repo and USD swaps. The four successful runs stored 1812, 800, 1320 and 915 normalized rows respectively, each with exactly one immutable artifact; the page published 11 metrics, four charts, two tables and returned HTTP 200 with 20 common-date rows and 40 visible operation rows.
started_at: '2026-07-14T13:16:36+08:00'
---

# 目标

把 `/liquidity/subsurface/` 从“真实数据拼装的通用页”升级为独立、可复算、失败可见的 v1 公开合同：展示 SOFR 尾部、成交量、IORB、非技术测试 SRF 和美元央行互换，只发布官方直接值与 Atlas Macro 透明派生值。

# 页面合同

## 必需指标

- SOFR、SOFR 99P 与 IORB。
- `SOFR 99P − SOFR` 和 `SOFR 99P − IORB`，单位 bp。
- SOFR 成交量和 60 个官方观察日的成交量 Z-score。
- SRF 非 small-value 操作接受额、操作利率和过去 30 个自然日的非测试激活天数。
- 剔除 small-value 技术测试后的美元央行互换在途余额。

## 透明公式

- `99P − SOFR bp = 100 × (SOFR_99P% − SOFR%)`。
- `99P − IORB bp = 100 × (SOFR_99P% − IORB%)`。
- `Volume Z60 = (V_t − mean(V_t…V_t-59)) / population_std(V_t…V_t-59)`。
- `SRF 非测试接受额 = Σ 非 small-value 操作 totalAmtAccepted / 1,000,000`。
- `SRF 30D 激活天数 = Σ 1[当日非测试接受额 > 0]`。
- `互换非测试在途 = 总在途 − small-value 在途`，仅纳入 `settlementDate ≤ as_of < maturityDate` 的操作。

Z60、激活天数和互换剔除值必须标记为 Atlas Macro 透明派生/代理，不得冒充 New York Fed 或 Federal Reserve 官方压力指标。

## 精确日期与批次

- 当前 SOFR 日必须是最新非未来官方有效日，并在同日具有 rate、99P、volume 和精确 IORB；缺任一项不得退回上一日冒充 fresh。
- Z60 只使用同一最新 SOFR exact batch 的最近 60 个官方观察日，不填周末、节假日或缺口；样本不足或标准差为 0 时禁止发布。
- SRF 30D 窗口以 SOFR/IORB 精确共同日为截止日，闭区间为 `[共同日−29 天, 共同日]`；同日多场相加，small-value 只单独展示而不计入激活。
- 美元互换保留自己的组件 `as_of`，不强行与日频 SOFR/SRF 对齐；页面显示组件级日期。
- SOFR、SRF 与互换必须来自同一 main-refresh cycle 的三个 exact batches；IORB 使用最新成功 PRATES exact batch，同时检查该数据集的最新 attempt。

## 图表

- `subsurface-sofr-tail-history`：SOFR、99P、IORB 与 99P−IORB。
- `subsurface-sofr-volume-history`：成交量和滚动 Z60。
- `subsurface-srf-history`：非测试接受额及 Treasury/Agency/MBS 分项。
- `subsurface-swap-drawdowns`：非测试美元互换 drawdown。
- `recent-subsurface-observations`：最近 20 个 SOFR/IORB 精确共同日，逐行血缘可复算。
- `recent-srf-operations`：最近 20 个操作日、场次、接受额、利率和技术测试标记。

# 数据源与边界

- SOFR、分位与成交量：[New York Fed SOFR](https://www.newyorkfed.org/markets/reference-rates/sofr) 与 [Markets API](https://markets.newyorkfed.org/static/docs/markets-api.html)。
- IORB：[Federal Reserve PRATES DDP](https://www.federalreserve.gov/datadownload/Choose.aspx?rel=PRATES)。
- Standing Repo：[New York Fed Standing Repo FAQ/results](https://www.newyorkfed.org/markets/repo-agreement-ops-faq.html)。
- 条款与强制声明：[New York Fed Terms of Use](https://www.newyorkfed.org/privacy/termsofuse)。
- 原站不透明综合压力分与“正常/尾部温和”阈值标记 NEEDS_SOURCE，不反推。
- 交易商/对手方级 repo 账簿、完整 sponsored/双边 repo、实时 haircut 与 specials 标记 PURCHASE_REQUIRED，可评估 DTCC、BNY、Bloomberg 或 LSEG 商业授权。
- 不复制比较站 HTML/CSS、文案、私有 API、历史库或不透明打分。

# Acceptance criteria

- [x] 建立 `subsurface v1` 独立协调器与专属公开选择器，并从 generic publication sets 移除。
- [x] 上述 11 项指标、4 张图和 2 张最近表格均满足精确批次、来源、许可、value/as-of/fetch time、质量和 fallback 合同。
- [x] SOFR/IORB 只使用精确共同日，Z60 只使用 60 个有效观察，不前值填充或补周末。
- [x] SRF 正常操作与 small-value 测试在 provider、序列、公式、图表和血缘中完全分离。
- [x] 互换在途余额按 settlement/maturity 日期逐笔复算，并剔除 small-value 技术测试。
- [x] NY Fed SOFR、SRF 和互换原始 JSON 以 immutable RawArtifact URI、SHA-256 和字节数保存；PRATES ZIP 继续保留原始哈希。
- [x] 任一必需源失败/过期/混批/回退/许可撤销/回退源/重复/未来日期/样本不足/公式或指纹失配时，上一完整快照仅以严格复验的 stale 状态保留。
- [x] 最新 attempt、旧写入者、重复触发、同值恢复和 PostgreSQL 锁定路径均有确定性回归。
- [x] 数据台账拆分四个官方输入、三个 Atlas 透明代理、一个不透明综合分缺口和一个商业微观数据采购项。
- [ ] Ruff、完整 pytest、Django check、迁移漂移、干净临时库真实刷新与 1440/390 浏览器验收通过。

最后一项仅剩 1440/390 浏览器门禁未执行：Browser Plugin `26.707.71524` 在可信运行时导入阶段因锁定的 `globalThis.process` 发生确定性兼容回归。未使用非官方浏览器替代方案冒充视觉验收。

# Verification plan

- Canonical: `.venv/bin/ruff check .`, `.venv/bin/pytest -q`, `.venv/bin/python manage.py check`.
- Additional: `git diff --check`, migration drift, provider raw-byte/hash tests, exact formula and row-lineage tests, failure/recovery and concurrency tests, clean temporary official refresh, desktop/mobile browser and console inspection.
