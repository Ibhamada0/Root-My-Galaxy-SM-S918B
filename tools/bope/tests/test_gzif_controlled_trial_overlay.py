"""Host-only checks that the GZIF guarded one-shot overlay is fail-closed.

These tests NEVER run BOPE or touch tracefs/Android.
"""
from pathlib import Path
import tempfile
import unittest

from tools.linux.gzif_controlled_trial_overlay import (
    ACK, apply_overlay, patch_orchestrator, patch_tracefs,
)

REPO = Path(__file__).resolve().parents[3]
DONOR = REPO / "targets/zzi8-WIP/brazilian-open-payload-engine/src"


class ControlledGzifTrialOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orchestrator = (DONOR / "00_orchestrator.c").read_text()
        cls.tracefs = (DONOR / "01_kernel_base_tracefs.c").read_text()

    def test_gzif_one_shot_is_explicit_and_rejects_forced_slide(self):
        result = patch_orchestrator(self.orchestrator)
        self.assertIn('int attempts = 1;', result)
        self.assertIn("GZIF_ONE_SHOT_ACK", result)
        self.assertIn(ACK, result)
        self.assertIn('getenv("SLIDE_P0_OFFSET")', result)
        self.assertIn("refusing forced/cached KASLR inputs", result)
        self.assertNotIn(
            'int attempts = env_int_clamped("EXPLOIT_ATTEMPTS", 8, 1, 0x40);',
            result,
        )


    def test_kaslr_only_bypasses_root_helper_and_mutation(self):
        patched = patch_orchestrator(self.orchestrator)
        diagnostic_start = patched.index(
            '  if (getenv("GZIF_KASLR_ONLY")) {',
            patched.index("static int do_one_attempt("),
        )
        preflight_start = patched.index("  if (!root_umh_preflight(root_umh_path))")
        mutation_start = patched.index("  uint64_t payload_base = groom_and_install_fops_object(")
        self.assertLess(diagnostic_start, preflight_start)
        self.assertLess(diagnostic_start, mutation_start)
        diag = patched[diagnostic_start:preflight_start]
        self.assertIn("kaslr_locate_via_tracefs(&base)", diag)
        self.assertIn("return 1;", diag)
        self.assertNotIn("root_umh_preflight(", diag)
        self.assertIn(
            'if (success && getenv("GZIF_KASLR_ONLY")) {',
            patched,
        )
        self.assertIn("root not attempted", patched)


    def test_kaslr_only_reports_diagnostic_not_exploit_success(self):
        patched = patch_orchestrator(self.orchestrator)
        self.assertIn(
            "stage=gzif-kaslr-child-completed root-not-attempted",
            patched,
        )
        self.assertIn(
            "stage=gzif-kaslr-resolved root-not-attempted",
            patched,
        )
        self.assertIn(
            "stage=gzif-kaslr-only-success root-not-attempted",
            patched,
        )
        self.assertIn(
            '      if (getenv("GZIF_KASLR_ONLY")) {',
            patched,
        )
        # In root path, donor's original "exploit completed" log is
        # preserved after the diagnostic-mode conditional.
        self.assertEqual(patched.count("exploit completed attempt=%d/%d"), 1)

    def test_kernel_mutation_requires_separate_ack(self):
        patched = patch_orchestrator(self.orchestrator)
        self.assertIn("GZIF_KERNEL_MUTATION_ACK", patched)
        self.assertIn("I_ACCEPT_GZIF_KERNEL_MUTATION_S918NKSU8GZIF", patched)
        self.assertIn(
            "refusing kernel mutation without separate authorization",
            patched,
        )
        self.assertLess(
            patched.index("GZIF_KERNEL_MUTATION_ACK"),
            patched.index('  int boot_quiet_sec = env_int_clamped('),
        )

    def test_donor_original_is_never_changed(self):
        patched = patch_orchestrator(self.orchestrator)
        self.assertNotEqual(patched, self.orchestrator)
        self.assertIn(
            'int attempts = env_int_clamped("EXPLOIT_ATTEMPTS", 8, 1, 0x40);',
            self.orchestrator,
        )

    def test_tracefs_overlay_has_no_global_clear_and_checks_baseline(self):
        patched = patch_tracefs(self.tracefs)
        self.assertNotIn('static const char trace[] = TRACEFS_ROOT "/trace";', patched)
        self.assertNotIn('int trace_fd = open(trace, O_WRONLY | O_TRUNC', patched)
        self.assertIn('gzif_tracefs_is_zero(tracing_on)', patched)
        self.assertIn('gzif_tracefs_is_zero(event_enable)', patched)
        self.assertIn("failed to restore 0/0 controls", patched)
        self.assertIn("gzif_tracefs_reset(tracing_on, event_enable)", patched)
        self.assertIn("prime_block_io();", patched)

    def test_gzif_kaslr_requires_votes_from_distinct_raw_pages(self):
        patched = patch_tracefs(self.tracefs)
        self.assertIn(
            "unsigned int page_votes[TARGET_KASLR_CANDIDATE_COUNT] = {0}",
            patched,
        )
        self.assertIn(
            "(void)parse_trace_page(page, (size_t)got, page_votes,",
            patched,
        )
        self.assertIn("if (!page_votes[slot]) continue;", patched)
        self.assertIn("if (votes[slot] < UINT32_MAX) votes[slot]++;", patched)
        self.assertIn("stage=gzif-kaslr-distinct-pages-quorum", patched)
        self.assertNotIn(
            "if (parse_trace_page(page, (size_t)got, votes, candidate_out))",
            patched,
        )

    def test_gzif_kaslr_capture_duration_includes_prime_io(self):
        patched = patch_tracefs(self.tracefs)
        self.assertLess(
            patched.index("uint64_t gzif_trace_started_ms = monotonic_ms();"),
            patched.index("  prime_block_io();"),
        )
        self.assertIn("stage=gzif-tracefs-live-capture-ms=", patched)
        self.assertIn(
            "gzif_trace_finished_ms - gzif_trace_started_ms",
            patched,
        )

    def test_changed_orchestrator_rejected(self):
        changed = self.orchestrator.replace(
            'int attempts = env_int_clamped("EXPLOIT_ATTEMPTS", 8, 1, 0x40);',
            "int attempts = 8;",
        )
        with self.assertRaisesRegex(ValueError, "single attempt limit"):
            patch_orchestrator(changed)

    def test_changed_tracing_block_rejected(self):
        changed = self.tracefs.replace(
            'int trace_fd = open(trace, O_WRONLY | O_TRUNC | O_CLOEXEC);',
            'int trace_fd = open(trace, O_WRONLY | O_CLOEXEC);',
        )
        with self.assertRaisesRegex(ValueError, "destructive tracefs block"):
            patch_tracefs(changed)

    def test_overlay_applies_to_disposable_copy_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "brazilian-open-payload-engine/src"
            root.mkdir(parents=True)
            for name in ("00_orchestrator.c", "01_kernel_base_tracefs.c"):
                (root / name).write_text((DONOR / name).read_text())
            result = apply_overlay(root.parent)
            self.assertEqual(result["attempts"], "1")
            self.assertEqual(result["global_trace_truncate"], "removed")
            self.assertIn("GZIF_ONE_SHOT_ACK", (root / "00_orchestrator.c").read_text())
            self.assertEqual(
                self.orchestrator, (DONOR / "00_orchestrator.c").read_text()
            )
            self.assertEqual(
                self.tracefs, (DONOR / "01_kernel_base_tracefs.c").read_text()
            )


if __name__ == "__main__":
    unittest.main()
