# PWE Studio v9.6.1 — Studio Admin 执行 handoff

> 状态：历史版本交接记录；当前 Platform Admin 交接入口见文件顶部。版本：`9.6.1`。

## 当前事实

- 源码分支：`codex/v9.3.0-cms-information-architecture`；`VERSION` 已更新为 `9.6.1`；部署候选 commit：`e46a3e3f4a407e8b2ac34ce8e230165c37150ea1`。
- 文档闭环 commit：`cf5303c`（仅更新 handoff、Release Notes 和生产证据；未重新打包或重新部署）；生产仍运行上面的部署候选 commit。
- 当前生产：`https://pwestudio.online`；`/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.6.1`，运行镜像为 `studiosaas:9.6.1`。
- Studio Admin 负责品牌、官网、报名入口、公开课表、草稿、预览与发布；CMS 负责日常运营。
- 家长话术不迁移数据、不新建发送系统，仍保留在 Studio Admin，入口归入「招生入口」子菜单；CMS 继续复制使用。
- 支付、银行转账信息、Gmail/SMTP、AWS SES、短信、SSE、WebSocket、浏览器 Push 均不在本版本。

## 已执行的交付队列

### P0：功能可信度

补齐时区、公开课表、家长话术等字段的 dirty tracking；修复 Registration 快捷入口；补齐课表中英文映射；保留 sticky 保存条安全空间；统一 `?view=` 深链、首次载入与前进/后退行为。

### P1：信息架构与发布中心

用四组工作流替代十个平铺标签：

```text
品牌与官网：品牌基础 / 首屏与行动按钮 / 官网版块 / 工作室作品 / 常见问答
招生入口：报名表 / 公开课表 / 家长话术
发布中心：草稿预览与发布 / 历史版本 / 页面健康
经营洞察：官网数据分析
```

预览明确标为私有草稿；保存条区分未保存、草稿未公开和已发布状态；桌面工作台使用可用宽度，编辑区/预览区维持约 `1.618:1`，平板在拥挤前堆叠预览，移动端改为单列且不依赖横向滚动。预览默认跟随后台语言，但保留独立的中英文对照按钮。

### P2：交接与回归

同步 Studio Admin、Owner 手册、在线用户手册文字与截图、手册截图脚本、Release Notes、版本号和生成资产；完成中英文/桌面移动/键盘/权限/租户隔离/打包/部署验收。`docs/sales/` 既有未跟踪路演资料保留且不纳入提交与发布包。

## 交接验收标准

- `?view=register`、`?view=messages`、`?view=advanced` 能直接打开对应工作区。
- 家长话术继续读取旧 `messageTemplates` 数据并进入现有发布载荷；没有第二个编辑器或发送服务。
- 草稿、预览、已发布官网三者文案不混淆；发布失败有明确恢复路径。
- 本地、双模式发布包和生产 `APP_VERSION` / `BUILD_INFO` / deep health 均为 `9.6.1`。

## 发布与验证证据

- SaaS 包：`dist/PWE-StudioSaaS-aws-9.6.1.tar.gz`；SHA-256：`f1465b393fefb83e962bac41402fff150430c3fcd3e9b7252911d985840aabb4`。
- Edition 包：`dist/PWE-Studio-Edition-9.6.1.tar.gz`；SHA-256：`3d881f7e3324b5acacc4aa89feadd23a278e5cd2cc412f0474d6c13b8deb7e0e`。
- 两个包的 `BUILD_INFO` 均为 `version=9.6.1`、部署候选 commit `e46a3e3f4a407e8b2ac34ce8e230165c37150ea1`，模式分别为 `saas` / `standalone`，构建时间为 `2026-08-10T01:16:13Z`。
- 本次部署前备份：`studiosaas_studiosaas_20260810T011745Z.dump`、`pwestudio-volumes-20260810T011746Z.tar.gz`；逻辑备份 manifest 同时生成。
- 公网 deep health：`appVersion=9.6.1`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；容器 healthy，磁盘可用约 `47.01 GB`。
- 公网 `/`、`/zh/`、`/zh/manual/`、展示租户门户、报名页、CMS、Studio Admin、双语 Release Notes 和中英文 Studio Admin 截图资源均返回 `200`；HTTP → HTTPS 为 `301`，TLS 校验为 `0`，HTTP/2。
- 本地完整门禁：`1945 passed, 8 skipped`；CMS smoke：`73 passed, 0 failed`；租户隔离：`237 passed, 0 failed`；生产部署后最近 5 分钟 app/db 错误关键词计数均为 `0`。
- 浏览器验收覆盖 Studio Admin 2000px 桌面、1024px 平板和 390px 移动布局：宽屏无大块空白，编辑/预览约 `1.618:1`，平板提前堆叠，移动端无横向溢出；后台语言会同步初始预览语言，手动切换后保持独立对照。公网手册为 `zh-Hans`，Studio Admin 未登录入口无控制台错误。

---

