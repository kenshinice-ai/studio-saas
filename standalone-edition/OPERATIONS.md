# PWE Studio Edition v10.6.4 candidate — 客户运维手册（未发布）

本文给已经完成交付的单店客户使用。把下文 `<slug>` 换成交付工程师提供的
工作室标识，例如 `example-studio`。

## 1. 你需要保管的三样东西

1. 服务器 SSH/控制台凭据；
2. 离线保存的 `/etc/pwe-studio/<slug>.env`；
3. 当前官方安装包及发布方单独提供的 SHA-256。

环境文件包含数据库密码与会话密钥。只应由 root 和已获授权的 Docker
运维人员读取，不要发到聊天群、工单截图或普通邮件。

## 2. 每日状态检查

```bash
pwe-studio-<slug> ps
curl -fsS "https://你的域名/v1/health?deep=1"
pwe-studio-<slug> logs --tail 100 app
```

健康接口失败、容器持续 restarting，或日志出现 `FATAL` 时，不要反复重装；
保留日志并联系维护人员。

常用操作：

```bash
pwe-studio-<slug> restart app
pwe-studio-<slug> logs -f app
pwe-studio-<slug> ps
```

首次安装后，交付操作员可能需要退出 SSH 再重新登录，Docker group 权限才会
生效。

## 3. 数据库备份

系统每天 02:30 由 root 自动备份，默认保留最近 14 份：

```bash
sudo ls -lt /var/lib/pwe-studio/<slug>/backups/postgres | head
sudo tail -100 /var/lib/pwe-studio/<slug>/logs/postgres-backup.log
```

手动备份：

```bash
sudo bash /opt/pwe-studio/<slug>/current/standalone-edition/maintenance.sh \
  --slug <slug> backup
```

每月至少执行一次恢复演练：

```bash
sudo bash /opt/pwe-studio/<slug>/current/standalone-edition/maintenance.sh \
  --slug <slug> restore-dry-run \
  --dump <列表中的dump文件名>
```

看到 `ok: true` 且关键表计数一致才算通过。不要只检查文件存在。

当前 v10.6.4 candidate 的明确边界：自动化覆盖 PostgreSQL；媒体文件异地备份暂不包含。
上传图片仍在独立 Docker volume 中，升级不会删除它，但这不等于已有灾备副本。

## 4. 升级

只接受带 `BUILD_INFO` 且 `mode=standalone` 的官方 Edition 包。解压到新目录后：

```bash
sudo bash standalone-edition/upgrade.sh --slug <slug>
```

升级器会自动：

- 创建升级前数据库备份；
- 保留数据库、媒体、档案和租户工作区卷；
- 切换稳定 `current` 链接；
- 构建并启动新版本；
- deep health 失败时恢复上一个版本与配置。

不要执行 `docker compose down -v`，其中 `-v` 会删除客户数据卷。

## 5. 真实恢复

真实恢复会覆盖当前数据库，只用于已确认的数据损坏或失败升级。先停止业务、
取得客户批准、记录恢复点，再由维护人员执行：

```bash
sudo bash /opt/pwe-studio/<slug>/current/standalone-edition/maintenance.sh \
  --slug <slug> restore \
  --dump <已经通过演练的dump文件名> \
  --confirm studiosaas
```

脚本会停止应用写入、恢复、重启并验证健康。备份之后的新报名、课次、账本和
配置会丢失，不能用它处理普通误操作。

## 6. 磁盘、证书与日志

```bash
df -h
docker system df
systemctl list-timers | grep certbot
sudo nginx -t
```

不要手工删除 `/var/lib/docker/volumes`、`/var/lib/pwe-studio` 或
`/etc/pwe-studio`。日志由 Docker 限制为每文件 10MB、最多 5 个文件；数据库
备份日志在稳定 state 目录。

## 7. 安全事件

如果怀疑服务器或 `.env` 泄露：

1. 立即限制主机网络访问并保留日志；
2. 不要把 secrets 粘贴到聊天或工单；
3. 联系维护人员轮换数据库、Session、API、owner 与 SSH 凭据；
4. 检查审计日志、最近登录和异常导出；
5. 完成确认后再恢复公网。

## 8. 当前不包含的服务

- PWE 平台方不会自动获得客户服务器访问权；
- v10.6.4 candidate 标准安装不包含媒体文件异地备份；
- 本轮没有 AWS/RDS/S3/SES 上线承诺。
