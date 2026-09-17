# 2026-09-17 · 仓库清理：远端分支、旧 stash、路演 deck 的生成器、旧发布包

> 状态：**已完成、已提交、已推送 `origin/main`**。文档与销售素材；零运行时改动，
> **未 bump、未部署**——生产仍是 v10.20.1（commit `147458b`）。
> 授权：Lee 在会话中逐项明确——22 个远端分支全删、两个 stash 可删、deck 源码进仓库、
> `achieve/` 里的旧版本包只留最新两个。

## 计划

1. 删除 `origin` 上除 `main` 外的全部 22 个分支，以及本地两个 `codex/*` 分支。
   其中 2 个未合并——删之前把分支尖端的完整 SHA 记在下面，作为恢复凭据。
2. 丢弃两个旧 stash（内容已核对：一个与 `main` 的既定契约相反，一个见第 3 条）。
3. 路演 deck 的生成器入库。它落后于已跟踪的 `.pptx`，不能原样提交——见下。
4. `achieve/dist/` 只留最新两个版本的包，其余移到废纸篓（不 `rm`）。

## 实际做了什么

### 1. 远端分支：22 → 0（只剩 `main`）

`git push origin --delete` 一次删除 22 个，`git fetch --prune` 后 `git branch -r` 只剩
`origin/main`。本地两个 `codex/*` 分支同时删除。**恢复方式**：下表的 SHA 在本机对象库里
仍然存在（直到 `git gc` 回收不可达对象），`git branch <name> <sha>` 即可找回；GitHub 侧也会
保留一段时间。20 个已合并的分支，其提交本来就在 `main` 上。

| 分支 | 尖端 SHA | 状态 |
|---|---|---|
| `claude/money-layer-v10` | `02e3d41a0b02b23da1d5ba6b0f2f34ee39471701` | 已合并 |
| `claude/online-manual-content-improvement-03b8f9` | `639ab5b4e408c6d6a9b53c9f4d140de3b7db5a6b` | 已合并 |
| `claude/ui-ux-pro-max-audit-073a82` | `811161dd375d33ed503a0df25131392e5db22a40` | 已合并 |
| `codex/portable-online-fixed-password` | `e71503a78bf0c2d64dc181414dff83c18ecc99ec` | 已合并 |
| `codex/product-home-v10.14.0` | `96ab50a0ae54551a97942b062ebaa942eec85375` | 已合并 |
| `codex/pwe-feather-star-brand-rollout` | `0b62f3924fd300dc8c9bd077dbd5de5ce6d48446` | 已合并 |
| `codex/super-admin-tunnel-chain-fix` | `9f884907ec1babe50a85452c91e173e6b99dd429` | 已合并 |
| `codex/v8.0.0-demo-commercial-release` | `abc01ce6e4f281056c3c22fa665e42d7811e0688` | 已合并 |
| `codex/v8.0.1-aws-production` | `6b22af6a424327741d97289a800da18dee3f4722` | 已合并 |
| `codex/v8.0.1-product-home-brand-release` | `0c8d585daf6e0dd156c75a6eede0c9d3e3f07aef` | 已合并 |
| `codex/v8.10.3-manual-refresh` | `08d6839c371d0acb4023a492076120e6d3193abd` | **未合并** |
| `codex/v8.2.1-ics-p0` | `dc06b8cc215da2651ad30d40883e092ffd300e4e` | 已合并 |
| `codex/v9.0.0-brand-cms-release` | `4ce322f8a92ea28254c0736a14d86ba75ef191fc` | 已合并 |
| `codex/v9.1.0-roster-polish` | `be91cf5b36e7ca1c2b16030f3030417077af8019` | 已合并 |
| `codex/v9.1.1-course-schedule-polish` | `d4ba14617c283ef22b7e4071cfd4fb23c7e5e88c` | 已合并 |
| `codex/v9.2.0-cms-notifications` | `d1a9b79d35b6544fcd22f422c3fa2387dc0a6821` | 已合并 |
| `codex/v9.3.0-cms-information-architecture` | `768b8155e02b55a8acf688546b680726ff591b2a` | **未合并** |
| `codex/v9.8.10-public-shell` | `9c53d58d62ba3f1bdc1663d739f169579e98b540` | 已合并 |
| `codex/v9.8.2-showcase-content-recovery` | `4c9f5d39bf7be4504f18cf02010b629921a7072c` | 已合并 |
| `codex/v9.8.9-studio-admin-publish` | `3fc3e69b5f61c3bcfe0ffc44fd3941eb396af4f4` | 已合并 |
| `release/10.18.0-pwe-house` | `3fc745ea93635da489a17785e065fc1cf18edbf0` | 已合并 |
| `rescue/docs-baseline-2026-08-23` | `b78fe7909fff4e6c750aec4087957bd37b605384` | 已合并 |

两个未合并分支的内容：`codex/v8.10.3-manual-refresh` 是 6 个 v8.10.3 手册刷新提交，
`codex/v9.3.0-cms-information-architecture` 是 1 个 v9.8.1 交接文档提交。都是 8 月初的工作，
其后在 `main` 上另行完成；**我没有逐提交核对它们与 `main` 的差异**，删除依据是 Lee 的明确指示。

