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
