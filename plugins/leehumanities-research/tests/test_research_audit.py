"""Meaningful safety and false-PASS checks using synthetic material only."""

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "scripts" / "research_audit.py"
SPEC = importlib.util.spec_from_file_location("leehumanities_research_audit", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name="evidence_valid_synthetic.json"):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def codes(result):
    return {row["code"] for row in result["errors"]}


class EvidenceRecordTests(unittest.TestCase):
    def test_non_doi_primary_source_is_valid_without_semantic_claim(self):
        result = audit.validate_evidence(fixture())
        self.assertEqual(result["record_validation"], "PASS")
        self.assertFalse(result["semantic_verification_performed"])
        self.assertFalse(result["source_retrieval_performed"])
        self.assertEqual(result["source_observations"][0]["tool_observation"], "NOT_FETCHED")
        self.assertEqual(result["verified_declarations_conforming"], 1)

    def test_negative_and_partial_findings_remain_valid(self):
        for support in ("UNSUPPORTED", "PARTIAL"):
            with self.subTest(support=support):
                data = fixture()
                data["claims"][0]["evidence"][0]["support"] = support
                result = audit.validate_evidence(data)
                self.assertEqual(result["record_validation"], "PASS")
                self.assertEqual(result["attributed_support_counts"], {support: 1})

    def test_abstract_cannot_pass_as_full_text(self):
        result = audit.validate_evidence(fixture("evidence_invalid_abstract_overclaim.json"))
        self.assertEqual(result["record_validation"], "FAIL")
        self.assertIn("SCOPE_OVERCLAIM", codes(result))
        self.assertEqual(result["verified_declarations_conforming"], 0)

    def test_limited_reading_is_preserved_as_limited(self):
        for scope in ("abstract", "excerpt"):
            with self.subTest(scope=scope):
                data = fixture()
                data["sources"][0]["access_scope"] = scope
                data["claims"][0]["evidence"][0]["verification_scope"] = scope
                result = audit.validate_evidence(data)
                self.assertEqual(result["record_validation"], "PASS")
                self.assertEqual(result["full_text_verified_declarations_conforming"], 0)
                self.assertIn("LIMITED_READING", {row["code"] for row in result["warnings"]})

    def test_metadata_cannot_establish_claim_support(self):
        data = fixture()
        data["sources"][0]["access_scope"] = "metadata"
        data["claims"][0]["evidence"][0]["verification_scope"] = "metadata"
        self.assertIn("SCOPE_OVERCLAIM", codes(audit.validate_evidence(data)))

    def test_required_evidence_cannot_be_omitted(self):
        for field in ("locator", "excerpt", "assessor", "assessment_note"):
            with self.subTest(field=field):
                data = fixture()
                del data["claims"][0]["evidence"][0][field]
                result = audit.validate_evidence(data)
                self.assertEqual(result["record_validation"], "FAIL")
                self.assertEqual(result["verified_declarations_conforming"], 0)

    def test_reading_attestation_cannot_be_omitted(self):
        for field in ("read_scope", "read_by", "accessed_at"):
            with self.subTest(field=field):
                data = fixture()
                del data["sources"][0][field]
                self.assertIn("READ_ATTESTATION", codes(audit.validate_evidence(data)))

    def test_missing_source_location_fails_verified_declaration(self):
        data = fixture()
        del data["sources"][0]["uri"]
        result = audit.validate_evidence(data)
        self.assertEqual(result["record_validation"], "FAIL")
        self.assertEqual(result["verified_declarations_conforming"], 0)

    def test_unresolved_is_not_fabricated_and_can_be_recorded(self):
        data = fixture()
        source = data["sources"][0]
        source.update(existence="UNRESOLVED", access_scope="none", existence_basis="Not found in a checked index")
        del source["uri"]
        record = data["claims"][0]["evidence"][0]
        record.update(status="UNVERIFIED", support="UNASSESSED")
        result = audit.validate_evidence(data)
        self.assertEqual(result["record_validation"], "PASS")
        self.assertEqual(result["verified_declarations_conforming"], 0)
        self.assertEqual(result["source_observations"][0]["existence_declared"], "UNRESOLVED")
        source["existence"] = "FABRICATED"
        self.assertIn("EXISTENCE_STATE", codes(audit.validate_evidence(data)))

    def test_unresolved_cannot_be_promoted_to_verified(self):
        data = fixture()
        data["sources"][0]["existence"] = "UNRESOLVED"
        self.assertIn("UNRESOLVED_VERIFIED", codes(audit.validate_evidence(data)))

    def test_duplicate_source_ids_and_unknown_source_fail(self):
        data = fixture()
        data["sources"].append(copy.deepcopy(data["sources"][0]))
        result = audit.validate_evidence(data)
        self.assertIn("DUPLICATE_SOURCE", codes(result))
        self.assertEqual(result["verified_declarations_conforming"], 0)
        data = fixture()
        data["claims"][0]["evidence"][0]["source_id"] = "MISSING"
        self.assertIn("UNKNOWN_SOURCE", codes(audit.validate_evidence(data)))

    def test_empty_or_malformed_records_do_not_pass_or_crash(self):
        for data in ({}, [], {"schema_version": audit.EVIDENCE_SCHEMA, "sources": [], "claims": []}):
            with self.subTest(data=data):
                self.assertEqual(audit.validate_evidence(data)["record_validation"], "FAIL")
        for section, field in (("source", "existence"), ("source", "access_scope"),
                               ("record", "status"), ("record", "support"), ("record", "verification_scope")):
            with self.subTest(field=field):
                data = fixture()
                target = data["sources"][0] if section == "source" else data["claims"][0]["evidence"][0]
                target[field] = ["malformed"]
                self.assertEqual(audit.validate_evidence(data)["record_validation"], "FAIL")


class LocalFileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lh-research-tests-")
        self.base = Path(self.temporary.name)
        self.source = self.base / "corpus"
        self.source.mkdir()
        self.document = self.source / "archival-note.txt"
        self.document.write_text("Synthetic primary note.\nQuestion recorded on folio 2.\n", encoding="utf-8")
        self.original = self.document.read_bytes()

    def tearDown(self):
        self.temporary.cleanup()

    def local_record(self):
        data = fixture()
        data["source_root"] = str(self.source)
        source = data["sources"][0]
        source.pop("uri")
        source["local_path"] = self.document.name
        source["sha256"] = hashlib.sha256(self.original).hexdigest()
        source["existence_basis"] = "Read the user-selected local primary artifact"
        return data

    def test_local_primary_artifact_needs_no_doi_or_url(self):
        result = audit.validate_evidence(self.local_record())
        self.assertEqual(result["record_validation"], "PASS")
        self.assertEqual(result["source_observations"][0]["tool_observation"], "LOCAL_FILE_CONFIRMED")
        self.assertEqual(self.document.read_bytes(), self.original)

    def test_path_traversal_absolute_and_symlink_references_fail(self):
        for path in ("../outside.txt", "..\\outside.txt", "/tmp/outside.txt", "C:\\outside.txt", "a/../archival-note.txt"):
            with self.subTest(path=path):
                data = self.local_record()
                data["sources"][0]["local_path"] = path
                self.assertIn("LOCAL_SOURCE", codes(audit.validate_evidence(data)))
        link = self.source / "linked.txt"
        try:
            link.symlink_to(self.document)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are not available")
        data = self.local_record()
        data["sources"][0]["local_path"] = "linked.txt"
        self.assertIn("LOCAL_SOURCE", codes(audit.validate_evidence(data)))
        folder = self.source / "linked-folder"
        folder.symlink_to(self.source, target_is_directory=True)
        data["sources"][0]["local_path"] = "linked-folder/archival-note.txt"
        self.assertIn("LOCAL_SOURCE", codes(audit.validate_evidence(data)))

    def test_hash_mismatch_rejects_stale_evidence(self):
        data = self.local_record()
        data["sources"][0]["sha256"] = "0" * 64
        self.assertIn("SOURCE_HASH_MISMATCH", codes(audit.validate_evidence(data)))

    def test_manifest_hash_binding_detects_changed_source(self):
        manifest = audit.corpus_index(self.source, self.base / "index-run")
        self.document.write_text("Synthetic changed document\n", encoding="utf-8")
        data = self.local_record()
        data["sources"][0].pop("sha256")
        self.assertIn("CORPUS_HASH_MISMATCH", codes(audit.validate_evidence(data, manifest)))

    def test_duplicate_or_malformed_manifest_cannot_pass(self):
        manifest = audit.corpus_index(self.source, self.base / "index-run")
        manifest["entries"].append(copy.deepcopy(manifest["entries"][0]))
        self.assertIn("CORPUS_DUPLICATE", codes(audit.validate_evidence(self.local_record(), manifest)))
        manifest["entries"] = [{"relative_path": "archival-note.txt", "sha256": []}]
        self.assertIn("CORPUS_ENTRY", codes(audit.validate_evidence(self.local_record(), manifest)))

    def test_index_excludes_sensitive_and_symlink_items_without_source_writes(self):
        (self.source / "credentials.txt").write_text("test fixture only", encoding="utf-8")
        (self.source / ".env").write_text("fixture only", encoding="utf-8")
        (self.source / "ordinary-note.md").write_text("api_key = TESTONLYABCDEFGHIJKLMNOPQRSTUV", encoding="utf-8")
        (self.source / "script.py").write_text("raise RuntimeError('must never execute')", encoding="utf-8")
        try:
            (self.source / "linked.txt").symlink_to(self.document)
        except (OSError, NotImplementedError):
            pass
        snapshots = {str(path): path.read_bytes() for path in self.source.iterdir() if path.is_file() and not path.is_symlink()}
        manifest = audit.corpus_index(self.source, self.base / "index-run")
        self.assertEqual(manifest["indexed_count"], 1)
        self.assertEqual(manifest["entries"][0]["relative_path"], "archival-note.txt")
        self.assertEqual(manifest["entries"][0]["access_scope"], "metadata")
        reasons = {row["reason"] for row in manifest["skipped"]}
        self.assertIn("hidden_or_sensitive_name", reasons)
        self.assertIn("credential_like_text", reasons)
        self.assertIn("unsupported_extension", reasons)
        self.assertEqual(snapshots, {str(path): path.read_bytes() for path in self.source.iterdir() if path.is_file() and not path.is_symlink()})

    def test_nonsymlink_reparse_directory_is_pruned_before_enumeration(self):
        junction = self.source / "junction"
        junction.mkdir()
        (junction / "must-not-be-enumerated.txt").write_text("Synthetic outside material", encoding="utf-8")
        real_lstat, real_scandir = Path.lstat, os.scandir
        scanned = []

        def reparse_lstat(path, *args, **kwargs):
            info = real_lstat(path, *args, **kwargs)
            if path == junction:
                # st_mode is a directory, not a symlink: Path.is_symlink alone
                # cannot identify this Windows junction-like fixture.
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=audit.REPARSE_POINT_ATTRIBUTE)
            return info

        def confined_scandir(path):
            if not isinstance(path, int):
                scanned.append(Path(path))
                if audit.within(Path(path), junction):
                    self.fail("os.walk entered a reparse directory before pruning it")
            return real_scandir(path)

        with mock.patch.object(Path, "lstat", reparse_lstat), mock.patch.object(audit.os, "scandir", confined_scandir):
            self.assertFalse(junction.is_symlink())
            result = audit.corpus_index(self.source, self.base / "reparse-run")
        self.assertEqual(result["indexed_count"], 1)
        self.assertEqual(result["errors"], [])
        self.assertIn({"relative_path": "junction", "reason": "reparse_point"}, result["skipped"])
        self.assertNotIn(junction, scanned)
        self.assertEqual(self.document.read_bytes(), self.original)

    def test_reparse_source_root_is_rejected_before_walk_or_output(self):
        real_lstat = Path.lstat

        def reparse_lstat(path, *args, **kwargs):
            info = real_lstat(path, *args, **kwargs)
            if path == self.source:
                return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=audit.REPARSE_POINT_ATTRIBUTE)
            return info

        run = self.base / "reparse-root-run"
        with mock.patch.object(Path, "lstat", reparse_lstat), mock.patch.object(audit.os, "walk") as walker:
            with self.assertRaisesRegex(audit.AuditError, "reparse"):
                audit.corpus_index(self.source, run)
            walker.assert_not_called()
        self.assertFalse(run.exists())

    def test_output_inside_corpus_or_plugin_is_rejected(self):
        for run in (self.source, self.source / "runs", PLUGIN / "unsafe-test-run"):
            with self.subTest(run=run):
                with self.assertRaises(audit.AuditError):
                    audit.corpus_index(self.source, run)
        self.assertEqual(list(self.source.iterdir()), [self.document])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO test requires POSIX")
    def test_fifo_is_rejected_without_waiting_for_writer(self):
        fifo = self.source / "pipe.txt"
        os.mkfifo(fifo)
        with self.assertRaises(audit.AuditError):
            audit.read_bytes(fifo)
        result = audit.corpus_index(self.source, self.base / "fifo-run")
        self.assertEqual(result["scan_status"], "PARTIAL")
        self.assertEqual(result["indexed_count"], 1)

    def test_separate_project_run_directory_is_allowed_even_when_project_has_git(self):
        project = self.base / "research-project"
        project.mkdir()
        (project / ".git").mkdir()
        run = project / ".leehumanities" / "runs" / "example"
        self.assertEqual(audit.corpus_index(self.source, run)["indexed_count"], 1)
        self.assertTrue((run / "corpus-manifest.json").exists())

    def test_output_symlink_is_not_followed(self):
        run = self.base / "run"
        run.mkdir()
        try:
            (run / "corpus-manifest.json").symlink_to(self.document)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are not available")
        with self.assertRaises(audit.AuditError):
            audit.corpus_index(self.source, run)
        self.assertEqual(self.document.read_bytes(), self.original)

    def test_symlink_run_directory_is_rejected(self):
        target = self.base / "real-run"
        target.mkdir()
        link = self.base / "linked-run"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are not available")
        with self.assertRaises(audit.AuditError):
            audit.corpus_index(self.source, link)
        self.assertEqual(list(target.iterdir()), [])

    def test_evidence_protects_every_declared_source_root(self):
        second = self.base / "second-corpus"
        second.mkdir()
        data = self.local_record()
        extra = copy.deepcopy(data["sources"][0])
        extra.update(source_id="S2", source_root=str(second), existence="UNRESOLVED", access_scope="none")
        extra.pop("local_path")
        data["sources"].append(extra)
        input_file = self.base / "evidence.json"
        input_file.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(audit.AuditError):
            audit.evidence_validate(input_file, second / "run")
        self.assertEqual(list(second.iterdir()), [])

    def test_duplicate_json_keys_and_input_overwrite_are_rejected(self):
        bad = self.base / "bad.json"
        bad.write_text('{"schema_version":"first","schema_version":"second"}', encoding="utf-8")
        with self.assertRaises(audit.AuditError):
            audit.read_json(bad)
        run = self.base / "run"
        run.mkdir()
        input_file = run / "evidence-ledger.json"
        original = json.dumps(self.local_record())
        input_file.write_text(original, encoding="utf-8")
        with self.assertRaises(audit.AuditError):
            audit.evidence_validate(input_file, run)
        self.assertEqual(input_file.read_text(encoding="utf-8"), original)

    def test_evidence_cli_rejects_false_pass_with_nonzero_exit(self):
        run = self.base / "invalid-run"
        completed = subprocess.run([sys.executable, str(SCRIPT), "evidence-validate", "--input",
                                    str(FIXTURES / "evidence_invalid_abstract_overclaim.json"),
                                    "--run-dir", str(run)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["record_validation"], "FAIL")
        self.assertTrue((run / "evidence-review.md").exists())

    def test_drift_is_advisory_and_preserves_manuscripts(self):
        before = self.base / "before.md"
        after = self.base / "after.md"
        terms = self.base / "terms.json"
        before.write_text("공진주체(WE)는 생득형 4I와 생성형 4I를 검토한다. [S1] 25%. (Example, 2024)\n", encoding="utf-8")
        after.write_text("공진주체는 생득형 4I를 검토한다. [S2] 75%. (Example, 2025)\n", encoding="utf-8")
        terms.write_text(json.dumps(["공진주체(WE)", "생득형 4I", "생성형 4I"], ensure_ascii=False), encoding="utf-8")
        originals = (before.read_bytes(), after.read_bytes())
        result = audit.drift_check(before, after, self.base / "drift-run", terms)
        self.assertEqual(result["result"], "ADVISORY_CHANGES_DETECTED")
        self.assertFalse(result["blocking"])
        self.assertEqual(len(result["changes"]["protected_terms"]), 2)
        self.assertTrue(result["changes"]["numbers"])
        self.assertTrue(result["changes"]["citation_tokens"])
        self.assertEqual((before.read_bytes(), after.read_bytes()), originals)

    def test_drift_cannot_overwrite_protected_terms(self):
        before = self.base / "before.md"
        after = self.base / "after.md"
        before.write_text("Synthetic 1", encoding="utf-8")
        after.write_text("Synthetic 2", encoding="utf-8")
        run = self.base / "run"
        run.mkdir()
        terms = run / "drift-ledger.json"
        terms.write_text('["Synthetic"]', encoding="utf-8")
        with self.assertRaises(audit.AuditError):
            audit.drift_check(before, after, run, terms)
        self.assertEqual(terms.read_text(encoding="utf-8"), '["Synthetic"]')


if __name__ == "__main__":
    unittest.main()
