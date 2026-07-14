# Design System

> **StudioSaaS Brand & UI Reference**
> Last updated: 2026-07-02

---

## Brand Identity

### Colours

| Token | Hex | Usage |
|---|---|---|
| `--primary` | `#1E40AF` | Primary buttons, links, active states |
| `--secondary` | `#0F766E` | Secondary actions, success states |
| `--accent` | `#F59E0B` | Highlights, warnings, active nav |
| `--bg` | `#F8FAFC` | Page background |
| `--surface` | `#FFFFFF` | Card, modal, form backgrounds |
| `--text` | `#1E293B` | Body text |
| `--text-muted` | `#64748B` | Captions, placeholders |
| `--border` | `#E2E8F0` | Dividers, input borders |
| `--error` | `#DC2626` | Validation errors, destructive actions |
| `--success` | `#16A34A` | Success confirmations |

### Typography

| Role | Font | Size | Weight | Line Height |
|---|---|---|---|---|
| H1 | Inter, sans-serif | 36px | 700 (Bold) | 1.2 |
| H2 | Inter, sans-serif | 28px | 600 (SemiBold) | 1.25 |
| H3 | Inter, sans-serif | 22px | 600 (SemiBold) | 1.3 |
| Body | Inter, sans-serif | 16px | 400 (Regular) | 1.5 |
| Small | Inter, sans-serif | 14px | 400 | 1.5 |
| Caption | Inter, sans-serif | 12px | 400 | 1.4 |

### Spacing Scale

```
4px  —  xs (0.25rem)
8px  —  sm (0.5rem)
12px —  md (0.75rem)
16px —  base (1rem)
24px —  lg (1.5rem)
32px —  xl (2rem)
48px —  2xl (3rem)
```

### Border Radius

| Context | Radius |
|---|---|
| Buttons, badges | `6px` |
| Cards, modals | `12px` |
| Input fields | `8px` |
| Images, avatars | `50%` (circular) |

---

## UI Components

### Buttons

| Variant | Background | Text | Border | Use Case |
|---|---|---|---|---|
| Primary | `--primary` | White | None | Main CTAs |
| Secondary | `--surface` | `--primary` | 1px `--primary` | Outlined actions |
| Tertiary | Transparent | `--text` | None | Low-emphasis links |
| Destructive | `--error` | White | None | Delete, remove |
| Ghost | Transparent | `--text` | None | Icon-only, minimal |

**States:** default, hover (lighten 8%), active (darken 4%), disabled (50% opacity).

### Cards

```html
<div class="card">
  <div class="card-header">Title</div>
  <div class="card-body">Content</div>
  <div class="card-footer">Actions</div>
</div>
```

| Property | Value |
|---|---|
| Background | `--surface` |
| Border | 1px `--border` |
| Border-radius | `12px` |
| Shadow | `0 1px 3px rgba(0,0,0,0.08)` |
| Padding | `24px` |

### Forms

| Element | Style |
|---|---|
| Input | 1px `--border`, `8px` radius, `16px` padding |
| Focus ring | 2px `--primary`, `2px` offset |
| Label | 14px SemiBold `--text`, `8px` bottom margin |
| Error state | 1px `--error`, error message below in `--error` 14px |
| Help text | 12px `--text-muted`, `8px` top margin |

### Navigation

| Element | Style |
|---|---|
| Top nav bar | 64px height, `--surface`, 1px bottom `--border` |
| Active link | `--primary` text, 2px bottom accent |
| Sidebar | 240px width, `--bg`, right border 1px `--border` |
| Sidebar active | `--primary` left border, `--primary` text |

### Tables

| Property | Value |
|---|---|
| Header | 14px SemiBold `--text`, `--bg` background |
| Row height | 48px |
| Alternating rows | `--surface` / `--bg` |
| Hover | `--bg` background |
| Border | 1px `--border` cell dividers |

### Toast Notifications

| Type | Icon | Colour | Duration |
|---|---|---|---|
| Success | Checkmark | Green left border | 4s |
| Error | X mark | Red left border | 6s |
| Warning | Exclamation | Amber left border | 5s |
| Info | i circle | Blue left border | 4s |

---

## Iconography

- **Library:** Lucide Icons (outline style)
- **Size:** 20px default, 16px small, 24px large
- **Stroke width:** 2px
- **Colour:** Inherits from parent text colour

---

## Responsive Breakpoints

| Breakpoint | Max Width | Target |
|---|---|---|
| Mobile | < 640px | Phones |
| Tablet | 640–1024px | Tablets |
| Desktop | > 1024px | Desktops |

**Mobile-first:** Base styles target mobile; breakpoints above add layout complexity.

---

## Accessibility

| Requirement | Standard |
|---|---|
| WCAG | AA minimum |
| Colour contrast | 4.5:1 body, 3:1 large text |
| Focus visible | Custom focus ring (2px `--primary`) |
| Keyboard nav | Full tab order, no keyboard traps |
| Screen reader | Semantic HTML, ARIA where needed |
| Font size | Minimum 14px body, 12px captions |

---

## Usage Guidelines

1. **Use CSS custom properties** for all tokens — never hard-code hex values.
2. **Follow the spacing scale** — avoid arbitrary pixel values.
3. **One heading level per section** — maintain document hierarchy.
4. **Icons + text** for primary actions; icons alone only in icon bars.
5. **Error messages** must be actionable — tell the user how to fix.
