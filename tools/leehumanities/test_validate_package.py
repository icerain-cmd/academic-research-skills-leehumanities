"""Packaging regressions: copied plugins must not depend on the parent checkout."""
import json
import tempfile
import unittest
from pathlib import Path

from validate_package import AGENTS, COMMANDS, REFERENCE_NAMES, PLUGIN_RELATIVE, validate_repo


class PackageValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.plugin = self.repo / PLUGIN_RELATIVE
        self.write(".claude-plugin/marketplace.json", json.dumps({
            "name": "leehumanities", "owner": {"name": "Example"},
            "plugins": [{"name": "leehumanities-research", "source": "./plugins/leehumanities-research", "version": "1.0.0"}],
        }))
        self.put(".claude-plugin/plugin.json", json.dumps({
            "name": "leehumanities-research", "version": "1.0.0", "license": "CC-BY-NC-4.0",
            "author": {"name": "Example"}, "description": "Fixture only",
        }))
        self.put("LICENSE", "CC BY-NC 4.0 fixture")
        self.put("NOTICE.md", "Derived from https://github.com/Imbad0202/academic-research-skills under CC BY-NC 4.0.")
        self.put("scripts/research_audit.py", "# Fixture only\n")
        self.put("skills/humanities-research/SKILL.md", "---\nname: humanities-research\ndescription: Example\n---\n[Rules](references/humanities-constitution.md)\n")
        for stem in REFERENCE_NAMES:
            self.put(f"skills/humanities-research/references/{stem}.md", "# Fixture\n")
        for stem in AGENTS:
            self.put(f"agents/{stem}.md", f"---\nname: {stem}\ndescription: Example\nmodel: inherit\n---\n")
        for stem in COMMANDS:
            self.put(f"commands/{stem}.md", "---\ndescription: Example\n---\nRead ${CLAUDE_PLUGIN_ROOT}/skills/humanities-research/SKILL.md\n")

    def write(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def put(self, path, text):
        self.write(PLUGIN_RELATIVE / path, text)

    def test_self_contained_package_is_valid(self):
        result = validate_repo(self.repo)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["validation_kind"], "package_conformance_only")

    def test_manifest_cannot_escape_to_parent_checkout(self):
        path = self.plugin / ".claude-plugin/plugin.json"
        value = json.loads(path.read_text())
        value["skills"] = ["./../../academic-paper"]
        path.write_text(json.dumps(value))
        self.assertFalse(validate_repo(self.repo)["ok"])

    def test_broken_markdown_reference_is_rejected(self):
        self.put("skills/humanities-research/SKILL.md", "---\nname: humanities-research\ndescription: Example\n---\n[Missing](references/missing.md)\n")
        errors = validate_repo(self.repo)["errors"]
        self.assertTrue(any("broken local link" in error for error in errors), errors)

    def test_existing_outside_file_does_not_satisfy_bundling(self):
        self.write("shared.md", "Outside plugin")
        self.put("commands/review.md", "---\ndescription: Example\n---\n[Shared](../../../shared.md)\n")
        errors = validate_repo(self.repo)["errors"]
        self.assertTrue(any("link escapes plugin" in error for error in errors), errors)

    def test_missing_real_agent_is_rejected(self):
        (self.plugin / "agents/lh-source-verifier.md").unlink()
        self.assertFalse(validate_repo(self.repo)["ok"])

    def test_version_mismatch_is_rejected(self):
        path = self.plugin / ".claude-plugin/plugin.json"
        value = json.loads(path.read_text())
        value["version"] = "1.1.0"
        path.write_text(json.dumps(value))
        self.assertFalse(validate_repo(self.repo)["ok"])

    def test_symlink_dependency_is_rejected(self):
        outside = self.repo / "outside.md"
        outside.write_text("outside")
        link = self.plugin / "linked.md"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Creating symlinks is not permitted on this runner")
        errors = validate_repo(self.repo)["errors"]
        self.assertTrue(any("symlinks" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
