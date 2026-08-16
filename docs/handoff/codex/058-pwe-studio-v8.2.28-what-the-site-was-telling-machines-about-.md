# PWE Studio v8.2.28 — what the site was telling machines about itself (deployed 2026-08-04)

The marketing skills from `coreyhaines31/marketingskills` were installed and
their `seo-audit`, `ai-seo` and `copywriting` frameworks run against
production. The audit found three real defects, all of which had been live for
weeks and none of which was visible from a browser.

## The three defects, and why nobody saw them

**Every `.webp` was served as `application/octet-stream`** — including the one
named by `og:image`. Browsers sniff the bytes and render the image anyway,
which is exactly why the pages looked correct; social crawlers do not sniff,
so a link shared to LinkedIn, X, WhatsApp or WeChat showed a card with no
picture, and Google Images could not index a single manual screenshot.

The cause: `send_from_directory` takes its Content-Type from `mimetypes`,
whose table is the interpreter's built-ins plus `/etc/mime.types` — a file
`python:3.11-slim` does not ship. The types are registered by the application
now, so the answer is a property of this codebase rather than of whichever
base image it runs on. Asserted per extension.

**Every static asset was sent `no-cache`.** The manual re-downloaded 502 KB of
screenshots on every single view, paid directly on the largest contentful
paint. Every asset URL already carried `?v=<APP_VERSION>`, so the URLs were
already safe to cache forever — the header just never said so. A URL naming
the running release now gets a year and `immutable`; a stale one revalidates.

**There was no `robots.txt` and no `sitemap.xml`.** Both 404ed. Nine addresses
were discoverable only by following links, the hreflang set existed in the
markup alone with nothing corroborating it, and the Search Console submission
that has been on the to-do list had nothing to submit.

## What else the audit turned up

* **The manual had no structured data at all** — the most citable thing the
  site publishes (3,800 words, first-hand, specific) and nothing marked its
  seven questions as questions or gave it a date.
* **Four customer documents served both languages from one URL** behind a DOM
  toggle, with no canonical and no hreflang — the arrangement the home page
  and the manual were moved off two releases ago. The Chinese half of the
  terms, the privacy policy and the service FAQ had no address that could be
  indexed, linked or pointed at.
* **`"User Manual | PWE Studio"`** was a 24-character title in front of those
  3,800 words, targeting nothing.
* **The FAQ, terms and privacy pages asserted product facts against `v8.2.2`**
  — six releases stale, on a live page, with nothing checking it.
* **A nested duplicate `<picture>`** in the nav brand mark, from an earlier
  edit.

## The rule that keeps the FAQ markup honest

`FAQPage` has exactly one failure mode: markup that does not match the visible
answer. A hand-maintained copy in Python agrees with the page only until the
next edit to the page, so there is no copy — `faq_pairs()` parses the
questions back out of the document that is about to be sent. That reorders
`_serve_product_home`: cards, then filter, then structured data, because the
structured data now reads the filtered document. The placeholder survives
filtering because it is a comment.

The same extractor serves the manual (`<h4>` + `<p>`, scoped to `#faq`), the
home page and the service FAQ (`<summary>` + `<p>`), which is why all three
got markup for the price of one.

## Machine-readable files

`/pricing.md` and `/llms.txt`, generated from the same plan rows as the
pricing cards. An agent shortlisting tools for a studio owner reads what it
can parse and silently skips what it cannot — the buyer never learns there was
a third option. This product's numbers are public, enforced and already
generated; the only thing missing was an address a parser could reach them at.
`SETUP_FEE_AUD` now holds the 299–999 range so the page prose and the markdown
file are asserted against one number instead of three.

## Copy

The page reads well — specific, customer's own words, no buzzwords — so the
changes are few and structural:

* **The scope exclusions moved off the conversion path.** Six clauses of
  what-is-not-included sat between the price and the button, the last thing a
  buyer read before deciding. They are an FAQ answer now, verbatim: the
  content was right, the position was wrong. The test that guards them was
  rewritten to tell a move from a deletion.
* **A new FAQ section** before the final call to action, splitting 61.8/38.2
  like the hero — answers in one column, the standing invitation in the other.
  There is no trial and no money-back guarantee to offer, so the risk reversal
  is the only honest one available: everything a buyer would want is already
  public, including what has not been built. Inventing a guarantee would have
  been easier and worse.
* **`Discuss Starter` → `Start with Starter`.** The old verb asked the reader
  to do the thing they were trying to avoid.
* Descriptions brought inside the space a result actually gives them — the
  English ones were losing their last clause at 195 characters, the Chinese
  ones were using half of theirs at 64.

## The deploy failed first, and what that was worth

The first attempt built, uploaded, switched and rolled itself back. One line
in `_jsonld_script` put a **backslash inside an f-string expression** — legal
from Python 3.12 (PEP 701), a `SyntaxError` before it. Development runs 3.14;
the production image is `python:3.11-slim`. The container could not import
`server` at all, deep health failed, and the deploy reverted to v8.2.23 with
the site healthy throughout. The rollback did exactly its job on a defect that
652 passing tests, three checkers and a successful bundle build could not see,
because every one of them ran on the wrong interpreter.

Two checks now run against the floor the Dockerfile pins
(`test_python_version_floor.py`):

* `ast.parse(feature_version=...)` over all 144 modules — rejects grammar
  newer than the target: match statements, `except*`, PEP 695 generics.
* a walk of every expression interpolated into an f-string, looking for a
  backslash.

**The second exists because the first does not catch this.** `feature_version`
constrains the parser, not the tokenizer, and a 3.12+ tokenizer reads PEP 701
f-strings before the parser is consulted. The first version of the test
claimed a guarantee it did not provide; that was caught by trying it against
the offending line rather than assuming. A self-test now pins the detector to
the exact expression that caused the rollback, and it was run against the
committed `e3a9262` source to confirm it fires there and is clean after the
fix.

Neither replaces building on the target image. They are what can be asserted
without one, and the honest ceiling of this check is worth remembering the
next time something passes locally and dies on the instance.

## Verified

940 tests pass; all three static checkers pass. `check_manual_print.py` still
reports 18 and 15 pages, so the print work from v8.2.23 is intact. The FAQ
section measures 61.8/38.2 exactly, `align-items: start`, summary rows 71px
against a 44px minimum, and contrast in both themes: 16.45:1 summary, 6.96:1
answer, 4.52:1 links and marker in light — the amber that was drawn for it.

Confirmed on production after the deploy (`8.2.28-7962ff39bb54`):

```text
/robots.txt /sitemap.xml /pricing.md /llms.txt        200
all 14 sitemap URLs                                   200
og:image                                              image/webp
/assets/manual/*.webp?v=8.2.28   public, max-age=31536000, immutable
/            SoftwareApplication, Organization, FAQPage(6)
/manual/     TechArticle, Organization, BreadcrumbList, FAQPage(7)
FAQ.html     Organization, BreadcrumbList, FAQPage(13)
manual print 18 / 15 pages, unchanged
```

## Still to do by hand

* Submit `/sitemap.xml` to Search Console. There is finally something to
  submit; the nine addresses no longer need to be inspected one at a time.
* Rotate the showcase password that was pasted into chat.
* The sister site still advertises 1500 students / 100 GB against the
  database's 1000 / 50. It is built from `02 WEBSITE/src/build.py`, which is
  not reachable from this repository.

---

