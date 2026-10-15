"""Source-only regression checks for the GZIF temporary-root helper fuse.

These tests never execute Android binaries, request root, or modify a device.
"""
from pathlib import Path
import tempfile
import unittest

from tools.linux.gzif_root_helper_guard import (
    GZIF_FUSE_SECONDS,
    apply_helper_overlay,
    patch_gzif_root_helper,
)

ROOT = Path(__file__).resolve().parents[3]
DONOR = ROOT / "targets/zzi8-WIP/helper/su_daemon.c"


class GzifRootHelperGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.donor = DONOR.read_text()

    def test_chmod_failure_closes_socket_and_attempts_selinux_recovery(self):
        guarded = patch_gzif_root_helper(self.donor)
        chmod_branch = guarded.split(
            "if (chmod(BOOTSTRAP_SOCK_PATH, 0666) != 0) {", 1
        )[1].split("\n  }", 1)[0]
        self.assertIn("close(fd);", chmod_branch)
        self.assertIn("unlink(BOOTSTRAP_SOCK_PATH);", chmod_branch)
        self.assertIn("(void)restore_selinux_enforcing();", chmod_branch)
        self.assertIn("return 135;", chmod_branch)
        self.assertNotIn(
            "  chmod(BOOTSTRAP_SOCK_PATH, 0666);\n\n  for (;;)",
            guarded,
        )

    def test_bounded_listener_and_independent_fuse_are_retained(self):
        guarded = patch_gzif_root_helper(self.donor)
        self.assertEqual(GZIF_FUSE_SECONDS, 180)
        for marker in (
            "gzif_start_selinux_watcher(deadline_ms)",
            "poll(&pfd, 1",
            "if (gzif_monotonic_ms() >= deadline_ms) break;",
            "unlink(BOOTSTRAP_SOCK_PATH);",
            "stage=gzif-selinux-fuse daemon-expired enforcing=",
            "stage=gzif-selinux-fuse watchdog enforcing=",
        ):
            self.assertIn(marker, guarded)

    def test_fails_closed_when_socket_mode_anchor_changes(self):
        modified = self.donor.replace(
            "  chmod(BOOTSTRAP_SOCK_PATH, 0666);",
            "  chmod(BOOTSTRAP_SOCK_PATH, 0600);",
            1,
        )
        self.assertNotEqual(modified, self.donor)
        # The earlier bind/listen anchor also contains this chmod call,
        # so either guard must reject any source drift before output.
        with self.assertRaises(ValueError):
            patch_gzif_root_helper(modified)

    def test_donor_unchanged_and_double_overlay_refused(self):
        guarded = patch_gzif_root_helper(self.donor)
        self.assertNotEqual(guarded, self.donor)
        self.assertIn(
            "  chmod(BOOTSTRAP_SOCK_PATH, 0666);", self.donor
        )
        with self.assertRaisesRegex(ValueError, "already contains a fuse"):
            patch_gzif_root_helper(guarded)

    def test_pre_watchdog_umh_failure_paths_attempt_enforcing_restore(self):
        guarded = patch_gzif_root_helper(self.donor)
        umh = guarded.split(
            "static int binfmt_umh_main(int argc, char **argv) {", 1
        )[1].split("static int umh_main(", 1)[0]
        expected = (
            "if (geteuid() == 0) (void)restore_selinux_enforcing();\n"
            "    return 124;",
            "(void)restore_selinux_enforcing();\n    return 125;",
            "if (daemon < 0) {\n"
            "    (void)restore_selinux_enforcing();\n    return 126;",
            "if (setsid() < 0) {\n"
            "    (void)restore_selinux_enforcing();\n    _exit(127);",
        )
        for snippet in expected:
            self.assertIn(snippet, umh)

    def test_umh_pre_watchdog_source_drift_is_fail_closed(self):
        changed = self.donor.replace(
            "  if (daemon < 0) {\n    return 126;\n  }",
            "  if (daemon < 0) {\n    return 128;\n  }",
            1,
        )
        self.assertNotEqual(changed, self.donor)
        with self.assertRaisesRegex(ValueError, "daemon fork failure"):
            patch_gzif_root_helper(changed)

    def test_apply_only_to_a_disposable_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "su_daemon.c"
            copy.write_text(self.donor)
            report = apply_helper_overlay(copy.parent)
            self.assertEqual(
                report["mode"], "GZIF_TEMP_ROOT_SELINUX_FUSE_HOST_SOURCE_ONLY"
            )
            self.assertEqual(report["device_execution"], "NOT_PERFORMED")
            self.assertIn("return 135;", copy.read_text())
            self.assertEqual(DONOR.read_text(), self.donor)


if __name__ == "__main__":
    unittest.main()
