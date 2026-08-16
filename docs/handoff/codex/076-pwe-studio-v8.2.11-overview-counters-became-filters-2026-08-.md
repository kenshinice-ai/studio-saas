# PWE Studio v8.2.11 — overview counters became filters (2026-08-02)

**Shipped.** The platform console printed eight numbers an operator could read
but not act on: seeing "Paid Tenants 3" meant scrolling to the tenants table and
reconstructing the filter by hand. Seven of the eight now filter that table
directly.

## The trap this could easily have walked into

Most counters are defined by the **subscription** status:

```sql
paid_tenants  = subscriptions.status = 'active'
trial_tenants = subscriptions.status = 'trialing'
past_due      = subscriptions.status = 'past_due'
```

The Status select in the tenants toolbar filters `tenants.status`. **Two
different fields that share the same vocabulary** — active, trial, past_due.
Wiring a counter to that select is the obvious implementation, it runs without
error, and it is wrong: on the local fixture every tenant carries
`tenants.status = 'active'`, so "Paid Tenants 3" would have listed **5 rows**.
Measured in the browser, both ways:

```text
card says 3  ->  metric filter shows 3 rows   (t.subscription_status === 'active')
card says 3  ->  status select shows 5 rows   (t.status === 'active')
```

So `METRIC_FILTERS` in `super-admin.html` carries one predicate per counter,
each mirroring the SQL in `/v1/admin/usage`, including the
`NOT IN ('archived','deleted')` clause. All seven verified card-value ==
row-count in the browser.

**MRR is deliberately not a button.** It totals money, not tenants; no set of
rows follows from clicking it.

## Two things removed rather than added

* **The "Commercial Attention" card is gone.** It rendered the same three
  metrics as the counters immediately above it, filtered to non-zero — it only
  existed because those counters were not clickable. Removing it took a whole
  card, ~54 lines of JS and ~70 lines of CSS off the page.
* **Hover feedback moved to `button.stat-card`.** It used to sit on every card,
  promising an interaction five of them did not have.

## Applied filters are now visible

Clicking a counter used to set an invisible predicate and jump to a table that
silently disagreed with every control above it — and typing one character into
search wiped it. Now: a dismissible chip under the toolbar, `aria-pressed` on
the counter, a "Filtering" marker so the state is not colour-only (1.4.1), and
the filter composes with search/plan/category instead of being erased by them.
Clicking the pressed counter again releases it.

## Audit log

100 rows rendered flat, with a UUID in every fourth cell and no way to search.
Now 15 per page with prev/next, a filter box, an `n of m events` count, and the
resource column truncated with the full value in `title`.

## Contrast and target sizes, measured not assumed

```text
"Filtering" marker   --brand 3.68:1 on the card -> FAIL at 11px
                     --brand-dark 5.17:1        -> pass
pressed border       3.68:1  (non-text, needs 3.0)   pass
chip border          3.38:1                          pass
chip close button    24x44 -> 44x44 via ::after      pass (2.5.5)
counters             248x59 desktop, 167x71 mobile   pass
```

On mobile the two-up grid leaves ~167px per card and the marker broke the label
across mid-word lines; `.stat-head` wraps there so it drops to its own line.

## A pre-existing i18n bug fixed on the way

Labels written by script after load were past the dictionary pass that runs at
load, so `Page 1 of 7 · 5 tenants` reverted to English after any filter change.
`relabel()` re-localises the specific node. Deliberately per-node, not a subtree
walk: the dictionary translates any text it recognises, and a studio actually
named "Overview" would have become 总览 inside the tenants table.

## Guards

`backend/tests/test_platform_admin_overview.py` — 9 cases. The important two
assert that subscription-scoped counters read `t.subscription_status` and that
lifecycle counters exclude archived/deleted; verified by rewriting the `paid`
predicate to `t.status === 'active'`, which failed both. Suite: 434 passed.

---

