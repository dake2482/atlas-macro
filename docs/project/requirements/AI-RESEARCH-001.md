---
schema_version: 1
id: AI-RESEARCH-001
project_id: AI-RESEARCH
title: 接入统一项目控制面
status: REVIEW
priority: P3
executor: codex
task_id: codex-governance-convergence-20260712
branch: main
worktree: local
dependencies:
- PORTFOLIO-005
updated_at: '2026-07-12T20:35:00+08:00'
next_action: Review and commit the onboarding files, then run `portfolio closeout AI-RESEARCH`.
evidence:
- The existing Git repository is clean at onboarding start and has no configured remote.
- Ruff, the complete pytest suite, and Django system checks passed on 2026-07-12.
- 'onboarding review: canonical validation and strict portfolio integration passed'
- The closeout gate correctly blocked completion because two governance paths remain uncommitted.
---

# 目标

将已有 Atlas Macro 工程从未分类仓库升级为有明确规则、状态、需求、决策和验证命令的正式项目。

## Acceptance criteria

- [x] 项目登记从 `UNTRIAGED` 调整为 `ACTIVE`。
- [x] 仓库拥有引用共享策略的 `AGENTS.md`。
- [x] `docs/project/project.yaml`、需求和决策文件存在。
- [x] 项目声明的 lint、测试和 Django 检查通过。
- [x] `portfolio check --strict` 通过且生成状态页最新。
- [ ] 治理文件形成明确 commit，且 `portfolio closeout AI-RESEARCH` 通过。

## Verification plan

- Run the three canonical validation commands.
- Render the portfolio and run the strict control-plane check.
