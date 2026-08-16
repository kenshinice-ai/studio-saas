# PWE Studio v10.8.0 — Handoff 索引（2026-08-16 起按 AI 分目录）

> 首标题始终点名当前版本 —— `test_release_ledger.py` 据此机器强制「索引不过期」；
> 每次发布随四层身份表一起更新。

> 本文件从 505KB 单文件瘦身为**索引 + 当前身份**。历史内容一字未改，按原顺序拆入
> `docs/handoff/`；拆分经字节保真校验（拼回 == 原文件 SHA-256）。
>
> **新惯例：按 AI 分目录写轮次文件，不再向本文件追加叙事。**
> - Claude（Fable）：`docs/handoff/claude/YYYY-MM-DD-主题.md`，一轮一文件。
> - codex 时代存档（只读）：`docs/handoff/codex/`，`index.md` 列全部 95 节。
> - 每轮结束只回本文件做两件事：更新下方「当前四层身份」表、更新「最新轮次」指针。
> - 其余纪律不变：Source / Package / Production / Backup 四层分别记录；docs-only
>   closure 不得写成已部署运行时代码；发布必经 STOP GATE。

## 当前四层身份（v10.7.1，2026-08-16）

| 层 | 精确事实 |
|---|---|
| Source | main == origin/main；v10.7.1 运行时 commit `9b7dfdcc12b33a8e448dc59270bab17dfd5d748b`（docs closure `501c741`） |
| Package / SaaS | `dist/PWE-StudioSaaS-aws-10.7.1.tar.gz`，SHA-256 `a087abe6…c14215`，BUILD_INFO commit `9b7dfdcc…` |
| Package / Edition | `dist/PWE-Studio-Edition-10.7.1.tar.gz`，SHA-256 `e4b9dc3d…87b1`，BUILD_INFO commit `9b7dfdcc…` |
| Production | `pwestudio.online` = v10.8.0（deploy exit 0，深健康通过）；deep health `db=ok`、`mode=saas`、`themes.unreadable=0`、`workspaces.stale=0`；6 租户（2 active / 2 onboarding / 1 archived / 1 paused） |
| Backup / migration | dump `studiosaas_studiosaas_20260816T124139Z.dump` + volume `pwestudio-volumes-20260816T124140Z.tar.gz`；schema 至 `0044_credit_refund_source.sql` |

完整证据见 `docs/handoff/claude/2026-08-16-v10.8.0-round.md`（v10.8.0）与 codex/001（v10.7.1 历史）。

## 最新轮次

- **2026-08-17（Claude Fable）v10.8.0 执行轮**：`docs/handoff/claude/2026-08-16-v10.8.0-round.md`
  —— Batch A–F 全量实现（发布证据在该文件随部署闭环）。

- **2026-08-16（Claude Fable）全面体检与下一轮方案（docs-only）**：
  `docs/handoff/claude/2026-08-16-full-system-audit.md`；
  权威方案：`docs/design/Full_System_Audit_Plan_2026-08-16.md`（rev2，含 Batch A 界面缺陷、
  Batch E 账务/学员优化、Batch F Xero 路线图、OPS 暂缓决定与触发条件）。
- **v10.7.1 发布轮（codex）**：`docs/handoff/codex/001-…`（发票打印修复与发布闭环）。

## 历史存档

- `docs/handoff/codex/index.md` — codex 时代全部 95 节（v7.x → v10.7.1），原文原序。
