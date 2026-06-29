# StudioSaaS MVP Blueprint v1

版本：v1.0  
日期：2026-06-29  
目标：将现有 Let’s Paint CMS 原型重构为可托管在 GitHub、后续部署到 AWS 的多租户 SaaS。

---

## 1. 产品名称与定位

产品名称：**StudioSaaS**

StudioSaaS 是面向小型创意教育工作室的云端管理系统，优先服务儿童美术、手工、陶艺、音乐、舞蹈、语言等课程型工作室。

一句话描述：

> StudioSaaS 帮助小型创意教育工作室管理学生、课时、注册、作品集和品牌化家长入口。

首批目标市场：

- 澳洲本地小型创意教育工作室。
- 1-5 名管理员或老师。
- 20-500 名学生。
- 1-3 个上课地点。
- 希望摆脱 Excel、纸质表格和聊天软件碎片化管理的工作室。

MVP 不优先支持大型连锁机构、复杂排课、完整财务会计、自动在线支付和 App Store 原生应用。

---

## 2. MVP 页面线框图

### 2.1 Super Admin

```text
┌──────────────────────────────────────────────────────────┐
│ StudioSaaS Super Admin                                  │
├──────────────┬───────────────────────────────────────────┤
│ Workspaces   │ [Create Studio]                           │
│ Plans        │                                           │
│ Billing      │ Studio Name | Status | Plan | Students    │
│ Usage        │ Let's Paint | active | Studio | 143        │
│ Audit Logs   │ Clay Lab    | trial  | Starter| 38         │
└──────────────┴───────────────────────────────────────────┘
```

核心动作：创建工作室、暂停/恢复租户、查看套餐、查看用量、查看审计日志。

### 2.2 Studio Admin

```text
┌──────────────────────────────────────────────────────────┐
│ StudioSaaS / Current Studio                              │
├──────────────┬───────────────────────────────────────────┤
│ Dashboard    │ Today: check-ins, low balance, pending     │
│ Students     │ Search | Add | Tags | Balance | Status     │
│ Courses      │ Courses | Packages | Credit unit           │
│ Portfolio    │ Upload | Albums | Public visibility        │
│ Registrations│ Pending registration review                │
│ Settings     │ Brand | Staff | Email | Data export        │
└──────────────┴───────────────────────────────────────────┘
```

核心动作：管理学生、课时、课包、作品集、注册审核、品牌设置、数据导出。

### 2.3 Parent Portal

```text
┌──────────────────────────────────────────────┐
│ Studio Logo + Studio Name                    │
├──────────────────────────────────────────────┤
│ Student Profile                              │
│ Remaining Credits                            │
│ Portfolio                                    │
│ Studio Contact                               │
│ [Register] [Check Balance] [View Portfolio]  │
└──────────────────────────────────────────────┘
```

核心动作：注册、查询余额、查看公开作品集、查看联系方式。

---

## 3. 数据库 Schema v1

数据库：PostgreSQL。  
租户隔离：所有业务数据必须包含 `tenant_id`，所有业务查询必须绑定租户上下文。  
删除策略：学生、课程、用户默认软删除或停用，不做无审计硬删除。

核心表：

| 表 | 用途 |
|---|---|
| `tenants` | 工作室租户、slug、状态、品牌配置 |
| `plans` | 套餐定义 |
| `subscriptions` | 租户订阅状态 |
| `users` | 平台用户 |
| `memberships` | 用户、租户、角色关系 |
| `students` | 学生档案 |
| `courses` | 课程定义 |
| `packages` | 课包定义 |
| `credit_accounts` | 学生余额账户 |
| `credit_transactions` | 充值、扣课、调整、退款流水 |
| `attendance_sessions` | 上课/签到记录 |
| `registrations` | 公开注册申请 |
| `media_assets` | 上传文件元数据 |
| `portfolio_items` | 学生作品集条目 |
| `share_tokens` | 家长端安全访问 token |
| `email_templates` | 每租户邮件模板 |
| `notification_logs` | 邮件/通知发送记录 |
| `audit_logs` | 关键操作审计 |
| `tenant_usage` | 存储、学生数、用户数统计 |

Schema 文件：`letspaint-cms-release/db/schema_v1.sql`

