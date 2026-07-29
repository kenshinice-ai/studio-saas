# Multi-campus Policy

## v8.0.0 decision

One physical/operational campus is one tenant.

This is the best current boundary because it keeps the following independent:

- student/family records and access;
- staff membership and least-privilege roles;
- schedules, attendance and credits;
- brand, contact details and public registration;
- plan, storage and commercial responsibility;
- backup, export, deletion and incident scope.

It also prevents an early “shared campus” feature from weakening tenant isolation or creating unclear billing and privacy ownership.

## How a multi-campus customer operates now

- create one tenant per campus;
- use different authorised staff memberships where appropriate;
- treat cross-campus transfers as an approved export/import workflow;
- issue separate plan/order lines;
- reconcile consolidated business reporting outside the operational tenant data until an organisation layer exists.

## Future organisation layer

A future organisation layer may link multiple tenants for:

- shared identity and controlled cross-campus staff;
- consolidated dashboards;
- centrally managed templates;
- cross-campus transfer workflow;
- group billing.

It must not merge operational tables or permit implicit cross-tenant access. Every aggregation must have an explicit organisation membership, purpose, audit trail and revocation path.
