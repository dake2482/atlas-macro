---
schema_version: 1
id: AI-RESEARCH-008
project_id: AI-RESEARCH
title: 分层补齐 Census 零售发布与完整历史
status: IN_PROGRESS
priority: P1
executor: codex
task_id: atlas-census-retail-alignment-20260713
branch: main
worktree: local
dependencies:
- AI-RESEARCH-006
updated_at: '2026-07-13T14:21:11+08:00'
next_action: Deploy the Census release-workbook retail fallback to Mina, rerun refresh_macro_data, audit the consumer/economy/daily-evidence impact, then keep CENSUS_API_KEY as the remaining complete-history action.
evidence:
- Production currently publishes April 2026 Census retail and food-services sales as 757,085 USD millions,
  +0.5% month over month and +4.9% year over year from batch 3b6ea974-4f6f-4379-b008-80d3e6056727;
  the public component is marked stale on 2026-07-13.
- The official Census sales page released May 2026 on June 17, 2026 at 763,705 USD millions, +0.9% month
  over month and +6.9% year over year, and revised the March-to-April change from +0.5% to +0.4%.
- The current adapter scans only the archived rsYYMM.xlsx directory. Its newest visible file is rs2604.xlsx,
  so it misses the current marts_current.xlsx release and stores only three levels plus two months of changes.
- Census identifies /data/timeseries/eits/marts as Advance Monthly Sales for Retail and Food Services and
  explicitly requires an API key. Production has no configured Census key, so the public refresh must retain
  the old complete snapshot and name the missing credential rather than silently fall back to stale current data.
- The official release page exposes current XLSX/TXT links, but ordinary local and Mina service requests are
  currently rejected by Cloudflare with HTTP 403. They are browser references, not a dependable keyless Celery
  ingestion path; the www2 historical directory remains reachable but ends at April 2026.
- Commit 8381640 implements the correct /eits/marts adapter, requires a continuous 1992-present level history,
  derives MoM/YoY with Decimal, stores a key-free response URI/hash, scopes consumer cards and charts to the exact
  Census API batch, and records the older workbook as a non-promoting revision witness. Commits aaecd6e and
  61928fc expose skipped-source reasons in both snapshot data and the public stale-data callout.
- All 335 tests, Ruff and Django checks pass. Tests cover the May 763,705 / +0.9% / +6.9% values, April +0.4%
  revision, 1,226 normalized level/rate rows, missing-month rejection, HTTP error redaction, artifact persistence,
  exact dataset/batch selection, workbook deltas, failed refresh retention and same-content recovery.
- Mina release 61928fc serves on HTTP 3080. A real production macro refresh completed the five available official
  sources with 18,861 rows and left only Census partial because CENSUS_API_KEY is absent; no consumer v1 snapshot
  was published, snapshot 93 retained April 757,085 / +0.5% / +4.9% as stale, and the page now names the missing key.
- The data-requirement catalogue was synchronized to keep both Census current retail and full history at
  NEEDS_SOURCE until the credential-backed production refresh succeeds. Desktop 1440px and mobile 390px browser
  checks found 14 cards, six charts, no horizontal overflow, the explicit failure reason and no fake May value;
  ECharts canvases initialized after scrolling and browser console logs were clean.
- The validated pre-release backup is /srv/atlasmacro/backups/20260713T002138Z.dump, size 7,868,138 bytes,
  SHA-256 a3d36c13e7717ca784fb97730885afac0cae13f5a353ba1d33d53a5ee0e4a2df; its pg_restore catalogue check passed.
- '2026-07-13 follow-up: live probing confirmed the Census EITS API returns 302 missing_key without
  CENSUS_API_KEY, but the official MARTS release workbook is already a traceable public source. The code now
  treats `census-release` as the current consumer-page retail source, keeps `census` API as the complete-history
  source, updates the data catalogue accordingly, and preserves the key requirement for 1992-present API history.'
started_at: '2026-07-13T08:02:09+08:00'
---

# 目标

用可公开抓取的 Census MARTS 官方发布工作簿发布当前零售与餐饮服务销售；在取得 CENSUS_API_KEY 后，再用 EITS/MARTS API 补齐 1992 至今完整历史。任何路径都必须同源可复算、带原始工件哈希，失败时保留上一完整快照。

## Acceptance criteria

- [x] Census MARTS API 原始响应作为一手工件保存脱敏 URI 和哈希；最新月份、最近水平及派生环比/同比必须来自同一完整 API batch。
- [ ] 季调零售与餐饮服务销售从 1992 年起完整入库；环比和同比用 Decimal 从水平序列透明计算，并按 Census 公布精度输出。
- [x] CENSUS_API_KEY 缺失时，consumer 当前零售指标改用 Census 官方发布工作簿，不再发布 demo 或过期静态数值；完整 API 历史继续单列为缺口。
- [x] API 适配器改用正确的 EITS /marts 路径并保持凭据门控；key 不进入日志、错误、工件 URI、页面或 Git，缺 key 时不得联网或发布半成品。
- [x] 当前源缺失、格式变化、交叉校验失败、过期、未授权或混批时保留上一完整 consumer 快照并显示具体失败；恢复后同值刷新血缘而不制造错误新版本。
- [ ] consumer 页面在 Mina 发布当前可用 Census 官方发布工作簿批次；不回归 BEA PIO、G.19、NY Fed 家庭债务或 economy 组合页。
- [ ] 数据目录把当前 Census release-workbook 零售指标标记为 LIVE，并把完整 API 历史保留为 NEEDS_SOURCE；Ruff、完整 pytest、Django check、Mina 生产刷新、路由烟测及桌面/390px 浏览器验收通过。

## Verification plan

- Build deterministic current-page, current-workbook, 1992-present text-series and archived-workbook fixtures;
  cover current agreement, current conflict, archived revision differences, malformed history and regression.
- Exercise the whole consumer source group with a failed Census current release and prove the prior complete
  snapshot remains visible and stale, then recover with exact current batches.
- Run canonical validation, create an immutable Mina release, refresh the production macro group, audit stored
  counts/lineage/current values, and verify the public page at desktop and 390px on port 3080.
