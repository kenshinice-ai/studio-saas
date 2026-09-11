# Brand Architecture

## House, product lines and tenants

**PWE · 天域** is the house: the parent brand, and the company website at the
root of `pwestudio.online` (`/`, `/zh/` and the house's section prefixes are
served ahead of the application from v10.18.0). Everything the company makes
is a line of the house.

**PWE Studio** is the house's SaaS product line — the multi-tenant studio
management product, delivered as SaaS or as the single-studio Edition. Its
home is `/studio`. Its Feather Star preserves one immutable meaning: the
four-point star is the starting point of creativity; the three feather blades
represent growth, ascent and possibility. A wing-family mark for the house's
product lines is planned; until it lands, the Feather Star stays this
product's mark and no icon or image is swapped.

**Paradise Production · 天域影像** is the house's film and creative line. Its
wing represents creative lift and provenance. It is a sibling line of PWE
Studio, not its parent, and it no longer appears as the product's producer.

**Tenant studios own their customer-facing identity.** Their logo, studio
name, colours and content are primary throughout their operational workspace
and public experience.

Approved relationship:

> PWE · 天域
>
> ├ PWE Studio — SaaS product line
>
> └ Paradise Production · 天域影像 — film and creative line

Product lockup and credit:

> PWE STUDIO
>
> Powered by PWE · 天域

The two lines remain visually separate. “SaaS” and “Edition” may describe
delivery models in running text, but never appear in the PWE Studio lockup.

## Paradise Production lockup selection (film and creative line)

The Paradise Production artwork in `logo/` belongs to the film and creative
line. It is not the house mark and is never used as the product's producer
credit.

| Asset | Approved use |
|---|---|
| Lockup A · horizontal | Paradise Production website, stationery and email signature |
| Lockup B · badge | Company profile cover, social profile and formal end page |
| Lockup C · star-wing | Joint launch material and restrained cross-line endorsement |
| Wing symbol | Paradise Production favicon, social avatar and decorative use |

## Surface rules

| Surface | Primary identity | House treatment |
|---|---|---|
| Product site (`/studio`, `/pricing`, `/manual/`) | PWE Studio | Header wordmark leads to the house at `/`; footer credit `PWE · 天域出品` linking to `/` |
| Super Admin | PWE Studio | Small text credit `PWE · 天域出品` linking to `/` on the login card |
| Studio Admin | Tenant logo + tenant name | Footer text only: `Powered by PWE` |
| CMS | Tenant logo + tenant name | Footer text only: `Powered by PWE` |
| Portal / Register | Tenant logo + tenant name | Footer text only: `Powered by PWE` |
| SaaS and Edition packages | PWE Studio | Delivery model described in prose |
| Sales deck | PWE Studio | Small house endorsement; no merged logo |
| README / Handoff | PWE Studio | Text credit where useful |

Tenant Studio Admin, Portal, Register and CMS must not show the PWE Studio,
house or Paradise Production logo in the top-left identity area. If a tenant
has no uploaded logo, use the tenant name without substituting a platform
mark.

Canonical tenant footer pattern:

> © 2026 [Tenant Name] · Powered by PWE

The house credit is quiet supporting text, never a heading, button or graphic
lockup. A commercial agreement may hide it through the documented
configuration flag (`STUDIOSAAS_SHOW_PRODUCER_CREDIT=0`), but must never
replace the tenant identity.

## Colour relationship

- Family Navy: `#0E1729`
- Family Amber: `#F5B335`
- Accessible Amber Text: `#A16207`
- Warm Paper: `#F7F5F2`
- White: `#FFFFFF`
- Black: `#000000`

The house and both lines share the family palette. Functional blue, success,
warning, danger and tenant theme tokens remain separate. Family amber is not
a general-purpose warning or button colour.

## Typography

- Paradise Production brand moments: Playfair Display.
- Paradise Production supporting text: Inter.
- PWE Studio authored wordmark: vector geometry, never typeset from a font.
- Product UI: system bilingual sans-serif stack.
- Chinese marketing titles: Source Han Serif / Songti SC.
- Chinese UI: PingFang SC / Source Han Sans / system sans-serif.

Paradise Production SVG lockups may contain editable live text. Use raster
exports where font availability is uncontrolled.
