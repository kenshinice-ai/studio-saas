# 2026-10-09 · 两本字典改用术语表已定的词（分支 `feat/wording-dictionaries`）

> 状态：**已提交、已推分支，未合并、未发布**。随下一次发布（v10.20.3）一起带上。
> 发布由 Lee 执行 `pwestudio_arm.sh`。
> 来源：2026-10-08 界面用词审计（Studio 一半）。Clinic 的同类改动是 pwe-clinic `76deb06`。

## 结论

- CMS 和两个控制台改用 `docs/Glossary.md` 已定的词。只改术语表已定的词，有争议的没动。
- 改的是界面文案和字典。零迁移，零接口变化。
- `check_terminology.py` 新加 3 条规则，挡住这次改掉的短语回来。

## 改了什么

| 类别 | 改动 |
|---|---|
| 课包 | 充值课包的「套餐 / package / Quick pack」改为「课包 / credit pack」：`topup.jsx`、`cms-app.jsx` 的提示与确认框、`dashboard.jsx` 的开店清单。 |
| 课时 | 「退课节数」改为「退课课时数」；退款确认框和按钮里的「N 节」改为「N 课时」；「均价/课」改为「均价/课时」；续课提醒阈值按钮改为「N 课时」。英文 `lessons` 改为 `credits`。 |
| 官网 | CMS 报名来源「门户网站」改为「官网」。Studio Admin 帮助文字里的 `the portal` 改为 `your website`。Super Admin 的 `Portal` 链接和 Studio Admin 的健康检查标签改为 `Website`。 |
| 其他 | 「被排了一节课」改为「被排进班次」。`充值结算` 英文改为 `Top-up & settlement`；`待审核` 英文改为 `Pending review`。 |
| 死键 | 删 11 条：核对过源码没有任何地方渲染它们。另有 `Portal`、`Open Portal`、`门户网站` 3 条随源码改名换成了新键。 |
| 文档 | 用户手册 `manual.html` 和 `docs/guides/` 里引用到的旧标签同步改名。术语表加一段：账本备注的 `套餐:` 前缀是数据，不改。 |

## 没改的，和原因

- 「作品 / Works / Portfolio」「画室」「画艺」：等 Lee 定「作品」的禁用范围。
- `Insights / 经营洞察` 导航组：等 Lee 定是否跟 Clinic 一样叫「数据分析」。
- Studio Admin 的 `Portal Label / 门户标题`：这个字段存的是租户门户自己的名字（默认 `Student Portal`），正是术语表留给 portal 的用法。改成「官网」会写错。
- 账本备注 `套餐: <名称>`（`cms-app.jsx` 充值写入）：`api_v1/tenant.py` 的课包销量排行用正则读它。改了旧充值就从排行里消失。
- 发给家长的话术模板里的「N 节」（续课提醒、退课确认话术）和操作日志描述：前者是对外文案，后者是存进日志的数据，本轮不动。

## 验证（2026-10-09，本机）

- local gate：`STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 输出 `All checks passed`。pytest 2464 passed、41 skipped；legacy smoke 73/0；租户隔离 257 passed、0 failed；console smoke 通过。
- 单独再跑 pytest（应用角色连库）：2465 passed、41 skipped。
- 两本字典在 node vm 里执行到 `mount()`，新词逐条翻译正确。
- `build_cms.sh` 重建 `cms-app.js`；`build_asset_manifest.py --check` 通过。
- **没在浏览器里登录 CMS 看。** 证据是字典执行结果和 bundle 一致性检查，不是一次真人操作。
