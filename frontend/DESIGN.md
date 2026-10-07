# WebQuery Design System

This file is the constitution of the WebQuery interface. Read it before
changing a screen, component or style. A change is incorrect if it violates a
rule written here.

Scope: `frontend/` only. Backend contracts, route structure and information
architecture are documented elsewhere.

Related records: [implemented feature contracts](../docs/features.md) and the
[architecture summary](../docs/architecture.md). Original SPEC-0010 and
ADR-0010 identifiers are mapped in the [migration analysis](../docs/migration-analysis.md).

## 1. Product definition

WebQuery is an enterprise console for running **auditable** SQL queries against
registered databases. Users write queries, risky statements go through
administrator approval, results pass through masking rules, and every step is
logged.

This has three direct design consequences:

1. **Density must stay high.** This is a work tool that may remain open for
   hours, not a marketing page. Generous empty space can hide information.
2. **State must always be visible.** Users should never have to guess whether a
   query is awaiting approval, which column was masked, or whether results were
   truncated.
3. **Destructive actions must not compete with decoration.** An administrator
   deciding whether to approve or reject a request should immediately see the
   relationship between risk and action.

## 2. Core principle: color carries meaning

**Application chrome is achromatic.** Use warm graphite (OKLCH hue 85–95,
chroma ≤ 0.008). Backgrounds, borders, body text and panel headings are not
colored.

**Chroma is reserved for three jobs:**

| Use | Token family |
| --- | --- |
| State: draft, pending, approved, rejected, risky | `--success`, `--warning`, `--danger` |
| Focus, selection, active navigation, brand mark | `--accent` (one hue: 205, teal) |
| SQL syntax highlighting | `--code-*` |

**The primary action uses ink, not the brand color** (`--primary`). It is the
highest-contrast object on the page, so an execution button is read as an
action instead of a status badge.

Before adding a color, ask whether it communicates a state. If it does not,
keep it achromatic.

## 3. Design dials

These values were chosen deliberately and should be discussed before changing.

| Dial | Value (0–10) | Meaning |
| --- | --- | --- |
| Visual variance | 3 | Systematic and predictable; screens feel related. |
| Motion intensity | 3 | Motion is feedback, not decoration; 110–260 ms with one easing curve. |
| Visual density | 7 | A compact console with 32 px controls and 13 px body text. |

## 4. Token layer

The single source is [`styles/tokens.css`](styles/tokens.css). Values use
OKLCH. The light theme lives on the bare `:root`; the dark theme is defined
both under `@media (prefers-color-scheme: dark)` and on
`:root[data-theme='dark']`, so an explicit user choice overrides the system
preference in either direction.

[`styles/global.css`](styles/global.css) connects these variables to Tailwind
v4 through `@theme inline`. `inline` matters: generated utilities keep a
reference to `var(--...)` instead of copying the value, so changing the theme
requires only one attribute write and no rebuild.

### 4.1 Surface ladder

Four levels run from lower to higher:

| Token | Utility | Use |
| --- | --- | --- |
| `--bg-sunken` | `bg-sunken` | Editor area, table header, disabled input. |
| `--bg-canvas` | `bg-canvas` | Page background; used by `body`. |
| `--bg-surface` | `bg-surface` | Panels, cards and rows. |
| `--bg-raised` | `bg-raised` | Dialogs, menus, popovers and toasts. |

Interaction states are `--bg-hover` (`bg-hover`), `--bg-active`
(`bg-pressed`) and `--bg-selected` (`bg-selected`, the one selection state
that carries accent color).

Build hierarchy with this ladder and hairline borders, not with shadow. Use
`shadow-overlay` only for layers that truly float above the page.

### 4.2 Text ramp

| Token | Utility | Use | Contrast target |
| --- | --- | --- | --- |
| `--fg` | `text-fg` | Body text, headings and data cells | ≥ 4.5:1 |
| `--fg-muted` | `text-muted` | Labels, secondary descriptions and icons | ≥ 4.5:1 |
| `--fg-subtle` | `text-subtle` | Placeholders, line numbers and help text | ≥ 4.5:1 |
| `--fg-faint` | `text-faint` | Decorative separators and disabled glyphs only | not assessed |
| `--fg-on-solid` | `text-on-solid` | Text on solid color surfaces | ≥ 4.5:1 |

