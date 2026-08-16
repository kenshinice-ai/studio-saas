# PWE Studio v8.2.19 — pricing endpoint and credit shipped; page port ready to execute (2026-08-02)

## Shipped

* **`/v1/public/plans`** — no auth, public fields only, `Cache-Control: 300`.
  Live and returning the three real plans. The query names its columns and
  omits `features`: that column carries entitlement flags edited from the
  platform console by someone thinking about billing, not about a public page.
* **Producer credit is a link.** `A Paradise Production · 天域文创出品` →
  `/paradise-production/`, and `Brand_Identity.md §10` changed with it.
  **Tenant footers deliberately unchanged**: `Powered by Paradise Production`
  is white-label attribution on somebody else's site, often in English, and the
  line a commercial agreement may remove — 出品 would overclaim there, and an
  outbound link on a customer's page is not ours to add.

## The plan numbers disagree, and the database wins

Confirmed by the owner: the database is authoritative.

```text
                 database (authoritative)        paradise page (wrong)
starter          100 students /  1 user /  2 GB  100 / 2 /   5 GB
studio           500 students /  5 users / 10 GB 500 / 8 /  30 GB
growth          1000 students / 20 users / 50 GB 1500 / 20 / 100 GB
```

Prices agree (A$49 / 99 / 199) and the Setup fee A$299–999 matches. Only the
limits drifted — which is exactly the failure a hardcoded marketing page
produces, and exactly what the new endpoint prevents on our side. **The
Paradise page needs its limits corrected at source** (`02 WEBSITE/src/build.py`
in the PARADISE PRODUCTION folder, then `python3 build.py --sub`).

## Copy to port — the owner's preferred version, verbatim

Source: `https://paradise-production.pages.dev/pwe-studio`. Pricing excluded
(that comes from the endpoint now). Seven sections:

```text
HERO      把时间还给创作
          官网获客 · 在线报名 · 课时账本 · 品牌门面 —— 琐事交给系统，你回到教室与作品。
          创意工作室的一体化操作系统，面向美术 / 音乐 / 舞蹈工作室与培训机构。

PAIN      你的才华，不该耗在台账和聊天记录里
          开工作室是因为热爱创作与教学。没有人是为了对账、催费、翻聊天记录才创业的。
          · 被打断的排练 —— 「还剩几节课？」一句询问，要翻三个月的群记录才答得上。
          · 深夜的对账表 —— 白天上课，晚上核 Excel，吃掉的是备课和新作品的时间。
          · 经不起丢的纸条 —— 收据在抽屉、承诺在口头，家长的信任不该系在一张纸上。
          · 看不见的作品墙 —— 作品攒了一屋子，线上无处可看，新学员只能靠转介绍。

SURFACES  台前是你的品牌，幕后是一个系统
          · 门户 Portal / 快速报名 Register / 运营 CMS / 品牌工作台
          + 另有平台侧 Super Admin……平台方不接触学员敏感数据，进店必须走留痕的支持模式。

TRUST     钱和信任，写进系统，不写在人情里
          · 账本不可篡改 · 权限写死在后端 · 未成年人隐私

PRICING   透明定价，随工作室一起成长      ← data from /v1/public/plans

ONBOARD   从签约到开幕，只需四步
          1 品牌配置 · 2 数据导入 · 3 团队培训 · 4 正式上线
          四步全部包含在一次性 Setup 服务费内。机构不需要懂技术。

CTA       管理退到幕后，作品站上台前。
          预约一次 30 分钟演示：用你工作室的名字、作品和课程，现场生成一个可预览的门户。
```

**Why this copy is better than what the home page has now**, in one line: it
names the operator's day (三个月的群记录、晚上核 Excel、抽屉里的收据) instead of
describing the software's features. The current page opens with "Put
administration behind the scenes" — a claim; this one opens with a grievance
the reader already has.

## What is left, in order

1. **Port the copy and the dark/amber/φ design into `product-home.html`**, with
   the pricing section reading `/v1/public/plans`.
2. **`/` + `/en/` split with hreflang.** Do it after 1, so the split happens
   once on the final markup. Today one URL serves both languages with no
   hreflang and a self-referential canonical — 69 `data-lang="zh"` nodes and a
   duplicated `<h1>` in the English DOM.
3. **Correct the Paradise page's plan limits** at source; the page is generated
   from `02 WEBSITE/src/build.py`, not editable from this repo.

Both projects already share the token system — `--navy #0E1729`,
`--amber #F5B335`, `--amber-d #A16207` (light-surface safe) — so this is
applying an identity both sides already own, not inventing one.

---

