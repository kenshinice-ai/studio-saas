# PWE Studio v8.2.21 — the manual is live (deployed 2026-08-03)

`PWE-StudioSaaS-aws-8.2.21-3c11e55b556e`. Logical dump taken first
(`studiosaas_studiosaas_20260804T012835Z.dump`). Deep health passed from the
instance and the public edge.

## Measured live

```text
                      /manual/                     /zh/manual/
<html lang>           en                           zh-Hans
canonical             …online/manual/              …online/zh/manual/
hreflang              3 (reciprocal)               3 (identical set)
<h1> / sections       1 / 12                       1 / 12
figures / images      11 / 11                      11 / 11
data-lang left        none                         none
version stamped       yes                          yes
rights notice         yes                          yes
print footer          yes                          yes
```

`/manual` and `/zh/manual` 301 to the trailing-slash form. **Every referenced
screenshot fetched and returned 200** — the earlier blank frames were a server
process older than the `/assets/<dir>/<file>` route, not the images.

Unchanged and still 200: `/`, `/zh/`, `/v1/public/plans`, `/platform-admin`,
`/customer-resources/FAQ.html`, the showcase portal and its CMS. Both home
pages link the manual in their own language.

## Still to do by hand

* **Submit `/manual/` and `/zh/manual/` to Search Console.** Two more new
  addresses with no history, same as `/zh/` last release.
* Send the welcome pack to the next studio onboarded (`Welcome_Pack.md`,
  checklist Phase 2) — and the temporary password separately.

## Not done

Phase D's remaining item: **printing has not been exercised on paper.** The
stylesheet is asserted (contents removed, `@page` band, page breaks, link
targets written out, `[hidden]` forced visible) and the rules parse in the
browser, but nobody has produced an actual PDF and read it. That is the one
claim in this work I have not verified end to end.

548 tests pass. main and tag `v8.2.21` pushed.

---

