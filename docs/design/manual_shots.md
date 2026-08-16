# Manual screenshots — the shot list

Every image in `/manual/` is produced by `backend/scripts/capture_manual_shots.py`
against a local instance and the `lets-paint-showcase` tenant. This file is the
spec the script reads; editing the table changes what gets captured.

**Why a script rather than a person with a screenshot key.** A manual's images
go stale in exactly the way its prose does, and re-shooting by hand is the step
that gets skipped — the same mechanism that left `docs/guides/` on a v8.1.0
baseline for nine releases. A shot list that runs means the next release
re-takes the set instead of re-deriving it.

## Why this tenant

`lets-paint-showcase` exists to be photographed. Its records are **synthetic**
— fictional students, fictional contact details, and synthetic artwork bundled
with the app — and `reset_professional_demo.py` refuses to touch any other
tenant or to copy anything out of a customer one. No screenshot in this manual
can contain a real student.

## Running it

```bash
# 1 · seed the tenant (destructive, showcase only)
export STUDIOSAAS_SHARED_DEMO_PASSWORD='<a local throwaway, ≥12 chars>'
export STUDIOSAAS_DEMO_CREDENTIALS_FILE="$HOME/.studiosaas/showcase-credentials.txt"
cd backend && STUDIOSAAS_DATABASE_URL=<local> python scripts/reset_professional_demo.py \
  --confirm RESET-LETS-PAINT-SHOWCASE

# 2 · start the dev server on 8899, then capture
python scripts/capture_manual_shots.py --base http://localhost:8899
```

The script reads the 0600 credentials file the reset wrote; passwords are never
passed on the command line and never printed.

## Conventions

| | |
|---|---|
| **Viewport** | 1440 × 900 desktop; 390 × 844 for the two screens that are used on a phone |
| **Theme** | the showcase tenant's own theme, light mode |
| **Language** | **each shot is captured twice**, `<name>.en.webp` and `<name>.zh.webp`. A Chinese screenshot in the English manual reads as a different install, not a different language |
| **Format** | WebP, quality 82, capped at 1600px wide, `loading="lazy"` with explicit `width`/`height` |
| **Location** | `backend/frontend/assets/manual/` → served at `/assets/manual/` |
| **Budget** | the whole set stays under 3 MB; the manual's first screen pulls at most three images |

**State the theme in the manual.** A studio on another palette sees different
colours in the same places, and a reader who does not know that assumes their
install is wrong.

## The shots

`role` is which account the script signs in as. `public` means no session.

| file | role | path | viewport | page state needed |
|---|---|---|---|---|
| `01-brand-workbench` | owner | `/lets-paint-showcase/studio-admin` | desktop | signed in, Brand foundation panel, draft preview visible |
| `01-showcase-workbench` | owner | `/lets-paint-showcase/studio-admin` | desktop | signed in, Selected work tab, an unsaved link-only work card showing the video field |
| `01-admissions-messages` | owner | `/lets-paint-showcase/studio-admin?view=messages` | desktop | signed in, Admissions → Family messages panel |
| `02-portal` | public | `/lets-paint-showcase` | desktop | published portal, top of page |
| `02-showcase-portal` | public | `/lets-paint-showcase` | desktop | published portal, scrolled to the synthetic Selected Work section |
| `02-showcase-page` | public | `/lets-paint-showcase/showcase` | desktop | the dedicated Selected Work page (v9.8.10 gave it its own URL); the home band is a six-work teaser that links here |
| `02-register` | public | `/lets-paint-showcase/register` | desktop | empty enquiry form |
| `02-pending` | manager | `/lets-paint-showcase/cms` | desktop | Pending / 待处理 tab, showing the duplicate badge |
| `03-courses` | manager | `/lets-paint-showcase/cms?view=courses` | desktop | Course catalogue / 课程目录 deep link |
| `03-roster` | manager | `/lets-paint-showcase/cms` | desktop | Course Schedule, moved to the next day that actually teaches |
| `03-roster-mobile` | teacher | `/lets-paint-showcase/cms` | mobile | Course Schedule as a teacher sees it |
| `04-timetable` | owner | `/lets-paint-showcase/studio-admin` | desktop | Brand & Website → Public timetable, both switches on, two-week window |
| `04-booking` | public | `/lets-paint-showcase/timetable` | mobile | Synthetic public timetable with the booking request dialog open |
| `04-topup` | manager | `/lets-paint-showcase/cms` | desktop | Recharge & refunds / 充值与退款 tab |
| `04-log` | manager | `/lets-paint-showcase/cms` | desktop | Operation log, unfiltered |
| `05-portfolio` | teacher | `/lets-paint-showcase/cms` | desktop | Students tab, first record opened |
| `05-works` | teacher | `/lets-paint-showcase/cms?view=works` | desktop | Portfolio / 作品管理 deep link |
| `06-student-area` | public | `/lets-paint-showcase` | mobile | student area lookup form |
| `07-settings` | owner | `/lets-paint-showcase/cms?view=settings&section=account` | desktop | Settings / 系统设置 full-page route |
| `08-stats` | manager | `/lets-paint-showcase/cms` | desktop | Business Stats tab |

