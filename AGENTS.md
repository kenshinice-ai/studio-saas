# AGENTS.md — StudioSaaS Project Constitution

> Project-level instructions for Codex working inside the StudioSaaS repository.
> This file supplements Lee's global `~/.codex/AGENTS.md`.
> Global rules define how to work; this file defines what StudioSaaS is, what must be protected, and how changes should be judged.

## 1. Project Identity

StudioSaaS is a multi-tenant SaaS platform for creative studios and education/service venues.

It evolved from a real single-studio operating system and is being generalised into a reusable multi-tenant product. The system includes public-facing product/tenant experiences and staff/admin workflows.

Treat StudioSaaS as a product, not as a collection of pages.

Primary product surfaces currently include:

- product marketing site;
- tenant public portal;
- tenant registration / enquiry flow;
- Studio Admin;
- CMS / operational back office;
- shared theme, brand, token, and tenant configuration systems.

The project must support multiple tenant identities, industries, languages, theme modes, and operating contexts without allowing one tenant or one surface to become a special-case implementation.

## 2. Product Priorities

When priorities conflict, use this order:

1. tenant data integrity and isolation;
2. operational reliability for staff;
3. user clarity and task completion;
4. accessibility;
5. consistency across product surfaces;
6. tenant brand fidelity;
7. maintainability and extensibility;
8. visual polish;
9. performance;
10. implementation convenience.

Do not sacrifice a higher priority merely because a lower-priority implementation is easier.

## 3. Core Product Principles

### Multi-tenant by design

Every feature must be evaluated for:

- tenant isolation;
- tenant-specific configuration;
- tenant-specific branding;
- tenant-specific terminology;
- tenant-specific data;
- safe defaults and fallbacks.

Never assume the current demo/reference tenant is the universal product model.

Do not hard-code studio-specific, school-specific, music-specific, or art-specific terminology into reusable product surfaces when a neutral token, tenant-configured term, or approved placeholder exists.

### Product system over one-off pages

Before adding local CSS, local state, duplicated validation, or page-specific theme behaviour, inspect the shared system first.

Prefer fixing the shared contract when the issue is systemic.

Do not solve a generator/token problem with repeated application-level patches.

Do not solve a one-page defect by changing the generator unless the defect genuinely affects the shared contract.

### Real operational software

CMS and Studio Admin are daily working tools.

Optimise them for:

- speed of completion;
- information clarity;
- predictable controls;
- low cognitive load;
- visible state;
- safe recovery;
- keyboard efficiency where useful;
- mobile resilience where operationally necessary.

Do not import marketing-site animation or decorative behaviour into operational interfaces unless it clearly improves task completion.

## 4. Repository Inspection Rules

Before changing StudioSaaS:

1. identify the active implementation and avoid editing stale/reference copies;
2. inspect repository status and existing uncommitted work;
3. find relevant design and architecture documents;
4. identify whether the change belongs in:
   - shared token/design layer;
   - theme generator;
   - tenant template;
   - product site;
   - CMS;
   - Studio Admin;
   - backend/API/data layer;
5. inspect existing tests/check scripts before inventing new validation.

Pay particular attention to similarly named reference, legacy, template, generated, migrated, and active files.

Never assume a file is production-active from its name alone.

## 5. Known Product Surfaces and Boundaries

### Product site

Purpose:

- explain StudioSaaS clearly;
- communicate product value;
- support bilingual presentation where provided;
- convert qualified visitors without compromising accessibility.

Product-site visual freedom is greater than CMS visual freedom, but it must still use the shared design system where one exists.

### Tenant portal

Purpose:

- present the tenant's identity;
- expose public studio/venue information and actions;
- provide a coherent branded customer experience.

Tenant branding must be driven by the tenant theme contract, not hard-coded colours.

### Registration / enquiry

Purpose:

