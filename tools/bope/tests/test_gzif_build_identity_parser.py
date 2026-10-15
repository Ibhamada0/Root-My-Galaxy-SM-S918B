"""Regression tests for GZIF builder's strict generated target identity parser."""

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[2] / "linux/build-gzif-android-wip.py"
SPEC = importlib.util.spec_from_file_location("build_gzif_android_wip", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GzifBuildIdentityParserTests(unittest.TestCase):
    def test_one_line_macro(self):
        header = '#define TARGET_BUILD "S918NKSU8GZIF"\n'
        self.assertEqual(
            MODULE.parse_header_string_macro(header, "TARGET_BUILD"),
            "S918NKSU8GZIF",
        )

    def test_two_line_macro_with_backslash(self):
        header = (
            '#define TARGET_KERNEL_RELEASE \\\n'
            '  "5.15.197-android13-8-34343818-abS918NKSU8GZIF"\n'
        )
        self.assertEqual(
            MODULE.parse_header_string_macro(header, "TARGET_KERNEL_RELEASE"),
            MODULE.EXPECTED["TARGET_KERNEL_RELEASE"],
        )

    def test_two_line_fingerprint_crlf(self):
        header = (
            "#define TARGET_FINGERPRINT \\\r\n"
            f'  "{MODULE.EXPECTED["TARGET_FINGERPRINT"]}"\r\n'
        )
        self.assertEqual(
            MODULE.parse_header_string_macro(header, "TARGET_FINGERPRINT"),
            MODULE.EXPECTED["TARGET_FINGERPRINT"],
        )

    def test_missing_definition_is_error(self):
        with self.assertRaisesRegex(ValueError, "found 0"):
            MODULE.parse_header_string_macro("", "TARGET_KERNEL_RELEASE")

    def test_duplicate_definitions_are_error(self):
        value = MODULE.EXPECTED["TARGET_KERNEL_RELEASE"]
        header = (
            f'#define TARGET_KERNEL_RELEASE "{value}"\n'
            f'#define TARGET_KERNEL_RELEASE "{value}"\n'
        )
        with self.assertRaisesRegex(ValueError, "found 2"):
            MODULE.parse_header_string_macro(header, "TARGET_KERNEL_RELEASE")

    def test_other_macro_does_not_match(self):
        header = '#define TARGET_KERNEL_RELEASE_SUFFIX "not a match"\n'
        with self.assertRaisesRegex(ValueError, "found 0"):
            MODULE.parse_header_string_macro(header, "TARGET_KERNEL_RELEASE")

    def test_wrong_firmware_value_stays_wrong(self):
        header = '#define TARGET_KERNEL_RELEASE "5.15.197-wrong-build"\n'
        actual = MODULE.parse_header_string_macro(header, "TARGET_KERNEL_RELEASE")
        self.assertNotEqual(actual, MODULE.EXPECTED["TARGET_KERNEL_RELEASE"])


if __name__ == "__main__":
    unittest.main()
