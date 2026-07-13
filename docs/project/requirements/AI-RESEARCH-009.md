---
schema_version: 1
id: AI-RESEARCH-009
project_id: AI-RESEARCH
title: Treasury 曲线历史、实际利率与债券入口原子闭环
status: REVIEW
priority: P1
executor: codex
task_id: atlas-treasury-curve-alignment-20260713
branch: main
worktree: local
dependencies:
- AI-RESEARCH-005
updated_at: '2026-07-13T10:00:00+08:00'
next_action: Run the project closeout gate after the pre-existing untracked docs/guides ownership is resolved; do not mix those user files into this requirement.
evidence:
- Production yield-curve snapshot 67 contains only the 2026-07-10 current nominal cross-section; it does
  not implement the promised current, one-week, one-month and three-month curve comparison.
- Production real-rates snapshot 68 contains only the current TIPS cross-section. It has no nominal-versus-real
  historical decomposition even though 5Y and 10Y breakeven metrics are already calculated.
- Production has only 131 observations per Treasury tenor from 2026-01-02 through 2026-07-10 because the
  current refresh fetches only the current annual datasets.
- The public bonds page has no snapshot and still waits for TLT, IEF, LQD and HYG market-data redistribution
  rights, while the official Treasury nominal and real curves are already licensed for public display
  and historical storage.
- The Treasury source currently has successful current-year nominal and real runs with 1,703 and 655 normalized
  rows respectively; this requirement has no API-key or paid-data dependency.
- Homepage and daily-report publication-safety gaps were audited separately and remain the next P0 research-workflow
  requirement; 009 does not auto-publish subjective market judgments.
- Commits 236ff99, b6ef971, a9008cf and 2948fb0 implement the requirement, the New York daily
  release window and the default chart-tab contract.
- Production release 2948fb0 is active on Mina. All six containers are running, web/worker/db/redis
  are healthy, and every container reports zero restarts and no OOM kill.
- The twelve 2021-2026 annual Treasury nominal/real components succeeded with one raw artifact each.
  UST 3M/2Y/5Y/10Y/30Y and TIPS 5Y/10Y each contain 1,380 observations from 2021-01-04 through
  2026-07-10.
- Production snapshots yield-curve 103, real-rates 104 and rates 108 use contract version 1 with no
  refresh failure. The two Treasury pages contain 1,249 common-date history rows and publish exact
  2026-07-10 values including 2s10s +35bp, 3m10s +71bp, 5s30s +76bp, 5Y BEI 2.28% and 10Y BEI 2.24%.
- Ruff, the full 343-test pytest suite and Django check passed. Mina loopback route smoke tests passed
  for rates, yield curve, real rates, bonds and asset overview; final 1440px and 390px Playwright
  checks passed without overflow, stale labels or JavaScript errors, and each selected chart rendered
  exactly one Canvas after entering the viewport.
started_at: '2026-07-13T08:43:30+08:00'
---

# 目标

把美国财政部名义和实际收益率曲线改为独立、跨年度、原子发布的数据合同：当前曲线、多时点曲线、关键利差历史和名义/实际/盈亏平衡分解都绑定精确年度批次；债券入口明确展示官方收益率而不是伪装成未授权 ETF 行情。

## Acceptance criteria

- [x] 名义与实际曲线至少抓取当前年和前五个完整年度；每个年度数据集分别保存原始工件、批次与质量状态，并拒绝未来日期、重复冲突、缺失关键期限和历史倒退。
- [x] Treasury contract v1 只在本次刷新所需年度名义/实际数据集全部成功、许可可公开且最新非未来共同有效日一致时发布；任一失败、回退、过期、未授权或混批时保留上一完整快照并显示具体失败组件。
- [x] 收益率曲线页展示当前、1 周、1 月、3 月前最近可用营业日的四条名义曲线；2s10s、3m10s、5s30s 指标与历史均用同日输入透明计算。
- [x] 实际利率页展示 5Y/10Y 名义、实际与盈亏平衡通胀历史；BEI 明确标记为 Atlas Macro 的同期限名义减实际估算，不提供无法由 Treasury 官方曲线直接计算的 5Y5Y。
- [x] 利率总览复用同一 Treasury contract；债券页改为官方 UST/TIPS/BEI 收益率看板，明确不是 ETF 价格或总回报；大类资产总览只在该合同通过公开许可与质量门后计入债券覆盖。
- [x] 支持 `period=1y/3y/5y`，同值重抓只更新血缘不制造新快照；公式、输入值日期、批次、来源、许可、fallback 与 fresh/stale 状态在数值和图表组件级可审计。
- [x] Ruff、完整 pytest、Django check、Mina 不可变发布、生产历史回填、路由烟测以及桌面/390px 浏览器验收通过。

## Verification plan

- Build deterministic multi-year nominal and real Treasury XML fixtures with weekends, missing tenors, duplicates, a future row and a deliberately failed annual component.
- Prove exact current/1W/1M/3M selection, common-date spread and BEI formulas, five-year chart windows, mixed-batch rejection, failure retention and same-value lineage refresh.
- Deploy an immutable Mina release, backfill six calendar years, audit exact production batch/date/count/lineage state, then verify all five affected public routes on HTTP 3080.
