#!/usr/bin/env python3
"""Local corpus manifests, evidence-record checks, and advisory revision checks.

Python standard library only. No network calls, model calls, document execution,
OCR, or semantic truth judgments. Source documents are opened read-only. PASS
means the submitted evidence records conform to this contract; it is never a
publication recommendation or an independently established claim-support result.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import unicodedata
from urllib.parse import urlsplit
import uuid


CORPUS_SCHEMA = "leehumanities-corpus/1.0"
EVIDENCE_SCHEMA = "leehumanities-evidence/1.0"
LEDGER_SCHEMA = "leehumanities-evidence-ledger/1.0"
DRIFT_SCHEMA = "leehumanities-drift/1.0"
EXTENSIONS = frozenset({
    ".md", ".txt", ".rst", ".pdf", ".docx", ".odt", ".rtf", ".tex",
    ".bib", ".ris", ".html", ".htm", ".epub", ".hwp", ".hwpx",
})
ACCESS_SCOPES = {"none", "metadata", "abstract", "excerpt", "full_text"}
SUPPORT_STATES = {"SUPPORTED", "PARTIAL", "UNSUPPORTED", "UNASSESSED"}
LOCATOR_KINDS = {"page", "section", "paragraph", "folio", "line", "timestamp"}
SENSITIVE_NAME = re.compile(
    r"(?:^|[_. -])(?:credentials?|secrets?|passwords?|tokens?|api[_. -]?keys?|"
    r"private[_. -]?keys?|auth|cookies?|sessions?)(?:[_. -]|$)", re.I,
)
SENSITIVE_EXTENSIONS = {".pem", ".key", ".p12", ".pfx", ".kdbx", ".keystore"}
SECRET_MARKERS = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    rb"(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)"
    rb"\s*[:=]\s*[\"']?[A-Za-z0-9_+/=-]{16,}", re.I,
)
TEXT_EXTENSIONS = {".md", ".txt", ".rst", ".tex", ".bib", ".ris", ".html", ".htm"}
POSIX_ANCHORED = os.name == "posix" and os.open in os.supports_dir_fd
REPARSE_POINT_ATTRIBUTE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
LIMIT_NOTE = (
    "PASS validates record conformance only. Source existence, access scope, and "
    "attributed claim support remain distinct. No semantic verification or online "
    "source retrieval was performed. An unresolved source is not a fabricated source."
)


class AuditError(ValueError):
    """A safe input or output precondition was not met."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def absolute_path(value: str | Path) -> Path:
    return Path(os.path.abspath(os.path.expanduser(str(value))))


def within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def path_link_reason(path: Path) -> str | None:
    """Reject links and all Windows reparse tags, including non-symlink junctions."""
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        return "symlink"
    if getattr(info, "st_file_attributes", 0) & REPARSE_POINT_ATTRIBUTE:
        return "reparse_point"
    return None


def reject_symlink_components(path: Path, *, allow_missing: bool = False) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            reason = path_link_reason(current)
        except FileNotFoundError:
            if allow_missing:
                continue
            raise AuditError(f"Missing path: {current}") from None
        if reason == "symlink":
            raise AuditError(f"Symlink paths are not accepted: {current}")
        if reason == "reparse_point":
            raise AuditError(f"Windows reparse points are not accepted: {current}")


def open_directory(path: Path, *, create: bool = False) -> int | None:
    """Anchor every POSIX component; Windows uses checked paths, not atomic anchors."""
    reject_symlink_components(path, allow_missing=create)
    if not POSIX_ANCHORED:
        if create:
            path.mkdir(parents=True, exist_ok=True, mode=0o700)
        reject_symlink_components(path)
        if not path.is_dir():
            raise AuditError(f"Not a directory: {path}")
        return None
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, 0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def open_readonly(path: Path):
    reject_symlink_components(path)
    if not stat.S_ISREG(path.lstat().st_mode):
        raise AuditError(f"Not a regular file: {path}")
    directory = open_directory(path.parent)
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(path.name if directory is not None else str(path), flags,
                     **({"dir_fd": directory} if directory is not None else {}))
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            os.close(fd)
            raise AuditError(f"Not a regular file: {path}")
        return os.fdopen(fd, "rb")
    finally:
        if directory is not None:
            os.close(directory)


