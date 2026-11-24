# Upstream and fork maintenance

This is a GitHub fork of [Imbad0202/academic-research-skills](https://github.com/Imbad0202/academic-research-skills), by Cheng-I Wu.

The initial Lee Humanities edition is based on upstream **3.24.4**, commit **83c23082f3613b1b105f5a93642efda2cca628b2** (2026-11-23).

## Distribution boundary

- Original research, paper, reviewer, pipeline, scripts and shared-contract directories remain available for attribution, inspection and deliberate future updates.
- The installable Lee Humanities plugin is self-contained at `plugins/leehumanities-research/`. Its original license and attribution travel with the plugin.
- The root marketplace lists this plugin as `leehumanities-research@leehumanities` so it can coexist with the original ARS plugin.
- The upstream root `.claude-plugin/plugin.json` still describes the original ARS package. For local loading of this edition use `claude --plugin-dir ./plugins/leehumanities-research`, not the repository root.
- Upstream maintenance workflows are retained unchanged and were not activated for this fork. An optional Ubuntu/Windows packaging and regression workflow example is provided in `tools/leehumanities/github-actions.example.yml`; it is not active GitHub CI in this release.
- The fork does not inherit claims about upstream evaluation results. Local schema checks, software tests, actual plugin loading and model behavior are reported separately.

## Updating deliberately

Add the upstream remote, fetch the desired release and inspect changes before merging. Do not overwrite the fork marketplace or local research data. Re-run the custom package validator, both local test suites and Claude Code's plugin validator. Compare the original license and notices. Record the new upstream commit, bump the custom plugin and marketplace version together, and publish a reviewed fork release.

Research corpora, manuscript drafts, evidence records and machine-specific locations belong outside this public repository. `.gitignore` is only a convenience, not a guarantee against accidentally staging private files. Review the staged file list before every publication.
