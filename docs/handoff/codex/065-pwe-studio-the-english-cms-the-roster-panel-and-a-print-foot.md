# PWE Studio — the English CMS, the roster panel, and a print footer (2026-08-03)

## The English CMS was 66 strings short

`backend/scripts/audit_cms_translation.py` is new and is the point of this
round. Untranslated UI has shipped from here four times and the mechanism is
always the same: **nothing fails.** A missing entry renders the source
Chinese, the page works, the tests pass, and only a reader who does not read
Chinese finds out. The manual's screenshot run is what finally surfaced it —
capturing every screen in English put the gaps on one contact sheet.

So the contact sheet is a command. It signs in, walks every tab, and reports
every Chinese text node **and attribute** still showing in English mode.

```text
before   66 distinct strings
after     0   (3 intentional: 中, 中文, "Language / 语言")
```

Most of them were **`aria-label`s and placeholders** — `全局搜索 ⌘K`,
`搜索学员姓名...`, `选择 <student name>` — which never appear in a screenshot
and are exactly what a screen-reader user hears. Fixed with ~45 dictionary
entries plus 9 pattern rules (`^选择\s+(.+)$` → `Select $1` covers every
student card with one rule, and keeps working for names nobody has entered
yet). Exits non-zero when anything is found, so it can gate a release.

The number-adjacent fragments I had documented as unfixable are fixed:
Chinese and English both put the measure word after the count, so
`6/10 人 · 60 分钟` → `6/10 students · 60 min` is a straight substitution. The
earlier note was too cautious.

## The roster panel never lined up

`items-end` on the two-column grid. The columns end at different heights — the
left trails a helper line, the right a 44px checkbox — so bottom-alignment
pushed the right column's label and its controls a row higher than the left's.
`items-start` puts both labels on one baseline and both control rows on
another; the unequal tails hang below, which is what they should do. The left
column's controls also lacked the `min-h-[50px]` the right column had.

Measured after: labels both at y=414, control rows both at y=434.

## Printing: a running footer, not a watermark

Discussed rather than assumed. A full-page watermark sits on top of the body
text and the screenshots — on a document whose whole design brief was measured
contrast, and whose screenshots exist to be looked at closely. It also costs
toner on a page meant to be printed for a front desk, and on a **public**
document a confidentiality mark would be a false claim.

What the worry actually is — a printout being read two years later — is
answered by a running footer: version, print date, and where the current one
lives, repeated on every page via a fixed element with `@page` reserving the
band. The date is stamped by the print button, because CSS cannot produce one
and page-load would go stale on a tab left open overnight.

**A watermark is still the right tool for a DRAFT or customer-specific copy.**
Not built, because this document is neither.

## Also

* Two bugs in my own additions, both caught by the tests I had written: the
  footer nested a `<span>` inside a `data-lang` `<span>`, which is the one
  rule the language filter needs; and the print handler used an undeclared
  `root`, which would have thrown on the first click.
* All 22 screenshots re-captured against the fixed CMS.
* Production has **no manual yet** — `/manual/` and `/zh/manual/` are 404
  there. The broken images seen earlier were a server that predated the
  `/assets/<dir>/<file>` route fix; nginx has no `/assets` block, so the
  subdirectory reaches Flask in production too.

519 tests pass. Not deployed.

---

