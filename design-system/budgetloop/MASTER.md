# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** BudgetLoop
**Design Skill:** design-taste-frontend (taste-skill v2)
**Generated:** 2026-07-23
**Updated:** 2026-07-25 — rewritten to document the light-blue theme that actually ships (`web/tailwind.config.ts` + `web/app/globals.css`); all earlier dark/OLED claims removed.
**Category:** Developer Tool / Technical Dashboard

---

## Design Read

> **"Reading this as: technical developer dashboard for engineering teams, with a light, airy blue-tinted workspace language — white surfaces, one confident blue accent, restrained motion."**

### Design Dials (taste-skill)

| Dial | Value | Rationale |
|------|-------|-----------|
| DESIGN_VARIANCE | 4 | Predictable dashboard layout, symmetry-first |
| MOTION_INTENSITY | 3 | Subtle micro-interactions only, static-first |
| VISUAL_DENSITY | 6 | Data-dense dashboard with breathing room |

---

## Global Rules

### Color Palette

Single source: `web/tailwind.config.ts` → `theme.extend.colors`. Never introduce raw hex values in components — use these tokens.

| Role | Hex | Tailwind token |
|------|-----|----------------|
| Background | `#F7FAFF` | `bg-background` |
| Foreground | `#0B1F44` | `text-foreground` |
| Surface | `#FFFFFF` | `bg-surface` |
| Surface Hover | `#F4F8FF` | `bg-surface-hover` |
| Muted | `#EDF4FF` | `bg-muted` |
| Muted Foreground | `#60759A` | `text-muted-foreground` |
| Border | `#D8E4F5` | `border-border` |
| Border Strong | `#BED2EE` | `border-border-strong` |
| Accent (CTA) | `#1769F6` | `bg-accent` / `text-accent` |
| Accent Foreground | `#FFFFFF` | `text-accent-foreground` |
| Accent Glow | `rgba(23,105,246,.12)` | `bg-accent-glow` |
| Destructive | `#EF4B5B` | `bg-destructive` |
| Success | `#0CAD72` | `text-success` / `bg-success` |
| Warning | `#F28A00` | `text-warning` / `bg-warning` |
| Info | `#2F7DF6` | `text-info` / `bg-info` |
| Critical | `#EF4B5B` | `text-critical` / `bg-critical` |
| Ring (focus) | `#1769F6` | `ring-accent/20` via `:focus-visible` |

**Color Notes:** Light-first. Single accent: blue-600 (`#1769F6`) — CTAs, links, active states. Semantic colors are reserved for status meaning (success/warning/info/critical). Destructive and critical intentionally share one red.

**Chart colors:** SVG `stroke`/`fill` attributes cannot use Tailwind classes, so they import from the single constants module `web/lib/chart-colors.ts` (`CHART_COLORS`), which mirrors the palette above (accent/success/warning/critical/grid=border/label=muted-foreground). Keep the two files in sync.

### Typography

- **Sans Font:** Inter, loaded via `next/font/google` (`--font-inter`), system fallback stack
- **Mono Font:** JetBrains Mono, loaded via `next/font/google` (`--font-jetbrains-mono`); used for IDs, token counts, costs, durations
- **Scale (tailwind.config.ts `fontSize`):** `2xs` 12px · `xs` 13px · `sm` 14px · `base` 15px · `lg` 17px · `xl` 20px · `2xl` 26px · `3xl` 34px — `body` defaults to `text-sm`
- **Headings:** tight tracking (`page-heading` uses `tracking-[-0.035em]`), semibold weight
- **Numbers:** `tabular-nums` for every metric column and KPI

### Spacing

Tailwind default scale on an 8px base rhythm. Page padding comes from `.page-shell` (`px-4 py-6 sm:px-8 sm:py-8`); section padding is `p-5 sm:p-6` (large surfaces) or `p-5` (compact surfaces); vertical rhythm between page sections is `space-y-5` to `space-y-7`.

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `sm` | `6px` | Small chips, dots |
| `DEFAULT` | `8px` | Standard elements |
| `md` | `10px` | Buttons, inputs |
| `lg` | `12px` | Cards, tables |
| `xl` | `16px` | Surfaces, modals |

### Shadow Depths (Soft, blue-tinted)

| Level | Value | Usage |
|-------|-------|-------|
| `surface` | `0 10px 30px rgba(35,89,160,.08)` | `.surface` panels |
| `elevated` | `0 18px 50px rgba(35,89,160,.14)` | Modals, popovers |
| `control` | `0 4px 14px rgba(35,89,160,.06)` | Buttons, inputs, `.card` |

---

## Shared Classes (`web/app/globals.css`)

