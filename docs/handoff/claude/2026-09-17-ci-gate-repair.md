# 2026-09-17 · GitHub 上的 release gate：60 次运行 0 次绿

> 状态：**已完成，已合入 `main` 并推送**。只改 CI 工作流与测试；零运行时改动，
> 未 bump、未部署——生产仍是 v10.20.1（commit `147458b`）。

## 起点

推送 `7e3e965` 后查 CI：`gh run list --limit 60` → 59 failure、1 in-progress（随后也失败）、
**0 success**。每次都是同样三条，本机 `verify_local.sh` 全绿。

一个恒红的门禁拦不住任何东西：真的回归到来时只是「还是红的」。`verify_local.sh`
第 45–51 行的注释写的正是这件事——它在本机修过一次，CI 没跟上。

## 三条失败

1. `test_python_version_floor.py::test_the_fstring_check_catches_the_line_that_caused_this`
   探测器用 `ast.parse` 解析那行带反斜杠的 f-string。CI 是 Python 3.11——**正是这条
   测试要保护的那个解释器**——而 3.11 对这行的反应是 `SyntaxError`，探测器没接。
   本机 3.14 能解析，所以只有生产用的版本上会坏。
2. `test_tenant_isolation_by_construction.py::test_the_application_role_cannot_bypass_its_own_policies`
3. `…::test_a_query_that_forgets_the_tenant_filter_returns_nothing`
   工作流让应用以 `postgres` 超级用户连库，RLS 无条件失效。**测试是对的，环境是错的。**

## 计划

- 探测器：`SyntaxError` 且消息指向 f-string 里的反斜杠 → 记为命中；其它语法错误照常抛。
- 工作流照 `verify_local.sh` 的配方：属主跑迁移 → `configure_runtime_db_role.py` 建
  `studiosaas_app` → pytest / 隔离测试以受限角色连库，属主 URL 走
  `STUDIOSAAS_OWNER_DATABASE_URL`，`STUDIOSAAS_MIGRATION_DATABASE_URL` 保持未设。
- 查清 CI 收集约 2495 条而本机 3488 条的差额。
- 在 3.11 上本机复现并验证（`uv` 取 3.11），推分支看 CI 变绿，再证明它还能变红。

## 实际做了什么

- `backend/tests/test_python_version_floor.py`：`ast.parse` 抛出「f-string … backslash」
  的 `SyntaxError` 即记为命中；别的语法错误照常抛。
- `.github/workflows/release-gate.yml`：
  - 不再全局导出超级用户 URL。属主跑迁移 → `configure_runtime_db_role.py` 建
    `studiosaas_app` → pytest 与 `test_tenant_isolation.py` 以它连库，属主走
    `STUDIOSAAS_OWNER_DATABASE_URL`；`STUDIOSAAS_MIGRATION_DATABASE_URL` 不进 pytest 步骤
    （理由同 `verify_local.sh`：会把整个进程提升成属主）。
  - 新增一步，在任何测试之前直接问库：当前应用角色 `rolsuper OR rolbypassrls` 必须为假。
  - pytest 加 `-rs`，跳过必须说原因。
  - `fetch-depth: 0`：`test_oracle_deploy_path.py` 要真实提交历史，浅克隆下它自己跳过。
  - 打包步骤传 `PYTHON="$(command -v python)"`。

### 红灯后面还藏着两件

pytest 那一步每次都失败，所以它后面的步骤**在 runner 上一次都没执行过**：

1. 「Build and inspect both delivery forms」一跑就挂——`smoke_release_archive.sh`
   默认找仓库里的 `.venv/bin/python`，runner 没有。
2. 上一轮新写的 4 条部署路径行为测试在 CI 上全部自跳过（浅克隆没有 `origin/main` 历史）。

两件都是「修好第一层才看得见」。

## 验证

| 运行 | 分支 | 结果 |
|---|---|---|
| `35222238765` | `fix/ci-release-gate` | pytest **2448 passed / 0 failed**（首次），隔离 254/0；打包步骤失败（上面第 1 件） |
| `35222547028` | `fix/ci-release-gate` | **success** —— 60 余次里第一次绿。pytest 2452 passed / 43 skipped（多出的 4 条就是不再跳过的部署路径测试），`smoke_release_archive: PASS (2 archive(s))` |
| `35222919034` | `tmp/ci-red-proof`（已删） | 故意让 pytest 以属主连库 → **failure，`2 failed`**，正是那两条 RLS 测试。门禁还会红，而且红在该红的地方 |

3.11 的探测器路径本机没有 3.11 可跑（未经许可不下载解释器），用两种方式验：本机把
`ast.parse` 换成 3.11 形状的拒绝，自测通过且无关 `SyntaxError` 仍然上抛；真 3.11 上由
上表 CI 运行验证。

## 「CI 比本机少一千条测试」——不是 CI 少，是本机多

上一轮本机门禁报 `3447 passed, 41 skipped`，CI 约 2495。差额查清了：
`test_python_version_floor.py` 的 `SOURCES` 是对磁盘上的 `*.py` 做 glob，**把
`.claude/worktrees/` 里两份完整检出也扫了进去**（约 940 条）。worktree 清掉之后本机收集
2546 条；与干净导出（2445）剩下的 ~100 条差额来自 `.agents/skills/` 等未跟踪目录。
CI 没有漏跑任何东西。未改：这个 glob 扫未跟踪文件是噪音而非漏洞，单独处理即可。

## 同一会话里的本地清理（不进仓库）

- 两个 `.claude/worktrees/*` 与 `~/.codex/worktrees/4d8a` 已移除。依据：
  - `backend/media`：本地库 131 条 `media_assets` 中 130 条的文件在主检出里，缺的 1 条
    哪个 worktree 里也没有；worktree 独有的 296 个资产 id 在全库 dump 里只命中
    `audit_logs`（120 行，全是隔离测试 75 字节的夹具上传记录）。没有任何活数据指向它们。
  - `backend/archives`：全部是 `isolation-*` 测试租户的删除快照。
  - codex worktree 的 4 个未提交文件与 `c940ea5`（2026-08-09，已在 main）**逐字节相同**。
- 两个旧 stash 的内容已**复制**到 `achieve/stashes-2026-09-17/`，stash 本身未动。

## 这一轮不声称的

- 没有在真 3.11 解释器上本机跑过；依据是 CI。
- `test_cms.py` 这一步现在不带任何数据库 URL（与本机门禁一致）；此前它拿到的是超级用户 URL。
  它通过了，但我没有逐条核对它是否有依赖数据库的分支因此改走了别的路径。
- 工作流里的运行时角色口令是写死的 CI 专用字符串，只存在于用完即毁的服务容器里。
