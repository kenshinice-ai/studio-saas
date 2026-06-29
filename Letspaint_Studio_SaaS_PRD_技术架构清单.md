# Let’s Paint Studio SaaS 产品需求文档 PRD + 技术架构清单

版本：v0.1  
日期：2026-06-29  
文档目的：将现有 Let’s Paint CMS 从单一工作室内部系统，重构为可销售给多个创意教育/培训工作室的标准化 SaaS 平台。

---

## 1. 产品概述

### 1.1 产品名称

暂定名称：**Let’s Paint Studio SaaS**

可选商业名称：

- StudioFlow
- ArtClass CRM
- Creative Studio Manager
- LetsPaint Studio Cloud
- Classfolio Studio

### 1.2 产品定位

一个面向小型至中型创意教育工作室的云端管理系统，支持学生管理、课程/课时管理、作品集展示、家长注册、品牌自定义和多端访问。

目标不是只做一个美术工作室 CMS，而是做成一套可配置、可复用、可销售的 **多租户工作室管理 SaaS 平台**。

### 1.3 一句话描述

> 为美术、音乐、舞蹈、陶艺、语言等创意教育工作室提供可自定义品牌的学生、课程、课时和作品集管理平台。

### 1.4 核心价值

对工作室：

- 减少 Excel、微信、纸质登记表和手动课时记录。
- 提升家长沟通体验。
- 建立专业的作品展示和注册流程。
- 支持品牌化页面和标准化管理。

对家长/学员：

- 快速注册。
- 查看课程余额。
- 查看作品集。
- 获取清晰的课程和联系信息。

对平台运营方：

- 可按月订阅收费。
- 可提供 setup fee + monthly subscription 的半服务型 SaaS。
- 可逐步扩展到多个创意教育细分市场。

---

## 2. 背景与机会

### 2.1 当前基础

现有 Let’s Paint CMS 已具备以下真实业务能力：

- 管理员后台。
- 学员注册页。
- 学生数据管理。
- 课时余额管理。
- 图片上传。
- 学生作品集。
- 邮件配置。
- 数据备份。
- AWS 部署。

这说明产品不是从零假设，而是来自真实工作室使用场景。

### 2.2 标准化机会

许多小型培训/创意教育机构存在类似痛点：

- 学生信息分散。
- 课时余额容易出错。
- 家长沟通依赖聊天软件。
- 学生作品缺少系统化沉淀。
- 缺少专业注册入口。
- 不愿购买复杂昂贵的大型教务系统。

因此可以将当前 CMS 标准化为面向多个工作室的轻量化 SaaS。

---

## 3. 目标客户

### 3.1 首批目标客户

优先面向：

1. 儿童美术工作室。
2. 小型音乐/舞蹈/语言培训机构。
3. 陶艺、手工、摄影等创意课程工作室。
4. 私教或小型课程品牌。

### 3.2 客户规模

MVP 阶段优先支持：

- 1–5 名管理员/老师。
- 20–500 名学生。
- 1–3 个校区或上课地点。
- 每月数百张图片上传。

暂不优先支持大型连锁教育集团。

### 3.3 购买者画像

| 角色 | 需求 | 关注点 |
|---|---|---|
| 工作室老板 | 管理学生、课程、课时、收入 | 简单、稳定、价格合理 |
| 老师 | 快速查看学生、上传作品、记录课程 | 手机/iPad 易用 |
| 前台/管理员 | 注册、课时、联系家长 | 数据清晰、少出错 |
| 家长 | 查看作品、余额、课程信息 | 方便、安心、界面专业 |

---

## 4. 产品范围

### 4.1 产品端口

系统建议分为三个端：

1. **平台管理端 Super Admin**  
   平台运营者使用，用于管理所有工作室、套餐、账单和系统状态。

2. **工作室管理端 Studio Admin**  
   工作室老板、老师、员工使用，是 MVP 核心。

3. **学员/家长端 Student/Parent Portal**  
   家长或学员查看注册、余额、作品集和工作室信息。

后期可增加 iOS App：

- 老师拍照上传。
- 快速扣课时。
- 移动端查看学生。

