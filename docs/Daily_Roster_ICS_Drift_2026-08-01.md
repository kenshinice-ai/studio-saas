# Daily roster and ICS convergence ledger — 2026-08-01

Reference inspected read-only: `LetsPaintCMS-v7.3.7-release.zip`. The reference
is a mature single-studio operating CMS; PWE Studio remains the multi-tenant
source of truth. Behaviour was adapted, not source-copied.

## Decision ledger

| Capability | Mature CMS evidence | PWE Studio v8.2.0 decision |
|---|---|---|
| Calendar context | Export follows the selected daily-roster date | Keep two explicit products: **Fixed schedule ICS** for recurring classes and **Export selected day ICS** beside the selected roster |
| Empty export | Day export only appears when a roster exists | Disable empty fixed-schedule export; hide private day export when the selected day has no effective students |
| Group semantics | Ordinary entries at the same time are one group class | Retain canonical server grouping; split only explicit `oneToOne` entries |
| Missing time | Export stops rather than inventing a class time | Existing migrated rows remain honest all-day events; every new manual booking starts from the tenant default but saves an explicit time |
| Default time | Operational controls default to 14:30 | Add tenant-wide, server-owned `defaultClassTime`, initially 14:30 and editable by Owner/Manager in CMS Settings |
| Existing bookings | Saved row time is authoritative | Changing the default never rewrites existing `daily_roster_entries.class_time` |
| Weekly inheritance | Fixed classes populate the matching weekday | Display inherited schedule time in slot grouping and student rows; explicit date override wins |
| Preview drift | Reference warns after change | Keep PWE's stronger SHA-256 revision binding; refresh a 409 conflict inside the dialog and require a second confirmation without a page-level error toast |
| Privacy | Daily export contains student names | Keep `data:export` permission, private-file warning and no guardian names; recurring schedule export contains no identities |
| Planner density | Advanced template/batch tools are secondary | Fold templates and batch tools by default so the selected day and roster stay above the fold |
| Reminder accuracy | Operations use the roster slot | Include each student's effective date/time and tenant name in copied/native SMS reminders |

## Improvements retained from PWE Studio

- PostgreSQL tenant ownership and role projection instead of browser-only state.
- Authenticated fetch download instead of an anchor that can save a JSON 401 as
  an `.ics` file.
- Canonical preview/download document, deterministic filename and revision
  conflict protection.
- Melbourne timezone rules, explicit private export permission and audit logs.
- Weekly schedule cancellation overrides and immutable attendance/credit
  history.

## Visual acceptance contract

- Date controls occupy the 38.2% planning column; add-student controls occupy
  the 61.8% action column on desktop and stack without horizontal overflow on
  mobile.
- All controls remain at least 44px; form controls use the shared 46px token.
- A roster row has one time control. Inherited fixed-class time is read-only;
  explicit daily time is editable in place.
- The mobile language switch lives in Settings instead of floating above roster
  actions.
