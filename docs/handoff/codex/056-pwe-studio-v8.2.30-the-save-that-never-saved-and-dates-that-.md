# PWE Studio v8.2.30 — the save that never saved, and dates that meant nothing (deployed 2026-08-04)

The owner reported that editing any existing studio showed "Internal Server
Error". It did, and had since **10 July** — twenty-five days. The cause is not
in anything the last two releases touched.

## Every edit of an existing studio 500'd and wrote nothing

```python
if user_id:                       # this studio already has a Studio Admin
    if email_owner and ...:       # a different user owns that address
        user_id = ...
    elif password:                # a new password was typed
        UPDATE users SET ... password_hash ...
    else:                         # reachable ONLY when password is empty
        if not password:          # ← therefore always true
            raise ValueError(...) # ← therefore always fires
        UPDATE users SET email, full_name ...   # ← unreachable
```

`elif password` had already consumed the truthy case, so the `else` was the
empty-password branch and its first line was a guard against an empty
password. The `UPDATE` beneath it — clearly the intended behaviour, change the
name and address and leave the credential alone — could never run. The raise
was a copy of the create-path guard that landed in the wrong branch
(`17b4497`, 2026-07-10).

**It failed safe, by accident.** The raise happens before the subscription
upsert and before `commit()`, so the whole transaction rolled back. Twenty-five
days of saves that reported an error and changed nothing. Production data
confirms it — all four trialing subscriptions still hold every date:

```text
status      rows  starts_at  trial_ends_at  current_period_ends_at
active        2       2            0                  2
trialing      4       4            4                  4
```

Which also means the date-clearing defect fixed in v8.2.29 never reached the
data: this bug was standing in front of it. **Two defects cancelling out is not
a safety property**, and both are asserted now.

## A business rule arriving as a fault

The route's `try/except ValueError` wrapped only `_tenant_write_payload`, not
the work inside the transaction. So "you need to set a password" reached the
operator as **Internal Server Error** — a sentence they can act on, delivered
as one they cannot. The transaction body is wrapped now and answers 400 with
its own message.

Unhandled 500s carry a short reference (`secrets.token_hex(3)`) logged beside
the traceback. Hiding internals is right; leaving the person at the screen with
nothing to quote is not.

## The other half of that branch

With no password and no existing account, the code did
`INSERT INTO users (password_hash = hash(""))`. `/auth/login` refuses an empty
password before verifying anything, so this was never a way in — it was a row
that **looks** like an account and is not one, which the onboarding checklist
then ticked as "Studio Admin login configured". The checklist was lying. It
now refuses and points at the password-setup link flow that already exists.

## The dates meant nothing

Nothing in this product read a subscription date and compared it to today. No
scheduled job, no expiry check, no code path anywhere. A trial could end, a
billing period could lapse and `ends_at` — the cancellation date — could pass,
with the studio keeping every feature and the console showing green. For a
product sold by subscription that is the centre of the thing, unenforced.

**Three additions, in order of how much they touch:**

1. **`validate_subscription_dates`** in `lifecycle.py`, beside the rules that
   were already there. Every pair in order, not each date against the start —
   the owner's screenshot showed a cancellation dated 2028 against a period
   ending 2029, which a start-only check accepts. Plus: `trialing` must have a
   trial end, `cancelled` must have a cancellation date. Both write paths call
   it. A date the caller did not mention is not checked, because not
   mentioning something is not a claim about it.

2. **`services/subscription_settlement.py`** — what the dates say has already
   happened. It **reports**; it does not cut anybody off. A studio losing
   access because a job ran overnight is a support incident and a broken
   promise. And it obeys the existing state machine rather than inventing
   moves: a lapsed trial is **never** applied automatically, because
   `trial → past_due` is not a legal transition *and* "did they buy?" is a
   commercial question. Two reasons, same answer. Applying is opt-in
   (`{"apply": true}`), goes through the same `validate_tenant_transition` the
   manual route uses, and writes its own audit row. Idempotent by
   construction — findings come from current state.

3. **A "Dates Passed" card** on the overview, loading with everything else.
   A count nobody sees until they open a menu is a count nobody sees.

## What the screenshots showed, fixed

* **`Sta2026-08-03`** — label and value overlapping, and «试用结束» wrapping one
  character per line. The row was a flex with `flex: 1` on the label, so in a
  200px card it squeezed to nothing. It is a container-query grid now.
* **A red "1 天前已过" on the subscription start date.** My error from v8.2.29:
  any past date read as overdue. **Only a deadline can be overdue** — a start
  in the past is what "this has begun" looks like, and colouring it red said
  every healthy studio needed attention.
* **`Start` untranslated**, the one date label that never got an entry.
* Danger Zone was a fold hiding one sentence that pointed elsewhere; it is
  that sentence plus the door.
* A fold holding an unsaved change now carries an amber dot.

## Verified

1046 tests pass; three checkers pass. Against a real database, every rule
end to end:

```text
ordinary edit, no password        200   (was 500 for 25 days)
period end before the start       400   names both dates
cancellation before period end    400   names both dates
trialing with no trial end        409   refused by the transition matrix first
a coherent set                    200
```

## Still to do by hand

* Submit `/sitemap.xml` to Search Console (from v8.2.28).
* Rotate the showcase password that was pasted into chat.
* **Decide whether the settlement should ever run unattended.** It is manual
  by design today. Automating it means agreeing what a lapsed trial is worth,
  which is a commercial decision, not an engineering one.

---

