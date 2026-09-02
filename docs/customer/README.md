# PWE Studio v10.13.0 — Customer Delivery Index

Status: customer-readable draft for commercial and legal review
Deployment stage: production on AWS Lightsail (`ap-southeast-2`) at `https://pwestudio.online`, live since 30 July 2026; PostgreSQL and media on the same instance
Production operations status: daily backups and a rehearsed restore are in place; an off-instance backup copy, uptime monitoring, backup-failure alerting, on-call ownership, a contractual SLA and privileged-account MFA are not

This folder is the editable customer-facing source set for the v10.13.0 commercial conversation. Current release acceptance is recorded in `Release_Notes.md`; exact runtime/package identity remains in `docs/HANDOFF_LATEST.md`. Public HTML under `customer-resources/` is a separate browser deliverable and must be kept aligned with this source set.

## Read first

1. [Release Notes and Acceptance Evidence](Release_Notes.md)
2. [Onboarding Checklist](Onboarding_Checklist.md)
3. [FAQ](FAQ.md)
4. [Pricing and Package Boundaries](Pricing_and_Package_Boundaries.md)
5. [Service Agreement Draft](Service_Agreement_Draft.md)
6. [Security, Privacy and Compliance](Security_Privacy_Compliance.md)
7. [Data Migration Guide](Data_Migration_Guide.md)
8. [Support Policy](Support_Policy.md)
9. [Multi-campus Policy](Multi_Campus_Policy.md)
10. [Integration Boundaries](Integration_Boundaries.md)
11. [Professional Demonstration Runbook](Demo_Runbook.md)

## Current product boundary

PWE Studio currently provides:

- a public studio website and quick-registration flow;
- a secure student/family area using a student access code;
- Studio Admin for website, brand and publishing work;
- CMS for enquiries, students, credits, attendance, recurring schedules, portfolio work and reporting;
- invoicing, recorded payments/refunds, credit settlement, teacher-payable summaries and customer statements;
- optional Xero Beta one-way push after connection, accountant-reviewed mapping, Demo Company trial and explicit enablement;
- role-based staff access and tenant isolation;
- CSV/Excel migration templates and a documented migration assessment process;
- privacy-safe weekly schedule export as an ICS calendar file;
- device-native Mail and Messages handoff, plus an SMTP email path when a deployment supplies and operates its own sending configuration.

The following remain explicitly outside the v10.13.0 product boundary:

- a contractual production SLA, uptime monitoring, backup-failure alerting or on-call ownership (AWS production hosting itself went live on 30 July 2026, with daily database and media backups and a passing restore rehearsal, but the backup copies are still on the same instance);
- online card/payment-provider processing and automatic bank reconciliation;
- SMS provider transport and managed/bundled email delivery;
- customer-owned custom domains;
- multi-campus aggregation within one tenant;
- a guarantee that an arbitrary historic spreadsheet is import-ready;
- MFA/SSO. MFA is a pre-production security gate for privileged accounts.

Xero is not in the deferred list: it is a paid Beta add-on with gated,
strictly one-way provider transport. It does not import or apply edits from
Xero, and failed jobs require operator review before replay.

## Document status

The internal legal/product consistency review was completed on 1 August 2026 and is recorded in [Legal Review](Legal_Review_2026-08-01.md). It is not external legal advice. The service agreement remains a commercial working draft and must be completed and reviewed by an Australian lawyer before signature.
