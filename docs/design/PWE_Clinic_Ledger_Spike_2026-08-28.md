# PWE Clinic · 套餐账本 Schema Spike

**日期:** 2026-08-28 · **作者:** Claude（Paradise / TheWoman 项目侧）
**问题:** 诊所垂直的套餐账本，扩展现有 credit 系列，还是平行新表？
**结论:** **平行新表，镜像不变量；发票/收款/Xero 层零改动完全复用。**
**关联:** TheWoman 项目 `PWE_Clinic_Blueprint.md` §2.2/§2.6；本文件是其账本决策的证据链。

---

## 1. 读到的事实（file:line 证据）

| 事实 | 证据 |
|---|---|
| 账户按 (tenant, student, course) 池化，course NULL 为默认户；每学生每课程一池 | `schema_v1.sql:280` `credit_accounts` UNIQUE 约束与部分唯一索引 |
| 单位是课时 `numeric(10,2)`；钱只作为 `fee_aud_cents` 附注在流水上 | `schema_v1.sql:294` `credit_transactions` |
| 流水类型固定枚举 purchase/consume/adjustment/refund/expire/migration | 同上 CHECK |
| **退款来源触发器强制"同一学生"** | `0044:` `assert_credit_transaction_source_is_legal()`：`source_student_id IS DISTINCT FROM NEW.student_id → EXCEPTION` |
| 信用↔发票桥接有形状约束（购买链五键全空/退款链五键全非空） | `0043:226` `credit_financial_links` `legal_shape` CHECK + 合法性触发器 |
| 隔离靠构造：RLS ENABLE+FORCE + `studiosaas.tenant_id` 会话变量 + `studiosaas_app` 角色；0043/0045/0047 的新表全部自带同款 policy | `0042` 头注释；`0043:437-452` |
| 复合外键模式 `(tenant_id, X) REFERENCES parent(tenant_id, id)` 是跨表完整性的标准写法 | `0043` 全部约束、`0044` source FK |
| `billing_accounts` 与人无关（kind: family/organisation，自由联系方式），发票金额单位无关、余额由库生成列派生 | `0034:51` `0034:113` |
| `packages.expires_after_days` 已存在，但无售卖窗口/赠送/共享/类型 | `schema_v1.sql:163` |

## 2. 为什么不扩展 credit 系列（三条硬冲突）

1. **受益人 vs 同学生触发器。** 诊所套餐可供亲友使用，核销的实际使用人 ≠
   持有人；0044 触发器把"流水属于同一 student"写成了数据库层的法律。放松它
   等于为一个垂直削弱教育产品的保护——AGENTS.md §3 明令禁止。
2. **池化 vs 实例化。** 教育模型把课时并进 (student, course) 一个池；诊所的
   每个套餐实例有自己的到期日、赠送构成、受益人清单和余额。把实例语义塞进
   池化账户需要改 UNIQUE 约束和全部读路径。
3. **单位。** 储值卡以分为单位；credit 的 balance/amount 是课时数值，
   `fee_aud_cents` 只是附注。加单位维度会污染每一个现有读写方。

**同时决定不做的事：** 不改 `credit_*` 任何表、不放宽任何 CHECK、不给共享
枚举加值、不动 0044 触发器。

## 3. 复用层（零改动）

`billing_accounts` / `invoices` / `invoice_lines` / `payments` / `credit_notes`
/ `refunds` / `document_number_sequences` / `xero_*` 全部原样使用：

- 诊所客户开票 → 每客户一个 `billing_accounts`（kind 用 `family`，UI 标签
  显示为"客户"；若要加 `client` 枚举值属共享契约变更，另行与主干协商，
  非本 spike 范围）。
- 单号独立前缀系列（建议 `TWC-INV-`），沿用 `document_number_sequences`，
  与 0047 同号守卫兼容。
- 套餐销售一张发票；核销不开票（预付服务的 GST 时点待记账师确认，
  见 Blueprint §9 Q8）。

## 4. 平行层（新表，镜像不变量）

迁移从 **0048** 起，每张表：`tenant_id` + UNIQUE(tenant_id, id) + 复合外键 +
RLS ENABLE+FORCE + 0043 同款 `tenant_isolation` policy + 租户隔离测试。

```text
0048_clinic_client_profiles      -- 1:1 students 扩展（生日/过敏/用药/禁忌/
                                 --   language_pref zh|en|both 默认 both/微信等）
0049_clinic_package_products     -- kind: treatment_pack|value_card|promo_pack
                                 --   unit: sessions|cents（由 kind 推定并 CHECK）
                                 --   适用项目、赠送规则 jsonb、售卖窗口、
                                 --   validity_days、共享政策 jsonb
0050_clinic_package_instances    -- product、owner_student_id、sold_by_user_id、
                                 --   price_paid_cents、expires_at、status、unit（冗余
                                 --   自 product 并 CHECK 一致）
       clinic_package_beneficiaries  -- instance × student + 限制 + added_by
       clinic_package_extension_events -- 旧/新到期、actor、reason（到期日只能走这里改）
0051_clinic_package_ledger       -- 按实例记账，append-only：
                                 --   entry_type: purchase|bonus|consume|adjust|
                                 --     refund|expire|migration
                                 --   amount_sessions numeric NULL / amount_cents int NULL
                                 --     （XOR CHECK，且必须与 instance.unit 一致→触发器）
                                 --   used_by_student_id（受益人核销，可 ≠ owner）
                                 --   service_record_id、balance_after、actor、
                                 --   source_entry_id（refund→purchase 同实例→触发器，
                                 --     镜像 0044 的写法但把"同学生"改为"同实例"）
0052_clinic_package_financial_links -- 镜像 0043 legal_shape：
                                 --   ledger_entry ↔ invoice/line/payment/credit_note/refund
0053_clinic_service_items + service_records  -- performed_by、room、核销实例、金额、
                                 --   临床备注（权限门控）
0054_clinic_membership           -- tiers + client_memberships（auto_suggested|manual）
0055_clinic_consents             -- 通用同意：documents × versions × events（四类，
                                 --   照片三用途独立勾选，签名 media 引用，撤回）
```

余额一致性：`balance_after` 链 + 汇总校验（`SUM(entries) = balance_after` 最新
行）进属性测试；不建余额缓存列，读路径按实例聚合（单店数据量下无性能问题，
与"负债报表"同一查询形状）。

## 5. 测试义务

- 每张新表进 0042 系列的租户隔离测试（现有 254 项的模式）。
- 账本属性测试：XOR 单位、unit 与 instance 一致、受益人核销合法、
  refund 只指向同实例 purchase、到期日只能被 extension_events 改动。
- 链接表形状测试（镜像 0043 现有测试的结构）。
- Edition 归档/导入清单加入全部新表（v10.0 曾发生过租户表被归档遗漏的事故，
  `IMPORT_ORDER` 是严格相等校验——新表忘登记会在打包时炸，这是好事）。

## 6. 对主干的影响面

新增迁移与新表、新界面路由；**共享表零 ALTER**。唯一的潜在共享契约议题是
`billing_accounts.kind` 是否加 `client` 枚举值——本 spike 按"不加，UI 重标签"
处理，留给主干侧将来定夺。
