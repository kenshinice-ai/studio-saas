# PWE Studio FAQ

## Is the current demonstration a production AWS deployment?

No. v8.0.1 is currently operated locally with PostgreSQL and exposed for controlled demonstrations through a Cloudflare Tunnel. AWS production hosting, production media/database backup and a production SLA are pending purchase, configuration and restore testing.

## What is the difference between Studio Admin and CMS?

Studio Admin is the owner’s website and brand workspace: public content, presentation, registration questions and publishing. CMS is the daily operations workspace: enquiries, students, credits, schedules, attendance, artwork and reports. They share identity and provide stable links between workspaces, but their responsibilities and permissions remain separate.

## Can families sign in?

A family can unlock one student’s private area using the student name, the registered mobile number and a six-digit access code issued by the studio. The view contains that student’s balance, next class, attendance and portfolio. A single account aggregating multiple children is not included in v8.0.1.

## Does PWE Studio send SMS or email automatically?

Not in v8.0.1. Communication actions open the device’s Mail or Messages application with a prepared message. The user reviews and sends it. This avoids claiming provider delivery before a messaging service, delivery logs, retry handling and commercial terms are ready.

## Are online payments included?

No. The system records credit purchases, refunds and balances, but online payment processing and automatic accounting reconciliation are deferred. Staff should use the customer’s approved payment process and record the result.

## Can we import our existing CSV or Excel file?

PWE Studio supports migration assessment and provides standard CSV/Excel templates. We cannot guarantee an arbitrary historic file is standardised or import-ready. We first produce a mapping report and exception list, then quote any cleaning/transformation work. No final import occurs without customer approval and a recoverable checkpoint.

## What calendar export is provided?

Authorised staff can download an ICS file containing active recurring class schedules in the studio timezone. It can be opened in Apple Calendar, Google Calendar, Outlook and other compatible calendar tools. It contains class details and location, not student roster names.

## How is student artwork handled?

Media is private by default. Student/family access is bound to one student. Public portfolio sharing requires recorded publication consent and safe display derivatives. The professional demo uses synthetic artwork and fictional records, not customer media.

## Can one tenant contain several campuses?

Not in v8.0.1. One campus is one tenant. This is currently the safer and clearer boundary for data, roles, branding, pricing, backup and support. A future organisation layer may aggregate multiple tenant campuses without merging their operational records.

## Can we use our own domain?

Custom customer domains are deferred. The current controlled public path uses Cloudflare Tunnel. Domain ownership, DNS, TLS, support and removal procedures will be specified when production hosting is ready.

## Which integrations are included?

v8.0.1 includes CSV/Excel templates and exports, ICS calendar export, and device-native Mail/Messages links. Stripe, Xero, Google/Outlook Calendar APIs and webhooks are documented extension points, not active integrations unless a signed order specifically includes them.

## What happens if we cancel?

The contract draft proposes a standard export window and a documented deletion schedule, subject to lawful retention and the signed order. Exact timeframes require legal and commercial approval before signature.

## Does PWE Studio have MFA?

Not yet. Password hashing, role separation and session controls are implemented, but MFA/SSO is an explicit pre-production gate for privileged accounts and is not represented as complete.

## How do we get support?

Use the Support & Feedback area on the PWE Studio product homepage. During the current stage, it opens your device’s Mail or Messages application. Do not include passwords, payment details or sensitive student data in the message.
