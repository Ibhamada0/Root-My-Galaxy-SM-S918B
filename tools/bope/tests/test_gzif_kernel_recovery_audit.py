"""Read-only recovery-gate checks; these tests NEVER run BOPE or ADB."""
from pathlib import Path
import unittest

from tools.linux.audit_gzif_kernel_recovery import (
    ORCHESTRATOR, UMH, STATUS, evaluate,
)


class GzifKernelRecoveryAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orchestrator = Path(ORCHESTRATOR).read_text()
        cls.umh = Path(UMH).read_text()

    def test_reports_four_open_recovery_blockers(self):
        report = evaluate(self.orchestrator, self.umh)
        self.assertEqual(report["status"], STATUS)
        self.assertFalse(report["device_io"])
        self.assertEqual(report["blockers"], 4)
        cases = {
            x["id"]: x["classification"] for x in report["findings"]
        }
        self.assertEqual(cases["FOPS_FALLBACK_LOG_ONLY"], "BLOCKER")
        self.assertEqual(cases["PIPE_INSTALL_FAILURE_AFTER_MUTATION"], "BLOCKER")
        self.assertEqual(cases["UMH_TIMEOUT_STATIC_PATH_PINNED"], "BLOCKER")
        self.assertEqual(cases["SELINUX_SUCCESS_LIFETIME_GAP"], "BLOCKER")
        self.assertEqual(cases["FOPS_PIPE_READBACK"], "PARTIAL_GUARD")
        self.assertEqual(cases["NO_RETRY_AFTER_MUTATION"], "PARTIAL_GUARD")

    def test_source_drift_does_not_falsely_clear_blockers(self):
        modified = self.orchestrator.replace(
            'oss_diag_checkpoint("fops-recovery-reboot-required");',
            'oss_diag_checkpoint("fops-recovery-guaranteed");',
            1,
        )
        self.assertNotEqual(modified, self.orchestrator)
        with self.assertRaisesRegex(ValueError, "fops_reboot_only"):
            evaluate(modified, self.umh)

    def test_umh_cleanup_anchor_drift_is_rejected(self):
        modified = self.umh.replace(
            "  if (!result && selinux_changed) {",
            "  if (result && selinux_changed) {",
            1,
        )
        self.assertNotEqual(modified, self.umh)
        with self.assertRaisesRegex(ValueError, "selinux_only_restored_on_failure"):
            evaluate(self.orchestrator, modified)


if __name__ == "__main__":
    unittest.main()