### 4.2 MVP 版本必须包含

- 多工作室租户。
- 工作室品牌自定义。
- 管理员登录。
- 学生管理。
- 课程和课时单位配置。
- 课时余额管理。
- 图片/作品上传。
- 作品集管理。
- 公开注册页。
- 学员/家长查看入口。
- 基础数据备份。
- 基础权限控制。

### 4.3 MVP 暂不包含

- 完整财务会计系统。
- 复杂排课系统。
- 在线支付自动结算。
- App Store 正式 iOS App。
- 多校区复杂排班。
- 高级营销自动化。
- AI 作品评价。

这些可以作为第二阶段或第三阶段能力。

---

## 5. 用户角色与权限

### 5.1 平台超级管理员 Super Admin

平台运营方使用。

权限：

- 创建/暂停/删除工作室。
- 查看所有工作室状态。
- 管理套餐。
- 查看订阅状态。
- 查看存储使用量。
- 查看系统日志。
- 管理全局配置。
- 触发平台级备份。

限制：

- 默认不直接查看客户敏感学生数据，除非进入支持模式并记录审计日志。

### 5.2 工作室 Owner

工作室拥有者。

权限：

- 管理工作室设置。
- 管理品牌 logo 和颜色。
- 管理课程。
- 管理学生。
- 管理员工账号。
- 查看课时和报表。
- 管理作品集。
- 导入导出数据。

### 5.3 工作室 Staff / Teacher

老师或员工。

权限可配置：

- 查看学生。
- 编辑学生备注。
- 上传作品。
- 扣课时。
- 查看自己的课程或学生。

默认不能：

- 修改账单。
- 修改工作室品牌。
- 删除工作室。
- 查看平台配置。

### 5.4 家长/学员 Parent / Student

权限：

- 登录或通过安全链接访问。
- 查看个人资料。
- 查看课程余额。
- 查看作品集。
- 提交注册信息。
- 更新联系方式。

限制：

- 只能访问自己的数据。
- 不可访问其他学生或后台数据。

---

## 6. 功能需求

## 6.1 多工作室租户管理

### 功能说明

平台支持多个独立工作室，每个工作室拥有独立数据、设置、品牌和用户。

### 需求清单

- 创建工作室。
- 设置工作室 slug，例如 `abc-art-studio`。
- 支持子域名，例如 `abc.yourplatform.com`。
- 支持工作室状态：trial、active、past_due、paused、cancelled。
- 工作室数据隔离。
- 工作室存储限制。
- 工作室用户数量限制。

### 验收标准

- A 工作室无法读取 B 工作室任何学生、课程、作品或设置。
- 同一 API 在不同租户上下文下返回不同数据。
- 所有业务数据必须带 `tenant_id` 或同等隔离字段。

---

## 6.2 品牌自定义

### 功能说明

每个工作室可以自定义对外展示和后台基础品牌。

### 需求清单

- 工作室名称。
- Logo 上传。
- 主色调。
- 辅助色。
- 欢迎语。
- 联系电话。
- Email。
- 地址。
- 社交媒体链接。
- 自定义注册页文案。
- 自定义作品集页文案。

### 后期扩展

- 自定义域名。
- 自定义 favicon。
- 多套主题模板。

### 验收标准

- 注册页和家长端展示当前工作室 logo、名称和颜色。
- 品牌设置变更后无需重新部署即可生效。

---

## 6.3 课程与课时单位配置

### 功能说明

不同工作室可以配置自己的课程、价格、单位和扣课规则。

### 需求清单

- 课程名称。
- 课程描述。
- 课程类别。
- 年龄段。
- 单次课时长度。
- 课时单位：课时、次、小时、节、Credits、Sessions。
- 默认扣课数量。
- 课程价格。
- 是否启用。

### 验收标准

- 工作室 A 可使用“课时”，工作室 B 可使用“Sessions”。
- 学生余额显示单位跟随工作室配置。

---

## 6.4 学生管理

### 功能说明

工作室可以管理学生档案、联系方式、课程、备注和状态。

### 需求清单

