# PWE Studio Edition · 实施工程师交付手册（RUNBOOK）

> 交付日全流程。每条命令可直接复制。前置阅读：REQUIREMENTS.md / DEPLOYMENT.md / DATABASE.md。
> 约定：`dc` = `docker compose -p studio-<slug> --env-file standalone-edition/.env -f standalone-edition/docker-compose.edition.yml`

## 0. 交付前检查（出发前一天）

1. [ ] 发布包已生成并校验（`deploy/aws/build_aws_bundle.sh` 产物 + standalone-edition/ 附件；核对 BUILD_INFO 版本与合同一致）
2. [ ] 服务器可达：Ubuntu 22.04/24.04，2C4G+，40GB+ 磁盘，root 或 sudo（REQUIREMENTS.md）
3. [ ] 域名 A 记录已指向服务器 IP（`dig +short <域名>` 返回目标 IP），80/443 入站已放行
4. [ ] 数据路径三选一已和客户确认，并拿到对应材料：
   - 全新开店：店名 / owner 邮箱 / 行业（art dance game general language math music sports）
   - 客户现有系统迁入：客户已填好 `templates/students_import_template.csv`，
     你已在本机跑过 `templates/csv_to_import_json.py` 转成 JSON（转换即校验，
     错误会指出第几行），并与客户书面确认脚本打印的**学员数与期初课时合计**
   - 平台迁出：平台侧已在支持会话下执行导出（见 §2），拿到 `<slug>-edition-bundle-<日期>.tar.gz` + 其 SHA-256
5. [ ] 交接文档打印：验收清单（DEPLOYMENT.md §4）、凭据移交记录表

## 1. 上传发布包

```bash
scp studiosaas-edition-<version>.tar.gz ubuntu@<服务器>:~
ssh ubuntu@<服务器>
tar xzf studiosaas-edition-<version>.tar.gz && cd studiosaas-<version>
```

## 2.（仅平台迁出路径）平台侧导出

在平台服务器、支持会话记录在案后执行（只读，不动租户状态）：

```bash
python standalone-edition/tools/export_tenant_bundle.py \
    --tenant-slug <slug> --output-dir /tmp/edition-out --include-media
# 记下打印的 Bundle sha256，写进交接记录；scp 包到客户服务器
```

平台侧收尾（按合同，验收通过后才做）：归档或删除原租户走既有 Super Admin 流程。

## 3. 安装（三条数据路径，选一条执行）

```bash
# A. 全新开店
sudo bash standalone-edition/install.sh \
    --domain <域名> --studio-name "<店名>" --owner-email <owner邮箱> --industry <行业>

# B. 现有系统迁入（JSON）
sudo bash standalone-edition/install.sh \
    --domain <域名> --studio-name "<店名>" --owner-email <owner邮箱> \
    --industry <行业> --import-json students.json

# C. 平台迁出（bundle）
sudo bash standalone-edition/install.sh \
    --domain <域名> --studio-name "<店名>" --owner-email <owner邮箱> \
    --import-bundle <slug>-edition-bundle-<日期>.tar.gz
```

要点：

1. 安装器会自动装 Docker（有确认提示）、生成 secrets 写入 `standalone-edition/.env`（0600）、起容器（自动迁移）、建租户或导入、然后去掉首启跳过标志重启。
2. 路径 B/C 结束会打印**验收对账单**：学员数、账本余额合计必须与源侧记录一致，拍照存档。
3. 任何一步失败：先 `dc logs --tail 100 app`，修复后重跑同一条命令（重复安装保护会提示 `--force-reinstall`；**除非确认全清重来，否则不要加**）。

## 4. TLS（安装器已打印命令，照抄执行）

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
sudo sed 's/server_name .*;/server_name <域名>;/' deploy/aws/nginx/studiosaas-bootstrap.conf \
    | sudo tee /etc/nginx/sites-available/<slug>.conf >/dev/null
