# Integration Boundaries

> Reconciled for v10.13.0 on 2026-08-23. This document states current
> provider behavior; older release-note entries remain historical evidence.

## Added in v10.0.0

| Integration | Current product state | What is still the customer's own |
|---|---|---|
| Xero | **Beta, gated one-way push.** OAuth2, encrypted tokens, refresh, account/tax mapping, Demo Company trial, persistent queue/backoff, idempotent replay and per-document reconciliation are implemented. Issued invoices, credit notes and recorded payments can be sent only after every gate passes and pushing is explicitly enabled. Nothing is imported from Xero or applied back to local records. | The customer's Xero subscription, organisation choice, chart of accounts, tax treatment, accountant-approved mapping and operational review of failed jobs. Two-way edit sync is **not** offered. |
| Payment providers | Payment records, allocation to invoices, refunds, idempotent webhook intake, and signature verification. Provider adapters are present with the transport left unimplemented in this release. | The merchant account. Funds settle to the customer, cards are entered on the provider's hosted page, and the platform never touches either — PCI scope stays at the lightest tier. |
| SMS | Channel routing, per-tenant sender configuration, delivery logging, opt-out handling, monthly quota and a spend dashboard that counts UCS-2 segments. The provider transport is not implemented in this release and **fails loudly rather than pretending to send**. | The SMS account and its charges. We are not a reseller and take no margin. |
| Email | Transactional templates, attempt logs and an SMTP adapter exist. The default backend is console-only and sends nothing externally. | A sending account/domain, SMTP credentials, DKIM/SPF/DMARC, bounce handling and ongoing reputation/operations. No managed sending service is included by default. |
| Calendar subscription | Per-family and per-teacher subscription feeds with revocable tokens, covering recurring lessons, reschedules, cancellations and term closures. | Nothing. This one is free to run and replaces the reminder traffic a studio would otherwise pay for — but it cannot carry same-day changes, because calendar clients refresh on their own schedule. |

## Included capabilities

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
| Managed email provider/domain | SMTP adapter exists, but no bundled account or managed sending domain | Sending domain and DKIM/SPF/DMARC owned by the customer, bounce handling |
| SMS provider transport | Routing, quota, opt-out and logging are live; the provider call is not implemented and raises rather than silently discarding a message | Customer's own account, sender identity registration where required, and a delivery contract |
| Webhooks | Interface reserved | Signing, replay protection, retries, event versioning and customer controls |
| Custom domain | Deferred | Domain ownership, DNS/TLS, support and offboarding |

No reserved interface is described to a customer as an included working integration. Xero is the exception to the earlier Preview boundary: it now has gated one-way provider transport and remains labelled Beta while the operating evidence matures. Payment-provider and SMS-provider calls remain unimplemented and fail visibly rather than pretending to succeed.