- 学生列表。
- 搜索学生。
- 新增学生。
- 编辑学生。
- 学生状态：active、inactive、trial、archived。
- 学生照片。
- 家长信息。
- 联系电话。
- Email。
- 微信/其他联系方式。
- 出生日期。
- 年龄。
- 课程偏好。
- 备注。
- 标签。
- 归档学生。

### 验收标准

- 老师只能看到授权范围内学生。
- Owner 可以查看所有学生。
- 删除建议采用软删除或归档，不直接硬删除。

---

## 6.5 课时余额管理

### 功能说明

记录学生购买、消耗和调整课时的历史。

### 需求清单

- 当前余额。
- 增加课时。
- 扣减课时。
- 手动调整。
- 交易类型：purchase、consume、adjustment、refund、expire。
- 操作人。
- 操作时间。
- 备注。
- 低余额提醒。

### 验收标准

- 每次余额变化必须生成记录。
- 不允许只改余额而没有历史记录。
- 可以追踪是谁在什么时候改了余额。

---

## 6.6 图片与作品集管理

### 功能说明

工作室可以上传学生作品，形成可分享的作品集。

### 需求清单

- 上传图片。
- 图片压缩。
- 图片预览。
- 删除图片。
- 编辑标题。
- 编辑描述。
- 设置作品日期。
- 按学生查看作品。
- 按课程或相册分类。
- 设置公开/隐藏。
- 生成分享链接。

### 后期扩展

- 水印。
- 批量上传。
- 家长下载权限。
- 作品评论。

### 验收标准

- 家长只能看到自己孩子公开的作品。
- 未授权用户不能直接遍历图片地址。
- 图片文件需要和租户绑定。

---

## 6.7 学员注册

### 功能说明

每个工作室拥有独立注册入口。

### URL 示例

```text
https://abc.yourplatform.com/register
https://yourplatform.com/s/abc-art-studio/register
```

### 需求清单

- 注册表单。
- 工作室品牌展示。
- 表单字段配置。
- 提交成功提示。
- 重复学生检查。
- 管理员审核。
- 自动创建学生。

### 可配置字段

- 学生姓名。
- 出生日期。
- 家长姓名。
- 手机。
- Email。
- 微信。
- 课程兴趣。
- 备注。
- 同意隐私政策。

### 验收标准

- 注册数据进入正确租户。
- 注册提交不会暴露其他工作室信息。

---

## 6.8 家长/学员端

### 功能说明

家长或学员可以查看与自己相关的信息。

### 需求清单

- 登录或安全链接访问。
- 查看学生资料。
- 查看课程余额。
- 查看作品集。
- 查看工作室联系方式。
- 更新联系方式。

### 后期扩展

- 预约课程。
- 在线付款。
- 消息通知。

### 验收标准

- 家长只能访问绑定学生。
- 分享链接可设置过期或撤销。

---

## 6.9 邮件和通知

### MVP 需求

- 注册成功通知工作室。
- 低余额提醒，初期可手动发送。
- 邮件模板配置。
- 邮件发送日志。

### 后期扩展

- SMS。
- WhatsApp。
- 微信通知。
- Push Notification。

---

## 6.10 备份与数据导出

### MVP 需求

- 自动数据库备份。
- 文件备份。
- 每租户导出学生数据。
- 平台级恢复流程。
- 保留策略配置。

### 建议默认策略

- 数据库每日自动备份。
- 文件对象存储启用版本化或定期快照。
- 客户可导出 CSV。

### 验收标准

- 单租户数据可导出。
- 系统故障后可恢复。
- 恢复操作需审计。

---

## 7. 非功能需求

## 7.1 安全

- HTTPS 强制。
- 密码哈希存储。
- Token/session 安全管理。
- 租户隔离。
- 服务端强制权限检查。
- 文件访问鉴权。
- 审计日志。
- 防止 IDOR，即通过猜 ID 访问其他租户数据。
- 管理员关键操作二次确认。

## 7.2 性能

MVP 目标：

- 单工作室 500 学生。
- 单工作室 10,000 作品图片。
- 常用接口响应小于 500ms，不含图片上传。
- 图片列表分页。

## 7.3 可用性