- minimise friction;
- gather only information justified by the flow;
- explain collection/privacy context at the point of collection;
- validate early enough to help users recover;
- preserve entered data when language/UI state changes where practical.

Required fields must be clear.

Optional/high-friction fields should use progressive disclosure when appropriate.

### CMS / operational back office

Purpose:

- enable staff to complete high-frequency operational work quickly and reliably.

CMS priorities:

1. correctness;
2. speed;
3. state visibility;
4. accessibility;
5. consistency;
6. brand expression.

Do not prioritise decorative motion over operational clarity.

### Studio Admin

Treat Studio Admin and CMS as related operational products.

Before introducing a new UI convention into one, check whether the other already has the equivalent pattern.

Avoid creating parallel component systems without a clear reason.

## 6. Design-System Contract

StudioSaaS has a shared token/theme direction. Respect it.

### Token-first rule

Before writing a hard-coded:

- colour;
- spacing value;
- radius;
- typography size;
- focus colour;
- semantic-state colour;
- disabled colour;

check whether the shared design/token system already defines the concept.

If a shared token exists, use it.

If a concept is genuinely missing across the product, extend the token system rather than scattering literals.

### Theme contract

Tenant themes must remain coherent across:

- portal;
- registration;
- CMS;
- Studio Admin where tenant identity is expected.

Do not let different surfaces consume different arbitrary subsets of a theme contract.

When adding or modifying a theme token:

- inspect all consumers;
- verify light and dark modes;
- verify semantic states;
- verify fallback behaviour;
- update generator/assertion logic when the contract itself changes.

### Current theme-system constraint

The project supports multiple theme modes, including light and dark variants. Never assume a value that works on a light surface also works on a dark surface.

Every theme-sensitive change should be checked against representative light and dark modes; shared generator changes should be validated against the full supported theme matrix when tooling exists.

### Semantic colours

Success, warning, and danger colours express state.

Do not use them as decorative module colours.

Do not substitute arbitrary Tailwind palette values for generated semantic colours where the shared semantic tokens exist.

## 7. Typography and Bilingual Rules

StudioSaaS includes English and Chinese-facing experiences.

Typography must respect language-specific behaviour.

### English / Latin

Letter spacing, uppercase labels, and condensed display treatments may be used only when they improve hierarchy and remain readable.

### Chinese / CJK

Do not blindly inherit Latin typography tricks.

Avoid:

- aggressive negative tracking on Chinese display text;
- wide letter spacing intended for Latin uppercase;
- forced uppercase logic;
- line heights that risk clipping dense glyphs;
- webfont decisions that create unnecessary mainland-network dependency.

Prefer approved system/CJK font stacks when present in the design system.

### Reading measure

Use language-aware reading widths/tokens where provided.

Do not assume one `ch`-based measure is equally suitable for Latin and CJK text.

## 8. Golden-Ratio / Layout Rule

StudioSaaS uses proportional design deliberately, not decoratively.

Use asymmetric/golden-ratio layouts only where one region is genuinely primary, such as:

- hero copy vs visual;
- explanation vs form;
- primary dashboard region vs secondary KPI region.

Do NOT use golden-ratio splits for peer controls such as:

- first name / surname;
- repeated KPI cards;
- table columns;
- peer form fields;
- mobile forms.

Peer elements should normally remain equal-width or content-driven.

Below responsive breakpoints, prioritise clarity over preserving a ratio.

## 9. Accessibility Is a Release Constraint

Accessibility is not optional polish.

For user-facing work:

- normal text should meet WCAG AA contrast expectations;
- interactive boundaries/focus indicators must remain visible;
- keyboard focus must be obvious;
- interactive targets should normally be at least 44×44px unless an explicitly documented compact-toolbar exception exists;
- icon-only buttons require accessible names;
- disabled states must not depend on opacity alone;
- reduced-motion preferences must be respected;
- form errors must be connected to fields programmatically;
- errors must be actionable and recoverable;
- do not rely on hover as the only interaction signal.

