---
schema_version: 1
id: AI-RESEARCH-010
project_id: AI-RESEARCH
title: 首页与每日报告官方证据发布安全闭环
status: IN_PROGRESS
priority: P0
executor: codex
task_id: atlas-daily-evidence-publication-safety-20260713
branch: main
worktree: local
dependencies:
- AI-RESEARCH-006
- AI-RESEARCH-007
updated_at: '2026-07-13T10:00:47+08:00'
next_action: Implement one shared public-thesis eligibility gate and prove every public consumer excludes
  future, incomplete, demo, stale or unlicensed research.
evidence:
- The current public-thesis selector can expose a future-dated Thesis with no published daily-evidence
  contract, no relationized evidence, no trigger and no invalidation.
- Homepage, daily list/detail, previous/next navigation and sitemap do not yet share one atomic publication
  eligibility contract.
- The daily detail template reads fields that are not part of the Thesis data model, while the homepage
  can label historical official news as future events and empty charts can serialize literal null.
- This requirement is limited to publication safety and evidence rendering. It does not add order entry,
  automatic publication, Trade Map performance, paid market data or new event-calendar sources.
started_at: '2026-07-13T10:00:47+08:00'
---

# 目标

为首页和每日报告建立同一个可审计发布门：只有经过人工审核、绑定已发布 `daily-evidence` contract-v1 原子快照、证据/触发器/证伪条件完整、日期非未来且所有嵌套来源许可有效的 Thesis 才能进入任何公开入口。

## Acceptance criteria

- [ ] `_public_theses()` 成为首页、日报列表/详情、上一篇/下一篇和 sitemap 的唯一公开选择器，并拒绝未来 `date/published_at`、空发布时间、未发布或错误合同快照、demo、refresh failure、fallback/stale/error 与许可失效数据。
- [ ] 每条公开 Thesis 必须至少包含关系化 EvidenceItem、Trigger 和 Invalidation；每项保存来源、URL、数值日期、抓取时间、批次、质量与许可状态，缺失或跨快照血缘时不得公开。
- [ ] Django Admin 不再允许直接勾选发布；只提供带完整校验、原子更新时间和审计结果的发布动作，失败时不改变原状态。
- [ ] 首页不把历史 NewsItem 冒充未来事件；没有已验证日历源时隐藏该区或明确标记为最新官方动态，空图表不得输出 literal `null` 占位数据。
- [ ] 日报列表与详情只读取 Thesis 的真实字段和关系；状态筛选、搜索说明、证据、触发器、证伪条件、快照 ID、批次、截至日、质量、许可与 stale 状态一致展示。
- [ ] 负向测试覆盖未来/空发布时间、未来日期、空/未发布/错误合同/demo/失败快照、嵌套受限来源、缺证据/触发器/证伪条件；这些记录不能出现在任一公开入口或 sitemap。
- [ ] Ruff、完整 pytest、Django check、生产备份、Mina 不可变发布、关键路由烟测和 1440px/390px 浏览器验收通过。

## Verification plan

- Build deterministic Thesis factories for every invalid publication state and assert the shared selector produces the same result for homepage, daily list/detail, adjacent navigation and sitemap.
- Exercise the Admin publication action as an atomic transaction, including source-licence revocation and partial relation failures.
- Deploy an immutable Mina release only after the full validation suite passes; verify no previously invalid Thesis becomes public and all published research exposes exact snapshot and relation lineage.