def read_bytes(path: Path, limit: int = 8 * 1024 * 1024) -> bytes:
    with open_readonly(path) as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise AuditError(f"Input exceeds {limit} bytes: {path}")
    return data


def read_json(path: Path):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise AuditError(f"Duplicate JSON key is ambiguous: {key}")
            result[key] = value
        return result

    try:
        return json.loads(read_bytes(path).decode("utf-8-sig"), object_pairs_hook=unique_keys)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AuditError(f"Invalid UTF-8 JSON in {path}: {error}") from error


def digest_file(path: Path, maximum: int = 256 * 1024 * 1024) -> dict:
    digest = hashlib.sha256()
    secret_candidate = False
    tail = b""
    with open_readonly(path) as stream:
        before = os.fstat(stream.fileno())
        if before.st_size > maximum:
            raise AuditError(f"File exceeds configured size limit: {path.name}")
        size = 0
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            size += len(block)
            if size > maximum:
                raise AuditError(f"File exceeds configured size limit: {path.name}")
            digest.update(block)
            if path.suffix.lower() in TEXT_EXTENSIONS:
                if SECRET_MARKERS.search(tail + block):
                    secret_candidate = True
                tail = block[-256:]
        after = os.fstat(stream.fileno())
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns
        ):
            raise AuditError(f"Source changed while being read: {path.name}")
    return {"sha256": digest.hexdigest(), "size_bytes": size,
            "modified_at": datetime.fromtimestamp(after.st_mtime, timezone.utc).isoformat(),
            "credential_pattern_detected": secret_candidate}


def distribution_roots() -> list[Path]:
    """Protect this installed plugin and, if present, its own source checkout."""
    script = Path(__file__).resolve()
    plugin = script.parent.parent
    roots = [plugin]
    for parent in plugin.parents:
        if (parent / ".git").exists():
            roots.append(parent)
            break
    return roots


def prepare_run_directory(value: str | Path, source_roots: list[Path]) -> Path:
    run = absolute_path(value)
    reject_symlink_components(run, allow_missing=True)
    for root in source_roots + distribution_roots():
        if within(run, absolute_path(root)):
            raise AuditError(f"Run directory must be outside source and plugin directories: {run}")
    descriptor = open_directory(run, create=True)
    if descriptor is not None:
        os.close(descriptor)
    return run


def write_output(run: Path, filename: str, text: str) -> None:
    """Atomic fixed-name output; never follow an existing output symlink."""
    if Path(filename).name != filename:
        raise AuditError("Output filename must have no path components")
    directory = open_directory(run)
    temporary = f".{filename}.{uuid.uuid4().hex}.tmp"
    target = run / filename
    try:
        try:
            current = (os.stat(filename, dir_fd=directory, follow_symlinks=False)
                       if directory is not None else target.lstat())
        except FileNotFoundError:
            current = None
        if current is not None and not stat.S_ISREG(current.st_mode):
            raise AuditError(f"Output target is not a regular file: {target}")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(temporary if directory is not None else str(run / temporary),
                     flags, 0o600, **({"dir_fd": directory} if directory is not None else {}))
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        if directory is not None:
            os.replace(temporary, filename, src_dir_fd=directory, dst_dir_fd=directory)
        else:
            reject_symlink_components(run)
            os.replace(run / temporary, target)
    finally:
        try:
            if directory is not None:
                os.unlink(temporary, dir_fd=directory)
            else:
                (run / temporary).unlink(missing_ok=True)
        except FileNotFoundError:
            pass
        if directory is not None:
            os.close(directory)


