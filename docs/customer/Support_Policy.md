# Support Policy

Status: pre-production draft

## Contact path

The PWE Studio product homepage contains Support & Feedback actions. In v8.0.1 they open the user’s Mail or Messages application. The user reviews and sends; the system does not claim automated delivery or ticket-provider tracking.

Never send passwords, access codes, payment details or sensitive student information in the first message. Use tenant slug, affected role, time, page and a non-sensitive description.

## Priority

| Priority | Example | Initial response target* |
|---|---|---:|
| P0 Critical | Confirmed privacy/security incident; all authorised users blocked; risk of material data loss | 2 business hours |
| P1 High | Core registration, attendance or family access unavailable with no safe workaround | 1 business day |
| P2 Normal | Degraded workflow, migration question or incorrect presentation with workaround | 2 business days |
| P3 Request | Enhancement, training or future integration | 5 business days |

\* Draft targets apply during stated support hours and are not resolution guarantees. A production order form must confirm support hours, timezone, holidays, included effort and after-hours terms.

## Support stages

1. acknowledge and confirm priority;
2. request minimum reproducible evidence;
3. contain security/data risks;
4. diagnose current version, mode, tenant and runtime;
5. communicate workaround or next update;
6. verify the repair in the affected surface;
7. close with evidence and any follow-up action.

## Customer responsibilities

- maintain an authorised support contact;
- report promptly and accurately;
- preserve source files and screenshots;
- avoid repeated changes while a data incident is being investigated;
- approve destructive recovery or migration actions in writing;
- verify a resolved workflow from the customer’s perspective.

## Production monitoring boundary

The current local + Cloudflare Tunnel mode has no contractual 24/7 monitoring. Production alerting, on-call ownership, backup-failure alerts and maintenance notices are AWS acceptance requirements.
