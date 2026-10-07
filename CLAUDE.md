@AGENTS.md

## Writing rules · STE-lite v1

Applies to: procedures, release and rollback steps, handoffs (HANDOFF, "等 Lee"), warnings, and notes for other sessions.

1. One action per step. Start with the verb. Put a condition first: "If …, do …".
2. Sentence length: at most 20 words in English, 40 characters in Chinese. Code, paths and commands do not count.
3. Give each step a success check: the expected output, status code or version. `healthy` or exit code 0 is not evidence unless the step says what it proves.
4. Write warnings as `> ⚠️`. First sentence: what to do or not do. Second: what happens if you don't. Then the reason. One hazard per warning.
5. Use active voice. Name the owner of each to-do.
6. One term, one meaning: use only the words in this repo's glossary. If a new word has two meanings, split it into two words first, then add them.
7. Date every value that can change: "measured 2026-10-03". Mark anything unchecked as "not verified" and say why. Never write a plan as done.
8. Keep steps, reasons and incident stories apart. An incident story never interrupts the steps.

Does not apply to:
- Explanations and reasons: no length limit, but lead with the conclusion.
- History logs (*-LOG.md, dated running entries): leave them as written.
- Product and brand copy in any language, App Store copy, AI prompts that visitors see.
- The format of "等 Lee" entries in handoff files: the global convention stands.
- TTS narration and voice-over scripts: never split sentences (qwen-tts measured 10 of 10 failures after splitting).
- Scripture, classical and cultural content.

Do not rewrite old docs in bulk. Tidy a section by these rules when you change it.

## Scope in this repo

- Applies to: `docs/Release_Runbook.md`, `docs/Deployment.md`, `docs/HANDOFF_LATEST.md`, `docs/handoff/`, `standalone-edition/RUNBOOK.md`, `standalone-edition/OPERATIONS.md`, `standalone-edition/DEPLOYMENT.md`, `deploy/aws/README_AWS.md`, `docs/QA_Checklist.md`.
- Does not apply to: `docs/customer/`, `docs/sales/`, UI copy.

## Related repo: pwe-clinic

pwe-clinic forked from this repo at v10.20.1 (`147458b`) on 2026-09-17.
It has been an independent product line since 2026-10-07 (Lee).
Fixes are not shared automatically.
When you change security, RLS, billing, Xero or accounting code, say in your report whether pwe-clinic needs the same change.
Both repos share the Claude memory group `studio`.

## Glossary

UI wording is governed by `docs/Glossary.md` and enforced by `backend/scripts/check_terminology.py`. This glossary covers wording in docs only.

| Use | Meaning (one only) | Not |
|---|---|---|
| PWE Studio | The product, in both deliveries (SaaS and Edition). | StudioSaaS, Studio (alone). Keep `StudioSaaS` / `studiosaas` only inside identifiers: package names, paths, env vars. |
| studio-saas | This repository (`kenshinice-ai/studio-saas`). | StudioSaaS (for the repo) |
| tenant (zh: 租户) | One customer business on PWE Studio, with its own data and slug. | studio, 工作室 (for a tenant) |
| Studio plan | The SaaS subscription plan with code `studio`. | Studio (alone) |
| SaaS | The multi-tenant delivery that serves `pwestudio.online` (`STUDIOSAAS_MODE=saas`). | 平台版 |
| Edition | The single-tenant delivery a customer installs on their own host (`STUDIOSAAS_MODE=standalone`). Full name: PWE Studio Edition. | Standalone Edition, 独立版, 单店独立版, standalone (as a noun). Keep `standalone` only as the mode value. |
| pwe-house | The static site at the root of `pwestudio.online`, built from paradise-production. Brand name PWE · 天域 only in external copy. | 房子, house, 门户 |
| product site | The PWE Studio marketing pages at `/studio` and `/zh/studio/`. | 门户, L1 门户, portal |
| tenant portal | The public pages of one tenant at `/<slug>`. | 门户 (alone) |
| host (zh: 主机) | A server that runs PWE Studio. Name which one, e.g. the production host. | box, machine, instance, 机器, 实例 (for a server) |
| local machine (zh: 本机) | The Mac where this repo is checked out and the local gate runs. | laptop, dev machine, 笔记本, 开发机; 本机 for anything on the host |
| release (zh: 发布) | One version taken through the nine steps in `docs/Release_Runbook.md`. | ship, 发版 |
| deploy (zh: 部署) | Step 8 only: put a built commit on a host. | ship, 上线, 发布 (for a deploy) |
| evidence closure | Step 9 only: the docs-only commit that records production and backup evidence. | closure (alone), 收口, 闭环 |
| local gate | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` on the local machine (step 4). | gate (alone), 闸, release gate |
| CI gate | The GitHub Actions workflow `.github/workflows/release-gate.yml`. | GitHub release gate, release gate |
| STOP GATE | Manual checks the release owner does before step 8, listed in the handoff. | gate (alone) |
| Xero gate | The per-tenant switch that lets the worker push to Xero (`/integrations/xero/gate`). | gate (alone) |
| guard (zh: 守卫) | A check inside a release or deploy script that refuses to continue. | guard for a test in the local gate (say "test" and name the file) |
| three-way commit guard (zh: 三方提交守卫) | The check before step 8: `BUILD_INFO` commit, local `HEAD` and `origin/main` must be identical. | three-way runtime guard, 三方守卫 |