`text-faint` must never carry meaning. This exception is intentional and is
marked in `tokens.css`.

### 4.3 Borders

| Token | Utility | Use |
| --- | --- | --- |
| `--line` | `border-line` | Default separators, panel edges and row dividers |
| `--line-strong` | `border-line-strong` | Emphasized dividers and scrollbar thumbs |
| `--control-line` | `border-control-line` | Interactive control borders at 3:1 (WCAG 1.4.11) |

Inputs, selects and secondary buttons must not use `border-line`. A control
border must have enough contrast to identify the element as interactive.

### 4.4 State colors

Each state has four variants and they are used together:

```text
--success       text tone      text-success
--success-soft  soft fill      bg-success-soft
--success-line  soft border    border-success-line
--success-solid solid marker   bg-success-solid (dots and bars only)
```

The same pattern applies to `--warning` and `--danger`. `--info` is an alias
for accent; there is no separate information color.

The badge formula is always:
`text-{tone} bg-{tone}-soft border border-{tone}-line`.

### 4.5 Radius, shadow, motion and layers

```text
--r-xs  4px    icon buttons, small chips, focus ring radius
--r-sm  6px    controls: buttons, inputs, selects and checkboxes
--r-md  10px   panels: cards, table frames and sections
--r-lg  14px   layers: dialogs, menus and command palette
--r-pill       status badges and scrollbars only
```

This scale is fixed. Adding a fifth radius creates ambiguity.

```text
--dur-fast 110ms   hover, active and color transitions
--dur      170ms   menus, tooltips and panel openings
--dur-slow 260ms   page entry and dialogs
--ease     cubic-bezier(0.2, 0, 0, 1)   one easing curve
```

Under `prefers-reduced-motion: reduce`, all animation and transition durations
fall to 1 ms.

```text
--z-sticky   20   sticky table header
--z-nav      30   top navigation
--z-overlay  50   dialog backdrop
--z-dialog   60
--z-toast    70
--z-tooltip  80
```

Components must not invent z-index values. Add a token here when a new layer
is required.

## 5. Typography

Geist Variable is used for text and Geist Mono Variable for code, identifiers
and numbers. Both are bundled through `@fontsource-variable`; there is no CDN.

| Role | Size | Weight | Note |
| --- | --- | --- | --- |
| `h1` | 22px | 560 | One page heading |
| `h2` | 16px | 560 | Section heading |
| `h3` | 14px | 560 | Panel heading |
| Body | 14px | 400 | `body` default |
| Controls / tables | 13px | 400 | Buttons, inputs and cells |
| Help text | 12px | 400 | With `text-subtle` |

Headings use `letter-spacing: -0.018em` and `text-wrap: balance`; paragraphs
use `text-wrap: pretty`.

Numbers use `tabular-nums` everywhere. `th`, `td`, `code`, `kbd`, `pre` and
elements carrying `[data-numeric]` receive it automatically. Values in this
product are compared with other values, so misaligned digits create reading
errors.

`font-feature-settings: 'cv11', 'ss01'` enables single-story `a` and straight
`l` so `1`, `l` and `I` are easier to distinguish.

## 6. Spacing and layout

Use the 4 px Tailwind scale. Common values are `gap-1.5` (6), `gap-2` (8),
`gap-3` (12), `gap-4` (16) and `gap-6` (24).

- Navigation height: `--nav-h` = 56 px, one line.
- Content width: `--shell-max` = 1440 px.
- Control heights: `sm` 28 px, `md` 32 px by default, `lg` 36 px.

Use grid instead of `flex-wrap` for list rows. A repeated piece of information
must begin at the same x position across rows. For example,
[`pages/Workspaces.tsx`](pages/Workspaces.tsx) uses
`grid grid-cols-1 items-center gap-x-4 gap-y-2 px-4 py-3` and
`md:grid-cols-[minmax(0,1fr)_15rem_8.5rem_9.5rem]`.

On mobile the layout becomes one column. Keep column widths stable and give
buttons a fixed width such as `w-[6.25rem]` so row edges remain aligned.

## 7. Component inventory

### 7.1 Primitives (`components/ui/`)

