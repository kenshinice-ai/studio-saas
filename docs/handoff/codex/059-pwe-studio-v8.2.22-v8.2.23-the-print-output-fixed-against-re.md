# PWE Studio v8.2.22–v8.2.23 — the print output, fixed against real PDFs (deployed 2026-08-04)

The owner printed both languages. Two defects the stylesheet and the screen
both hid, plus a third found while verifying the fix.

```text
                        before        after
English                 28 pages      18
Chinese                 25 pages      15
text over the footer    every full    none
                        page
```

## What was wrong, and what it cost to learn

**The running footer does not work in Chrome.** Two attempts, both measured:
`position: fixed; bottom: 0` anchors to the *text column*, so it printed on
the last lines of every full page; `bottom: -20mm` with a reserved `@page`
band landed at the *top of the next page*. A true running footer needs the
document wrapped in a table with `<tfoot>`. Abandoned, with the reasoning in
`manual.css` and a test that fails if `position: fixed` returns to the print
block — so nobody spends those two attempts again.

The browser's own print dialogue already stamps **URL, date and page number**
on every page. Only the version is beyond it, so version and licence are a
**colophon at the top of page 1**.

**`break-before: page` per section** was most of the white space — twelve
forced breaks plus figures that cannot split. Removed; figures capped at
118mm in print (58mm for phone captures).

**The date was stamped only by the Print button** (v8.2.23). Most people press
Ctrl+P, which never reaches it, so those copies printed a dash. Moved to
`beforeprint`, which covers every path.

## The tool

`backend/scripts/check_manual_print.py` renders both languages through
headless Chrome `Page.printToPDF` and reports page counts. Its first run
reproduced the owner's 28/25 exactly, which is what turned this from guessing
into measurement. Run it after touching the print block.

## Verified on production

Rendered `https://pwestudio.online/manual/` and `/zh/manual/` to PDF after
deploying: 18 and 15 pages, colophon present with v8.2.23, no overprinting.

## Still to do by hand

* Submit `/manual/` and `/zh/manual/` to Search Console.
* Rotate the showcase password that was pasted into chat.

549 tests pass.

---

