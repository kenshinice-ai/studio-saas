# Professional Demonstration Runbook

Tenant: `lets-paint-showcase`
Story brand: Let’s Paint Studio
Safety: fictional records and synthetic artwork only

## Reset

Double-click `RESET_DEMO_TENANT.command`, or run:

```bash
STUDIOSAAS_MODE=saas .venv/bin/python \
  backend/scripts/reset_professional_demo.py \
  --confirm RESET-LETS-PAINT-SHOWCASE
```

The script:

- refuses standalone/customer-edition mode;
- touches only the permanently marked showcase tenant;
- refuses an existing tenant without `settings.professional_demo=true`;
- rotates owner, manager, teacher and front-desk passwords;
- writes presenter credentials to `~/.studiosaas/showcase-credentials.txt` with mode `0600`;
- seeds realistic courses, packages, schedules, enquiries, attendance and balances;
- seeds three original synthetic artworks;
- rotates the family/student access code.

Never screen-share the credential file.

## Pre-demo checks

1. Confirm `VERSION`, `/v1/health`, mode and database.
2. Confirm exactly the expected Cloudflare route and current public/local version parity.
3. Confirm no `.test` data, engineering notes or other tenant media appear.
4. Open the following on phone and desktop:
   - `/`
   - `/lets-paint-showcase`
   - `/lets-paint-showcase/register`
   - `/lets-paint-showcase/studio-admin`
   - `/lets-paint-showcase/cms`
5. Download and open the ICS file.
6. Verify Mail/Messages actions open a device app without silently submitting.

## 12-minute story

1. **Product home (1 min)** — explain clear role entrances and current deployment stage.
2. **Family discovers the studio (1.5 min)** — public story, courses and registration CTA.
3. **Enquiry becomes a student (2 min)** — open CMS pending pipeline, show follow-up states.
4. **Owner prepares the brand (1.5 min)** — switch to Studio Admin, preview and publish boundaries.
5. **Manager schedules the term (1.5 min)** — recurring group rosters and ICS export.
6. **Teacher runs today (1.5 min)** — mobile three-step flow, check-in and artwork upload.
7. **Family sees progress (1.5 min)** — private access, balance, next class, history and portfolio.
8. **Owner reads the business (1 min)** — reporting, export, security and migration boundaries.
9. **Commercial close (0.5 min)** — plans, onboarding, support and explicit deferred items.

## Claims to avoid

- Do not say the service is deployed on AWS.
- Do not promise automated SMS/email delivery.
- Do not imply online payments or Xero/Stripe integration are live.
- Do not say arbitrary spreadsheets import automatically.
- Do not claim MFA/SSO is complete.
- Do not imply multiple campuses share one tenant.
- Do not show or use real customer/student records.
