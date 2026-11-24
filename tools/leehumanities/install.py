#!/usr/bin/env python3
"""Install only leehumanities-research through Claude Code's public CLI.

No settings files are edited directly. No model, API key, or research document
is used. Existing marketplace-name collisions fail without mutation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from validate_package import PLUGIN_NAME, MARKETPLACE_NAME, validate_repo

SOURCE = "icerain-cmd/academic-research-skills-leehumanities"
PLUGIN_ID = f"{PLUGIN_NAME}@{MARKETPLACE_NAME}"


class InstallError(RuntimeError):
    pass


class ClaudeCLI:
    def __init__(self, executable: str):
        self.executable = executable

    def run(self, args: list[str], *, check: bool = True) -> str:
        try:
            result = subprocess.run(
                [self.executable, *args], text=True, encoding="utf-8", errors="replace",
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=180, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise InstallError(f"Claude command did not complete: {exc}") from exc
        if check and result.returncode:
            message = (result.stderr or result.stdout).strip()
            raise InstallError(f"claude {' '.join(args)} failed ({result.returncode}): {message}")
        return result.stdout + ("\n" + result.stderr if result.stderr else "")


def parse_json_output(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        # Newer mutation commands emit one final JSON line after progress text.
        for line in reversed(text.splitlines()):
            try:
                return json.loads(line)
            except ValueError:
                continue
    raise InstallError("Claude did not return readable JSON; nothing further was changed.")


def rows(value, key: str) -> list[dict]:
    if isinstance(value, dict) and key in value:
        value = value[key]
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise InstallError(f"Unsupported Claude {key} JSON shape; refusing to infer installed state.")
    return value


def same_marketplace_source(row: dict, requested: str) -> bool:
    source = row.get("source")
    detail = source if isinstance(source, dict) else row
    source_type = detail.get("source") if isinstance(source, dict) else source
    if requested == SOURCE:
        if source_type == "github":
            return detail.get("repo", "").lower() == SOURCE.lower()
        if source_type == "git":
            value = str(detail.get("url", "")).rstrip("/")
            return value.removesuffix(".git").lower() == f"https://github.com/{SOURCE}".lower()
        return False
    if source_type not in {"directory", "file"}:
        return False
    try:
        return os.path.normcase(str(Path(str(detail.get("path", ""))).resolve())) == os.path.normcase(str(Path(requested).resolve()))
    except OSError:
        return False


def supports(help_text: str, flag: str) -> bool:
    return bool(re.search(r"(?<![A-Za-z0-9-])" + re.escape(flag) + r"(?![A-Za-z0-9-])", help_text))


def install(cli: ClaudeCLI, *, source: str = SOURCE, dry_run: bool = False, update: bool = False) -> dict:
    version = cli.run(["--version"]).strip()
    plugin_help = cli.run(["plugin", "--help"])
    if "marketplace" not in plugin_help or "install" not in plugin_help:
        raise InstallError("This Claude Code version does not advertise plugin installation.")
    install_help = cli.run(["plugin", "install", "--help"])
    add_help = cli.run(["plugin", "marketplace", "add", "--help"])
    market_list_help = cli.run(["plugin", "marketplace", "list", "--help"])
    plugin_list_help = cli.run(["plugin", "list", "--help"])
    if not supports(install_help, "--scope"):
        raise InstallError("This Claude Code version cannot explicitly install at user scope.")
    if not supports(market_list_help, "--json") or not supports(plugin_list_help, "--json"):
        raise InstallError("This installer requires JSON marketplace/plugin listing to verify the result safely.")
    markets = rows(parse_json_output(cli.run(["plugin", "marketplace", "list", "--json"])), "marketplaces")
    matching = [row for row in markets if row.get("name") == MARKETPLACE_NAME]
    if len(matching) > 1:
        raise InstallError("Multiple leehumanities marketplaces are registered; resolve the ambiguity in Claude Code first.")
    if matching and not same_marketplace_source(matching[0], source):
        raise InstallError("A different source already uses marketplace name 'leehumanities'. It was left unchanged.")
    commands: list[list[str]] = []
    if not matching:
        command = ["plugin", "marketplace", "add", source]
        if supports(add_help, "--scope"):
            command += ["--scope", "user"]
        if supports(add_help, "--json"):
            command += ["--json"]
        commands.append(command)
    elif update:
        cli.run(["plugin", "marketplace", "update", "--help"])
        commands.append(["plugin", "marketplace", "update", MARKETPLACE_NAME])
    existing = rows(parse_json_output(cli.run(["plugin", "list", "--json"])), "installed")
    installed_user = any(row.get("id") == PLUGIN_ID and row.get("scope") == "user" for row in existing)
    if update and installed_user:
        update_help = cli.run(["plugin", "update", "--help"])
        if not supports(update_help, "--scope"):
            raise InstallError("This Claude Code version cannot explicitly update at user scope.")
        command = ["plugin", "update", PLUGIN_ID, "--scope", "user"]
        if supports(update_help, "--json"):
            command.append("--json")
    else:
        command = ["plugin", "install", PLUGIN_ID, "--scope", "user"]
        if supports(install_help, "--json"):
            command.append("--json")
    commands.append(command)
    if dry_run:
        return {"status": "DRY_RUN", "claude_version": version, "commands": commands, "changes_made": False}
    for command in commands:
        output = cli.run(command)
        if "--json" in command:
            result = parse_json_output(output)
            if not isinstance(result, dict) or result.get("outcome") != "ok":
                raise InstallError(f"Claude did not confirm command success: {output.strip()}")
        else:
            print(output.strip())
    actual = rows(parse_json_output(cli.run(["plugin", "list", "--json"])), "installed")
    matches = [row for row in actual if row.get("id") == PLUGIN_ID and row.get("scope") == "user"]
    if len(matches) != 1:
        raise InstallError("Installation command completed, but the expected user-scope install was not verified.")
    row = matches[0]
    if row.get("errors"):
        raise InstallError("Claude recorded plugin load errors: " + "; ".join(map(str, row["errors"])))
    if row.get("enabled") is not True:
        raise InstallError("The plugin is installed but disabled by current settings. Existing settings were preserved.")
    return {
        "status": "INSTALLED", "plugin_id": PLUGIN_ID, "scope": "user",
        "plugin_version": row.get("version"), "install_path": row.get("installPath"),
        "claude_version": version, "enabled": True, "load_errors": [],
        "next_command": "/leehumanities-research:plan",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Inspect help/state and show intended commands without changing anything")
    parser.add_argument("--update", action="store_true", help="Refresh this marketplace and update this plugin only")
    parser.add_argument("--source", default=SOURCE, help="Default GitHub repository, or an explicitly selected local checkout")
    parser.add_argument("--claude", help="Optional exact Claude executable path")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    try:
        package = validate_repo(repo)
        if not package["ok"]:
            raise InstallError("Package validation failed:\n" + "\n".join(package["errors"]))
        if args.source != SOURCE:
            source = Path(args.source).expanduser().resolve()
            if not source.is_dir():
                raise InstallError("--source must name the published GitHub repository or a local checkout directory.")
            source_validation = validate_repo(source)
            if not source_validation["ok"]:
                raise InstallError("The selected local marketplace failed package validation.")
            args.source = str(source)
        executable = args.claude or shutil.which("claude")
        if not executable:
            raise InstallError("Claude Code was not found on PATH. Install Claude Code before running this installer.")
        result = install(ClaudeCLI(executable), source=args.source, dry_run=args.dry_run, update=args.update)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["status"] == "INSTALLED":
            print("Open a new Claude Code session, or use /reload-plugins if your version supports it.")
        return 0
    except InstallError as exc:
        print(str(exc), file=sys.stderr)
        print("No legacy copying or settings replacement was attempted.", file=sys.stderr)
        plugin = repo / "plugins" / PLUGIN_NAME
        print(f'For a supported session-only fallback: claude --plugin-dir "{plugin}"', file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
