# Mini-Spec: Source-map dependency security remediation

## 1. Spec card

- Feature: Resolve inherited frontend build dependency advisory
- Status: Implemented
- Version: 2026-10-07
- Date: 2026-10-07
- Owner: WebQuery maintainer

## 2. Purpose and success signal

The fresh npm audit reports GHSA-68fv-2mgg-jv7q / CVE-2026-93749 against inherited
`source-map-js@1.2.1`, a Vite/PostCSS/Tailwind build dependency. Update only its
locked patch release and prove malformed source maps are rejected. This does
not claim an exploit against WebQuery's browser-facing runtime.

## 3. Scope / exclusions

Update the transitive lock entry to 1.2.2, add a regression check and keep the
existing dependency audit blocking. No framework/major upgrades, new runtime
dependency, SQL/API behavior or security-policy redesign; no ADR needed for
this routine compatible patch.

## 4. Contract

The upstream dependency must reject excessive indexed-map offsets, including
nested offsets, without flattening attacker-controlled maps. Normal source-map
positions must still resolve. Existing dependency ranges already permit 1.2.2.

## 5. Business rules

- BR-01: Change only the affected resolution/version/integrity entry, using
  official registry metadata; preserve all unrelated lockfile resolutions.
- BR-02: Regression fixtures exercise constructor validation, not unbounded
  flattening, so testing the vulnerable baseline does not cause resource exhaustion.

## 6. Acceptance criteria

- AC-01: `npm ci` resolves source-map-js 1.2.2 from the committed lockfile.
- AC-02: Excessive direct/nested offsets are rejected; valid mappings resolve.
- AC-03: Typecheck, export/API/contrast checks and production build still pass.
- AC-04: Fresh `npm audit --audit-level=high` passes after the patch.

## 7. Technical and security constraints

Keep the root public baseline's provenance and list this deliberate dependency
exception. Never suppress the advisory or turn the audit informational to get CI green.

## 8. Open questions

None. This is a compatible remediation within the requested optimization scope.

## 9. Done check

- [x] Regression failure on inherited dependency, then passing patched result
- [x] Lockfile delta and frontend checks verified; handoff updated

AC-01: clean `npm ci` and lockfile comparison. AC-02:
`npm run verify:source-map-security`, failing on 1.2.1 and passing on 1.2.2.
AC-03: all existing frontend checks and build passed after installation.
AC-04: fresh npm audit reports zero vulnerabilities. This targeted dependency
regression script does not introduce a frontend behavioral test framework.

References: [upstream fix](https://github.com/7rulnik/source-map-js/pull/79),
[release 1.2.2](https://github.com/7rulnik/source-map-js/releases/tag/v1.2.2),
[advisory](https://github.com/advisories/GHSA-68fv-2mgg-jv7q).
