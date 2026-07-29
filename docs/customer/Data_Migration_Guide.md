# Data Migration Guide

## Commitment and boundary

PWE Studio will support a structured migration process. It will not silently accept or “best guess” arbitrary customer spreadsheets. A file that opens successfully may still contain duplicate people, ambiguous columns, stale balances, invalid dates, unsupported formulas or data the customer is not authorised to transfer.

The standard templates are:

- `customer-resources/PWE_Studio_Data_Import_Template.csv`
- `customer-resources/PWE_Studio_Data_Import_Template.xlsx`

The Excel workbook includes Instructions, Students, Courses, Packages and Field Guide worksheets with validation lists and examples.

## Required process

1. **Source authority** — identify the data owner and confirm authority to transfer.
2. **Preserve original** — retain an unchanged, access-controlled copy and record its hash.
3. **Template mapping** — map every source column to a PWE field or explicitly exclude it.
4. **Profiling** — count rows, unique IDs, duplicates, blanks, invalid dates and outliers.
5. **Exceptions** — return rejected and ambiguous rows to the customer.
6. **Transformation approval** — document every normalisation rule.
7. **Rehearsal** — import into an isolated target and reconcile.
8. **Backup/rollback** — record the target checkpoint and restore method.
9. **Final cut-over** — freeze the source, repeat deterministically and compare.
10. **Acceptance** — customer signs the reconciliation and retained exceptions.

## Stable IDs

Every student, course and package must have a stable external ID. Names, phone numbers and email addresses can change and must not be used as the only reconciliation key.

## Dates and numbers

- dates: `YYYY-MM-DD`;
- currency: AUD numeric value without currency symbols in CSV;
- credits: non-negative decimal;
- mobile: customer-authorised contact number;
- status: values listed in the workbook validation;
- boolean choices: `yes` or `no`.

## Privacy exclusions

Do not place these in the standard migration workbook:

- passwords or access codes;
- payment-card details;
- identity documents;
- unnecessary medical or sensitive notes;
- media binaries;
- publication consent inferred from a portfolio image.

Publication consent requires its own evidence and review. “The image was already online” is not enough.

## Acceptance checks

| Check | Source | Target | Difference | Accepted by |
|---|---:|---:|---:|---|
| Students | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| Active students | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| Courses | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| Packages | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| Total opening credits | `[ ]` | `[ ]` | `[ ]` | `[ ]` |
| Rejected records | `[ ]` | `[ ]` | `[ ]` | `[ ]` |

Sample at least:

- one active, trial and inactive student;
- one student with low balance;
- one course/package link;
- one schedule roster;
- one family access session;
- one portfolio item with and without publication consent.

## Unsupported assumptions

PWE Studio does not promise:

- automatic interpretation of merged headers or presentation-style worksheets;
- evaluation of arbitrary workbook macros;
- import of hidden tabs without explicit mapping;
- conversion of free-text financial history into audited accounting records;
- deduplication based only on similar names;
- preservation of unsupported source-system behaviour.