---

## 4. API v1

API 前缀：`/v1`

租户解析顺序：

1. `/s/{tenant_slug}/...`
2. `X-Tenant-Slug` header
3. 子域名，例如 `lets-paint.studiosa.as`

没有租户上下文时，租户级 API 必须返回明确错误，不允许静默使用默认租户。

```text
GET  /v1/health

Auth
POST /v1/auth/login
POST /v1/auth/logout
GET  /v1/auth/me

Tenant
GET   /v1/tenant
PATCH /v1/tenant
GET   /v1/tenant/brand

Students
GET   /v1/students
POST  /v1/students
GET   /v1/students/{student_id}
PATCH /v1/students/{student_id}
POST  /v1/students/{student_id}/archive

Courses and Packages
GET  /v1/courses
POST /v1/courses
GET  /v1/packages
POST /v1/packages

Credits
GET  /v1/students/{student_id}/credits
POST /v1/students/{student_id}/credit-transactions

Portfolio
GET    /v1/students/{student_id}/portfolio
POST   /v1/students/{student_id}/portfolio
PATCH  /v1/portfolio/{portfolio_item_id}
DELETE /v1/portfolio/{portfolio_item_id}

Public
GET  /v1/public/{tenant_slug}/brand
POST /v1/public/{tenant_slug}/registrations
POST /v1/public/{tenant_slug}/balance-query
GET  /v1/public/portfolio/{token}

Super Admin
GET  /v1/admin/tenants
POST /v1/admin/tenants
PATCH /v1/admin/tenants/{tenant_id}
GET  /v1/admin/usage
```

---

## 5. 套餐 v1

| 套餐 | 月费建议 | 限制 | 适合 |
|---|---:|---|---|
| Starter | AUD 49 | 100 学生、2 用户、5GB 存储 | 单老师或刚起步工作室 |
| Studio | AUD 99 | 500 学生、8 用户、30GB 存储 | MVP 主推工作室 |
| Growth | AUD 199 | 1500 学生、20 用户、100GB 存储 | 多地点或增长型工作室 |

可选一次性 setup fee：AUD 299-799，用于品牌设置、数据迁移和培训。

---

## 6. 试点访谈名单

1. Scribble Cat Studios  
   适合验证多地点、小团队、课程报名、儿童/青少年作品管理需求。

2. Fizz Kidz  
   适合验证多地点儿童创意活动、假期项目、生日派对和课后项目的管理流程。

3. Victorian Artists Society Art School  
   适合验证成人/青少年课程、会员、艺术作品和课程管理的扩展市场。

访谈重点：

- 现在如何管理学生资料、课时余额和作品图片。
- 家长最常问什么问题。
- 老师在手机或 iPad 上最需要完成什么动作。
- 是否愿意支付月费和 setup fee。
- 数据迁移、隐私、照片存储和品牌页面的接受度。

---

## 7. 第一阶段重构范围

本阶段目标不是一次性替换整个 Let’s Paint CMS，而是建立 StudioSaaS 的可扩展骨架：

1. Git checkpoint：保存原型基线。
2. PostgreSQL schema v1：定义多租户数据模型。
3. 租户上下文：解析 `tenant_slug/subdomain -> tenant_id`。
4. `/v1` API：建立资源式 API 外壳。
5. 前端入口：拆出 Super Admin、Studio Admin、Parent Portal 三个入口占位。
6. 权限与审计：定义角色、权限检查、审计记录接口。
7. 迁移脚本：把现有 `database.json` 导入为第一个 tenant。
8. 套餐限制：先定义套餐和用量边界，后续接入 Stripe 或其他支付。

---

## 8. AWS 部署方向

MVP 推荐：

- App: AWS Lightsail 或 ECS Fargate。
- Database: Amazon RDS PostgreSQL。
- Object storage: S3，用于照片和作品集。
- CDN: CloudFront，后续用于公开作品和静态资源。
- Secrets: AWS Secrets Manager 或 SSM Parameter Store。
- Email: Amazon SES 或现有 SMTP 过渡。

早期可以继续使用 Lightsail 单机部署，但业务数据应尽快迁移到 RDS，图片迁移到 S3，避免单机磁盘成为扩展瓶颈。
