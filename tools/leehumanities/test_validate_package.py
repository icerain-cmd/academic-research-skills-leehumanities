"""Packaging regressions: copied plugins must not depend on the parent checkout."""
import json
import tempfile
import unittest
from pathlib import Path

from validate_package import (
    AGENTS, BASE_READ_TOOLS, COMMANDS, OPTIONAL_READ_MCP_TOOLS, REFERENCE_NAMES,
    PLUGIN_RELATIVE, WEB_READ_TOOLS, validate_repo,
)


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
            self.agent(stem, BASE_READ_TOOLS if stem == "lh-style-editor" else WEB_READ_TOOLS)
        for stem in COMMANDS:
            self.put(f"commands/{stem}.md", "---\ndescription: Example\n---\nRead ${CLAUDE_PLUGIN_ROOT}/skills/humanities-research/SKILL.md\n")

    def write(self, path, text):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def put(self, path, text):
        self.write(PLUGIN_RELATIVE / path, text)

    def agent(self, stem, tools=None):
        declaration = "" if tools is None else "tools: " + ", ".join(sorted(tools)) + "\n"
        self.put(f"agents/{stem}.md", f"---\nname: {stem}\ndescription: Example\n{declaration}model: inherit\n---\n")

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

    def test_optional_retrieval_tools_are_valid_without_mcp_configuration(self):
        for stem in ("lh-source-verifier", "lh-theorist"):
            self.agent(stem, WEB_READ_TOOLS | {"ToolSearch"} | OPTIONAL_READ_MCP_TOOLS)
        self.assertFalse((self.plugin / ".mcp.json").exists())
        result = validate_repo(self.repo)
        self.assertTrue(result["ok"], result["errors"])

    def test_builtin_fallback_is_valid_without_optional_lookup_tools(self):
        for stem in ("lh-source-verifier", "lh-theorist"):
            self.agent(stem, WEB_READ_TOOLS)
        result = validate_repo(self.repo)
        self.assertTrue(result["ok"], result["errors"])

    def test_mcp_wildcards_are_rejected(self):
        for tool in ("*", "mcp__*", "mcp__jj-academic-korea__*", "mcp__jj-filesystem__*"):
            with self.subTest(tool=tool):
                self.agent("lh-source-verifier", WEB_READ_TOOLS | {tool})
                errors = validate_repo(self.repo)["errors"]
                self.assertTrue(any("read-only allowlist" in error and tool in error for error in errors), errors)

    def test_write_exec_and_unapproved_mcp_tools_are_rejected(self):
        # MCP mutation names are negative fixtures, not claims about a server's inventory.
        prohibited = {"Write", "Edit", "Bash", "PowerShell", "NotebookEdit", "Agent",
                      "mcp__jj-filesystem__write_file", "mcp__jj-filesystem__delete_file",
                      "mcp__asr__save_record"}
        for stem in AGENTS:
            for tool in prohibited:
                with self.subTest(agent=stem, tool=tool):
                    self.agent(stem, BASE_READ_TOOLS | {tool})
                    errors = validate_repo(self.repo)["errors"]
                    self.assertTrue(any(stem in error and "read-only allowlist" in error and tool in error for error in errors), errors)
            self.agent(stem, BASE_READ_TOOLS)

    def test_optional_lookup_tools_are_not_granted_to_other_roles(self):
        for stem in ("lh-argument-critic", "lh-style-editor"):
            for tool in ("ToolSearch", "mcp__semantic-scholar__get_paper"):
                with self.subTest(agent=stem, tool=tool):
                    self.agent(stem, BASE_READ_TOOLS | {tool})
                    errors = validate_repo(self.repo)["errors"]
                    self.assertTrue(any(stem in error and "read-only allowlist" in error for error in errors), errors)
            self.agent(stem, BASE_READ_TOOLS)

    def test_implicit_tool_inheritance_is_rejected(self):
        for tools in (None, set()):
            with self.subTest(tools=tools):
                self.agent("lh-source-verifier", tools)
                errors = validate_repo(self.repo)["errors"]
                self.assertTrue(any("explicit nonempty tools allowlist" in error for error in errors), errors)

    def test_mcp_only_role_is_rejected_without_builtin_fallback(self):
        self.agent("lh-source-verifier", {"ToolSearch", "mcp__semantic-scholar__get_paper"})
        errors = validate_repo(self.repo)["errors"]
        self.assertTrue(any("missing built-in read tools" in error for error in errors), errors)

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