Do not claim accessibility based on visual inspection alone when a script or measurable check exists.

## 10. UI Motion and Interaction

Motion must communicate something.

Acceptable purposes include:

- state change;
- hierarchy;
- confirmation;
- transition continuity;
- progress/busy indication.

Avoid:

- decorative infinite animation in operational surfaces;
- cursor-following effects;
- gratuitous parallax;
- magnetic controls;
- universal hover elevation on navigation/table rows;
- animation that makes repeated staff work slower.

Operational interfaces should feel calm, fast, and deliberate.

## 11. Forms and Validation

For forms:

- validate on blur or at the earliest helpful moment for common fields where practical;
- validate again on submit;
- focus or reveal the first actionable error;
- preserve user input through non-destructive UI state changes;
- use clear labels;
- avoid tiny labels and unnecessarily weak contrast;
- disclose why sensitive data is collected when relevant;
- keep optional/high-friction sections collapsed or deferred when this improves completion.

Do not add fields merely because they might be useful later.

## 12. Tenant Terminology

Reusable tenant surfaces must remain industry-neutral where the product contract requires it.

Before introducing nouns such as:

- studio;
- art studio;
- music school;
- piano school;
- class-specific industry language;

check the project terminology system and existing placeholders/configuration.

Use approved tenant-configured terminology rather than hard-coded industry words.

If a terminology validation script exists, run it for changes touching tenant-facing copy/templates.

## 13. Data and Tenant Isolation

Treat tenant isolation as a hard architectural boundary.

For any data-layer/API change, verify:

- every read is scoped correctly;
- every write is scoped correctly;
- identifiers cannot cross tenant boundaries;
- caching does not leak tenant data;
- logs/errors do not expose another tenant's data;
- admin elevation is explicit and auditable;
- migrations preserve tenant ownership.

Never introduce a convenience query that bypasses tenant scoping without explicit architectural review.

For destructive or broad updates:

- prefer dry-run;
- show affected tenant/record counts;
- make operations recoverable/idempotent where practical.

## 14. Reference System Policy

The project contains or refers to earlier/single-studio systems.

Use them as evidence, not as authority.

Reference implementations are useful for:

- proven workflows;
- operational behaviour;
- migration lessons;
- regression comparison.

Do not copy:

- single-tenant assumptions;
- tenant-specific branding;
- legacy hard-coded colours;
- duplicate design systems;
- old accessibility defects;
- old architecture merely because it already works.

When reference behaviour conflicts with the current StudioSaaS product contract, the current contract wins.

## 15. Legacy-Code Policy

Legacy code may remain operationally important.

Do not rewrite large legacy areas merely to modernise them.

Prefer:

1. characterise existing behaviour;
2. establish tests/checks where practical;
3. introduce shared primitives;
4. migrate incrementally;
5. verify each phase.

For large UI migrations, avoid changing typography, colours, components, layout, and business logic simultaneously unless the task specifically requires it.

Keep migration phases reviewable.

## 16. Component Strategy

Before creating new UI primitives, search for existing equivalents.

For high-frequency CMS/Admin patterns, prefer shared components for concepts such as:

- Button;
- IconButton;
- Badge;
- FormField;
- Tabs;
- SegmentedControl;
- Accordion;
- Dialog;
- EmptyState;
- Toast.

Do not create abstraction purely to reduce line count.

Create a shared component when it materially improves consistency, accessibility, validation, or future changes.

## 17. Icons

Prefer the project's approved inline SVG/icon system.

Do not use emoji or font-dependent glyphs as functional UI icons when a proper icon exists or can reasonably be added.

For icon-only controls:

- SVG can be `aria-hidden`;
- the button itself must have an accessible name.

## 18. Styling Migration Rule

When migrating legacy utility styles into the design system:

