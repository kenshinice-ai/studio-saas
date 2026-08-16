# PWE Studio v8.2.31 — sixty-five lines of my own JavaScript, above the doctype (deployed 2026-08-04)

The owner opened the console and found a wall of source code across the top of
the page. It was mine, it went out in v8.2.30, and it was visible on
production for about twenty minutes.

## What happened

The v8.2.30 edit that replaced `validateSubscriptionDates` was scripted:

```python
old = t[t.index("/* The four dates have to describe a period…"):
        t.index("/* A subscription date field.")]
t = t.replace(old, new, 1)
```

`dateField`'s comment sits **earlier** in the file than
`validateSubscriptionDates`, so `end < start`, so the slice was `""` — and
`str.replace("", new, 1)` inserts at position 0. Sixty-five lines of
JavaScript landed above `<!DOCTYPE html>`, where the browser rendered them as
text, and the function they were meant to replace stayed exactly where it was
and kept running.

So the release had two faults at once: source code printed across the console,
and the pairwise date validation it was supposed to ship **never ran**. The
start-only check was still the live one.

## Why nothing caught it

The test written for that change:

```python
assert "SUBSCRIPTION_DATE_FIELDS.slice(index + 1)" in source
```

`source` was the file. The string was in the file. It was above the doctype,
outside the script, doing nothing — and the assertion passed. **A test that
cannot tell running code from a decorative string is not testing the thing it
names.**

Three checkers passed too. The inline-script checker parses what is inside
`<script>`; it has no opinion about what is outside one.

## The fix, and the guard

The block is removed and the corrected function installed where the old one
actually lived — one definition, inside the script. Then:

* `script_source()` in the tests extracts only `<script>` contents, and every
  assertion about JavaScript behaviour reads from it rather than from the file.
* `test_nothing_precedes_the_doctype`.
* `test_each_function_is_defined_once_and_inside_the_script`, parametrised
  over the seven functions this work touched — two definitions means one is
  dead, and the dead one is the one you were reading when you decided the
  behaviour was correct.

Both new tests were run against a reconstruction of the exact accident and
both fail on it.

## Verified on the running page

```text
document starts with <!DOCTYPE html>        yes
source visible to a reader (innerText)      no
stray text nodes under <body>               none
validateSubscriptionDates definitions       1, inside <script>
cancellation 2028 vs period ending 2029     refused: 「取消或到期 早于 当前周期结束」
the offending field                         aria-invalid="true"
```

That last row is the case from the owner's screenshot, and it is the check
that v8.2.30 was supposed to deliver and did not.

## The lesson worth keeping

Two scripted edits in this session have now gone wrong in the same family of
way — a `str.replace` whose anchor did not mean what I assumed. `replace("")`
is the sharp one: it silently prepends instead of failing. Anchored slice
edits need `assert end > start` before they are used, and any test written for
an edit to a page must assert against the code that runs.

---