| File | Exports | Notes |
| --- | --- | --- |
| `Button.tsx` | `Button`, `IconButton` | Five variants, three sizes, loading state |
| `Input.tsx` | `Input`, `Textarea`, `ReadonlyValue` | Shares `controlClasses` |
| `Select.tsx` | `Select` | Radix Select; reads `Field` context |
| `Checkbox.tsx` | `Checkbox` | Radix Checkbox |
| `Field.tsx` | `Field`, `useField`, `useOptionalField`, `controlClasses` | Associates labels, errors and help |
| `Panel.tsx` | `Panel`, `PanelHeader` | Surface, `--r-md` and hairline |
| `Dialog.tsx` | `Dialog`, `ConfirmDialog` | Four sizes; replaces `window.confirm` |
| `Menu.tsx` | Menu primitives | Radix DropdownMenu |
| `Toast.tsx` | `ToastProvider`, `useToast` | Replaces `window.alert` |
| `Tooltip.tsx` | `TooltipProvider`, `Tooltip` | Required for icon-only buttons |
| `Badge.tsx` | `Badge`, `Identifier` | Mono identifiers for servers and databases |
| `DataGrid.tsx` | `DataGrid` | Result table |
| `EmptyState.tsx` | `EmptyState` | Icon, title, description and action |
| `Skeleton.tsx` | `Skeleton`, `SkeletonRows` | Loading placeholders |
| `Spinner.tsx` | `Spinner` | Buttons and inline rows only |
| `Kbd.tsx` | `Kbd` | Shortcut display |
| `Picker.tsx` | `Picker` | Searchable server/database list |
| `SegmentedControl.tsx` | `SegmentedControl` | `role="group"` and `aria-pressed` |

### 7.2 Button variants

```text
primary     bg-primary text-primary-fg          the page's main action
secondary   bg-surface + border-control-line    default action
ghost       transparent, bg-hover on hover      toolbars and icon neighbors
danger      transparent + border-danger-line    destructive action
quiet       underlined link appearance          inline secondary action
```

An individual screen may have only one `primary` button. If two actions have
equal importance, make both secondary.

The `danger` variant is outlined rather than filled. The confirmation dialog
communicates the destructive nature of the action.

### 7.3 Product components (`components/app/`)

| File | Responsibility |
| --- | --- |
| `AppShell.tsx` | 56 px navigation, skip link, theme and account menus, palette trigger |
| `AuthLayout.tsx` | Two-column login and registration layout |
| `BrandMark.tsx` | Geometric SVG brand mark |
| `CodeEditor.tsx` | CodeMirror 6 with token theme and dialect support |
| `CommandPalette.tsx` | ⌘K palette grouped by Git, actions, workspaces, appearance and account |
| `ResultPanel.tsx` | Result states and export menu |
| `SplitPane.tsx` | Drag or keyboard resizing, persistent ratio, vertical stack below `lg` |
| `admin/*.tsx` | Approvals, review dialog, masking, credentials and user activation tabs |

## 8. State patterns

Every data surface has four states, and all four must be designed:

| State | Display |
| --- | --- |
| Loading | `SkeletonRows` or `Skeleton`; never only a centered spinner |
| Empty | `EmptyState`: what it is, why it is empty and the next step |
| Error | Inline message plus retry action; a toast alone is insufficient |
| Full | The content |

`errorMessage(error)` in `api.ts` turns any thrown value into one user-facing
sentence. Do not render a raw `Error.message` directly.

Loading skeletons should follow the real layout so content does not jump when
loading completes.

## 9. Data table rules

[`components/ui/DataGrid.tsx`](components/ui/DataGrid.tsx) renders 200 rows at
a time and reveals more on demand. New results reset the counter with
`useEffect(() => setVisible(PAGE), [rows])`.

Numeric columns are right-aligned and mono, detected by `isNumericColumn()`.
Masked columns are marked in their headers. The marker is derived only from
the response's `masked_columns`, never from the requested masking set. A
database administrator may intentionally bypass masking, and the badge must
then be absent.

`NULL`, empty text and real values are three different displays. `formatCell()`
preserves that distinction. Sticky headers use an opaque background. A
truncated result is stated explicitly in the table.

## 10. Accessibility contract

These rules are acceptance criteria, not optional polish:

1. Use one global `:focus-visible` indicator in `global.css`. Components must
   not remove it or replace it with a private ring.
2. Text contrast is 4.5:1; control borders and focus rings are 3:1.
   `npm run audit:contrast` checks 32 pairs in both themes, 64 checks total.
3. Every icon-only button has an `aria-label` and a `Tooltip`. Every form
   control is labelled through `Field`.
