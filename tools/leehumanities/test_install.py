"""Installer safety tests with a local fake CLI; no real configuration changes."""
import json
import unittest

from install import InstallError, PLUGIN_ID, SOURCE, install


class FakeCLI:
    def __init__(self, *, markets=None, installed=None, modern=True, result_enabled=True, load_errors=None):
        self.markets = list(markets or [])
        self.installed = list(installed or [])
        self.modern = modern
        self.result_enabled = result_enabled
        self.load_errors = load_errors or []
        self.calls = []

    def run(self, args, *, check=True):
        self.calls.append(args[:])
        if args == ["--version"]:
            return "2.1.288 (Claude Code)"
        if "--help" in args:
            if args == ["plugin", "--help"]:
                return "Commands: install marketplace list update" if self.modern else "Unknown command"
            return "Options: --scope <scope> --json --help"
        if args == ["plugin", "marketplace", "list", "--json"]:
            return json.dumps(self.markets)
        if args == ["plugin", "list", "--json"]:
            return json.dumps(self.installed)
        if args[:3] == ["plugin", "marketplace", "add"]:
            self.markets.append({"name": "leehumanities", "source": "github", "repo": SOURCE})
            return json.dumps({"outcome": "ok", "command": "marketplace-add"})
        if args[:3] == ["plugin", "marketplace", "update"]:
            return "Updated leehumanities"
        if args[:2] in (["plugin", "install"], ["plugin", "update"]):
            self.installed = [row for row in self.installed if row.get("id") != PLUGIN_ID]
            self.installed.append({"id": PLUGIN_ID, "scope": "user", "version": "1.0.0", "installPath": "fixture", "enabled": self.result_enabled, "errors": self.load_errors})
            return json.dumps({"outcome": "ok", "command": args[1]})
        raise AssertionError(f"Unexpected command: {args}")

    def mutations(self):
        return [args for args in self.calls if "--help" not in args and (args[:2] in (["plugin", "install"], ["plugin", "update"], ["plugin", "enable"], ["plugin", "uninstall"]) or args[:3] in (["plugin", "marketplace", "add"], ["plugin", "marketplace", "update"], ["plugin", "marketplace", "remove"]))]


class InstallerTests(unittest.TestCase):
    def test_install_changes_only_target_at_user_scope(self):
        cli = FakeCLI()
        result = install(cli)
        self.assertEqual(result["status"], "INSTALLED")
        self.assertEqual(cli.mutations(), [
            ["plugin", "marketplace", "add", SOURCE, "--scope", "user", "--json"],
            ["plugin", "install", PLUGIN_ID, "--scope", "user", "--json"],
        ])

    def test_collision_fails_before_any_mutation(self):
        cli = FakeCLI(markets=[{"name": "leehumanities", "source": "github", "repo": "someone/else"}])
        with self.assertRaisesRegex(InstallError, "different source"):
            install(cli)
        self.assertEqual(cli.mutations(), [])

    def test_old_cli_fails_before_any_mutation(self):
        cli = FakeCLI(modern=False)
        with self.assertRaises(InstallError):
            install(cli)
        self.assertEqual(cli.mutations(), [])

    def test_dry_run_has_no_mutations(self):
        cli = FakeCLI()
        result = install(cli, dry_run=True)
        self.assertEqual(result["status"], "DRY_RUN")
        self.assertEqual(len(result["commands"]), 2)
        self.assertEqual(cli.mutations(), [])

    def test_existing_matching_marketplace_is_not_replaced(self):
        cli = FakeCLI(markets=[{"name": "leehumanities", "source": {"source": "github", "repo": SOURCE}}])
        install(cli)
        self.assertEqual(len(cli.mutations()), 1)
        self.assertEqual(cli.mutations()[0][1], "install")

    def test_disabled_install_is_not_reported_usable(self):
        cli = FakeCLI(result_enabled=False)
        with self.assertRaisesRegex(InstallError, "disabled"):
            install(cli)
        self.assertFalse(any("enable" in args for args in cli.mutations()))

    def test_load_error_is_not_reported_successful(self):
        cli = FakeCLI(load_errors=["Missing skill reference"])
        with self.assertRaisesRegex(InstallError, "load errors"):
            install(cli)

    def test_explicit_update_targets_only_named_plugin(self):
        cli = FakeCLI(markets=[{"name": "leehumanities", "source": "github", "repo": SOURCE}], installed=[{"id": PLUGIN_ID, "scope": "user"}])
        install(cli, update=True)
        self.assertEqual(cli.mutations(), [
            ["plugin", "marketplace", "update", "leehumanities"],
            ["plugin", "update", PLUGIN_ID, "--scope", "user", "--json"],
        ])


if __name__ == "__main__":
    unittest.main()