Use these instead of re-composing utilities:

- **Layout:** `.page-shell`, `.page-heading`, `.page-subtitle`, `.section-title`
- **Surfaces:** `.surface` (white/90, blur, `shadow-surface`, `rounded-xl`), `.card`, `.card-hover`, `.skeleton`, `.divider`, `.code-block`
- **Badges:** `.badge` + `.badge-success` / `.badge-warning` / `.badge-critical` / `.badge-info` / `.badge-muted` — always driven by `statusClass()` + `STATUS_LABELS` from `web/lib/presentation.ts` (single source for run statuses and LLM `request_status`)
- **Buttons:** `.btn` + `.btn-primary` / `.btn-secondary` / `.btn-ghost` / `.btn-destructive`
- **Forms:** `.input-base`, `.field-label`, `.field-hint`, `.field-error`
- **Tables:** `.data-table` (header tint, row hover, cell padding built in) inside an `overflow-x-auto` wrapper — the only table system; do not hand-roll `divide-y` tables

## Primitives (`web/components/ui.tsx`)

- `ProgressBar` — the only progress bar (`ratio`, `color`, `track`, `height`); never hand-roll bar divs
- `EmptyState` — icon + title + hint + optional action
- `KeyValue` — dense dl row for detail panels
- `Tabs` — underline tab bar (`tabs`, `active`, `onChange`, `ariaLabel`); the only tab system
- `SvgLineChart` (`web/components/SvgLineChart.tsx`) — dependency-free trend chart; colors via `CHART_COLORS`

---

## Style Guidelines

**Style:** Light workspace — soft blue tints on white, Swiss-influenced minimalism

**Keywords:** light theme, airy, high readability, developer tool, technical dashboard, precision, clean

**Key Effects:** subtle blue-tinted shadows, white/90 surfaces with backdrop blur over a faint radial gradient body background, one accent color, status meaning carried by semantic tokens (never color-only — pair with icon or label)

### Animations

| Animation | Duration | Easing | Usage |
|-----------|----------|--------|-------|
| `fade-in` / `in` | 150–180ms | ease-out | Page/appear transitions |
| `slide-up` (`.animate-in`) | 200ms | cubic-bezier(0.16, 1, 0.3, 1) | Content reveal |
| `pulse-subtle` | 2s loop | ease-in-out | Live/active indicators |

**Motion policy:** MOTION_INTENSITY=3 → animations limited to hover/active states and subtle indicators. Transition durations use the `fast` (160ms) / default (200ms) / `slow` (300ms) tokens. No scroll-triggered reveals, no parallax, CSS-only. `prefers-reduced-motion` is honored globally in `globals.css`.

---

## Anti-Patterns (Do NOT Use)

- ❌ **Raw hex / `rgba()` colors or off-palette utilities** (`red-500`, `blue-600`, `bg-[#...]`) in components — palette tokens only; chart SVGs use `CHART_COLORS`
- ❌ **Dark sections or dark-mode re-theming** — the product ships light-only
- ❌ **Emojis in UI text** — use Lucide icons exclusively
- ❌ **Serif fonts** — sans-serif only for this technical dashboard
- ❌ **Mixed icon families** — Lucide only
- ❌ **Hand-rolled tables, tabs, progress bars, or status-badge style maps** — use `.data-table`, `Tabs`, `ProgressBar`, `statusClass()`/`STATUS_LABELS`
- ❌ **Undefined class names** — only the shared classes listed above exist
- ❌ **Google Fonts via `<link>` or `@import`** — use `next/font`
- ❌ **Layout-shifting hover transforms** (`.card-hover` uses a 1px lift only)
- ❌ **Low contrast text** (min 4.5:1)
- ❌ **Invisible focus states** — keep the global `:focus-visible` ring intact

---

## Pre-Delivery Checklist

Before delivering any UI code, verify:

- [ ] No emojis in UI text — use Lucide icons
- [ ] All icons from consistent set (Lucide)
- [ ] Fonts loaded via `next/font` (not @import)
- [ ] Colors come from palette tokens / `CHART_COLORS`, never raw hex
- [ ] Tables use `.data-table`; tabs use `Tabs`; bars use `ProgressBar`; badges use `statusClass()` + `STATUS_LABELS`
- [ ] Button text contrast ≥ 4.5:1 (WCAG AA)
- [ ] Form inputs have labels, placeholders, help text
- [ ] Focus states visible for keyboard navigation (`:focus-visible` ring)
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No horizontal page scroll on mobile (wide tables scroll inside `overflow-x-auto`)
- [ ] UI copy in zh-CN; unavailable data labeled (e.g. 未上报 / 价格未配置), never zero-filled