- 后台核心功能移动端可用。
- 老师在 iPad 上可快速上传作品。
- 表单保存失败必须明确提示，不允许无声失败。

## 7.4 可维护性

- API 返回统一格式。
- 错误码统一。
- 数据库迁移版本化。
- 日志可追踪。
- 自动化测试覆盖核心业务。

---

## 8. 技术架构建议

## 8.1 推荐架构

```text
Web Frontend / Admin Portal
        ↓
Backend API
        ↓
PostgreSQL + Object Storage
        ↓
Backup / Monitoring / Email Service
```

### 推荐技术栈 A：快速商业化

- Frontend：React / Next.js / TypeScript
- Backend：FastAPI / Python
- Database：PostgreSQL
- Storage：AWS S3 or compatible object storage
- Auth：Session/JWT + role-based access control
- Email：AWS SES / SendGrid / SMTP
- Deployment：AWS Lightsail 起步，后期 ECS/Fargate/RDS

### 推荐技术栈 B：企业结构更强

- Frontend：Next.js / TypeScript
- Backend：NestJS / TypeScript
- Database：PostgreSQL
- Storage：S3
- Queue：BullMQ / Redis
- Deployment：AWS ECS / RDS / S3 / CloudFront

### 不建议 MVP 继续使用

- JSON 文件作为主数据库。
- 单实例无数据库备份策略。
- 图片直接散落在应用目录中。

现有系统可作为原型参考，但商业 SaaS 应迁移到正式数据库。

---

## 8.2 多租户架构

### 推荐方式

MVP 使用共享数据库 + `tenant_id` 隔离。

每个核心业务表包含：

```text
tenant_id UUID NOT NULL
```

查询时必须加租户条件：

```sql
WHERE tenant_id = :current_tenant_id
```

### 后期增强

- PostgreSQL Row Level Security。
- 大客户独立数据库。
- 大客户独立存储 bucket/prefix。

### 数据隔离原则

- 所有 API 根据当前登录用户解析 tenant。
- 前端传入的 tenant_id 不可信。
- 服务端必须从 session/token 中确定 tenant。
- 文件路径必须包含 tenant scope。

---

## 9. 数据库模型草案

### 9.1 平台表

#### tenants

- id
- name
- slug
- status
- plan_id
- timezone
- locale
- created_at
- updated_at

#### tenant_branding

- id
- tenant_id
- logo_url
- primary_color
- secondary_color
- welcome_text
- contact_email
- phone
- address

#### plans

- id
- name
- max_students
- max_staff
- storage_limit_mb
- monthly_price
- yearly_price

#### subscriptions

- id
- tenant_id
- plan_id
- status
- current_period_start
- current_period_end
- payment_provider
- provider_subscription_id

---

### 9.2 用户与权限

#### users

- id
- tenant_id nullable for super admin
- email
- password_hash
- name
- role
- status
- last_login_at
- created_at

#### roles

- id
- tenant_id
- name
- permissions jsonb

#### sessions

- id
- user_id
- token_hash
- expires_at
- created_at

---

### 9.3 学生与家长

#### students

- id
- tenant_id
- first_name
- last_name
- display_name
- date_of_birth
- status
- notes
- avatar_url
- created_at
- updated_at
- archived_at

#### guardians

- id
- tenant_id
- student_id
- name
- phone
- email
- relationship
- wechat
- notes

---

### 9.4 课程与课时

#### courses

- id
- tenant_id
- name
- description
- unit_label
- default_debit_amount
- default_duration_minutes
- price
- status

#### enrollments

- id
- tenant_id
- student_id
- course_id
- status
- started_at
- ended_at

#### lesson_balances

- id
- tenant_id
- student_id
- course_id nullable
- balance_amount
- unit_label
- updated_at

#### lesson_transactions

- id
- tenant_id
- student_id
- course_id nullable
- type
- amount
- balance_after
- note
- created_by
- created_at

---

### 9.5 作品与文件

#### media_files

- id
- tenant_id
- student_id nullable
- storage_key
- original_filename
- mime_type
- size_bytes
- width
- height
- created_by
- created_at

#### portfolio_items

