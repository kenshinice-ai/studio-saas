# Integration Boundaries

## Included in v8.0.1

- CSV student template;
- multi-sheet Excel migration template;
- operational CSV exports already present in the product;
- privacy-safe ICS recurring class calendar export;
- `mailto:` and `sms:` device-native handoff;
- documented extension points for future integrations.

## Reserved, not active

| Integration | Current boundary | Production acceptance needed |
|---|---|---|
| Stripe | Online payments deferred | Payment model, webhook verification, refunds, reconciliation, PCI scope and contract |
| Xero | No automatic accounting sync | Account mapping, tax treatment, idempotency, error queue and audit |
| Google Calendar | Use downloaded ICS | OAuth consent, per-user calendar ownership, update/delete semantics |
| Outlook Calendar | Use downloaded ICS | Microsoft identity, consent, update/delete semantics |
| Email provider | Device Mail app only | Sending domain, consent, templates, bounce/retry logs, suppression |
| SMS provider | Device Messages app only | Sender identity, consent, opt-out, delivery logs, cost and retry policy |
| Webhooks | Interface reserved | Signing, replay protection, retries, event versioning and customer controls |
| Custom domain | Deferred | Domain ownership, DNS/TLS, support and offboarding |

No reserved interface is described to a customer as an included working integration.
