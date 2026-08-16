# PWE Studio — marketing page work, scoped not started (2026-08-02)

v8.2.18 shipped the operational items (disk headroom in deep health, build
context tightened). The page work below is **measured and planned, not begun**.

## The two pages, measured

```text
                    /  (product-home.html)        /paradise-production/pwe-studio
language            <html lang="en"> AND 69       <html lang="zh">, monolingual
                    data-lang="zh" nodes
<h1>                rendered twice, once per      once
                    language, in one DOM
hreflang            none                          /en/ sibling
structured data     none                          JSON-LD SoftwareApplication
                                                  + AggregateOffer
pricing data        hardcoded $99 in the HTML     hardcoded A$49/99/199
lives in            this repo                     /var/www/paradise-production,
                                                  nginx static, generated elsewhere
```

The SEO problem is real and measurable: one URL serves both languages with no
hreflang and a self-referential canonical, so each language dilutes the other.

## Three facts that block a naive implementation

1. **`/v1/plans` is auth-gated** (`@permission_required("plans:read")`, returns
   401 publicly). "Pricing from the database" needs a *new public* endpoint
   exposing only public fields — code, name, price, the three limits — and not
   the entitlements JSON that plan rows also carry.
2. **The Paradise site is not in this repo.** It is static files under
   `/var/www/paradise-production` served by an nginx `^~` block, generated for
   the Cloudflare Pages convention. Its plan numbers cannot be corrected from
   here; its source lives somewhere else.
3. **A `/` + `/en/` split changes URLs.** It needs routes, paired canonical and
   hreflang, and the language toggle stops being a DOM switch and becomes
   navigation — which also removes the duplicate-DOM weight from every page
   load.

## Proposed sequence — three releases, smallest risk first

* **A — public plans endpoint, pricing reads it.** No visual change. Makes the
  home page and any future page agree with the database instead of with a
  hardcoded number that has already drifted once.
* **B — port the Paradise design language.** Deep navy sections, amber accent
  and spark motif, the recommended pill, φ spacing, and the JSON-LD the
  Paradise page carries and the home page does not. This is the large one and
  it is a design review, not a mechanical port.
* **C — `/` + `/en/` with hreflang.** The SEO fix. Best done after B so the
  split happens once, on the final markup.

## Open questions

* The canonical producer credit is `Powered by Paradise Production · 天域文创`
  (Brand_Identity.md §10). The proposed link text
  `A PARADISE PRODUCTION · 天域文创出品` is different wording — link the
  existing line, or change the brand spec?
* Where does the Paradise site's source live? Its plan numbers need correcting
  and this repo cannot reach them.

---