- id
- tenant_id
- student_id
- media_file_id
- title
- description
- work_date
- visibility
- sort_order
- created_at
- updated_at

#### share_links

- id
- tenant_id
- student_id nullable
- portfolio_item_id nullable
- token
- expires_at
- revoked_at
- created_at

---

### 9.6 系统与审计

#### audit_logs

- id
- tenant_id
- actor_user_id
- action
- entity_type
- entity_id
- metadata jsonb
- ip_address
- created_at

#### backup_jobs

- id
- tenant_id nullable
- status
- backup_type
- file_url
- size_bytes
- started_at
- completed_at
- error_message

---

## 10. API 设计草案

### 10.1 统一返回格式

成功：

```json
{
  "ok": true,
  "data": {},
  "error": null
}
```

失败：

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "STUDENT_NOT_FOUND",
    "message": "Student not found"
  }
}
```

---

### 10.2 平台 Admin API

```text
POST   /platform/login
GET    /platform/tenants
POST   /platform/tenants
GET    /platform/tenants/:id
PATCH  /platform/tenants/:id
POST   /platform/tenants/:id/suspend
GET    /platform/plans
POST   /platform/plans
GET    /platform/system/health
```

---

### 10.3 工作室 Admin API

```text
POST   /api/admin/login
POST   /api/admin/logout
GET    /api/admin/me

GET    /api/admin/settings
PATCH  /api/admin/settings
POST   /api/admin/logo

GET    /api/admin/students
POST   /api/admin/students
GET    /api/admin/students/:id
PATCH  /api/admin/students/:id
POST   /api/admin/students/:id/archive

GET    /api/admin/courses
POST   /api/admin/courses
PATCH  /api/admin/courses/:id

GET    /api/admin/students/:id/balance
POST   /api/admin/students/:id/lesson-transactions
GET    /api/admin/students/:id/lesson-transactions

POST   /api/admin/media/upload
GET    /api/admin/students/:id/portfolio
POST   /api/admin/students/:id/portfolio
PATCH  /api/admin/portfolio/:id
DELETE /api/admin/portfolio/:id

GET    /api/admin/backups
POST   /api/admin/backups
GET    /api/admin/audit-logs
```

---

### 10.4 学员/家长 API

```text
GET    /public/studios/:slug
POST   /public/studios/:slug/register

POST   /student/login
GET    /student/me
GET    /student/balance
GET    /student/portfolio
PATCH  /student/profile

