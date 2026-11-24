#!/usr/bin/env python3
"""Check this fork's self-contained Claude plugin without network or model calls.

This is a packaging/conformance check. It does not measure research quality or
replace `claude plugin validate` on the installed Claude Code version.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

PLUGIN_NAME = "leehumanities-research"
MARKETPLACE_NAME = "leehumanities"
PLUGIN_RELATIVE = Path("plugins") / PLUGIN_NAME
AGENTS = {"lh-theorist", "lh-argument-critic", "lh-source-verifier", "lh-style-editor"}
COMMANDS = {"plan", "research", "write", "review", "citations", "revise", "abstract", "corpus", "doctor"}
REFERENCE_NAMES = {
    "humanities-constitution", "workflow-and-artifacts", "corpus-and-sources",
    "citation-audit", "korean-bibliography", "review-and-revision",
    "abstracts-and-language", "concept-continuity",
}


def read_json(path: Path, errors: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(value, dict):
            raise ValueError("expected a JSON object")
        return value
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"{path.name}: {exc}")
        return {}


def contained(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError, RuntimeError):
        return False


def component_path(root: Path, raw: object, errors: list[str], label: str) -> Path | None:
    if not isinstance(raw, str) or not raw.startswith("./"):
        errors.append(f"{label}: component path must start with './'")
        return None
    if "\\" in raw or ".." in PurePosixPath(raw).parts:
        errors.append(f"{label}: path traversal or non-portable separator: {raw}")
        return None
    target = root / raw
    if not contained(root, target):
        errors.append(f"{label}: path escapes package: {raw}")
        return None
    if not target.exists():
        errors.append(f"{label}: missing path: {raw}")
        return None
    return target


def frontmatter(path: Path, errors: list[str]) -> dict[str, str]:
    """Parse the deliberately flat frontmatter used by this plugin.

    This is not a general YAML parser. Unsupported nested or ambiguous syntax
    fails explicitly rather than silently validating a different structure.
    """
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{path.name}: {exc}")
        return {}
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        errors.append(f"{path.name}: missing frontmatter")
        return {}
    try:
        end = lines.index("---", 1)
    except ValueError:
        errors.append(f"{path.name}: unclosed frontmatter")
        return {}
    result: dict[str, str] = {}
    block_key = None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1].isspace():
            if block_key is None:
                errors.append(f"{path.name}: nested frontmatter is unsupported by this validator")
            else:
                result[block_key] += " " + line.strip()
            continue
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9_-]*):\s*(.*)", line)
        if not match:
            errors.append(f"{path.name}: invalid flat frontmatter line")
            continue
        key, value = match.groups()
        if key in result:
            errors.append(f"{path.name}: duplicate frontmatter key {key}")
        block_key = key if value in {"|", ">", "|-", ">-"} else None
        if block_key:
            value = ""
        elif value[:1] in {"'", '"'}:
            if len(value) < 2 or value[-1] != value[0]:
                errors.append(f"{path.name}: unclosed quoted frontmatter value")
            else:
                value = value[1:-1]
        result[key] = value
    return result


def check_markdown_links(root: Path, path: Path, errors: list[str]) -> None:
    text = path.read_text(encoding="utf-8-sig")
    # Markdown links are authoritative file dependencies; inline example
    # filenames and paths to user-supplied papers are intentionally not inferred.
    for raw in re.findall(r"!?\[[^\]\n]*\]\(([^\)\n]+)\)", text):
        target_text = raw.strip().split(' "', 1)[0].strip("<>")
        parts = urlsplit(target_text)
        if not parts.path or parts.scheme in {"https", "http", "mailto"}:
            continue
        if parts.scheme:
            errors.append(f"{path.relative_to(root)}: unsupported local link scheme: {parts.scheme}")
            continue
        target = path.parent / unquote(parts.path)
        if not contained(root, target):
            errors.append(f"{path.relative_to(root)}: link escapes plugin: {target_text}")
        elif not target.exists():
            errors.append(f"{path.relative_to(root)}: broken local link: {target_text}")
    for raw in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([A-Za-z0-9_./-]+)", text):
        raw = raw.rstrip(".")
        target = root / raw
        if not contained(root, target):
            errors.append(f"{path.relative_to(root)}: plugin-root reference escapes package: {raw}")
        elif not target.exists():
            errors.append(f"{path.relative_to(root)}: missing plugin-root reference: {raw}")


def validate_repo(repo: Path) -> dict:
    repo = repo.resolve()
    root = repo / PLUGIN_RELATIVE
    errors: list[str] = []
    market = read_json(repo / ".claude-plugin" / "marketplace.json", errors)
    manifest = read_json(root / ".claude-plugin" / "plugin.json", errors)
    if market.get("name") != MARKETPLACE_NAME:
        errors.append("marketplace name must be leehumanities")
    entries = [e for e in market.get("plugins", []) if isinstance(e, dict) and e.get("name") == PLUGIN_NAME]
    if len(entries) != 1:
        errors.append("marketplace must contain exactly one leehumanities-research entry")
    else:
        entry = entries[0]
        target = component_path(repo, entry.get("source"), errors, "marketplace source")
        if target is not None and target.resolve() != root.resolve():
            errors.append("marketplace source must point to the isolated nested plugin")
        if entry.get("version") and entry["version"] != manifest.get("version"):
            errors.append("marketplace version and plugin version differ")
    if manifest.get("name") != PLUGIN_NAME:
        errors.append("plugin name must be leehumanities-research")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", str(manifest.get("version", ""))):
        errors.append("plugin version must be semantic versioning")
    if manifest.get("license") != "CC-BY-NC-4.0":
        errors.append("plugin must preserve the CC-BY-NC-4.0 license")
    if not manifest.get("description") or not isinstance(manifest.get("author"), dict):
        errors.append("plugin description and author metadata are required")
    if manifest.get("dependencies"):
        errors.append("v1 is self-contained: external plugin dependencies are not supported")

    for key in ("skills", "agents", "commands", "outputStyles", "workflows"):
        value = manifest.get(key)
        if value is None:
            continue
        if key == "commands" and isinstance(value, dict):
            for name, command in value.items():
                if not isinstance(command, dict):
                    errors.append(f"commands.{name}: expected an object")
                    continue
                if "source" in command:
                    component_path(root, command["source"], errors, f"commands.{name}")
                elif "content" not in command:
                    errors.append(f"commands.{name}: source or content is required")
            continue
        values = value if isinstance(value, list) else [value]
        for raw in values:
            target = component_path(root, raw, errors, key)
            if target is None:
                continue
            if key == "skills" and not target.is_dir():
                errors.append("skills component must name a directory")
            if key == "agents" and (not target.is_file() or target.suffix != ".md"):
                errors.append("agents component must name Markdown files")

    for name in ("LICENSE", "NOTICE.md", "scripts/research_audit.py"):
        if not (root / name).is_file():
            errors.append(f"missing bundled file: {name}")
    if (root / "NOTICE.md").is_file():
        notice = (root / "NOTICE.md").read_text(encoding="utf-8-sig")
        if "Imbad0202/academic-research-skills" not in notice or "CC BY-NC" not in notice:
            errors.append("NOTICE.md must attribute ARS and its CC BY-NC license")
    skill = root / "skills" / "humanities-research" / "SKILL.md"
    data = frontmatter(skill, errors)
    if data.get("name") != "humanities-research" or not data.get("description"):
        errors.append("main skill needs its name and a nonempty description")
    for stem in REFERENCE_NAMES:
        path = skill.parent / "references" / (stem + ".md")
        if not path.is_file():
            errors.append(f"missing skill reference: {stem}.md")
    agents = {p.stem: p for p in (root / "agents").glob("*.md")}
    commands = {p.stem: p for p in (root / "commands").glob("*.md")}
    if set(agents) != AGENTS:
        errors.append(f"agent inventory differs: expected {sorted(AGENTS)}, got {sorted(agents)}")
    if set(commands) != COMMANDS:
        errors.append(f"command inventory differs: expected {sorted(COMMANDS)}, got {sorted(commands)}")
    for stem, path in agents.items():
        agent = frontmatter(path, errors)
        if agent.get("name") != stem or not agent.get("description"):
            errors.append(f"{path.name}: agent name/description mismatch")
        if agent.get("model", "inherit") != "inherit":
            errors.append(f"{path.name}: default agent model must inherit the user's session")
    for path in commands.values():
        if not frontmatter(path, errors).get("description"):
            errors.append(f"{path.name}: command description is required")
    for path in root.rglob("*"):
        if path.is_symlink():
            errors.append(f"symlinks are not portable package contents: {path.relative_to(root)}")
        elif path.is_file() and path.suffix == ".md":
            try:
                check_markdown_links(root, path, errors)
            except (OSError, UnicodeError) as exc:
                errors.append(f"{path.relative_to(root)}: {exc}")
    return {
        "ok": not errors, "validation_kind": "package_conformance_only",
        "plugin": PLUGIN_NAME, "version": manifest.get("version"),
        "agent_count": len(agents), "command_count": len(commands), "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    result = validate_repo(args.repo)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
