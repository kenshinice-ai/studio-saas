# PWE Studio Edition · 部署方式

> 当前源码候选：v10.9.1（未提交、未打包、未交付）；最后验证的 Edition
> 运行包仍为 v10.6.3。Edition 包内 `BUILD_INFO` 必须包含
> `mode=standalone`；客户/实施人员的完整部署方案见
> [DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md)。

## 1. 主路径：Docker Compose（单机同箱）

复用平台版容器基础，独立版固定为单机 Docker Compose：

```
┌─ 客户服务器 ──────────────────────────────┐
│  nginx (TLS, bootstrap→certbot 流程已有)   │
│    → app 容器 (waitress, STUDIOSAAS_MODE= │
│       standalone, 依赖 requirements.lock)  │
│    → db 容器 (postgres:16，独立版默认服务)  │
│  volumes: data / media / archives /        │
│           tenants / pgdata（五卷全持久）    │
└───────────────────────────────────────────┘
```

1. **db 容器成为默认**（单店无 RDS 必要）
2. `STUDIOSAAS_MODE=standalone`，数据库总共恰好一个 active 租户
3. 应用使用 `studiosaas_app` 最小权限角色；迁移 owner 只在 entrypoint
   启动阶段可见，启动 server 前即从环境移除
4. compose 项目名独立（`studio-<客户slug>`）
5. secrets、数据库备份、当前版本指针都在发布目录之外：
   `/etc/pwe-studio`、`/var/lib/pwe-studio`、`/opt/pwe-studio/<slug>/current`

安装流程（`install.sh` 一条命令，实现轮交付）：

```
install.sh --domain studio.example.com --studio-name "..." \
           [--import-bundle 平台导出包 --expected-bundle-sha256 <可信值> \
            | --import-json 学员JSON]
  = 装 docker → 生成稳定 secrets + 运维 wrapper → up -d（自动迁移）
  → 建租户+owner（或导入）→ certbot 流程 → 验收清单自检
```

升级使用新包内的：

```bash
sudo bash standalone-edition/upgrade.sh --slug <客户slug>
```

脚本先创建 PostgreSQL 备份，再切换稳定 `current` 链接并构建；深度健康
检查失败时自动恢复上一代码与配置。PostgreSQL/media named volumes 不删除。
媒体自动备份按用户决定暂缓，因此“升级保留媒体”不能等同“服务器损坏可恢复媒体”。

## 2. 备选：裸机 systemd（定制路径）

客户内网明确禁止 Docker 时，才考虑 `deploy/aws/systemd/` 路径和系统包
PostgreSQL。它不会复用 Edition 的一键安装器、默认卷布局、root backup cron
和交付 wrapper，因此不属于标准客户交付；需要单独的实施方案、备份方案和
验收报价，不能把裸机路径与 Docker 路径混写。

## 3. 打包与版本

- 交付物 = `build_aws_bundle.sh --edition` 产物（BUILD_INFO 含版本、commit、
  `mode=standalone`）+ standalone 附件（install.sh、导入模板、客户手册）
- 候选包名为 `PWE-Studio-Edition-10.9.1.tar.gz`，但本轮尚未构建；不得发送或部署。
  候选包构建后，发送前必须在包所在目录执行
  `shasum -a 256 -c PWE-Studio-Edition-10.9.1.tar.gz.sha256`
- 客户拿到的是**指定版本的完整源码包**（Apache-2.0 内核 + 交付协议
  约束商用条款——COMMERCIAL.md 详述）
- 版本升级节奏与是否含大版本，由维护协议档位决定

## 4. 验收清单（交付日逐项走）

- [ ] `https://<域名>/` 直达门户（根路径不再是 super-admin）
- [ ] `/platform-admin`、`/super-admin` 与 `/v1/admin/*` 全部 404/关闭
- [ ] owner 登录 CMS/Studio Admin；角色账号按名单建好
- [ ] 数据迁移计数与账本总额与源对账单一致（manifest 校验）
- [ ] 平台迁出包的整包 SHA-256 与平台侧交接记录一致
- [ ] 主机只公开 80/443，8899 和 5432 未暴露到公网
- [ ] 手机 4G 提交测试报名 → CMS 待审出现 → 拒绝闭环
- [ ] root cron 已跑出第一份 PostgreSQL dump 和 manifest（均 0600）+
      恢复 dry-run 通过
- [ ] TLS 证书自动续期 timer 生效；`/v1/health?deep=1` 返回 db ok
- [ ] 交接：owner 密码由客户当场改掉；服务器凭据移交记录签字

## 5. 与 Super Admin 的隔离声明（写进合同附件）

独立版**代码层面**关闭平台控制面：无 Super Admin 路由、无平台成员、
无支持模式、无遥测回连。平台方对独立实例**没有任何技术访问能力**；
后续协助（升级/排障）需客户按维护协议主动提供访问，操作全程留在
客户实例自己的审计日志里（owner 可见）。

## 6. 当前运营边界

- SaaS：**已上线生产**，`https://pwestudio.online`，AWS Lightsail 单实例，
  host nginx 终止 TLS，容器内 PostgreSQL 16 + 本机媒体卷（2026-07-30）。
  Cloudflare Tunnel 已退出生产链路，只保留本地开发用途
- Edition：可构建、可安装、可升级的软件交付形态；当前没有客户实例的
  公网生产验收证据，交付前仍须严格走 RUNBOOK 和客户签收。Edition 装在
  客户自己的主机上，不受上述 SaaS 托管形态影响
- RDS/S3/SES：代码与历史方案保留，**未采用**；SaaS 生产的数据库与媒体都在
  同一实例上
- 媒体独立备份、异地备份副本、监控与 SLA：标准安装不包含，必须在合同或
  维护协议中单独确认
