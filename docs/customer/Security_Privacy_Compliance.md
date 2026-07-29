# Security, Privacy and Compliance Delivery Pack

Status: v8.0.1 pre-production disclosure
Scope: PWE Studio SaaS mode and the professional showcase

## Honest deployment status

PWE Studio is currently served locally with PostgreSQL and exposed for controlled demonstration through a Cloudflare Tunnel. This is not represented as an AWS production deployment and has no production SLA.

Production AWS hosting, database backup, media backup, monitoring, recovery objectives and operational ownership will be completed and tested after the required AWS account/services are purchased. A release is not production-ready merely because local tests pass.

## Current controls

| Area | v8.0.1 control |
|---|---|
| Tenant separation | Tenant context is explicit in authenticated routes and tenant data is scoped by tenant ID |
| Roles | Platform administrator, owner, manager, teacher, front desk and staff permissions are separated |
| Password storage | PBKDF2-HMAC-SHA256 with per-password salt and 600,000 iterations |
| Sessions | HttpOnly cookies, SameSite controls and secure-cookie behaviour for HTTPS |
| Public student area | Name, registered mobile and a six-digit student access code create a bounded HttpOnly session |
| Brute-force resistance | Student access attempts are rate-limited and temporarily locked |
| Media | Original assets are private; public/student views use validated derivatives and tenant ownership checks |
| Publication | Portfolio sharing requires recorded consent state and supports revocation |
| Audit | Material administrative and operational actions create audit records |
| Export | ICS schedule export excludes roster members and other student data |
| Demo data | The professional showcase is isolated, uses fictional contacts and synthetic artwork, and is reset only by a guarded script |
| Secrets | Reset credentials rotate and are written to a local owner-only `0600` file |
| Customer deletion | Tenant archive/delete workflow requires explicit lifecycle state and confirmation |

## Known gaps and pre-production gates

The following are open gates, not hidden assurances:

- privileged-account MFA is not yet implemented;
- the current local + tunnel stage has no production availability commitment;
- AWS database/media backup and tested restore are pending purchase and deployment;
- Cloudflare connector ownership and count must be verified before every public presentation;
- automated email/SMS delivery, provider logs and bounce/retry handling are not included;
- a final privacy policy, service agreement and data-processing schedule require legal review;
- an incident contact roster and production monitoring/on-call path must be assigned.

The Australian Cyber Security Centre recommends MFA, software updates and backups as core small-business measures. PWE Studio treats MFA plus tested backup/restore as production acceptance gates, not optional polish. See the [Small Business Cyber Security Guide](https://www.cyber.gov.au/business-government/small-business-cyber-security/small-business-hub/small-business-cyber-security-guide).

## Privacy principles

PWE Studio’s implementation and customer process are designed around:

- data minimisation and purpose limitation;
- clear collection notices;
- accurate and correctable records;
- least-privilege access;
- private-by-default student media;
- specific publication consent;
- export, deletion and incident response procedures.

The OAIC describes 13 Australian Privacy Principles covering collection, use/disclosure, governance, data quality, security, access and correction. Applicability depends on the entity and activity; legal advice is required for the final customer arrangement. See the [Australian Privacy Principles](https://www.oaic.gov.au/privacy/australian-privacy-principles).

APP 11 requires covered entities to take reasonable steps to protect personal information and, when no longer required and not legally retained, destroy or de-identify it. See [Read the Australian Privacy Principles](https://www.oaic.gov.au/privacy/australian-privacy-principles/read-the-australian-privacy-principles).

## Children and media

- Collect only the child/family information needed for studio operations.
- The customer is responsible for appropriate parent/guardian authority.
- Portfolio media remains private unless a specific publication decision is recorded.
- A family access code reveals only the bound student’s records.
- Calendar exports never include student or guardian names.
- Demonstrations must never use customer media without specific recorded authority.

## Incident response

On a suspected incident:

1. contain access and preserve logs/evidence;
2. identify systems, tenants, people and data types affected;
3. rotate exposed credentials and revoke sessions;
4. assess likely harm and remedial actions;
5. notify the customer contact without unreasonable delay;
6. determine legal notification obligations and who leads communications;
7. restore only from verified evidence and reconcile affected records;
8. document cause, decisions, corrective actions and follow-up tests.

The OAIC states that covered entities must notify affected individuals and the OAIC when an eligible breach is likely to cause serious harm. The circumstances and entity coverage must be assessed, not assumed. See the [Notifiable Data Breaches scheme](https://www.oaic.gov.au/privacy/notifiable-data-breaches/about-the-notifiable-data-breaches-scheme).

## AWS production acceptance record

Before a production claim, record and demonstrate:

- AWS account owner, billing owner and emergency contact;
- region and data-location decision;
- network architecture, TLS and domain/DNS control;
- secrets management and privileged MFA;
- PostgreSQL backup frequency, encryption, retention and restore test;
- media backup/versioning, retention and restore test;
- documented RPO/RTO;
- monitoring for health, errors, storage, backup failure and expiry;
- maintenance and incident communication paths;
- deployment artifact hash, database migration level and data counts;
- rollback/recovery rehearsal;
- customer acceptance signature.

Suggested minimum evidence table:

| Evidence | Owner | Date | Result | Link/hash |
|---|---|---|---|---|
| Database restore rehearsal | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| Media restore rehearsal | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| Privileged MFA | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| Public health/version parity | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| Incident exercise | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