4. The complete flow works from the keyboard. Radix supplies focus handling
   for dialogs and menus; `SplitPane` responds to arrow keys.
5. `.skip-link` appears on the first tab and reaches the actual main content.
6. `prefers-reduced-motion` disables animation.
7. Use `role="group"` and `aria-pressed` for `SegmentedControl`; use
   `radiogroup` only when implementing roving focus.

## 11. Keyboard map

| Shortcut | Effect | Where |
| --- | --- | --- |
| `⌘K` / `Ctrl+K` | Toggle command palette | Everywhere, including text fields |
| `⌘↵` / `Ctrl+↵` | Run query | Studio and RunWorkspace |
| `⌘S` / `Ctrl+S` | Save workspace | Studio |
| `Esc` | Close current layer | Dialog, menu and palette |

CodeMirror binds `Mod-Enter` in its own keymap. The window-level
`useHotkey('mod+enter', ...)` must not set `allowInEditable`, or the query will
run twice.

## 12. Avoid generic AI styling

The following patterns do not belong in this codebase:

| Pattern | Reason |
| --- | --- |
| Gradient background, glow or blur blob | Adds no meaning and consumes the chroma budget |
| Purple/indigo-to-pink brand gradient | State colors carry product meaning |
| `uppercase tracking-[0.3em]` micro-labels | Reduces readability without adding information |
| Mixed radii such as `rounded-3xl` and `rounded-lg` | The radius scale is fixed in section 4.5 |
| Decorative colored dots or gradients | Color is reserved for state |
| Fake technical words such as “initialize” or “purge” | Use the concrete action users understand |
| New z-index values | Add a `--z-*` token |
| CDN scripts, fonts or styles | The product must work on a closed network |
| Emoji icons or mixed icon libraries | Use `@phosphor-icons/react` consistently |

## 13. Product language

The interface is entirely in English. Text lives in the components because the
product currently has one supported language; do not introduce a translation
observer or runtime dictionary for a single-language change.

Workspace states have one source in `lib/workspace-status.ts`:

| Backend value | Label | Tone |
| --- | --- | --- |
| `draft` | Draft | neutral |
| `pending_approval` | Pending approval | warning |
| `approved_and_executed` | Approved | success |
| `approved_with_results` | Ready to run | success |
| `rejected` | Rejected | danger |

Each state has a `hint` that explains what the user can do. New screens read
the label, tone and hint from that source instead of defining their own map.

Writing rules:

- Buttons use verbs: “Save”, “Run”, “Approve”.
- An error says what happened and what the user can do next.
- Prefer “Running query” to inflated technical language such as “Initializing
  the query execution engine”.

## 14. Backend contract

This section keeps the frontend aligned with the contract that actually runs.

### 14.1 Types mirror the API

[`types.ts`](types.ts) mirrors the backend Pydantic schemas with their exact
snake_case field names. Do not rename fields for presentation. Reshaping lives
in `lib/` beside the code that performs it.

### 14.2 Target databases use UUIDs

`servername` and `database_name` are display values only. Query execution,
masking-rule reads and workspace creation all require `db_uuid`. Picker values
are UUIDs and their labels are names.

If a workspace target is not among the user's permitted targets, leave the
target empty and report the problem. Silently falling back to another database
could run a query against the wrong production data.

### 14.3 Resolve execution results once

`SQLResponse` returns `{response_type, data, message, error, masked_columns}`.
`masked_columns` contains the names of columns actually masked in the response,
using the spelling from result rows. Row counts and truncation are encoded in
the English `message`.

[`lib/execution.ts`](lib/execution.ts) parses that message once and produces an
`ExecutionOutcome`. Screens must not search inside `message` themselves.

### 14.4 Error envelope

Service errors return `{success, error_code, message, error, trace_id}`. `ApiError`
exposes the `code` and `traceId` fields.

- Branch on `error_code`, not message text. Messages can change; codes are the
  historical data contract.
- `QUERY_REJECTED_BY_ANALYZER` is a pending state, not an execution failure.
- `QUERY_SYNTAX_ERROR` means the statement could not be parsed and no role
  decision was reached; no workspace is created.
- `trace_id` is the single support reference shown to the user.

### 14.5 Session refresh

