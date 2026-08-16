# PWE Studio — read-through of both languages, then deploy (2026-08-03)

Read end to end in English and Chinese. Seven corrections, and one of them was
only findable by reading the Chinese *against the Chinese interface*.

## What was wrong

1. **"Five screens" over a table of four.** The fifth is the platform console,
   which the owner and I decided to keep out of a customer manual — the
   heading predated that decision. Both languages.
2. **The Chinese manual named English buttons.** `Save Draft` and `Publish`
   *are* translated in Studio Admin (保存草稿 / 发布), so a Chinese reader was
   being told to press something that is not on their screen. Six places.
3. **Two Studio Admin strings genuinely stay English** — `Restore to Draft`
   and `Improve colour contrast before publishing:` were missing from
   `admin-i18n.js`. Added, and the manual now names them in Chinese too. Same
   class of bug as the CMS sweep, found the same way.
4. **The register screenshot sat between two sentences about the pending
   queue.** Both visitor-facing surfaces now come first, then the queue they
   feed. (Moving it duplicated the figure on the first attempt — 12 figures
   instead of 11 — because the regex had already captured the indent I was
   also matching on. Caught by counting.)
5. **The ICS warning appeared twice**, near-verbatim, a screen apart. The
   pitfall keeps the explanation; the callout points at it.
6. **A callout repeated §01 word for word** about empty sections.
7. **The English access-code pitfall read as though the parent were entering
   their own child.** Rewritten in both languages, with the order of checks
   made explicit.

## What the read confirmed

* No stray English UI labels left in the Chinese manual. What stays Latin is
  deliberate: `PWE Studio`, `Portal`, `Register`, `CMS`, `Studio Admin`,
  `slug`, `ICS`, `CSV` — product and surface names, which the interface does
  not translate either.
* Every counted claim still matches the code: 30 log actions, 45 status
  colours, 30 megapixels, two-year audit retention, over 200 isolation checks.
* English 3,824 words; Chinese 7,579 characters.

548 tests pass.

---

