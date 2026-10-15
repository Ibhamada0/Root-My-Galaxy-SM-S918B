"""Safe, host-only tests for the standalone boot input adapter."""

import tempfile
import unittest
from pathlib import Path

from tools.bope.errors import BopeError
from tools.bope.standalone import inspect_standalone_boot, verify_standalone_kernel_identity


FINGERPRINT = (
    "samsung/dm3qksx/dm3q:17/CP2A.260605.016/"
    "S918NKSU8GZIF:user/release-keys"
)
DONOR = "samsung/dm3qxxx/dm3q:17/CP2A.260605.016/S918BXXUAZZI8:user/release-keys"


class StandaloneBootTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "boot.img.lz4"
        self.path.write_bytes(b"\x04\x22\x4d\x18" + b"fixture")

    def inspect(self, fingerprint=FINGERPRINT, device="dm3q"):
        return inspect_standalone_boot(
            self.path,
            donor_build="S918BXXUAZZI8",
            donor_fingerprint=DONOR,
            target_fingerprint=fingerprint,
            device=device,
            target_slug="s918ngzif",
        )

    def test_identifies_exact_target(self):
        info = self.inspect()
        self.assertEqual(info.post_build, "S918NKSU8GZIF")
        self.assertEqual(info.model, "SM-S918N")
        self.assertEqual(info.slug, "s918ngzif")
        self.assertEqual(info.android_version, "17")

    def test_accepts_matching_kernel_release(self):
        verify_standalone_kernel_identity(
            self.inspect(),
            "5.15.197-android13-8-34343818-abS918NKSU8GZIF",
            expected_release="5.15.197-android13-8-34343818-abS918NKSU8GZIF",
        )

    def test_rejects_mismatched_kernel_build(self):
        with self.assertRaises(BopeError):
            verify_standalone_kernel_identity(
                self.inspect(),
                "5.15.197-android13-8-34343818-abS918BXXUAZZI8",
            )

    def test_rejects_wrong_exact_kernel_release(self):
        with self.assertRaises(BopeError):
            verify_standalone_kernel_identity(
                self.inspect(),
                "5.15.197-android13-8-34343818-abS918NKSU8GZIF",
                expected_release="5.15.189-android13-8-33413713-abS918NKSU8GZIF",
            )

    def test_rejects_wrong_device(self):
        with self.assertRaises(BopeError):
            self.inspect(device="dm2q")

    def test_rejects_wrong_release_keys(self):
        with self.assertRaises(BopeError):
            self.inspect(FINGERPRINT.replace("release-keys", "test-keys"))

    def test_rejects_invalid_lz4(self):
        self.path.write_bytes(b"NOT-LZ4")
        with self.assertRaises(BopeError):
            self.inspect()

    def test_rejects_untrusted_slug(self):
        with self.assertRaises(BopeError):
            inspect_standalone_boot(
                self.path, donor_build="S918BXXUAZZI8",
                donor_fingerprint=DONOR, target_fingerprint=FINGERPRINT,
                device="dm3q", target_slug="../../oops",
            )


if __name__ == "__main__":
    unittest.main()
