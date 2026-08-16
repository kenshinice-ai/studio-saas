# PWE Studio — the manual printed, and what that showed (2026-08-03)

The owner printed both languages. Two defects that neither the CSS nor the
screen could reveal, and a tool so the next change is measured instead of
guessed.

## What the paper showed

1. **Body text printed on top of the running footer.** Page 8 English, page 4
   Chinese — the last two lines of a full page overprinted the footer rule and
   its text, unreadable.
2. **Half the document was white space.** 28 pages English / 25 Chinese for
   3,800 words, including a page carrying two lines and nothing else.

## The tool

`backend/scripts/check_manual_print.py` renders both languages through
headless Chrome's `Page.printToPDF` with `preferCSSPageSize`, and reports page
counts. Its first run reproduced 28/25 exactly, which is what made the rest of
this a measurement rather than a series of guesses.

## The running footer does not work in Chrome, and is gone

Two attempts, both against real PDFs:

* `position: fixed; bottom: 0` — Chrome anchors it to the **text column**, not
  the paper, so it sits on the last line of every full page.
* `bottom: -20mm` with a reserved `@page` band — it landed at the **top of the
  next page**, over the first lines.

A true running footer in Chrome needs the whole document wrapped in a table
with a `<tfoot>`. That is a large change to buy a line of small print, and the
browser's own print dialogue already stamps **the URL, the date and a page
number on every page** — two of the three things the footer was for. What it
cannot know is the version, so that is now a **colophon at the top of page 1**,
with the rights notice, on the page a reader keeps.

Recorded in the stylesheet and asserted, so the next person does not spend the
same two attempts finding out.

## Pages

`break-before: page` per section is gone — twelve forced breaks plus figures
that cannot split is most of a ream. Figures are capped at 118mm in print
(58mm for phone captures); on screen they still fill the reading column.

```text
            before   after
English       28      18
Chinese       25      15
```

549 tests pass.

---

