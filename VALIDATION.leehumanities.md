# Lee Humanities 1.0.0 validation record

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
- A live review was attempted on two synthetic Markdown fixtures with the argument critic and source verifier requested. Claude returned `Failed to authenticate: OAuth session expired and could not be refreshed` before any role call. `claude auth status` subsequently reported `loggedIn: false`. Therefore live model dispatch and review quality are **not verified**. Sign in with `claude auth login` and repeat the review to test them.
- Publication and installation inventory verification will be recorded after the published package is installed.

## Limits

No discipline-wide error rate, publication-readiness score or hallucination-elimination claim is made. Separate role dispatch uses the active Claude model unless the user independently configures otherwise. There is no external-model API integration or automatic connection to existing production research agents in this release.