### 2. 两个 stash：已丢弃

- `stash@{0}`（`f4340ef`，2026-08-15）：让 `backup_postgres.py` 优先读
  `STUDIOSAAS_MIGRATION_DATABASE_URL`。与 `main` 的既定契约**相反**——
  `test_backup_credential_path.py` 的 docstring 记录了 v10.11.1 正是因为改这个契约而卡死在
  自己的部署前备份上，此后刻意锁定「脚本只读 `STUDIOSAAS_DATABASE_URL`」。
- `stash@{1}`（`a759fa2`，2026-08-11）：旧版 `manual.html` 改动（已被后续版本取代）＋
  路演 deck 的生成器（见下）。

### 3. 路演 deck 的生成器入库——校正之后

`docs/sales/roadshow-build.mjs`、`roadshow-assets/`（18 张图 + `design-tokens.css`，5.4 MB）、
`PWE_Studio_Roadshow_Bilingual.html`，以及说明 `docs/sales/ROADSHOW_SOURCE.md`。

**它不能原样提交。** 生成器写于 2026-08-09，随后在 stash 里躺了五周；2026-08-18 那一轮找不到它，
记下「deck 无生成器，是手工 XML 维护」，从此直接改 `.pptx`。于是已跟踪的 deck 走在了生成器前面：

| | stash 里的生成器 | 已跟踪的 `.pptx` / 迁移 0046 / 线上定价页 |
|---|---|---|
| Growth 价格 | $199 | **$189** |
| 学员上限 | 100 / 500 / 1,000 | **50 / 250 / 500** |
| 页数 | 10 | 11（多一张财务 / Xero 页） |

仓库是公开的，价格是一句对外声明，所以入库前按迁移 0046 与现行 deck 校正了价格和三档套餐行
（脚本里 PPTX 与 HTML 两处各 7 个字符串，逐条断言出现次数后替换）。另改一处：`.pptx` 的输出
改到 `docs/sales/build/`（已被 `.gitignore` 的 `build/` 规则覆盖，已验证）——否则运行它会用
10 页旧版覆盖 11 页现行 deck。它依赖的 `@oai/artifact-tool` 不是本仓库的依赖，`npm ci` 装不上，
README 里写明了。

顺带加了 `.claude/launch.json` 的 `sales-static` 配置（`docs/sales` 的静态预览，端口 8898），
验证用，留着以后看销售素材也用得上。

### 4. `achieve/dist/`：只留最新两个版本

保留 v10.19.0 与 v10.20.0（各 SaaS + Edition + `.sha256`，移动后 `shasum -c` 四个全 OK）；
当前版 v10.20.1 在主 `dist/`。其余 331 项（v7.4.0 → v10.18.0、`pre-aws-v8.0.1/`、7 月的候选包，
2.6 GB）连同 stash 的归档副本，**移到 macOS 废纸篓**的 `studiosaas-old-bundles-2026-09-17/`——
没有 `rm`，清空废纸篓之前可恢复。`achieve/` 从 2.9 GB 降到 256 MB。

「最新两个」我取的是**归档区里**的最新两个（加上 `dist/` 里的当前版，本机共三版）；
若本意是总共两版，把 v10.19.0 再移走即可。

## 验证

- 生成器的 HTML 在浏览器里走过：18 张图 0 破损、`design-tokens.css` 已加载、控制台无报错；
  定价页读数 `$49 / $99 / $189` 与 `50 / 250 / 500`；六条套餐文字无横向或纵向溢出；
  1280×720（它的设计画布）下三张价格卡完整可见。800px 宽的面板下画面会被裁切——那是固定画布
  的原设计，不是这次引入的。
- `node --check docs/sales/roadshow-build.mjs` 通过；HTML 的本地引用 0 条悬空。
- 本机门禁（暂存全部改动后）：`verify_local.sh` **All checks passed** —— pytest `2505 passed, 41 skipped`、
  smoke 73/0、租户隔离 254/0。pytest 数比上一轮的 3447 少，是因为 worktree 删了
  （见 `2026-09-17-ci-gate-repair.md`：地板测试对磁盘 glob，曾把两份 worktree 检出一并扫入）。
- 推送后的 CI 结果以 GitHub Actions 为准（本文件在提交时写不了自己那次运行的结论）。

## 这一轮不声称的

- **生成器没有被运行过**（依赖装不上）。验证的是它提交的 HTML 产物和脚本语法，不是一次真实构建。
- 已跟踪的 `.pptx` 与生成器的页脚署名都还是「Powered by Paradise Production · 天域文创 / 天域影像」，
  早于 v10.18.0 的品牌口径（PWE · 天域 = 房子）。**没有改**：那是 deck 内容的决定，不是清理。
- 被移走的旧包没有逐个核对「是否还被某份文档当作可取用的路径引用」；账本里记录的是哈希，不是取用承诺。
