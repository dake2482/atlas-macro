---
schema_version: 1
id: AI-RESEARCH-011
project_id: AI-RESEARCH
title: SEC 四家公司基础面与现金资本开支公开发布闭环
status: REVIEW
priority: P1
executor: codex
task_id: atlas-sec-four-company-publication-correction2-20260713
branch: main
worktree: local
dependencies:
- AI-RESEARCH-008
updated_at: '2026-07-13T17:30:00+08:00'
next_action: Review the local SEC four-company slice, then provision a real monitored SEC_USER_AGENT contact email before any production refresh; keep the remaining 215 contract company routes pending.
evidence:
- The reviewed SEC scope is exactly Microsoft, Alphabet, Amazon and Meta. A successful complete batch publishes exactly four company profiles and keeps the other 215 public-contract slugs as transparent pending pages.
- Company-level annual fundamentals and reported cash CapEx are stored with exact response-byte artifacts, filing/value dates, actual fetch times, source and licence lineage, quality state, batch identity and fallback state. Amazon productive-assets remains explicitly broader/non-comparable; no AI-only CapEx label is used.
- >-
  Latest-five-year selection is fail-closed: the selected window must be consecutive, end at the latest observed fiscal year and contain no incomplete prior year. Publication is atomic and preserves the last complete batch as stale on refresh failure.
- Generic company pages retain public-license FinancialFact and authorized non-demo MarketBar behavior. Reviewed SEC pages require public+derived rights for financial/projection surfaces and do not show stale cached market prices or valuations.
- Deterministic tests cover effective licence gates, derived-only revocation, invalid newer snapshots, missing/mixed demand components, per-component lineage, universal/reviewed Company constraints, Admin immutability, route lifecycle, discovery filtering, retry behavior and artifact safety.
- No live SEC request was made and no production deployment was performed. SEC_USER_AGENT still requires a real monitored contact email before a production SEC refresh is permitted; no email is invented in this checkout.
- This requirement is only the reviewed SEC four-company publication slice. It does not mark the whole Atlas parity goal complete, and AI-RESEARCH-008 remains IN_PROGRESS.
started_at: '2026-07-13T16:30:00+08:00'
---

# 目标

在 clean-room Atlas Macro 中完成 Microsoft、Alphabet、Amazon、Meta 四家公司的 SEC EDGAR 年度基本面与报告现金资本开支发布合同。所有公开数字保留可复核的公司、财年、申报、抓取、批次、质量、许可与 fallback 血缘；不把公司层面的总 CapEx 表述为 AI-only CapEx。

## Acceptance criteria

- [x] 四家公司才可进入完整 SEC 公开批次；其余 215 个合同 slug 保持 pending，首次失败或不完整提交不改变 URL 语义。
- [x] 五年窗口、精确原始字节、有效存储/展示许可、事务锁、发布约束、Admin 不可变性、generic/reviewed 页面分支与需求快照共享校验器均有实现和确定性测试。
- [x] 需求快照只接受四家公司、20 行、五个连续且结束于最新观察财年的行、三张非空图表、单一批次和可见组件血缘；无效新快照不能替代上一份完整 stale 快照。
- [x] 本地 Ruff、迁移漂移、目标 pytest、Django check 与 diff check 通过后进入 REVIEW；未进行实时 SEC 请求或生产部署。

## Verification plan

- 使用本地 fixture provider、MockTransport、注入时钟和 SQLite 测试数据库验证 refresh、失败保留、许可撤销、路由发现和全部约束。
- 生产刷新前必须由人工提供真实、受监控的 SEC_USER_AGENT 联系邮箱，并重新执行生产侧数据授权、网络、部署和浏览器验收；本需求不替代该上线门。