The access cookie is short-lived (`ACCESS_TOKEN_EXPIRE_MINUTES`, 20 minutes by
default); the refresh cookie lasts longer. `services/api.ts` tries
`POST /api/refresh` once before redirecting and retries the original request
with the same body when refresh succeeds.

Refresh tokens are single-use. Concurrent 401 responses share one in-flight
refresh promise so that one request does not consume the token needed by the
next request. Login, registration and refresh itself remain outside this path.

The browser never reads the token. Cookies are `httponly`; refresh works only
through cookies.

### 14.6 Approval decisions are final and explained

Rejection requires a reason of 3–500 characters. The client validates this
early so the user does not lose input to a 422 response, while the server
remains authoritative.

The decision service writes the reason into the workspace description as
`Rejected by <administrator>: <reason>`. A stale list is refreshed after a
conflict; the decision itself is not silently repeated.

### 14.7 Known contract boundaries

| Boundary | Result |
| --- | --- |
| `PUT /api/workspaces/{id}` accepts only `query` and `status` | Name, description and target are not edited through that route |
| `GET /api/me` does not return email | The account menu shows username and role |
| `POST /api/workspaces` returns `{success, workspace_id}` | The created record is read separately |
| `POST /api/admin/associate_user` requires `user_id` | Platform user activation and database role assignment remain separate scopes |
| `GET /api/admin/audit_log` exists without a UI | Audit records are read through the API |

`scripts/api-contract-audit.mjs` compares every call in `services/api.ts` with
the FastAPI routes and lists backend-only routes for information. Run it after
adding or changing an endpoint. It checks paths and methods, not request body
fields; read the relevant Pydantic schema for body changes.

## 15. Hard technical constraints

1. No CDN at runtime. The application queries production databases and must
   work on a closed network; fonts, styles and scripts are bundled.
2. Apply the theme before the first paint so users do not see a white flash.
3. TypeScript keeps strict checks such as `noFallthroughCasesInSwitch`; do not
   silence errors with `any`.
4. Heavy modules load lazily: Studio, RunWorkspace and Admin use `React.lazy`,
   and `xlsx` uses dynamic `import()`. Keep the first load close to 150 kB
   gzip unless a larger size is justified.
5. Routes remain `/`, `/login`, `/register`, `/editor`, `/editor/:id`,
   `/execute/:id` and `/admin` through `HashRouter`.
6. Components call the API only through the `api` object in `services/api.ts`;
   they do not call `fetch` directly.

## 16. Adding a new thing

Follow this order:

1. Reuse an existing primitive or add a variant before creating a new pattern.
2. Use design tokens. If a token is missing, add it to `tokens.css` and wire it
   into the `@theme inline` block in `global.css`.
3. Design loading, empty, error and full states.
4. Test with the keyboard: tab order, focus visibility and Escape behavior.
5. Check both themes.
6. Validate with `npm run typecheck`, `npm run build` and the relevant audits.

There is no committed frontend test command. Do not invent a passing test
result; the build, audits and browser inspection are the current validation
surface.

## 17. File map

```text
frontend/
├── README.md                  setup, commands and architecture summary
├── index.html                 theme preloader, favicon and noscript message
├── App.tsx                    provider chain, routes and guards
├── types.ts                   TypeScript form of the backend contract
├── styles/
│   ├── tokens.css             single color and scale source
│   └── global.css             Tailwind binding, base, components and utilities
├── lib/
│   ├── theme.tsx              theme preference and resolution
│   ├── workspaces.tsx         shared workspace cache
│   ├── workspace-status.ts    state dictionary
│   ├── targets.ts             db_uuid to server/database resolution
│   ├── execution.ts           SQLResponse to ExecutionOutcome adapter
│   ├── format.ts              number, size, duration and cell formatting
│   └── export.ts              xlsx and csv export
├── components/
│   ├── ui/                    reusable primitives
│   └── app/                   product components and admin flows
└── scripts/
    ├── contrast-audit.mjs     WCAG contrast gate
    └── api-contract-audit.mjs frontend/backend endpoint gate
```

## 18. Quick reference for the next session

For a change, start with the relevant one of these four files:

1. Color or scale: `styles/tokens.css`
2. Control appearance: the related file in `components/ui/`
3. Screen composition: the related file in `pages/`
4. Endpoint contract: `services/api.ts` and `types.ts`

Remember the core rule: color carries meaning. If a new color does not mark a
state, it should be gray.