GET    /share/portfolio/:token
```

---

## 11. 前端页面清单

## 11.1 平台超级管理员页面

- 平台登录。
- 工作室列表。
- 新建工作室。
- 工作室详情。
- 套餐管理。
- 系统状态。
- 使用量统计。
- 支持模式入口。

## 11.2 工作室管理后台页面

- 登录页。
- Dashboard。
- 学生列表。
- 学生详情。
- 新增/编辑学生。
- 课时余额页面。
- 课程管理。
- 作品集管理。
- 图片上传。
- 注册表单设置。
- 品牌设置。
- 员工管理。
- 备份/导出。
- 系统设置。

## 11.3 学员/家长页面

- 工作室公开主页。
- 注册页。
- 登录页。
- 我的资料。
- 我的课时余额。
- 我的作品集。
- 分享作品页面。

---

## 12. 商业套餐草案

### 12.1 Starter

适合小型个人工作室。

- 最多 100 学生。
- 2 个员工账号。
- 5GB 存储。
- 品牌自定义。
- 学员注册页。

建议价格：AUD 29–49/月。

### 12.2 Studio

适合稳定运营工作室。

- 最多 500 学生。
- 10 个员工账号。
- 50GB 存储。
- 作品集分享。
- 数据导出。
- 邮件通知。

建议价格：AUD 79–129/月。

### 12.3 Pro

适合多老师、多课程工作室。

- 2000+ 学生。
- 更多员工账号。
- 200GB 存储。
- 自定义域名。
- 高级报表。
- 优先支持。

建议价格：AUD 149–299/月。

### 12.4 Setup Fee

前期建议采用半服务型 SaaS：

- 一次性设置费：AUD 299–999。
- 包含数据导入、品牌配置、初始培训。

---

## 13. 开发路线图

## Phase 0：产品定义与原型，1–2 周

产出：

- 完整 PRD。
- 数据模型。
- 页面线框图。
- API 草案。
- 商业套餐。
- 试点客户名单。

## Phase 1：SaaS MVP，8–12 周

目标：支持 1–3 个试点工作室真实使用。

包含：

- 多租户基础。
- 工作室后台。
- 学生管理。
- 课程管理。
- 课时余额。
- 作品上传。
- 注册页。
- 品牌自定义。
- 基础备份。

## Phase 2：试点优化，4–8 周

包含：

- 修复真实使用问题。
- 优化 UI。
- 数据导入工具。
- 权限细化。
- 邮件通知。
- 报表增强。

## Phase 3：商业发布，2–4 个月

包含：

- 官网。
- 价格页。
- 订阅系统。
- 客户自助开通。
- 隐私政策。
- 服务条款。
- 支持后台。
- 系统监控。

## Phase 4：移动 App，2–4 个月

优先做老师/管理员端：

- 拍照上传作品。
- 快速扣课时。
- 快速搜索学生。
- 当日课程列表。

---

## 14. 工作量估算

| 阶段 | 工作量 | 说明 |
|---|---:|---|
| PRD + 原型 | 1–2 周 | 明确产品和页面 |
| SaaS MVP | 8–12 周 | 可给试点客户使用 |
| 试点迭代 | 4–8 周 | 根据真实客户反馈调整 |
| 正式商业版 | 4–6 个月 | 可公开销售 |
| 成熟 SaaS | 6–12 个月 | 自助开通、账单、App、扩展能力 |

---

## 15. 关键风险

### 15.1 范围膨胀

风险：每个工作室都要求定制。  
控制：只允许配置，不轻易做客户专属代码。

### 15.2 数据隔离风险

风险：A 工作室看到 B 工作室数据。  
控制：tenant_id 强制隔离、服务端权限检查、测试覆盖。

### 15.3 图片存储成本

风险：作品图片越来越多。  
控制：图片压缩、存储套餐限制、对象存储生命周期规则。

### 15.4 客服负担

风险：客户不会导入数据或配置系统。  
控制：setup fee、模板、导入工具、帮助文档。

### 15.5 法律和隐私

风险：涉及儿童照片和个人信息。  
控制：隐私政策、家长同意、权限控制、数据删除/导出机制。

---

## 16. MVP 验收标准

MVP 视为完成，当满足：

1. 可创建至少 3 个独立工作室。
2. 每个工作室可上传自己的 logo 和设置课程单位。
3. 每个工作室可管理自己的学生。
4. 每个学生可记录课时余额和交易历史。
5. 每个工作室可上传学生作品。
6. 家长可通过公开入口注册。
7. 家长只能查看自己孩子相关数据。
8. 平台管理员可查看工作室状态。
9. 数据库有自动备份。
10. 关键操作有审计日志。
11. 所有 API 均强制租户隔离。
12. 系统可部署到云端并稳定运行。

---

## 17. 建议下一步

建议下一步不是马上写 App，而是先完成 SaaS 产品蓝图的落地设计：

1. 确定产品名称和目标市场。
2. 画 MVP 页面线框图。
3. 确定数据库 schema v1。
4. 确定 API v1。
5. 确定 3 个套餐。
6. 找 2–3 个潜在试点工作室访谈。
7. 以现有 Let’s Paint CMS 为原型，重构为多租户 SaaS。

---

## 18. 决策建议

推荐策略：

```text
不要直接把现有 CMS 简单复制出售。
也不要第一步就做完整 iOS App。

先做 Web SaaS 多租户平台，保留作品集和课时管理作为差异化核心。
等 Web SaaS 跑通后，再做老师端 iOS App。
```

商业化路径：

```text
半服务型 SaaS
= 一次性设置费 + 月费
= 前期更容易成交，也能支持客户上手
```

产品边界：

```text
允许 logo、颜色、课程、字段、文案配置。
不为每个客户写独立代码。
```

这会让系统可销售、可维护、可扩展。