Tabs inside the CMS are reached by clicking, not by URL — the CMS is a routed
workspace shell. The script drives those clicks by the tab's visible label,
which is why a renamed tab fails the capture loudly instead of silently
producing the wrong screen.

## Callouts

Numbered markers are **DOM text in `manual.html`**, never pixels burnt into the
image: they translate with the page, a screen reader announces them, and they
follow the theme. Each `<figure>` pairs a `.shot` with an `<ol class="marks">`
whose items are numbered by CSS counter, so the numbers cannot fall out of step
with the list.

## Two things the first run found

**The roster was empty.** Today had no class — the showcase teaches Tuesday,
Thursday and Saturday — so the most-used screen in the product would have been
photographed as an empty state. `next_class_date()` moves the capture to the
next day that actually teaches. (`class_schedules.weekday` is 1 = Monday;
Python's `date.weekday()` is 0 = Monday, and the first version of this was off
by one in a way that still produced a plausible screenshot.)

**The English CMS was incomplete.** Capturing every screen in English put the
gaps on a contact sheet: 22 Chinese strings on the roster alone. The
self-contained ones were added to `cms-i18n.js` in the same change. What
remains is number-adjacent fragments — `人`, `次`, `笔`, `条`, `分钟` — which
React splits into their own text nodes; translating those in isolation would
reorder the phrase rather than translate it, so they need the dictionary to
grow pattern support first. **Known gap, not fixed here.**

## v10.2.0 新增：钱这一层的四张

演示租户从 v10.1.1 起带着一学期的账，所以这四张拍出来是有数字的 ——
一张空列表的手册截图教不了任何东西，只会让人以为功能没做完。

| 名称 | 角色 | 位置 | 这张要说明什么 |
|---|---|---|---|
| `09-billing` | owner | `?view=billing` | 筛选栏、四种状态的发票、已开具单据没有编辑入口 |
| `09-finance` | owner | `?view=finance` | 期间可选、老师可搜、承包/雇员决定这笔钱下一步能做什么 |
| `09-billing-identity` | owner | `?view=settings&section=billing-identity` | 开票主体与 ABN；没有它一张发票都开不出去 |
| `09-private-lessons` | owner | `?view=roster` | 一次请假的三个答案分开显示 |

## v10.8.0 — pending capture (next shot run)

| file | role | path | viewport | page state needed |
|---|---|---|---|---|
| `10-statement` | owner | `/lets-paint-showcase/cms?view=billing` | desktop | an invoice selected, Statement panel open on its payer, current month |
| `10-timeline` | owner | `/lets-paint-showcase/cms?view=students` | desktop | a student profile open on 记录 tab, 学员时间线 expanded |
| `10-receivables` | owner | `/lets-paint-showcase/cms` | desktop | dashboard with the receivables card visible (seed leaves one unpaid invoice) |

These three ship in the manual as prose in v10.8.0; the figures join at the
next capture run (the seed needs one unpaid invoice and one issued statement
month to photograph honestly).
