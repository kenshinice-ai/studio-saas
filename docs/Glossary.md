# StudioSaaS Glossary

One word per concept, in each language. When two words exist for the same thing,
a studio owner reading the CMS and Studio Admin on the same day has to work out
whether they mean the same thing — and sometimes they don't.

`backend/scripts/check_terminology.py` enforces the banned column in CI.

## Core terms

| Concept | 中文 | English | Banned | Why |
|---|---|---|---|---|
| A person taking classes | 学员 | student | 客户, customer, client | The KPI tile said 「客户总数」 while 84 other places said 学员. |
| Putting students on a day's list | 排课 | roster | 排班 | The dashboard KPI read 「今日排班」 next to a button reading 「今日排课」. |
| The recurring weekly definition | 班次 | class | 课次 | A `class` is the recurring slot; a `roster` is one day's list. |
| Unit of prepaid teaching time | 课时 | credit | 节 (in UI copy), class (as a unit) | One class may draw more than one credit, so "classes remaining" was wrong. Use **credits**. |
| A pack of prepaid credits | 课包 | credit pack | 套餐 (that is a *plan*) | 套餐 is reserved for the SaaS subscription plan. |
| Marking a student present | 签到 | check-in | 打卡 | — |
| The business renting StudioSaaS | 工作室 | studio | 门店, 商家 | The tenant record; also the default `%VENUE%`. |
| The public venue noun shown to families | `%VENUE%` | `%VENUE%` | 画室 (hard-coded) | Resolved per industry: 画室 / 琴行 / 教室 / 舞蹈教室 / 训练中心. |
| What a student produces | `%WORK%` | `%WORK%` | 作品 (hard-coded) | Resolved per industry: 作品 / 曲目 / 练习 / 舞蹈录像 / 项目. |
| The SaaS subscription tier | 套餐 | plan | 计划, package | — |
| The public marketing site | 官网 | website | 门户, portal | "Portal" is reserved for the tenant portal surface name. |
| The staff operations app | 运营 CMS | CMS | 后台 | 后台 is ambiguous between CMS and Studio Admin. |
| The brand/website admin | 工作室管理 | Studio Admin | 管理后台 | — |
| The platform admin | 平台管理 | Super Admin | 总后台 | — |
| Business figures screen | 经营统计 | Business Stats | 商业洞察 | "Insights" oversells attendance and revenue counts for a small studio. |

## Placeholders

Public templates and family-facing messages use these tokens. Never hard-code
what they stand for.

| Token | Filled with |
|---|---|
| `%VENUE%` | the industry's venue noun (`presets.py` → `venue_noun`) |
| `%WORK%` | the industry's work noun, singular (`presets.py` → `work_noun`) |
| `%WORKS%` | the same noun, English plural (`work_noun.en_plural`) |
| `{student}` | the student's name |
| `{studio}` | the tenant's display name — never the literal word "Studio" |
| `{balance}` | credits remaining |
| `{credits}` | credits just purchased |
| `{fee}` | amount received, already parenthesised, or empty |
| `{note}` | a trailing qualifier such as 「（已用完）」, or empty |

## Bilingual scope

Not everything is translated, and that is a decision rather than an omission.

| Class | Fields | Rule |
|---|---|---|
| **Brand copy** | hero title/subtitle, CTAs, section headings and leads, FAQ, registration title/intro, privacy notice | **Bilingual** `{zh, en}`. A studio writes both, or one is reused for the other. |
| **Studio identity** | welcome message, category label, slogan, principal title/bio/quote, website section labels, registration form title | **Bilingual** `{zh, en}`, stored in `settings.localized_copy`. |
| **Operational data** | `programs[]` name / description / category, `gallery[].title` | **Single language, never translated.** |
| **Literal values** | address, email, phone, tenant name | Never translated. |

**Why operational data is not translated.** Course names and work titles are
typed by front-desk staff during the working day, not written as brand copy.
Requiring a second language there would tax every entry to fix a cosmetic
inconsistency on a page a parent reads once. They render as entered in both
languages, on purpose.

Do not "fix" this by adding translation fields to programs or gallery items,
and do not file it as a zh/en consistency bug. The CMS work-title field and the
Studio Admin **Website sections** panel both say so on screen, so the person
typing knows before they wonder.

**Where the bilingual values live.** All of it is one bundle:
`settings.localized_copy`, a map of `key → {zh, en}`, validated by
`_normalize_localized_copy` on both the read and the write path. The older flat
fields (`tenants.welcome_message`, `settings.slogan`, `website_profile.*_label`,
`principal_profile.title|bio|quote`) are still written with the English value so
the CMS, Super Admin and any older reader keep working; the pair wins wherever
both exist. A tenant saved before a key moved into the bundle has its single
string copied into both languages rather than replaced by an industry default.

One filled language is enough anywhere in the bundle: the empty side is
mirrored from the filled one, because a studio's own words beat a generic
placeholder in either language.

## Language surfaces

Two independent language choices, on purpose — the person who runs the studio and
the family visiting its website are not the same person and do not want the same
language.

| Surface | Storage key | Scope | First visit |
|---|---|---|---|
| Portal, Register (visitor) | `pwe_lang_<slug>` | per tenant | `?lang=` → stored → `navigator.language` → `zh` |
| Studio Admin, Super Admin, CMS (staff) | `studiosaas_admin_language` | one per browser | stored → `zh` |

The visitor key is per tenant because one browser may visit several studios, and
a studio's audience language is a property of that studio. The staff key is
global because one operator works across their own consoles in one language.

`?lang=zh` / `?lang=en` makes each language of a public page a distinct,
shareable URL. `setLang()` keeps `<html lang>`, `og:locale`,
`og:locale:alternate`, the canonical URL and the `hreflang` alternates in step
with it; Chinese is `x-default`, so its canonical carries no query.

## Rules

1. **No emoji as an icon.** Emoji glyphs differ across Windows, Android and
   macOS, cannot take the brand colour or a stroke weight, and are read aloud
   by screen readers as descriptions. Use the inline SVG `Icon` component in
   the CMS, or an inline `<svg>` with `currentColor` elsewhere. Emoji inside
   copy a human wrote (a birthday message they chose) is fine.
2. **No industry-specific noun in shared code.** If a string would be wrong for
   a piano, dance or games studio, it needs `%VENUE%` / `%WORK%`.
3. **No studio name in a literal.** Outbound copy uses `{studio}`.
