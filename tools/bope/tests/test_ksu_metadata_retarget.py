"""Host-only tests: GZIF donor module may only be changed at vermagic."""

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "linux/check-gzif-ksu-retarget.py"
SPEC = importlib.util.spec_from_file_location("check_gzif_ksu_retarget", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MetadataOnlyRetargetTests(unittest.TestCase):
    def test_identical_length_only_one_vermagic_string_changes(self):
        source = (
            b"\x7fELF\x00padding\x00vermagic="
            + MODULE.DONOR_RELEASE.encode("ascii")
            + b" SMP preempt mod_unload modversions aarch64\x00tail"
        )
        updated = MODULE.expected_metadata_only_copy(source)
        self.assertEqual(len(updated), len(source))
        self.assertEqual(
            updated,
            source.replace(
                ("vermagic=" + MODULE.DONOR_RELEASE).encode("ascii"),
                ("vermagic=" + MODULE.TARGET_RELEASE).encode("ascii"),
                1,
            )
        )
        self.assertNotEqual(updated, source)

    def test_missing_donor_vermagic_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.expected_metadata_only_copy(b"unrelated kernel module")

    def test_duplicate_donor_vermagic_is_rejected(self):
        tag = ("vermagic=" + MODULE.DONOR_RELEASE).encode("ascii")
        with self.assertRaises(ValueError):
            MODULE.expected_metadata_only_copy(tag + b"\x00" + tag)


if __name__ == "__main__":
    unittest.main()
