# PWE Studio Edition · 必须环境

> v8.1.0 已实现并纳入发布验证（2026-07-29）。

## 1. 服务器（二选一）

| 形态 | 规格建议 | 适用 |
|---|---|---|
| **云主机（推荐）** | 2 vCPU / 2GB RAM / 40GB SSD 起（AWS Lightsail $10、t4g.micro、阿里云轻量 2C2G 均可） | 绝大多数单店：≤500 学员、≤5 员工并发 |
| 客户自有内网服务器 | 同上规格；需能出网装依赖 | 有 IT 管理能力、坚持数据不出内网的机构 |

单店负载远低于平台版：waitress 8 线程 + 本机 PostgreSQL 同机即可，
无需独立数据库实例（客户坚持 RDS/云数据库亦支持）。

## 2. 软件栈（与平台版一致，安装脚本代装）

- **OS**：Ubuntu 22.04/24.04（推荐）；Debian 12 兼容；macOS 仅限演示
- **运行时**：Docker + docker-compose-v2（主路径，见 DEPLOYMENT.md）
  或裸机 Python 3.11+ / PostgreSQL 16+ / nginx
- **依赖锁定**：沿用 `deploy/aws/requirements.lock`（生产精确版本）
- **PostgreSQL 16+ 硬性要求**（迁移链 0016 使用 PG16 函数）

## 3. 网络与域名

- 客户提供域名一个（如 `studio.example.com`），DNS A 记录指向服务器
- 开放 80/443；TLS 用 certbot（部署脚本含 bootstrap 流程）或客户已有证书
- **无任何回连**：独立版不向平台发送遥测/心跳/授权校验（交付即断链）
- 邮件通知（可选）：客户提供 SMTP（或我们协助申请 SES），不配则通知
  停留在日志模式，业务不受阻

## 4. 安全基线（交付时即配好）

- 与平台版同源的全部安全机制：PBKDF2-600k 密码、CSRF 双层防护、
  安全头、会话 Secure cookie、限流、审计日志
- 独立随机 `SESSION_SECRET` / `API_KEY`（安装脚本生成，600 权限落盘）
- 数据库仅本机监听（同机部署）或 `sslmode=require`（外部库）
- PostgreSQL 每日本地备份 + 保留 14 份（安装器写 root-owned cron）；
  媒体备份按用户决定暂缓，异地数据库副本属维护协议项

## 5. 运维账号边界

- 安装命令使用 `sudo`；secrets 固定在 `/etc/pwe-studio/<slug>.env`
- 安装器把交付操作员加入 `docker` 组，并生成
  `/usr/local/bin/pwe-studio-<slug>`；首次安装后需重新登录一次让组权限生效
- 数据库备份 cron 由 root 执行，不依赖个人 shell、个人 crontab 或登录状态
- Docker 组本身等同主机高权限，只授予合同中指定的运维人员

## 6. 客户侧需要准备的清单（售前发给客户）

1. 服务器（或授权我们代购，费用实报）与 SSH 访问
2. 域名及 DNS 修改权限
3. 品牌素材：Logo、主色偏好、公开文案（或用行业预设起步）
4. 迁移数据：现有学员名单（Excel/JSON）、剩余课时表、套餐定义
5. 一个负责人邮箱（owner 账号）+ 员工名单与角色分配
