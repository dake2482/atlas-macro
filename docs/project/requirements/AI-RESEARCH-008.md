---
schema_version: 1
id: AI-RESEARCH-008
project_id: AI-RESEARCH
title: 修正 Census 当期零售发布与完整历史
status: IN_PROGRESS
priority: P1
executor: codex
task_id: atlas-census-retail-alignment-20260713
branch: main
worktree: local
dependencies:
- AI-RESEARCH-006
updated_at: '2026-07-13T08:02:09+08:00'
next_action: Replace the lagging historical-directory tail with the current Census MARTS workbook and the official 1992-present adjusted-sales series, then fail closed on any same-vintage disagreement.
evidence:
- Production currently publishes April 2026 Census retail and food-services sales as 757,085 USD millions,
  +0.5% month over month and +4.9% year over year from batch 3b6ea974-4f6f-4379-b008-80d3e6056727;
  the public component is marked stale on 2026-07-13.
- The official Census sales page released May 2026 on June 17, 2026 at 763,705 USD millions, +0.9% month
  over month and +6.9% year over year, and revised the March-to-April change from +0.5% to +0.4%.
- The current adapter scans only the archived rsYYMM.xlsx directory. Its newest visible file is rs2604.xlsx,
  so it misses the current marts_current.xlsx release and stores only three levels plus two months of changes.
- Census identifies /data/timeseries/eits/marts as Advance Monthly Sales for Retail and Food Services and
  explicitly requires an API key. Production has no configured Census key, so the public refresh must not
  silently depend on the credential-gated API.
- The same official release page exposes a keyless adjusted total-sales series from 1992 to present at
  /retail/marts/www/adv44X72.txt. Its May, April and March values are 763,705, 757,036 and 754,013.
started_at: '2026-07-13T08:02:09+08:00'
---

# 目标

用 Census 当期 MARTS 官方工作簿和 1992 至今官方季调销售序列替换滞后的历史目录尾部；当期值、环比、同比和完整图表历史必须同源可复算，任何同一当前 vintage 的冲突都停止发布并保留上一完整快照。

## Acceptance criteria

- [ ] Census 当前页、marts_current.xlsx 和 adv44X72.txt 均作为一手工件保存哈希；最新月份、最近重叠水平和官方公布的环比/同比必须一致，否则本批次失败。
- [ ] 季调零售与餐饮服务销售从 1992 年起完整入库；环比和同比用 Decimal 从水平序列透明计算，并按 Census 公布精度交叉校验。
- [ ] 旧 rsYYMM.xlsx 只作为历史 vintage/修订对照；其较旧月份不得覆盖当前源，同一当前 vintage 冲突不得发布，旧回放不得使已存官方日期倒退。
- [ ] API 适配器改用正确的 EITS /marts 路径并保持凭据门控；公开生产刷新使用无需凭据的当前发布工件，不伪装成 API 数据。
- [ ] 当前源缺失、格式变化、交叉校验失败、过期、未授权或混批时保留上一完整 consumer 快照并显示具体失败；恢复后同值刷新血缘而不制造错误新版本。
- [ ] consumer 页面发布 May 2026 的 763,705、+0.9% 和 +6.9%，April 历史修订为 757,036 与 +0.4%；不回归 BEA PIO、G.19、NY Fed 家庭债务或 economy 组合页。
- [ ] 数据目录把 Census 零售完整历史标记为 LIVE；Ruff、完整 pytest、Django check、Mina 生产刷新、路由烟测及桌面/390px 浏览器验收通过。

## Verification plan

- Build deterministic current-page, current-workbook, 1992-present text-series and archived-workbook fixtures;
  cover current agreement, current conflict, archived revision differences, malformed history and regression.
- Exercise the whole consumer source group with a failed Census current release and prove the prior complete
  snapshot remains visible and stale, then recover with exact current batches.
- Run canonical validation, create an immutable Mina release, refresh the production macro group, audit stored
  counts/lineage/current values, and verify the public page at desktop and 390px on port 3080.
