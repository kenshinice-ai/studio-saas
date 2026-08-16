# Integration Boundaries

> Updated for v10.6.4 candidate. The money layer moved several rows out of "reserved"
> and into the product, and left others deliberately where they were. A
> boundary document that still described the v8.1.0 position would be the
> most dangerous kind of stale: confidently wrong about what a customer is
> buying.

## Added in v10.0.0

| Integration | Current product state | What is still the customer's own |
|---|---|---|
| Xero | **Preview only.** The product exposes account/tax mapping, gate state, idempotency-key and queue/replay structures for inspection. There is no OAuth lifecycle, Xero HTTP client, token refresh, worker/consumer or provider-response handling in this release, so no invoice, receipt or payable data is sent to Xero. | A future provider integration would require the customer's Xero subscription, chart of accounts, tax treatment and a separate implementation/acceptance boundary. Two-way edit sync is **not** offered. |
| Payment providers | Payment records, allocation to invoices, refunds, idempotent webhook intake, and signature verification. Provider adapters are present with the transport left unimplemented in this release. | The merchant account. Funds settle to the customer, cards are entered on the provider's hosted page, and the platform never touches either — PCI scope stays at the lightest tier. |
| SMS | Channel routing, per-tenant sender configuration, delivery logging, opt-out handling, monthly quota and a spend dashboard that counts UCS-2 segments. The provider transport is not implemented in this release and **fails loudly rather than pretending to send**. | The SMS account and its charges. We are not a reseller and take no margin. |
| Calendar subscription | Per-family and per-teacher subscription feeds with revocable tokens, covering recurring lessons, reschedules, cancellations and term closures. | Nothing. This one is free to run and replaces the reminder traffic a studio would otherwise pay for — but it cannot carry same-day changes, because calendar clients refresh on their own schedule. |

## Included since v8.1.0

- CSV student template;
- multi-sheet Excel migration template;
- operational CSV exports already present in the product;
- privacy-safe ICS recurring class calendar export;
- `mailto:` and `sms:` device-native handoff;
- documented extension points for future integrations.

## Reserved, not active

| Integration | Current boundary | Production acceptance needed |
|---|---|---|
| Google Calendar | Use downloaded ICS | OAuth consent, per-user calendar ownership, update/delete semantics |
| Outlook Calendar | Use downloaded ICS | Microsoft identity, consent, update/delete semantics |
| Email provider | Transactional send over the configured SMTP path; no managed sending domain | Sending domain and DKIM/SPF/DMARC owned by the customer, bounce handling |
| SMS provider transport | Routing, quota, opt-out and logging are live; the provider call is not implemented and raises rather than silently discarding a message | Customer's own account, sender identity registration where required, and a delivery contract |
| Webhooks | Interface reserved | Signing, replay protection, retries, event versioning and customer controls |
| Custom domain | Deferred | Domain ownership, DNS/TLS, support and offboarding |

No reserved interface is described to a customer as an included working integration. Xero is currently a preview with no provider transport; payment and SMS provider calls likewise remain unimplemented and raise instead of returning success, because a message a studio believes was delivered and was not is worse than one that visibly failed.
