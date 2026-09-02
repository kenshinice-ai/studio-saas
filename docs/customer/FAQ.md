# PWE Studio FAQ

## Is this a production AWS deployment?

Yes, since 30 July 2026. `https://pwestudio.online` is served from an AWS Lightsail instance in `ap-southeast-2`. The host terminates TLS with an automatically renewed Let’s Encrypt certificate covering the apex and `www`, HTTP redirects to HTTPS, and the application listens only on the instance’s loopback interface. Daily PostgreSQL logical dumps and a media-volume archive run under cron, and the restore rehearsal passes. The Cloudflare Tunnel used for earlier invitation demonstrations is no longer the production path and will not be reintroduced for this hostname.

Still open on this live service, and disclosed as open: an off-instance copy of the backups, uptime and backup-failure alerting, on-call ownership, a contractual SLA, and multi-factor authentication for privileged accounts. Managed AWS services (RDS, S3, SES) are not in use.

## What is the difference between Studio Admin and CMS?

Studio Admin is the owner’s website and brand workspace: public content, presentation, registration questions and publishing. CMS is the daily operations workspace: enquiries, students, credits, schedules, attendance, artwork and reports. They share identity and provide stable links between workspaces, but their responsibilities and permissions remain separate.

## Can families sign in?

A family can unlock one student’s private area using the student name, the registered mobile number and a six-digit access code issued by the studio. The view contains that student’s balance, next class, attendance and portfolio. A single account aggregating multiple children is not included in the current release.

## Does PWE Studio send SMS or email automatically?

Most operator communication actions open the device’s Mail or Messages application with prepared text, and the user reviews and sends it. The product also has a logged SMTP email path for configured transactional events, but production/customer delivery is available only when the deployment supplies and operates its own sending account and domain. PWE Studio does not currently provide a managed sending domain or SMS provider transport.

## Are online payments included?

No. The system records credit purchases, invoices, payments, refunds and balances, but it does not capture cards or move money. Automatic merchant/bank settlement reconciliation is deferred. The optional Xero add-on pushes recorded documents one way; it is not a payment processor.

## Can we import our existing CSV or Excel file?

PWE Studio supports migration assessment and provides standard CSV/Excel templates. We cannot guarantee an arbitrary historic file is standardised or import-ready. We first produce a mapping report and exception list, then quote any cleaning/transformation work. No final import occurs without customer approval and a recoverable checkpoint.

## What calendar export is provided?

Authorised staff can download an ICS file containing active recurring class schedules in the studio timezone. It can be opened in Apple Calendar, Google Calendar, Outlook and other compatible calendar tools. It contains class details and location, not student roster names.

## How is student artwork handled?

Media is private by default. Student/family access is bound to one student. Public portfolio sharing requires recorded publication consent and safe display derivatives. The professional demo uses synthetic artwork and fictional records, not customer media.

## Can one tenant contain several campuses?

One campus is one tenant and one subscription in the current release. This is the safer boundary for data, roles, branding, pricing, backup and support. A future organisation layer may aggregate multiple campus tenants without merging their operational records.

## Can we use our own domain?

Per-studio custom domains are deferred. Every studio is reached today as a path under `https://pwestudio.online`, which the platform operates end to end (Route 53 DNS, a Let’s Encrypt certificate on the host, automatic renewal). Adding a customer-owned domain means a second certificate lifecycle and a second failure mode per studio, so domain ownership, DNS delegation, TLS issuance and renewal, support boundary and removal procedure must be specified in a signed order before it is offered.

## Which integrations are included?

The current release includes CSV/Excel templates and exports, ICS calendar export, and device-native Mail/Messages links. Xero is a gated one-way push (an add-on): issued invoices, credit notes and recorded payments are queued into your own Xero organisation after the studio connects it, confirms the account mapping, completes a trial run against the Xero Demo Company, and switches pushing on — until that switch is on, no data is sent to Xero, and nothing is ever read back or edited from Xero. Stripe, Google/Outlook Calendar APIs and webhooks are documented extension points, not active integrations unless a signed order specifically includes implementation and acceptance.

## What happens if we cancel?

The contract draft proposes a standard export window and a documented deletion schedule, subject to lawful retention and the signed order. Exact timeframes require legal and commercial approval before signature.

## Does PWE Studio have MFA?

Not yet. Password hashing, role separation and session controls are implemented, but MFA/SSO is an explicit pre-production gate for privileged accounts and is not represented as complete.

## How do we get support?

Read the public [Support Policy](/customer-resources/Support_Policy.html), then use the Support & Feedback area on the PWE Studio product homepage. It opens your device’s Mail or Messages application; you review and send. Do not include passwords, payment details or sensitive student data in the first message.

## What is in an ICS calendar export?

The weekly schedule contains recurring class details and location but no student or guardian identities. The separate daily roster is an operational attendance file and may contain student names; only staff with data-export permission can download it, a privacy warning is shown first, and guardian names are never included.
