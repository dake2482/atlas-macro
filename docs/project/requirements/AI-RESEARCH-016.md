---
schema_version: 1
id: AI-RESEARCH-016
project_id: AI-RESEARCH
title: 美联储资产负债表与净流动性精确周度公开合同
status: REVIEW
priority: P1
executor: codex
task_id: atlas-fed-balance-sheet-alignment-20260714
branch: main
worktree: local
dependencies:
- AI-RESEARCH-007
- AI-RESEARCH-014
updated_at: '2026-07-14T13:16:36+08:00'
next_action: Re-run the recorded 1440/390 browser acceptance after the Browser Plugin runtime regression is fixed; production deployment remains separately authorized.
evidence:
- The previously captured comparison-page contract shows four headline values for Federal Reserve total assets, Treasury holdings, MBS holdings and net liquidity, followed by a recent-20 table with those same fields.
- The current route and generic H.4.1 publisher expose only total assets, Treasury holdings, MBS and reserves. They do not provide a dedicated contract, net-liquidity proxy, recent-20 table or page-specific public selector.
- Federal Reserve H.4.1 directly supplies RESPPMA_N.WW, RESPPALGUO_N.WW, RESPPALGASMO_N.WW and RESH4R_N.WW; Atlas already stores them as exact-batch WALCL, WSHOTSL, WSHOMCB and WRBWFRBL observations.
- The net-liquidity proxy can be transparently calculated as WALCL minus ON RRP minus TGA using the direct NY Fed Markets API and Treasury FiscalData inputs. It is an Atlas proxy, not an official Federal Reserve LPI.
- The comparison site spreads weekly H.4.1 values across non-weekly dates and leaves some columns blank. Atlas will instead use exact non-future common Wednesday observations without forward filling.
- A clean temporary-database refresh published the five-metric v1 contract on the exact common Wednesday 2026-07-08 with 20 common rows, two 20-row charts and a 20-row recent table. The published values were WALCL 6.735609, Treasuries 4.502749, MBS 1.948398, reserves 3.137377 and net-liquidity proxy 5.983018 USD trillions.
- The accepted live component runs were H.4.1 7,380 rows, NY Fed ON RRP 717 rows and Treasury TGA 100 rows. The ON RRP batch contained only its seven allowed series; the public snapshot contained five normalized MetricSnapshot rows, zero fallback observations and no demo snapshot.
- The immutable H.4.1 ZIP artifact was 8,986,826 bytes with SHA-256 `15abd532f6c49b964ee71fb436e97f774f666d79f1ba2bcd6f1943328130eadc`. NY Fed and FiscalData JSON runs retain source/fetch/run lineage but do not yet have immutable RawArtifact rows; that broader raw-response governance gap remains explicit.
- A real Treasury transport disconnect retained snapshot 8 as durable stale with refresh_failure. The next successful official refresh cleared the failure in place, kept semantic fingerprint `2b9855be32f3ea15421dab224fd8e62b1a288feb38605db39fcef634e64c7e96`, refreshed all component batches and returned HTTP 200 from `/liquidity/fed-balance-sheet/`.
- Independent adversarial review added latest-attempt checks, transient stale retention, guarded ON RRP/TGA writers, canonical date and series whitelists, nonnegative-value checks, shared fingerprint recomputation and strict publication-state enumeration. Unknown-series, malformed-date, negative-value, superseded-writer, refresh-window and payload-tamper regressions all pass.
- Canonical validation passed with Ruff, 632 collected pytest cases, Django check, migration drift check and git diff check. Browser Plugin 26.707.71524 still fails before browser discovery because its trusted bundle attempts to redefine the locked Node `process` facade, so the 1440/390 visual gate remains unexecuted rather than being reported as passed.
started_at: '2026-07-14T12:07:35+08:00'
---

# 目标

把 `/liquidity/fed-balance-sheet/` 从通用 H.4.1 卡片升级为独立、可验证的周度公开合同：直接展示联储总资产、美债、MBS、准备金，并用完全同日的 WALCL、ON RRP 与 TGA 计算净流动性代理。

# 口径与边界

- H.4.1 四项直接值必须来自同一个最新成功精确批次和同一个非未来周三。
- ON RRP 与 TGA 必须来自各自最新成功精确批次；净流动性只在三源完全共同有效日计算，不做前值填充。
- `净流动性代理 = WALCL − ON RRP − TGA`，先统一为 USD millions，再换算为 USD trillions。
- 页面明确标注净流动性为 Atlas Macro 透明代理，不是 Federal Reserve 官方指标，也不是 LPI 综合分。
- 不复制比较站点的 HTML、CSS、文案、私有接口、历史数据库或已知日期错位。
- 生产部署、生产刷新、数据库迁移和 GitHub 推送均属于单独授权动作。

# Acceptance criteria

- [x] 建立 `fed-balance-sheet v1` 独立协调器，通用发布器不能绕过该合同。
- [x] 当前五项指标为总资产、美债、MBS、准备金和净流动性代理；每项均保留来源、value date、fetch time、精确批次、质量、许可和 fallback 状态。
- [x] 发布 H.4.1 四分项历史图、净流动性历史图和最近 20 个精确共同周三表格，逐点/逐行血缘可复算且不前值填充。
- [x] 专属公开选择器重新校验 contract version、最新成功输入批次、当前许可、公式、共同日期、规范化 MetricSnapshot 与无 fallback 状态。
- [x] 任一必需源失败、过期、回退、许可撤销、重复日期、混批、日期倒退、样本不足或发布后置条件失败时保留上一完整快照并显示 stale。
- [x] 同值重抓只更新血缘而不制造新内容版本；旧批次 replay 和重复触发均为 no-op；PostgreSQL 锁定路径有确定性覆盖。
- [x] 数据台账分开标识 H.4.1 直接输入为 LIVE，并将包含 Atlas 净流动性派生值的完整页面合同显式标为 PROXY。
- [ ] Ruff、完整 pytest、Django check、迁移漂移检查、真实官方源临时库刷新和 1440/390 浏览器验收通过。

# Verification plan

- Canonical: `.venv/bin/ruff check .`, `.venv/bin/pytest -q`, `.venv/bin/python manage.py check`.
- Additional: `git diff --check`, migration drift check, clean temporary SQLite live refresh, exact batch/formula/licence/artifact audit, PostgreSQL concurrency review and desktop/mobile browser plus console inspection.
