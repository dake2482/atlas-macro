---
schema_version: 1
id: AI-RESEARCH-014
project_id: AI-RESEARCH
title: Fed H.8 商业银行资产与准备金覆盖近似原子公开合同
status: REVIEW
priority: P1
executor: codex
task_id: atlas-reserves-h8-alignment-20260714
branch: main
worktree: local
dependencies:
- AI-RESEARCH-013
updated_at: '2026-07-14T10:32:38+08:00'
next_action: After separate deployment authorization, back up production, deploy and run H.4.1 followed by H.8 so the dual-source contract can publish atomically; then repeat lineage, route and browser checks. The comparison page's SOFR-3M T-bill and SOFR-IORB components remain a separate NEEDS_SOURCE alignment slice.
evidence:
- Read-only route and data audit counted 92 URL patterns, 43 dashboard templates and 97 explicit data requirements; reserves currently publishes only one H.4.1 balance despite declaring ratio and history features.
- The Federal Reserve H.8 fixed ZIP endpoint was checked read-only and returned FRB_H8.zip with H8_data.xml; the official XML identifies B1151NCBA as total assets of all commercial banks, seasonally adjusted, in USD millions.
- H.4.1 WRBWFRBL and H.8 B1151NCBA are both Wednesday weekly observations and can be joined on an exact non-future common date without an external data licence.
- The planned ratio is explicitly a coverage proxy because the H.4.1 numerator covers reserve balances of depository institutions while the H.8 denominator covers commercial banks. It will not be described as a regulatory adequacy measure or a Federal Reserve indicator.
- The final read-only live refresh accepted the current strict Board schemas and persisted 7,380 H.4.1 rows plus 2,792 H.8 B1151NCBA rows. The exact ZIP artifacts retained SHA-256 hashes, byte sizes, Prepared times, fetch times and source URLs.
- The live reserves v1 snapshot joined the latest common Wednesday 2026-07-01 from two exact batches, published five metrics and two 260-row charts, used an exact 56-calendar-day change pair, and calculated the z-score from 156 exact changes in the recent three-year window.
- Provider gates now reject duplicate archive members, duplicate requested series or dates, invalid or non-Wednesday periods, unknown statuses, semantic dimension drift, excessive release lag, future timestamps, release-time regression and superseded concurrent persistence before public rows can be overwritten.
- Source failure, partial data, stale inputs, invalid licences, missing H.4.1/H.8 counterparts and failed publication postconditions retain the prior complete snapshot. Both H.4.1 and H.8 CLI/Celery paths fail loudly when the required reserves contract is stale.
- >-
  Final local gates passed: 584 full tests, 94 targeted hardening tests, Ruff, Django system check, migration-drift check, production deployment check and git diff whitespace check.
- A post-hardening live H.8 replay with the same official Prepared time passed the durable run/observation release-watermark gate, updated the exact H.8 component batch in place, kept one public snapshot, and produced no stale or refresh failure state.
- Three independent final re-reviews found no remaining P0/P1 issues after the provider-schema, release-lag, concurrent-persistence TOCTOU and H.4.1/H.8 fail-loud corrections.
- >-
  Local browser acceptance passed at 1440px and 390px: five lineage-rich metric cards and the selected ECharts view rendered, period/tab GET filters worked, the mobile drawer opened and closed, no horizontal overflow occurred, and the browser console had no warnings or errors.
- >-
  The data catalog now contains 101 explicit requirements: 41 LIVE, 19 NEEDS_SOURCE, 37 PURCHASE_REQUIRED, 3 LICENSE_REVIEW and 1 PROXY. The reserves coverage proxy is LIVE, while like-for-like adequacy and the comparison page's SOFR spread components remain NEEDS_SOURCE.
started_at: '2026-07-14T09:05:32+08:00'
---

# 目标

直接接入 Federal Reserve H.8 `B1151NCBA`，并与 H.4.1 `WRBWFRBL` 构建双官方源、双精确批次的 `reserves v1` 原子快照。页面发布准备金余额、商业银行总资产、覆盖近似比率及透明的 8 周变化统计；任何必需组件失败时保留上一完整快照并显示 stale。

# 边界

- H.8 与 H.4.1 均直接来自 Federal Reserve Board Data Download Program，不经 FRED、Yahoo 或比较站点中转。
- 分子与分母覆盖机构集合不完全一致，派生比率只称“准备金 / 商业银行资产覆盖近似”。
- 不自动输出“充裕、稀缺、偏紧”等状态，不把统计位置解释为监管资本、LCR 或可交易信号。
- 本地实现不授权真实生产刷新、部署、推送或迁移。

# Acceptance criteria

- [x] H.8 流式 ZIP/SDMX provider 保留 Board series ID、状态、单位、原始 ZIP 哈希和完整性元数据。
- [x] H.4.1/H.8 双源协调器只接受各自最新成功精确批次，并在共同非未来周三构造完整快照。
- [x] 直接值、覆盖近似、8 周变化和 3 年样本 z-score 均携带可复算 input lineage、批次、许可、质量和无 fallback 状态。
- [x] `reserves v1` 指标与图表合同、日期回退门、许可撤销、样本不足、零方差、失败保留和幂等均有确定性测试。
- [x] 页面明确覆盖差异和方法边界；严格同口径充裕度方法继续显示为待来源/待审核，而不是伪精确结论。
- [x] 周任务、管理命令、完整测试、生产检查和桌面/移动浏览器验收通过。

# Verification plan

- Canonical local commands: `.venv/bin/ruff check .`, `.venv/bin/pytest -q`, `.venv/bin/python manage.py check`.
- Additional gates: migration drift, production Django check, `git diff --check`, clean temporary-database live H.8/H.4.1 refresh and 1440/390 browser inspection.
- Deployment remains a separate high-impact action requiring explicit authorization.
