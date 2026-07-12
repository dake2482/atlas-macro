---
schema_version: 1
id: AI-RESEARCH-003
project_id: AI-RESEARCH
title: 修正并补齐官方就业数据页
status: IN_PROGRESS
priority: P1
executor: codex
task_id: atlas-employment-official-20260712
branch: main
worktree: local
dependencies: []
updated_at: '2026-07-12T22:22:27+08:00'
next_action: Validate BLS series and DOL weekly-claims contracts, then implement the employment-page correction.
evidence:
- Production currently displays total payroll employment as the headline nonfarm metric instead of monthly
  payroll change.
- Production displays the hourly-wage dollar level rather than year-over-year wage growth and has no weekly
  claims data despite the page description.
started_at: '2026-07-12T22:22:27+08:00'
---

# 目标

以 BLS 与 U.S. Department of Labor 官方免费数据修正就业页的指标语义，补齐初请/续请，并将不同单位拆分为可追溯的独立图表。

## Acceptance criteria

- [ ] 非农新增由总量序列的一阶差分计算，三月均值由最近三个月增量计算；不再把总量冒充新增。
- [ ] 平均时薪同比由 12 个月比值计算，失业率、劳动参与率、职位空缺及 JOLTS 流量/比率保留官方口径。
- [ ] DOL Weekly Claims 适配器发布全国季调初请、续请与官方四周均值，保留原始工件哈希、响应运行日、抓取批次、许可与质量状态。
- [ ] 就业页按 CES、CPS、JOLTS、Claims 拆分图表，不把百分比、美元和人数放入同一 y 轴；支持可分享的 `period=1y|3y|5y` 参数。
- [ ] BLS 或 DOL 任一必需批次失败时不发布混装快照，继续保留上一版完整页面并标记 stale。
- [ ] 公式、精度、缺月、修订、路由、血缘、响应式和生产刷新测试通过；页面明确说明申领人数不等于全部失业人口。

## Verification plan

- Run deterministic BLS-derived-series and DOL XML parser fixtures, publication-gate and stale-retention tests.
- Run Ruff, the complete pytest suite, Django checks, route/sitemap smoke tests and project closeout.
- Deploy an immutable Mina release, refresh official sources, verify database lineage and browser-test desktop/390px layouts on port 3080.
