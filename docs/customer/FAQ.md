# PWE Studio FAQ

## Is this a production AWS deployment?

Yes, since 30 July 2026. `https://pwestudio.online` is served from an AWS Lightsail instance in `ap-southeast-2`. The host terminates TLS with an automatically renewed Let’s Encrypt certificate covering the apex and `www`, HTTP redirects to HTTPS, and the application listens only on the instance’s loopback interface. Daily PostgreSQL logical dumps and a media-volume archive run under cron, and the restore rehearsal passes. The Cloudflare Tunnel used for earlier invitation demonstrations is no longer the production path and will not be reintroduced for this hostname.

Still open on this live service, and disclosed as open: an off-instance copy of the backups, uptime and backup-failure alerting, on-call ownership, a contractual SLA, and multi-factor authentication for privileged accounts. Managed AWS services (RDS, S3, SES) are not in use.

## What is the difference between Studio Admin and CMS?

Studio Admin is the owner’s website and brand workspace: public content, presentation, registration questions and publishing. CMS is the daily operations workspace: enquiries, students, credits, schedules, attendance, artwork and reports. They share identity and provide stable links between workspaces, but their responsibilities and permissions remain separate.

## Can families sign in?

A family can unlock one student’s private area using the student name, the registered mobile number and a six-digit access code issued by the studio. The view contains that student’s balance, next class, attendance and portfolio. A single account aggregating multiple children is not included in v8.1.0.

## Does PWE Studio send SMS or email automatically?

Not in v8.1.0. Communication actions open the device’s Mail or Messages application with a prepared message. The user reviews and sends it. This avoids claiming provider delivery before a messaging service, delivery logs, retry handling and commercial terms are ready.

## Are online payments included?

No. The system records credit purchases, refunds and balances, but online payment processing and automatic accounting reconciliation are deferred. Staff should use the customer’s approved payment process and record the result.

## Can we import our existing CSV or Excel file?

PWE Studio supports migration assessment and provides standard CSV/Excel templates. We cannot guarantee an arbitrary historic file is standardised or import-ready. We first produce a mapping report and exception list, then quote any cleaning/transformation work. No final import occurs without customer approval and a recoverable checkpoint.

## What calendar export is provided?

Authorised staff can download an ICS file containing active recurring class schedules in the studio timezone. It can be opened in Apple Calendar, Google Calendar, Outlook and other compatible calendar tools. It contains class details and location, not student roster names.

## How is student artwork handled?

Media is private by default. Student/family access is bound to one student. Public portfolio sharing requires recorded publication consent and safe display derivatives. The professional demo uses synthetic artwork and fictional records, not customer media.

## Can one tenant contain several campuses?

Not in v8.1.0. One campus is one tenant. This is currently the safer and clearer boundary for data, roles, branding, pricing, backup and support. A future organisation layer may aggregate multiple tenant campuses without merging their operational records.

## Can we use our own domain?

Per-studio custom domains are deferred. Every studio is reached today as a path under `https://pwestudio.online`, which the platform operates end to end (Route 53 DNS, a Let’s Encrypt certificate on the host, automatic renewal). Adding a customer-owned domain means a second certificate lifecycle and a second failure mode per studio, so domain ownership, DNS delegation, TLS issuance and renewal, support boundary and removal procedure must be specified in a signed order before it is offered.

## Which integrations are included?

v8.1.0 includes CSV/Excel templates and exports, ICS calendar export, and device-native Mail/Messages links. Stripe, Xero, Google/Outlook Calendar APIs and webhooks are documented extension points, not active integrations unless a signed order specifically includes them.

## What happens if we cancel?

The contract draft proposes a standard export window and a documented deletion schedule, subject to lawful retention and the signed order. Exact timeframes require legal and commercial approval before signature.

## Does PWE Studio have MFA?

Not yet. Password hashing, role separation and session controls are implemented, but MFA/SSO is an explicit pre-production gate for privileged accounts and is not represented as complete.

## How do we get support?

Read the public [Support Policy](/customer-resources/Support_Policy.html), then use the Support & Feedback area on the PWE Studio product homepage. It opens your device’s Mail or Messages application; you review and send. Do not include passwords, payment details or sensitive student data in the first message.

## What is in an ICS calendar export?

The weekly schedule contains recurring class details and location but no student or guardian identities. The separate daily roster is an operational attendance file and may contain student names; only staff with data-export permission can download it, a privacy warning is shown first, and guardian names are never included.
