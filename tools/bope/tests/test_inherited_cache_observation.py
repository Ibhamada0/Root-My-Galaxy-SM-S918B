"""Tests for GZIF inherited slab-size observation semantics.

Import the standalone audit using its actual hyphenated script path.
"""

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "linux/audit-gzif-inherited.py"
SPEC = importlib.util.spec_from_file_location("audit_gzif_inherited", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CacheObservationTests(unittest.TestCase):
    def test_cache_allocation_can_exceed_btf_struct_size(self):
        observation = MODULE.observe_file_cache_size(320, 264)
        self.assertEqual(observation["status"], "UNVERIFIED_SLAB_OBJECT_SIZE")
        self.assertTrue(observation["struct_fits_in_assumed_cache"])
        self.assertEqual(observation["inherited_cache_size"], 320)
        self.assertEqual(observation["btf_struct_file_size"], 264)

    def test_smaller_cache_is_not_mistaken_for_valid(self):
        observation = MODULE.observe_file_cache_size(128, 264)
        self.assertFalse(observation["struct_fits_in_assumed_cache"])
        self.assertEqual(observation["status"], "UNVERIFIED_SLAB_OBJECT_SIZE")

    def test_missing_btf_size_is_unverified(self):
        observation = MODULE.observe_file_cache_size(320, None)
        self.assertFalse(observation["struct_fits_in_assumed_cache"])
        self.assertEqual(observation["status"], "UNVERIFIED_SLAB_OBJECT_SIZE")


if __name__ == "__main__":
    unittest.main()
