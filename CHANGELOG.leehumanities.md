# Lee Humanities changes

## 1.0.1 — 2026-11-24

- Allowed the theorist and source verifier to discover and call explicitly listed read-only scholarly/file MCP tools from already-configured servers; retained narrower critic/style roles and a parent-provided-source fallback.
- Added package checks against write/execute tools, unknown MCP tool IDs and broad MCP wildcards in the role definitions.
- Made doctor distinguish configuration, connection, tool permissions, actual tool calls and source verification. Clarified that RISS query helpers do not perform a RISS search, and that a filesystem MCP failure does not establish failure of native file reads.
- Kept runtime `.in_use` bookkeeping separate from plugin-owned output and diagnoses.

## 1.0.0 — 2026-11-24

- Added a self-contained Claude Code plugin under `plugins/leehumanities-research` and a dedicated `leehumanities` marketplace.
- Added nine Korean-facing commands: plan, research, write, review, citations, revise, abstract, corpus and doctor.
- Replaced implicit role multiplication in the custom workflow with four explicit, separately dispatchable roles: conceptual theorist, argument critic, source verifier and Korean style editor. All inherit the user's active model by default.
- Added humanities drafting, conceptual genealogy, author terminology, counterargument and source-reading protocols without mandatory empirical-paper structures.
- Added separate bibliographic existence, reading scope, edition/translation and claim-support records, including legitimate sources without DOIs.
- Added Korean/English abstract instructions with claim-strength preservation and local revision drift reports.
- Added read-only corpus indexing, mechanical evidence-record validation, fixture-based regression tests, portable installers and an optional cross-platform CI workflow example.
- Preserved upstream attribution and CC BY-NC 4.0 licensing. No source manuscripts, credentials or live research data are distributed.
