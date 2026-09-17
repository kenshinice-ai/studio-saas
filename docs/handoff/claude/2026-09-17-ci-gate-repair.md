# 2026-09-17 · GitHub 上的 release gate：60 次运行 0 次绿

> 状态：**进行中**。只改 CI 工作流与测试；零运行时改动，不 bump、不部署。

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

## 验证

（收口时回填）