sudo ln -sf /etc/nginx/sites-available/<slug>.conf /etc/nginx/sites-enabled/<slug>.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d <域名>
systemctl list-timers | grep certbot     # 续期 timer 必须在列
```

## 5. 备份 cron（交付默认配置，DATABASE.md §3）

`backups/` 是**主机绑定挂载**（compose `../backups:/app/backups`），因此
`dc up -d --build`（更新步骤）不会清掉 dump 历史 —— 用命名卷或容器内路径都会。
install.sh 已建好该目录并 `chown 10001`。

```bash
( crontab -l 2>/dev/null; cat <<'CRON'
30 2 * * * cd <发布包目录> && docker compose -p studio-<slug> --env-file standalone-edition/.env -f standalone-edition/docker-compose.edition.yml exec -T app python scripts/backup_postgres.py backup >> /var/log/studiosaas-backup.log 2>&1
CRON
) | crontab -

# 立刻手动跑第一份，并在主机上确认文件真的落地（0600）：
dc exec -T app python scripts/backup_postgres.py backup
ls -l <发布包目录>/backups/postgres/

# 恢复演练（写临时库，不碰真实数据）—— 交付时必须当着客户跑一次：
dc exec -T app python scripts/backup_postgres.py restore-dry-run \
    /app/backups/postgres/<刚生成的文件名>
```

**异地副本**：同一台机器上的备份挡不住机器本身坏掉。无维护协议的客户按
OPERATIONS.md §2 自行季度 rsync；护航 Care+ 及以上由我们代管。

## 6. 验收清单（与客户逐项走，DEPLOYMENT.md §4）

1. [ ] `https://<域名>/` 直达门户（不是 super-admin）
2. [ ] `/super-admin`、`/v1/admin/*` 全部 404/关闭
3. [ ] owner 登录 CMS / Studio Admin；员工角色账号按名单建好
4. [ ] 数据计数 + 账本总额与对账单一致（路径 B/C）
5. [ ] 手机 4G 提交测试报名 → CMS 待审出现 → 拒绝闭环
6. [ ] 第一份备份 dump 存在于**主机** `backups/postgres/`（0600）+ `restore-dry-run` 通过
7. [ ] certbot 续期 timer 生效；`/v1/health?deep=1` 返回 db ok
8. [ ] 页脚署名按合同（默认保留）

## 7. 交接仪式（当场完成，缺一不可）

1. owner 用安装器打印的临时密码登录 → **当场改密码**（工程师转身回避）
2. bundle 路径：其余员工账号密码逐个重置发放，旧平台密码全部失效（导入即已置为不可用随机值）
3. 填写并双签**凭据移交记录**：服务器 SSH、`standalone-edition/.env` 备份、DB 密码、域名注册商
4. 提醒：`.env` 即全部秘密，客户须离线保存一份；平台方交付后**无任何技术访问能力**（DEPLOYMENT.md §5）
5. 客户版操作手册 [OPERATIONS.md](OPERATIONS.md) 当面交付，并现场演示：
   §2 每月备份自查（`ls -lt backups/postgres/`）、§3 `restore-dry-run`、
   附录里的 `dc` 速记函数（把 `<你的标识>` 替换好后让客户自己存进备忘录）

## 8. 验收失败回滚

```bash
# 数据/导入问题（最常见）：全清重装 —— 仅在客户确认数据可重导时执行
sudo bash standalone-edition/install.sh ... --force-reinstall   # 需输入 REINSTALL <slug>

# 应用问题：回上一发布包
cd <上一版本目录> && dc up -d --build      # 迁移向后兼容政策沿用（DEPLOYMENT.md §1）

# 彻底放弃当日交付：
dc down            # 保留数据卷；与客户另约时间
dc down -v         # 连数据一起清（客户签字确认后才可执行）
```

回滚后必做：与客户书面确认状态、约定二次交付时间、把失败原因记入交付工单。

---

*A PARADISE PRODUCTION · 天域文创出品*
