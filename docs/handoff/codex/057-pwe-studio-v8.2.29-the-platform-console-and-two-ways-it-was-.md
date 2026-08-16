# PWE Studio v8.2.29 — the platform console, and two ways it was losing data (deployed 2026-08-04)

A UI/UX pass over `/platform-admin` that started as five batches of design
work and turned up two silent data-loss defects on the way in. Both had been
live for weeks. Neither is visible from the code alone; the first was found by
reading a screenshot of the running modal against the API's actual output.

## The subscription dates were being wiped on every save

```text
API      jsonify(datetime)        → "Wed, 29 Jul 2026 00:00:00 GMT"   (RFC 1123)
page     String(v).slice(0, 10)   → "Wed, 29 Ju"                      (assumes ISO)
input    <input type="date" value="Wed, 29 Ju">  → invalid, renders EMPTY
save     $('m_startsAt').value || null            → null
database starts_at = EXCLUDED.starts_at           → NULL
```

Open a studio, change a phone number, press Save: all four subscription dates
gone. The `Wed, 29 Ju` visible in the detail modal was the same bug wearing
its other face — one defect, two symptoms, and the ugly one was the harmless
one.

`dateOnly` now parses and reads **UTC** components. Deliberately UTC: these
are calendar dates and the server sends GMT midnight, so taking local parts
would walk every date backwards by a day for any operator west of Greenwich,
once per save.

## And a second, independent path cleared the trial end

The form never sent `trialEndsAt`. The server read all four dates with
`payload.get(...)`, where an absent key and an explicit null are the same
thing, so **every tenant save wrote NULL over `trial_ends_at`** — the column
the trial state and the expiring-trial counter are both read from.

Two fixes, because either alone would leave the hole open for the next caller:
the form sends the full set, and `_subscription_date` returns a `KEEP`
sentinel for a key nobody mentioned, which the upsert honours per column with
`CASE WHEN %s THEN subscriptions.<col> ELSE EXCLUDED.<col> END`. An explicit
null still clears. `or`-chaining was wrong twice over — an empty string is
falsy, so a deliberate clear fell through to the snake_case key.

## The detail view rendered seven fields twice

`tenant-summary` and `detail-grid` were both being appended, overlapping on
studio, status, subscription, plan, category, student usage, storage and owner
email. It is five tabs now — Overview, Subscription & Billing, Contacts,
Usage, Operations — with a status bar **outside** the tab strip, because
health and quota are the two readings you want no matter which tab answers
your question. Arrow keys, Home and End drive the tablist.

Tabs rather than folds for the detail view, folds for the edit form: one is a
reading surface where the operator already knows which kind of question they
have, the other is a sequence of things to fill in. The folds now carry a
reading of their own contents, so a collapsed form is still scannable.

The same modal printed `20 MB / 50 GB` in one block and `20 / 51200` in
another. Every quota figure goes through `quotaParts` now.

## Light, and finally the family identity

The console sat on Family Warm Paper `#F7F5F2` with cold blue-tinted slate for
every neutral above it and a generic Tailwind blue as the brand. Warm ground
under cold furniture is the disharmony an operator feels before they can name
it.

Light on purpose — this is read for hours. Navy became ink rather than a
surface; amber is the single accent, and on a light ground that means the
**dark** amber, because Family Amber measures 1.70:1 on paper and can only be
a fill with navy on it (9.70:1). Purple is gone: it coloured one KPI stripe
and named a meaning nobody could say out loud.

The token block was the easy half. The test found **eighteen raw cold hex
values** still hard-coded in components — the drift the check exists to catch,
caught on its first run.

* **Spacing** 4/8/12/16/24 → **5/8/13/21/34/55**, the same Fibonacci generator
  as the marketing site and the manual, taken at its low end.
* **Type** twelve ad-hoc sizes → **13 / 17 / 21 / 27 / 34**, each step
  φ^(1/2). Two of those land on Fibonacci integers, which is what happens when
  both come from the same ratio. `--f-min: 12px` is deliberately off the
  ladder — the rung below 13 is 10.2px and this console is read in Chinese.
  That also retires the 11px that was in use, below the floor already.
* **61.8 / 38.2** on the Overview tab.

## Plan editor

Storage is edited in **GB** (51200 was not a number anyone could check).
Entitlements are grouped by who feels them, each with a line saying what it
turns on. The publish controls moved to the **top** with a live preview of the
row a visitor would read — they are the only controls on the page that change
the public website on save. Saving a limit now warns which studios would be
over it immediately. The JSON escape hatch stays, because a flag added
tomorrow has to be reachable, but it validates as you type instead of throwing
after the operator has left the field.

## Verified

1018 tests pass; all three checkers pass. On the running page, with a
synthetic tenant: 0 contrast failures, 0 text under 12px except the 10px
Latin-only producer credit its own brand spec caps, 0 touch targets under
32px, and every new string translating. The header's white-on-navy measures
6.10:1 at its worst stop.

Two things worth remembering:

* The first version of the contrast probe reported three failures in the
  header. All three were false: it walked for `background-color` and the
  header paints a `linear-gradient`, which is a background *image*. Measured
  against both gradient stops directly, everything passes.
* The immutable asset caching added in v8.2.28 means editing an asset without
  bumping the version leaves the browser holding it for a year. Correct in
  production, where a release always changes `?v=`; during development it
  needs a forced revalidation.

## Still to do by hand

* Submit `/sitemap.xml` to Search Console (from v8.2.28).
* Rotate the showcase password that was pasted into chat.

---

