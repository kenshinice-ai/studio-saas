# 独立版 · 部署方式

> 提案文档，随 README.md 一起等待确认。

## 1. 主路径：Docker Compose（单机同箱）

复用平台版已实战验证的 `deploy/aws/` 套件，独立版差异只有三点：

```
┌─ 客户服务器 ──────────────────────────────┐
│  nginx (TLS, bootstrap→certbot 流程已有)   │
│    → app 容器 (waitress, STUDIOSAAS_MODE= │
│       standalone, 依赖 requirements.lock)  │
│    → db 容器 (postgres:16, 即平台版        │
│       --profile local-db，独立版为默认)     │
│  volumes: data / media / archives /        │
│           tenants / pgdata（五卷全持久）    │
└───────────────────────────────────────────┘
```

1. **db 容器成为默认**（平台版它是彩排 profile；单店无 RDS 必要）
2. **`STUDIOSAAS_MODE=standalone`** 环境变量（实现轮新增）
3. compose 项目名/包名独立（`studio-<客户slug>`），避免与平台混装

安装流程（`install.sh` 一条命令，实现轮交付）：

```
install.sh --domain studio.example.com --studio-name "..." \
           [--import-archive 平台导出包 | --import-json 学员JSON]
  = 装 docker → 生成 secrets/.env → up -d（自动迁移）
  → 建租户+owner（或导入）→ certbot 流程 → 验收清单自检
```

升级 = 新发布包解压 → 同一条 `up -d --build`（entrypoint 先迁移后启动，
与平台版一致）；回滚 = 上一发布包重跑（迁移向后兼容政策沿用）。

## 2. 备选：裸机 systemd

客户内网无 Docker 时走 `deploy/aws/systemd/` 路径（v7.7.7 已修好
ReadWritePaths），PostgreSQL 用系统包。文档已有，独立版补 standalone
环境变量即可。

## 3. 打包与版本

- 交付物 = `build_aws_bundle.sh` 产物（BUILD_INFO 含版本+commit）+
  standalone 附件（install.sh、导入模板、客户手册）
- 客户拿到的是**指定版本的完整源码包**（Apache-2.0 内核 + 交付协议
  约束商用条款——COMMERCIAL.md 详述）
- 版本升级节奏与是否含大版本，由维护协议档位决定

## 4. 验收清单（交付日逐项走）

- [ ] `https://<域名>/` 直达门户（根路径不再是 super-admin）
- [ ] `/super-admin` 与 `/v1/admin/*` 全部 404/关闭
- [ ] owner 登录 CMS/Studio Admin；角色账号按名单建好
- [ ] 数据迁移计数与账本总额与源对账单一致（manifest 校验）
- [ ] 手机 4G 提交测试报名 → CMS 待审出现 → 拒绝闭环
- [ ] 备份 cron 已跑出第一份 dump（0600）+ 恢复 dry-run 通过
- [ ] TLS 证书自动续期 timer 生效；`/v1/health?deep=1` 返回 db ok
- [ ] 交接：owner 密码由客户当场改掉；服务器凭据移交记录签字

## 5. 与 Super Admin 的隔离声明（写进合同附件）

独立版**代码层面**关闭平台控制面：无 Super Admin 路由、无平台成员、
无支持模式、无遥测回连。平台方对独立实例**没有任何技术访问能力**；
后续协助（升级/排障）需客户按维护协议主动提供访问，操作全程留在
客户实例自己的审计日志里（owner 可见）。
