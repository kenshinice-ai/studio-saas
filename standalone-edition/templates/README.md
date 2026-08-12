# 学员导入模板 · Student import templates

给「现有系统迁入」路径用（DATABASE.md §2 路径 2 /
DEPLOYMENT_PLAN.md §6.4）。
全新开店和平台迁出都不需要这个文件夹。

| 文件 | 给谁 | 用途 |
|---|---|---|
| `students_import_template.csv` | **客户** | 发给客户填。三行示例请客户删掉后再填自己的数据。 |
| `csv_to_import_json.py` | 实施工程师 | 把填好的 CSV 转成导入器要的 JSON，并逐行校验。 |
| `students_import_example.json` | 实施工程师 | 转换结果长什么样（就是模板三行的输出）。 |

## 流程

```bash
# 1. 把模板发给客户，收回填好的文件（下面假设叫 students_filled.csv）

# 2. 在自己机器上转换 —— 校验在这一步发生，错误会指出第几行
python standalone-edition/templates/csv_to_import_json.py students_filled.csv -o students.json

# 3. 交给安装器（它会先跑一次只读预览，再执行）
sudo bash standalone-edition/install.sh --domain … --studio-name … \
    --owner-email … --import-json students.json
```

**第 2 步用的是服务器端同一个校验函数**（`studiosaas.migration.normalize_core_student`）。
能转换成功的文件，导入时不会再因为格式失败 —— 问题在你的笔记本上暴露，
不在客户面前的安装现场。

## 列说明

| 列 | 必填 | 说明 |
|---|---|---|
| `id` | ✅ | 老系统里的稳定标识，**不能重复**。导入后存进 `source_legacy_id`，用于二次核对。 |
| `name` | 二者其一 | 显示名。填了 `firstName` 可以不填。 |
| `firstName` / `lastName` | 二者其一 | 留空时从 `name` 按第一个空格拆分。中文名通常只填 `name`。 |
| `birthday` | | ISO `YYYY-MM-DD`。格式不对直接报错，不猜。 |
| `mobile` / `email` / `wechat` | | 联系方式，原样存。 |
| `remark` | | 落到学员档案的备注字段。 |
| `balance` | ✅ | 剩余课时。可以是小数（`4.5`）。`0` 可以，负数报错。 |
| `archived` | | `true`/`false`，也接受 `1`/`0`、`yes`/`no`、`是`/`否`。留空当 `false`。 |

## 不导入什么（这是产品决策，不是限制）

历史签到、排课、课时流水历史、作品媒体、学员访问码、隐私同意历史 —— 都留在老系统。

导入只写**当前状态**：学员档案 + 一条 `migration` 类型的期初课时账本行（带来源摘要）。
理由见 `DATABASE.md §2`：迁进来的历史无法核对，混进新账本会让第一次对账无从下手。
客户需要历史时，保留老系统只读一段时间比迁移它更可靠。

> 期初余额写成账本行而不是直接写余额字段 —— 所以客户第一天就能在课时流水里
> 看到「期初 12 课时（迁入）」，而不是一个来历不明的数字。

## 交付前必做

转换输出的**学员数和期初课时合计**要和客户自己的账对上。
`csv_to_import_json.py` 每次都会打印这两个数；抄进交接记录，安装后用
Studio Admin → 数据分析 再核一次（DEPLOYMENT_PLAN.md §10 数据验收）。

---

*A PARADISE PRODUCTION · 天域文创出品*