def save_pair(run: Path, stem: str, data: dict, review: str) -> None:
    write_output(run, stem + ".json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    write_output(run, stem.replace("ledger", "review").replace("manifest", "review") + ".md", review)


def sensitive_name(name: str) -> bool:
    return (name.startswith(".") or name.lower() in {"id_rsa", "id_ed25519", "known_hosts"}
            or Path(name).suffix.lower() in SENSITIVE_EXTENSIONS
            or SENSITIVE_NAME.search(name) is not None)


def corpus_index(source: str | Path, run_dir: str | Path, *, max_bytes: int = 256 * 1024 * 1024) -> dict:
    root = absolute_path(source)
    descriptor = open_directory(root)
    if descriptor is not None:
        os.close(descriptor)
    run = prepare_run_directory(run_dir, [root])
    entries, skipped, errors = [], [], []

    def walk_error(error):
        errors.append({"path": str(error.filename), "reason": str(error)})

    for directory, names, files in os.walk(root, topdown=True, followlinks=False, onerror=walk_error):
        base = Path(directory)
        kept = []
        for name in sorted(names):
            child = base / name
            try:
                reason = path_link_reason(child) or ("hidden_or_sensitive_name" if sensitive_name(name) else None)
            except OSError as error:
                errors.append({"relative_path": child.relative_to(root).as_posix(), "reason": str(error)})
                continue
            if reason:
                skipped.append({"relative_path": child.relative_to(root).as_posix(), "reason": reason})
            else:
                kept.append(name)
        # followlinks=False does not exclude every NTFS reparse tag. Prune this
        # shared list before os.walk resumes so a junction is never enumerated.
        names[:] = kept
        for name in sorted(files):
            path = base / name
            relative = path.relative_to(root).as_posix()
            try:
                reason = (path_link_reason(path) or ("hidden_or_sensitive_name" if sensitive_name(name)
                          else "unsupported_extension" if path.suffix.lower() not in EXTENSIONS else None))
            except OSError as error:
                errors.append({"relative_path": relative, "reason": str(error)})
                continue
            if reason:
                skipped.append({"relative_path": relative, "reason": reason})
                continue
            try:
                info = digest_file(path, max_bytes)
                if info.pop("credential_pattern_detected"):
                    skipped.append({"relative_path": relative, "reason": "credential_like_text"})
                    continue
                entries.append({
                    "source_id": "src-" + hashlib.sha256(relative.encode("utf-8")).hexdigest()[:16],
                    "relative_path": relative, **info,
                    "source_metadata": {"title": None, "author": None, "year": None,
                                        "source_type": "UNCLASSIFIED"},
                    "existence_observation": "LOCAL_FILE_CONFIRMED",
                    "access_scope": "metadata", "content_read_for_hash_only": True,
                    "claim_support": "UNASSESSED",
                })
            except (OSError, AuditError) as error:
                errors.append({"relative_path": relative, "reason": str(error)})
    entries.sort(key=lambda row: row["relative_path"])
    data = {"schema_version": CORPUS_SCHEMA, "created_at": utc_now(), "source_root": str(root),
            "scan_status": "PARTIAL" if errors else "COMPLETE_WITH_DECLARED_EXCLUSIONS",
            "indexed_count": len(entries), "entries": entries, "skipped": skipped, "errors": errors,
            "limits": ["No document text was extracted, interpreted, or uploaded.",
                       "Hashing is not a reading attestation. Metadata fields are intentionally unfilled.",
                       "Only listed extensions are indexed; hidden, symlink, Windows reparse, and credential-like items are excluded.",
                       "Filename and text-pattern exclusions cannot certify that documents contain no sensitive data.",
                       "POSIX path components are anchored; Windows path checks are best-effort, not atomic."]}
    review = ("# Corpus manifest review\n\n"
              f"- Status: **{data['scan_status']}**\n- Indexed documents: {len(entries)}\n"
              f"- Excluded items: {len(skipped)}\n- Read errors: {len(errors)}\n\n"
              "This manifest records file existence and SHA-256 hashes. It does not establish that any "
              "document has been read for research or supports a claim. No source file was written.\n\n"
              "## Limits\n\n" + "\n".join(f"- {item}" for item in data["limits"]) + "\n")
    save_pair(run, "corpus-manifest", data, review)
    return data


def text_value(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def enum_value(value, allowed: set[str]) -> bool:
    return isinstance(value, str) and value in allowed


def local_source_path(root_value, relative_value) -> Path:
    if not text_value(root_value) or not Path(root_value).is_absolute():
        raise AuditError("Local sources require an explicitly declared absolute source_root")
    if not text_value(relative_value):
        raise AuditError("local_path must be a nonempty relative path")
    pieces = re.split(r"[/\\]", relative_value)
    if (relative_value.startswith(("/", "\\")) or ":" in pieces[0]
            or any(part in {"", ".", ".."} for part in pieces)):
        raise AuditError("local_path must not contain absolute, empty, dot, or parent components")
    if any(sensitive_name(part) for part in pieces):
        raise AuditError("Hidden or credential-looking local source paths are excluded")
    root = absolute_path(root_value)
    path = root.joinpath(*pieces)
    reject_symlink_components(path)
    return path


def declared_roots(document: dict, corpus: dict | None = None) -> list[Path]:
    values = [document.get("source_root")]
    if isinstance(document.get("sources"), list):
        values.extend(s.get("source_root") for s in document["sources"] if isinstance(s, dict))
    if corpus:
        values.append(corpus.get("source_root"))
    roots = []
    for value in values:
        if text_value(value):
            roots.append(absolute_path(value))
    return roots


def validate_evidence(document, corpus: dict | None = None) -> dict:
    """Check recorded evidence, preserving negative and unresolved findings."""
    errors, warnings, observations = [], [], []
    verified, full_text_verified = 0, 0
    support_counts = Counter()

    def error(code, location, message):
        errors.append({"code": code, "location": location, "message": message})

    if not isinstance(document, dict):
        document = {}
        error("ENVELOPE_TYPE", "$", "Evidence input must be an object")
    if document.get("schema_version") != EVIDENCE_SCHEMA:
        error("SCHEMA_VERSION", "$", f"Expected {EVIDENCE_SCHEMA}")
    source_rows = document.get("sources")
    claim_rows = document.get("claims")
    if not isinstance(source_rows, list) or not source_rows:
        error("SOURCES_REQUIRED", "sources", "At least one source record is required")
        source_rows = []
    if not isinstance(claim_rows, list) or not claim_rows:
        error("CLAIMS_REQUIRED", "claims", "At least one claim record is required")
        claim_rows = []
    corpus_lookup = {}
    if corpus is not None:
        if not isinstance(corpus, dict) or corpus.get("schema_version") != CORPUS_SCHEMA:
            error("CORPUS_SCHEMA", "corpus", "Invalid corpus manifest schema")
        elif not isinstance(corpus.get("entries"), list):
            error("CORPUS_ENTRIES", "corpus", "Corpus entries must be an array")
        else:
            if not text_value(corpus.get("source_root")) or not Path(corpus["source_root"]).is_absolute():
                error("CORPUS_ROOT", "corpus", "Corpus source_root must be an absolute path")
            for index, row in enumerate(corpus["entries"]):
                where = f"corpus.entries[{index}]"
                if (not isinstance(row, dict) or not text_value(row.get("relative_path"))
                        or not isinstance(row.get("sha256"), str)
                        or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
                    error("CORPUS_ENTRY", where, "Each corpus entry needs relative_path and a lowercase SHA-256")
                    continue
                if row["relative_path"] in corpus_lookup:
                    error("CORPUS_DUPLICATE", where, "Corpus relative paths must be unique")
                corpus_lookup[row["relative_path"]] = row["sha256"]
    sources, source_errors = {}, set()
    for index, row in enumerate(source_rows):
        location = f"sources[{index}]"
        before = len(errors)
        if not isinstance(row, dict):
            error("SOURCE_TYPE", location, "Source must be an object")
            continue
        source_id = row.get("source_id")
        if not text_value(source_id):
            error("SOURCE_ID", location, "A nonempty source_id is required")
            continue
        if source_id in sources:
            error("DUPLICATE_SOURCE", location, "source_id must be unique")
            source_errors.add(source_id)
            continue
        sources[source_id] = row
        if not text_value(row.get("title")):
            error("SOURCE_TITLE", location, "Record a source title or archival description")
        if not enum_value(row.get("existence"), {"CONFIRMED", "UNRESOLVED"}):
            error("EXISTENCE_STATE", location, "Use CONFIRMED or UNRESOLVED; index absence does not establish fabrication")
        if row.get("existence") == "CONFIRMED" and not text_value(row.get("existence_basis")):
            error("EXISTENCE_BASIS", location, "Confirmed existence needs a recorded basis")
        if not enum_value(row.get("access_scope"), ACCESS_SCOPES):
            error("ACCESS_SCOPE", location, "Record the actual access scope")
        uri, local = row.get("uri"), row.get("local_path")
        if uri is not None:
            try:
                parsed = urlsplit(uri) if isinstance(uri, str) else None
                valid_uri = (parsed is not None and parsed.scheme == "https" and bool(parsed.hostname)
                             and not parsed.username and not parsed.password and not any(c.isspace() for c in uri))
            except ValueError:
                valid_uri = False
            if not valid_uri:
                error("SOURCE_URI", location, "uri must be an HTTPS source URL without credentials; local archival sources need no URI")
        observation = {"source_id": source_id, "existence_declared": row.get("existence"),
                       "access_scope_declared": row.get("access_scope"),
                       "tool_observation": "NOT_FETCHED" if uri else "UNRESOLVED"}
        if local is not None:
            try:
                root_value = row.get("source_root", document.get("source_root"))
                path = local_source_path(root_value, local)
                info = digest_file(path)
                if info["credential_pattern_detected"]:
                    raise AuditError("Credential-like source text is excluded")
                observation.update(tool_observation="LOCAL_FILE_CONFIRMED", sha256=info["sha256"])
                if row.get("sha256") is not None and row.get("sha256") != info["sha256"]:
                    error("SOURCE_HASH_MISMATCH", location, "Current source does not match the recorded SHA-256")
                if corpus is not None and isinstance(corpus, dict):
                    if absolute_path(root_value) != absolute_path(corpus.get("source_root", "")):
                        error("CORPUS_ROOT_MISMATCH", location, "Local record and supplied corpus manifest use different roots")
                    normalized = path.relative_to(absolute_path(root_value)).as_posix()
                    if normalized not in corpus_lookup:
                        error("CORPUS_SOURCE_MISSING", location, "Local source is not in the supplied manifest")
                    elif corpus_lookup[normalized] != info["sha256"]:
                        error("CORPUS_HASH_MISMATCH", location, "Source changed since the supplied corpus manifest was produced")
            except (AuditError, OSError, TypeError, ValueError) as problem:
                error("LOCAL_SOURCE", location, str(problem))
                observation["tool_observation"] = "UNRESOLVED"
        if uri is None and local is None and row.get("existence") == "CONFIRMED":
            error("SOURCE_LOCATION", location, "Confirmed sources need a source URI or confined local_path")
        if row.get("existence") == "UNRESOLVED":
            warnings.append({"code": "SOURCE_UNRESOLVED", "location": location,
                             "message": "Unresolved is not fabricated; preserve it for manual source work"})
        observations.append(observation)
        if len(errors) > before:
            source_errors.add(source_id)
    claim_ids = set()
    for index, claim in enumerate(claim_rows):
        location = f"claims[{index}]"
        if not isinstance(claim, dict):
            error("CLAIM_TYPE", location, "Claim must be an object")
            continue
        claim_id = claim.get("claim_id")
        if not text_value(claim_id) or claim_id in claim_ids:
            error("CLAIM_ID", location, "Each claim needs a nonempty unique claim_id")
        else:
            claim_ids.add(claim_id)
        if not text_value(claim.get("text")):
            error("CLAIM_TEXT", location, "Record the exact claim being assessed")
        records = claim.get("evidence")
        if not isinstance(records, list) or not records:
            error("EVIDENCE_REQUIRED", location, "Include at least one evidence record, even when UNVERIFIED")
            continue
        for record_index, record in enumerate(records):
            where = f"{location}.evidence[{record_index}]"
            before = len(errors)
            if not isinstance(record, dict):
                error("EVIDENCE_TYPE", where, "Evidence record must be an object")
                continue
            source_id = record.get("source_id")
            source = sources.get(source_id) if isinstance(source_id, str) else None
            if source is None:
                error("UNKNOWN_SOURCE", where, "Evidence must reference a declared source_id")
            status, support = record.get("status"), record.get("support")
            if not enum_value(status, {"VERIFIED", "UNVERIFIED"}):
                error("EVIDENCE_STATUS", where, "status must be VERIFIED or UNVERIFIED")
            if not enum_value(support, SUPPORT_STATES):
                error("SUPPORT_STATE", where, "Use SUPPORTED, PARTIAL, UNSUPPORTED, or UNASSESSED")
            else:
                support_counts[support] += 1
            if status != "VERIFIED":
                if enum_value(support, {"SUPPORTED", "PARTIAL", "UNSUPPORTED"}):
                    warnings.append({"code": "UNVERIFIED_SUPPORT", "location": where,
                                     "message": "Support is a provisional attributed judgment, not verified evidence"})
                continue
            if source is None:
                continue
            if source_id in source_errors:
                error("INVALID_SOURCE_RECORD", where, "A VERIFIED declaration cannot rely on an invalid source record")
            if source.get("existence") != "CONFIRMED":
                error("UNRESOLVED_VERIFIED", where, "Unresolved sources cannot carry VERIFIED evidence")
            if not (text_value(source.get("uri")) or text_value(source.get("local_path"))):
                error("VERIFIED_LOCATION", where, "VERIFIED evidence needs a source URI or local artifact")
            for field in ("read_scope", "read_by", "accessed_at"):
                if not text_value(source.get(field)):
                    error("READ_ATTESTATION", where, f"VERIFIED evidence requires source.{field}")
            if text_value(source.get("accessed_at")):
                try:
                    datetime.fromisoformat(source["accessed_at"].replace("Z", "+00:00"))
                except ValueError:
                    error("ACCESS_DATE", where, "accessed_at must be an ISO date or timestamp")
            scope = record.get("verification_scope")
            access = source.get("access_scope")
            permitted = {"full_text": {"full_text", "excerpt", "abstract"},
                         "excerpt": {"excerpt"}, "abstract": {"abstract"}}
            if not enum_value(scope, permitted.get(access, set()) if isinstance(access, str) else set()):
                error("SCOPE_OVERCLAIM", where, "Verification scope cannot exceed the actually recorded reading scope; metadata is not claim evidence")
            locator = record.get("locator")
            if (not isinstance(locator, dict) or not enum_value(locator.get("kind"), LOCATOR_KINDS)
                    or not text_value(locator.get("value"))):
                error("EVIDENCE_LOCATOR", where, "A page, section, paragraph, folio, line, or timestamp locator is required")
            for field in ("excerpt", "assessor", "assessment_note"):
                if not text_value(record.get(field)):
                    error("EVIDENCE_DETAIL", where, f"VERIFIED evidence requires {field}")
            if support == "UNASSESSED":
                error("UNASSESSED_VERIFIED", where, "VERIFIED records must state an attributed support judgment")
            if enum_value(scope, {"abstract", "excerpt"}):
                warnings.append({"code": "LIMITED_READING", "location": where,
                                 "message": "This declaration covers only the recorded abstract/excerpt, not full-text verification"})
            if len(errors) == before:
                verified += 1
                full_text_verified += int(scope == "full_text")
    return {"schema_version": LEDGER_SCHEMA, "created_at": utc_now(),
            "record_validation": "FAIL" if errors else "PASS",
            "semantic_verification_performed": False, "source_retrieval_performed": False,
            "verified_declarations_conforming": verified,
            "full_text_verified_declarations_conforming": full_text_verified,
            "attributed_support_counts": dict(sorted(support_counts.items())),
            "source_observations": observations, "errors": errors, "warnings": warnings,
            "limits": LIMIT_NOTE, "evidence_record": document}


def evidence_validate(input_path: str | Path, run_dir: str | Path, corpus_path: str | Path | None = None) -> dict:
    document = read_json(absolute_path(input_path))
    corpus = read_json(absolute_path(corpus_path)) if corpus_path else None
    roots = declared_roots(document if isinstance(document, dict) else {}, corpus if isinstance(corpus, dict) else None)
    run = prepare_run_directory(run_dir, roots)
    inputs = [absolute_path(input_path)] + ([absolute_path(corpus_path)] if corpus_path else [])
    if any(path == run / name for path in inputs for name in ("evidence-ledger.json", "evidence-review.md")):
        raise AuditError("Evidence outputs must not overwrite an input file")
    result = validate_evidence(document, corpus)
    lines = ["# Evidence record review", "", f"Record conformance: **{result['record_validation']}**", "",
             f"Conforming VERIFIED declarations: {result['verified_declarations_conforming']}", "",
             f"Of those, full-text declarations: {result['full_text_verified_declarations_conforming']}", "",
             LIMIT_NOTE, "", "VERIFIED reflects the named assessor's recorded judgment. This local tool does not confirm "
             "that the excerpt is authentic, that the locator is correct, or that the interpretation follows from it.", ""]
    for heading, key in (("Record errors", "errors"), ("Review notes", "warnings")):
        lines.extend([f"## {heading}", ""])
        lines.extend([f"- `{r['code']}` at `{r['location']}`: {r['message']}" for r in result[key]] or ["None."])
        lines.append("")
    save_pair(run, "evidence-ledger", result, "\n".join(lines))
    return result


NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])[-+−]?(?:\d+(?:,\d{3})*)(?:\.\d+)?(?:[eE][-+]?\d+)?(?:%|‰)?(?![A-Za-z0-9_])")
CITATION_PATTERN = re.compile(
    r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+|"
    r"\[(?:@[^\]\n]+|S\d+|\d+(?:\s*[,;–-]\s*\d+)*)\]|"
    r"\([^()\n]{0,120}\b(?:18|19|20)\d{2}[a-z]?\b[^()\n]{0,120}\)|"
    r"https?://[^\s<>\]]+"
)


def differences(before: Counter, after: Counter) -> list[dict]:
    return [{"token": token, "before": before[token], "after": after[token]}
            for token in sorted(before.keys() | after.keys()) if before[token] != after[token]]


def drift_check(before_path: str | Path, after_path: str | Path, run_dir: str | Path,
                protected_terms: str | Path | None = None) -> dict:
    before_file, after_file = absolute_path(before_path), absolute_path(after_path)
    run = prepare_run_directory(run_dir, [])
    inputs = [before_file, after_file] + ([absolute_path(protected_terms)] if protected_terms else [])
    for source in inputs:
        if within(source, run):
            raise AuditError("Run directory must not contain manuscript or protected-term input files")
    before = unicodedata.normalize("NFC", read_bytes(before_file).decode("utf-8-sig"))
    after = unicodedata.normalize("NFC", read_bytes(after_file).decode("utf-8-sig"))
    terms = []
    if protected_terms:
        terms = read_json(absolute_path(protected_terms))
        if isinstance(terms, dict):
            terms = terms.get("terms")
        if not isinstance(terms, list) or any(not text_value(term) for term in terms):
            raise AuditError("Protected terms must be a JSON array of nonempty strings or an object with a terms array")
        terms = sorted(set(unicodedata.normalize("NFC", term) for term in terms))
    changes = {
        "protected_terms": differences(Counter({term: before.count(term) for term in terms}),
                                       Counter({term: after.count(term) for term in terms})),
        "numbers": differences(Counter(NUMBER_PATTERN.findall(before)), Counter(NUMBER_PATTERN.findall(after))),
        "citation_tokens": differences(Counter(CITATION_PATTERN.findall(before)), Counter(CITATION_PATTERN.findall(after))),
    }
    result = {"schema_version": DRIFT_SCHEMA, "created_at": utc_now(),
              "result": "ADVISORY_CHANGES_DETECTED" if any(changes.values()) else "NO_TOKEN_CHANGES_DETECTED",
              "blocking": False, "semantic_verification_performed": False,
              "before_sha256": hashlib.sha256(before.encode()).hexdigest(),
              "after_sha256": hashlib.sha256(after.encode()).hexdigest(),
              "hash_basis": "UTF-8 text after BOM removal and NFC normalization", "changes": changes,
              "limits": "Exact token counts only. Intentional edits can trigger findings; reordered or semantically changed text can evade them. "
                        "Citation patterns are heuristic and incomplete. No judgment of AI authorship, originality, or philosophical validity is made."}
    lines = ["# Revision drift review", "", f"Result: **{result['result']}**", "",
             "These are advisory differences for the author to review. No manuscript was edited.", ""]
    for heading, key in (("Protected terms", "protected_terms"), ("Numbers", "numbers"), ("Citation tokens", "citation_tokens")):
        lines.extend([f"## {heading}", ""])
        lines.extend([f"- {json.dumps(row['token'], ensure_ascii=False)}: {row['before']} → {row['after']}" for row in changes[key]] or ["No count changes detected."])
        lines.append("")
    lines.extend(["## Limits", "", result["limits"], ""])
    save_pair(run, "drift-ledger", result, "\n".join(lines))
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    corpus = commands.add_parser("corpus-index", help="Index an explicitly selected local corpus without modifying it")
    corpus.add_argument("--source", required=True)
    corpus.add_argument("--run-dir", required=True)
    corpus.add_argument("--max-file-mib", type=int, default=256)
    evidence = commands.add_parser("evidence-validate", help="Validate evidence records, not semantic truth")
    evidence.add_argument("--input", required=True)
    evidence.add_argument("--run-dir", required=True)
    evidence.add_argument("--corpus")
    drift = commands.add_parser("drift-check", help="Report advisory protected-term, numeric, and citation-token changes")
    drift.add_argument("--before", required=True)
    drift.add_argument("--after", required=True)
    drift.add_argument("--protected-terms")
    drift.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "corpus-index":
            if args.max_file_mib < 1:
                raise AuditError("--max-file-mib must be positive")
            result = corpus_index(args.source, args.run_dir, max_bytes=args.max_file_mib * 1024 * 1024)
            print(json.dumps({"scan_status": result["scan_status"], "indexed_count": result["indexed_count"]}))
            return 1 if result["errors"] else 0
        if args.command == "evidence-validate":
            result = evidence_validate(args.input, args.run_dir, args.corpus)
            print(json.dumps({key: result[key] for key in ("record_validation", "semantic_verification_performed", "verified_declarations_conforming")}))
            return 1 if result["errors"] else 0
        result = drift_check(args.before, args.after, args.run_dir, args.protected_terms)
        print(json.dumps({"result": result["result"], "blocking": False}))
        return 0
    except (AuditError, OSError, UnicodeError) as problem:
        print(f"research_audit: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
