# StudioSaaS Documentation Map

Status: current documentation authority map

Current product release: v10.13.0

Last reconciled: 2026-08-23

This file answers one question: **which document is allowed to define the
current product?** StudioSaaS retains detailed historical handoffs and design
work, but an older release note or plan must never override current code,
tests, package identity, or production evidence.

## Authority order

1. Current passing behavior checks and live production evidence.
2. Current repository code, migrations, generated assets, and configuration.
3. Current tests and release scripts.
4. The current documents listed below.
5. Dated plans, acceptance records, handoffs, references, and archives.

Source, Package, Production, and Backup are separate facts. The canonical
four-layer release ledger is [HANDOFF_LATEST.md](HANDOFF_LATEST.md). A version
label or archive filename alone is not deployment evidence.

## Current canonical documents

| Document | Owns | Update trigger |
|---|---|---|
| [HANDOFF_LATEST.md](HANDOFF_LATEST.md) | Current Source / Package / Production / Backup identity and latest work pointer | Every release and evidence-only closure |
| [Architecture.md](Architecture.md) | Current runtime topology, module boundaries, data flow, and target-vs-current distinction | Architecture, deployment, or module boundary change |
| [Product_Surface_Model.md](Product_Surface_Model.md) | Surface ownership, routes, role baseline, and product invariants | Route, responsibility, or role change |
| [API.md](API.md) | API contract, auth, tenant resolution, money and integration endpoints | Public or operator API change |
| [Database.md](Database.md) | PostgreSQL schema model, migrations, RLS, and data operations | Migration or database-operation change |
| [Deployment.md](Deployment.md) | Local, SaaS production, and Edition deployment topology | Runtime or deployment-path change |
| [Release_Runbook.md](Release_Runbook.md) | Release, package, deploy, recovery, and evidence sequence | Release tooling or gate change |
| [QA_Checklist.md](QA_Checklist.md) | Release acceptance matrix | New product surface, role, breakpoint, or gate |
| [Development_Roadmap.md](Development_Roadmap.md) | Strategic phases and explicitly deferred scope | Priority or phase decision |
| [Design_System.md](Design_System.md) | Implemented token, theme, accessibility, and layout rules | Shared visual contract change |
| [Admin_Guide.md](Admin_Guide.md) | Platform operator procedures | Platform workflow or operational procedure change |
| [Glossary.md](Glossary.md) | Canonical product vocabulary | User-facing terminology change |

The root [README.md](../README.md) is the release landing page, not a second
architecture or roadmap authority.

## Customer and delivery documents

`docs/customer/` is the editable customer/commercial source set. Public HTML
under `customer-resources/` is a separately maintained browser deliverable and
must be checked against the source set whenever product boundaries change.

| Source | Public counterpart | Status |
|---|---|---|
| [customer/FAQ.md](customer/FAQ.md) | `customer-resources/FAQ.html` | Current boundary; keep bilingual HTML aligned |
| [customer/Release_Notes.md](customer/Release_Notes.md) | `customer-resources/Release_Notes.html` | Chronological evidence; old entries are historical facts |
| [customer/Support_Policy.md](customer/Support_Policy.md) | `customer-resources/Support_Policy.html` | Current support boundary |
| [customer/Security_Privacy_Compliance.md](customer/Security_Privacy_Compliance.md) | `customer-resources/Privacy_Policy.html` | Working compliance source; public policy remains legal-review material |
| [customer/Service_Agreement_Draft.md](customer/Service_Agreement_Draft.md) | `customer-resources/Terms_of_Service.html` | Draft until signed and legally reviewed |

[customer/README.md](customer/README.md) is the customer-set index.
`standalone-edition/` is the Edition delivery set. A verified Edition archive
does not prove a customer installation exists; each installation needs its own
server, DNS, backup, restore, security, and acceptance record.

## Active plans and accepted remaining work

- [design/CMS_Roster_Split_Plan.md](design/CMS_Roster_Split_Plan.md): phase 1
  shipped in v10.13.0; phase 2 steps 9–19 remain planned.
- Per-account permission overrides and the weekly-timetable permission model
  remain product decisions, not implemented capabilities.
- Privileged MFA, off-instance backups, uptime/backup-failure monitoring,
  on-call ownership, and a contractual SLA remain open production controls.
- Online card processing, SMS provider transport, per-tenant custom domains,
  and an organisation-level multi-campus layer remain deferred.

Other files in `docs/design/` are dated plans, audit evidence, or design
references. Their completed checkboxes and historical version claims remain
useful archaeology but do not define the current release.

## Historical evidence

- `docs/handoff/claude/`: dated implementation narratives; immutable as
  historical evidence except for an explicit superseded-status correction in
  the latest file.
- `docs/handoff/codex/`: read-only historical archive indexed by
  `docs/handoff/codex/index.md`.
- `docs/reference/`: reference implementations, never current authority.
- `achieve/`: archived material, never current authority.

## Documentation release check

Before a documentation-only handoff or product release:

1. Search current documents for stale release labels and candidate wording.
2. Compare customer Markdown with the public HTML counterpart.
3. Run the release-ledger, manual, guide, customer-resource, terminology, and
   product-truth tests.
4. Verify links and `git diff --check`.
5. Record whether the change is documentation-only; never describe it as a
   deployed runtime change.
