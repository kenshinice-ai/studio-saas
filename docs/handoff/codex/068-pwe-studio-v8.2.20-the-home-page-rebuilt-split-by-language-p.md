# PWE Studio v8.2.20 — the home page rebuilt, split by language, priced from the database (deployed 2026-08-03)

## Shipped and live

**1. The page.** `product-home.html` rebuilt on the Paradise design language:
Family Navy end to end, Family Amber as the single accent, φ^(k/2) type,
Fibonacci spacing, 61.8/38.2 splits, 17px root. Seven sections in the order the
owner chose — hero · pain · surfaces · templates · trust · pricing · launch ·
contact. The copy names the operator's day (三个月的群记录, 晚上核 Excel,
抽屉里的收据) instead of describing the software; the English is written to
carry that voice, not translated word for word.

**2. Light and dark, from the system.** Authored dark, re-skinned onto Warm
Paper under `prefers-color-scheme: light`. Both themes are the *same rules*
driven by five surface tokens plus `--accent`, so the layout cannot fork.
Measured, both themes, every text role: worst case 4.52:1 (the light-mode
eyebrow at 13.4px), nothing below AA. The brand mark switches with the theme
via `<picture>` — `pwe-mark-dark.svg` on navy, per Brand_Identity §7.

**3. One language per URL.** `/` is English, `/zh/` is Chinese, `/zh` 301s to
`/zh/`. Reciprocal `hreflang` (en-AU · zh-Hans · x-default) identical on both,
paired canonicals, `Content-Language`, one `<h1>` and one `<title>` each.

  Both languages are still authored in **one file** — the translations cannot
  drift apart — and `services/public_site.filter_language` removes the other
  one server-side. It is an `HTMLParser`, not a regex: start tags are re-emitted
  from `get_starttag_text()`, so a document with nothing to strip comes out
  byte for byte identical, which is asserted. The `data-lang` marker is stripped
  from surviving tags too. **The one rule the markup must keep:** a `data-lang`
  element may not contain another element of the same tag name, because skipping
  counts that tag. A test walks the real page and enforces it.

**4. Pricing is rendered from the plan table**, server-side — cards *and* the
JSON-LD `AggregateOffer`, from the same rows `/v1/public/plans` returns. Not a
client fetch: structured data and prices belong in the HTML, and there is no
empty state without JavaScript. A database outage costs the pricing grid only;
the section falls back to a contact line and the rest of the page is static.
A test asserts **no plan limit or price appears literally in the page** — that
is the property that makes the earlier drift impossible, stated as a check.

## What the rebuild found — a plan row was automatically an offer

Rendering the page against the local database put **`Isolation No Portfolio`,
A$1, on the public pricing grid** beside the real three, and moved the
"Recommended" badge onto Starter — because the badge was inferred from the
median price and a fourth row shifted the median. Production happened to be
clean; nothing was keeping it that way, and `/v1/public/plans` had been serving
the unfiltered table since v8.2.19.

Migration `0023_public_plan_publication.sql`:

* `is_public boolean NOT NULL DEFAULT false` — **false on purpose**. A plan
  created tomorrow is invisible until somebody decides to sell it. Publishing
  is now the deliberate act; the old behaviour was the accident. Backfilled
  true for `starter`/`studio`/`growth` — written as an explicit list, because
  the reason this migration exists is that "what exists" and "what is sold"
  had already diverged.
* `is_recommended` + a unique partial index, so at most one plan wears the
  badge. Setting it in the console clears the others (a radio, not a
  constraint violation the UI never mentioned).
* Console: a **Public** column in the plans table and two checkboxes in the
  add/edit dialog, with the Chinese strings added to `admin-i18n.js`.

## Deployed and verified

`PWE-StudioSaaS-aws-8.2.20-26f609fa9e33`, 2026-08-03. Logical dump taken first
(`studiosaas_studiosaas_20260803T020035Z.dump`). Deep health passed from the
instance and from the public edge; the deploy pruned the v8.2.17 release
directory, the v8.2.19 bundle and the v8.2.17 image behind itself. Disk 16.2%,
47.8 GB free.

**Migration 0023 applied itself.** `deploy/aws/entrypoint.sh` runs
`run_migrations.py` on every container start, before the app serves — checked
in the script rather than assumed, because without it the pricing section
would have 500'd on `is_public`.

Measured live, both languages:

```text
                    /                          /zh/
<html lang>         en                         zh-Hans
Content-Language    en                         zh-Hans
<title>             Studio Management Soft…    工作室管理系统 · 报名、排课…
canonical           https://pwestudio.online/  https://pwestudio.online/zh/
hreflang            en-AU · zh-Hans · x-default (identical on both)
<h1>                1                          1
data-lang left      none                       none
plans               49 / 99 / 199, badge on Studio (both)
JSON-LD offers      AggregateOffer AUD 49–199, offerCount 3 (both)
bytes               44,520                     40,070
```

`/zh` 301s to `/zh/`. `/v1/public/plans`, `/platform-admin`,
`/customer-resources/FAQ.html` and `/lets-paint-showcase` all still 200.

The only CJK remaining on the English page is `中文` (the switch link, carrying
`lang="zh-Hans"`) and `天域文创出品` in the producer credit — the studio's
Chinese name is part of the signature, not translatable copy (Brand_Identity
§10).

**Still to do by hand: submit both URLs to Search Console.** `/zh/` is a new
address with no history, and the hreflang pair only helps once both are known.

`zh` and `en` are now reserved tenant slugs.

## Still open

1. **The Paradise page's plan limits are still wrong at source** (1500 / 100 GB
   against a database that caps at 1000 / 50 GB). `02 WEBSITE/src/build.py`,
   then `python3 build.py --sub`. Not reachable from this repo. Now that
   `/v1/public/plans` is public and filtered, that page could read it instead
   of restating it.
2. **`customer-resources/*.html` still toggle language in the DOM** and read
   `pwe-public-language` from localStorage. The home page sets that key from
   its URL so the footer links stay in the reader's language, but those five
   pages have not been split. They have no SEO ambition; splitting them is the
   consistent finish, not an urgent one.
3. **No web font.** Latin headings fall back to Georgia rather than Playfair
   Display. Deliberate — the front door should not make a render-blocking
   third-party request — but self-hosting Playfair is the upgrade if the
   Latin display type matters more than the ~100 KB.
4. **The 6-step operating flow was dropped** (咨询→跟进→排课→签到→作品→洞察).
   It restated the surface cards as verbs and the reference page is tight for
   exactly that reason. Say so if it should come back.

---

