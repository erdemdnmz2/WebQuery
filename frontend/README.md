# WebQuery frontend

React + TypeScript + Vite. Read [DESIGN.md](DESIGN.md) before UI changes; shared
tokens and UI primitives define appearance, accessibility and interaction.

```bash
npm ci
npm run dev
```

The development server uses port **3000** and proxies `/api` to
`http://localhost:8080`. Optional `.env.example` documents `VITE_API_TARGET`.
Do not put credentials in frontend configuration. The backend requires its own
metadata database, Redis, secrets and first OWNER; see
[development setup](../docs/development.md).

```bash
npm run typecheck
npm run verify:export
npm run verify:source-map-security
npm run audit:api
npm run audit:contrast
npm run build
```

There is no frontend behavioral test command yet. Typecheck/static audits/build
do not prove query cancellation, session retry or governance interactions.
The gaps are in the [implementation plan](../docs/implementation-plan.md).

Source is organized directly under `pages/`, `components/`, `lib/`, `services/`
and `styles/`, not `src/`. `package.json` has `private: true` to prevent accidental
npm publication; that does not make the GitHub repository private.