- preserve behaviour first;
- replace arbitrary palette classes with semantic tokens;
- reduce one-off style variants;
- do not globally remap a utility colour name to tenant branding if that utility currently carries multiple meanings;
- do not use broad `!important` interception as the long-term theme architecture.

If a legacy class name is currently acting as a hidden semantic API, make that dependency explicit before removing it.

## 19. Generated Theme / Palette Changes

The palette generator is infrastructure.

Any generator change must be treated as a product-wide change.

Before modifying it:

1. identify all generated outputs;
2. understand current contrast targets;
3. add/update assertions with the change;
4. regenerate deterministically;
5. inspect diffs;
6. verify representative surfaces;
7. run the complete theme validation matrix where available.

Never hand-edit generated theme output and leave the generator inconsistent.

## 20. Responsive Behaviour

Verify important user flows at representative widths, including:

- 375px;
- 768px;
- 1024px;
- 1440px;

or the repository's current equivalent breakpoints.

Avoid horizontal overflow for core lists/forms on mobile.

Do not preserve desktop multi-column composition when a single-column mobile flow is clearer.

## 21. Performance

Prioritise performance where it affects:

- initial tenant portal load;
- CMS daily interaction;
- large student/customer lists;
- dashboard queries;
- image galleries;
- uploads;
- search;
- theme/bootstrap loading.

Do not optimise by removing correctness, accessibility, or tenant isolation.

Avoid adding heavy client dependencies for small UI effects.

## 22. Testing and Checks

Before declaring StudioSaaS work complete, run the relevant existing checks.

Depending on the touched area, inspect and use project-provided checks for:

- tests;
- type checking;
- build;
- terminology;
- theme/palette validation;
- accessibility assertions;
- tenant-template validation;
- product-home validation;
- migration validation;
- visual/theme checks.

Do not invent command names. Inspect the repository's actual scripts/configuration first.

For UI changes, supplement automated checks with targeted browser verification.

## 23. Browser Verification for UI Work

For substantial UI changes, verify the affected flow in a browser when tooling is available.

Check:

- correct route/surface;
- light and dark representative themes when relevant;
- English and Chinese when relevant;
- keyboard focus;
- form validation/error states;
- loading/empty/success states;
- responsive layout;
- no obvious console/runtime errors.

For theme-system changes, do not verify only the default tenant.

## 24. High-Risk Change Boundary

In addition to Lee's global escalation rules, StudioSaaS requires escalation before:

- changing the tenant-isolation model;
- changing authentication/authorisation ownership;
- changing the canonical tenant theme contract;
- destructive production-data migration;
- replacing the theme generator;
- removing compatibility with an active tenant/template;
- large CMS rewrite;
- changing collection/consent behaviour for personal data;
- changing shared terminology architecture;
- breaking public registration/API contracts.

Provide the safest path and a migration strategy rather than silently proceeding.

## 25. StudioSaaS Definition of Done

A StudioSaaS task is complete only when:

- requested behaviour works;
- tenant boundaries are preserved;
- relevant shared contracts are respected;
- applicable light/dark theme behaviour is correct;
- applicable English/Chinese behaviour is correct;
- important responsive states work;
- accessibility is not regressed;
- relevant tests/checks pass or known exceptions are stated;
- no unrelated user work was overwritten;
- completion report distinguishes implementation, verification, assumptions, and remaining risk.

For user-facing changes, "it renders" is not enough.

For data changes, "the query runs" is not enough.

For multi-tenant changes, "it works for the default tenant" is not enough.

## 26. Project-Specific Completion Report

For substantial StudioSaaS tasks, finish with:

### Completed
What changed and which product surface(s) were affected.

### Shared contracts
Whether tokens, theme generation, terminology, data model, API, or tenant behaviour changed.

### Verification
Exact tests/checks/browser states verified.

### Tenant / theme coverage
Which tenant/theme/language states were checked where relevant.

### Remaining risks
Only genuine unresolved risks or follow-up work.

Keep it concise.
