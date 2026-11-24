# Lee Humanities validation record

## 1.0.1 — 2026-11-24 (Asia/Seoul)

### Package and permission checks

- Linux package/installer suite: 22 tests passed, including seven new tests covering role tool boundaries and optional-MCP fallback.
- Windows package/installer suite: 22 tests completed, 21 passed and one skipped for unavailable symbolic-link capability.
- Package conformance: four agents, nine commands, matching `1.0.1` manifest versions, no errors.
- Native Claude Code `2.1.288` strict plugin and marketplace validation: no errors or warnings.
- The local corpus/evidence/drift implementation is unchanged from 1.0.0; its earlier 30-test results remain documented below. They were not repeated for this tool-permission update.

### Live role and tool checks

A real Claude Code run loaded the `1.0.1` candidate via `--plugin-dir` and separately dispatched all four namespaced roles with the same synthetic manuscript/source pair. The runtime reported `claude-sonnet-5-5`. Streamed tool events tied the source verifier's MCP calls to its own Agent invocation, rather than to the parent.

- The theorist identified a shift from the provisional definition of mutual revision to agreement and then to all interactions.
- The argument critic identified the unsupported move from agreeing answers to universal truth, the universalized conclusion and the claim of no errors.
- The source verifier compared the claimed quotation with section 2 of synthetic source A and identified the reversed negation; it reported the quotation as unsupported. It used native `Read` after the MCP path restriction below.
- The style editor proposed a sentence preserving the provisional definition.
- The fixture files' SHA-256 values were unchanged after the run. The live run ended successfully in 113.2 seconds. This is one synthetic diagnostic, not a benchmark of research accuracy or publication readiness.

The two public fixtures are in `plugins/leehumanities-research/tests/fixtures/runtime-manuscript.md` and `runtime-source-a.md`; runtime copies differed only in blank-line layout.

### Service and access findings

- `jj-filesystem` initialization and tool discovery succeeded in approximately 2.45 seconds. Fresh native Claude Code health checks also connected successfully. The earlier reported 30-second connection timeout did not recur; its cause was not established and no timeout/configuration change was made.
- Reading the synthetic fixture from the system temporary folder through `jj-filesystem` was denied because that folder was outside the server's existing allowed directories. This was a functioning access boundary, not a connection failure. The allowed directories were not broadened.
- The verifier directly called the RISS manual-search-URL generator successfully. Its result was `NEEDS_MANUAL_CHECK`: no RISS search or bibliography verification occurred.
- Semantic Scholar's MCP server connected, but the verifier's `get_paper` call and one retry returned `Working outside of request context`. This external tool failure is unresolved; MCP connection success must not be reported as retrieval success.
- A separate direct request to Semantic Scholar's official Graph REST endpoint returned HTTP 200 with title/year/URL for the public test DOI. This was a distinct metadata-only channel, not a successful MCP call or full-text reading.
- The inspected `.in_use` marker contained a PID and process-start marker; its PID matched a live Claude process. It was left unchanged. Current plugin documentation describes cache lifecycle, while the exact lease interpretation is corroborated by implementation reports rather than a documented public marker schema.

### Allowed-directory and retrieval positive control

A second bounded run dispatched the source verifier once. It completed in 36.2 seconds, and streamed events attributed all three operations below to that subagent:

- `jj-filesystem.read_text_file` successfully read the first eight lines of an explicitly scoped program-source file inside an already-allowed directory. Together with the denied temporary-folder read above, this confirmed both permitted access and the existing directory boundary.
- `jj-academic-korea.kci_search_articles` actually searched the public topic `사이버문학`; the response reported 17 total records and returned 10. This was bibliography retrieval, not original-paper verification. Some abstract fields were `[object Object]`; that formatting defect remains in the existing MCP service, and the plugin now explicitly treats such placeholders as unreadable text rather than accessed abstracts.
- The verifier's `WebFetch` call to Semantic Scholar's official Graph REST URL successfully retrieved the public test paper's title, year and source URL. It preserved the earlier MCP failure and did not claim full-text access.

The direct MCP permission defect is corrected in the candidate. Final published-package installation verification will be recorded after the update.

## 1.0.0 baseline

Date: 2026-11-24 (Asia/Seoul). Upstream baseline: `83c23082f3613b1b105f5a93642efda2cca628b2`.

## Software checks

- Self-contained package validator: PASS; four agents and nine commands; manifest versions match; referenced local resources exist inside the installed plugin.
- Installer and package regression suite: 15 tests PASS.
- Local corpus/evidence/drift regression suite: 30 tests PASS, including pre-descent Windows reparse-directory pruning regressions.
- Git whitespace/diff check: PASS.
- Tests use synthetic fixtures and temporary directories. No private research corpus is included or required.
- GitHub Actions automation is not activated for this release. The publishing credential lacked workflow-write scope, so upstream workflows were left unchanged and an optional example was provided at `tools/leehumanities/github-actions.example.yml`. The software checks above were executed directly on Linux and the target Windows host; no GitHub CI success is claimed.

The record validator reports `semantic_verification_performed: false` and `source_retrieval_performed: false`. A conforming evidence declaration does not prove that an assessor actually read a source or that its interpretation is correct. The drift checker detects selected token changes, not semantic equivalence.

## Target host checks

Windows Claude Code **2.1.288** and Python **3.12** were identified on the target host.

- Installer/package suite: 15 tests completed, 14 passed and 1 skipped for unavailable symbolic-link capability.
- Local research-audit suite: 30 tests completed, 26 passed and 4 skipped for unavailable symbolic-link/FIFO capabilities. The two portable reparse-directory regression tests passed.
- A separate Windows smoke test created two real NTFS junctions: one to an external fixture directory and one back to the corpus root. Both were pruned before descent; the scan terminated with only the intended local file indexed and no read errors. A junction supplied as the source root was also rejected.
- Native `claude plugin validate --strict --json` accepted the standalone plugin and marketplace, with no errors or warnings.
- Claude's startup inventory from the local-plugin smoke attempt registered all four namespaced agents, all nine command entries and the `humanities-research` skill. This confirms component discovery, not execution by a model.
- A live review was attempted on two synthetic Markdown fixtures with the argument critic and source verifier requested. Claude returned `Failed to authenticate: OAuth session expired and could not be refreshed` before any role call. `claude auth status` subsequently reported `loggedIn: false`. Therefore live model dispatch and review quality are **not verified**. Sign in with `claude auth login` and repeat the review to test them.
- The package was published to `icerain-cmd/academic-research-skills-leehumanities` and installed from that GitHub source with `tools/leehumanities/install.py` at user scope. The installed plugin ID is `leehumanities-research@leehumanities`, version `1.0.0`; the installer verified `enabled: true` and no load errors.
- `claude plugin details leehumanities-research@leehumanities` listed four agents and ten skill entries (the nine command files plus the primary skill), with zero hooks, MCP servers or LSP servers. The installed plugin code corresponds to commit `1f1cd4754cd818167de1849074b2a2c5f98ba77b`; subsequent release-preparation changes are documentation only.

## Limits

No discipline-wide error rate, publication-readiness score or hallucination-elimination claim is made. Separate role dispatch uses the active Claude model unless the user independently configures otherwise. There is no external-model API integration or automatic connection to existing production research agents in this release.
