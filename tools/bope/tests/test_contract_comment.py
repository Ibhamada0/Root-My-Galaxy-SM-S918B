"""Host-only regression tests for generated BOPE firmware prose identity."""

import unittest

from tools.bope.contract import normalize_firmware_contract_comment


class ContractCommentTests(unittest.TestCase):
    def test_replaces_multiline_legacy_s918b_beta_comment(self):
        donor = (
            "/*\n"
            " * Firmware contract for SM-S918B / S918BXXUAZZI8, the latest One UI 9 Beta 2\n"
            " * firmware.\n"
            " * Other commentary stays.\n"
            " */\n"
            '#define TARGET_MODEL "SM-S918B"\n'
        )
        result = normalize_firmware_contract_comment(
            donor, model="SM-S918N", build="S918NKSU8GZIF"
        )
        self.assertIn(
            "Firmware contract for SM-S918N / S918NKSU8GZIF "
            "(generated WIP; device validation required).",
            result,
        )
        self.assertNotIn("latest One UI 9 Beta 2", result)
        self.assertNotIn(" * firmware.\n", result)
        self.assertIn(" * Other commentary stays.", result)
        # Macro identity is rewritten separately by derive_contract().
        self.assertIn('#define TARGET_MODEL "SM-S918B"', result)

    def test_does_not_mutate_unknown_header_comments(self):
        donor = "/*\n * Firmware identity is defined below.\n */\n"
        self.assertEqual(
            normalize_firmware_contract_comment(
                donor, model="SM-S918N", build="S918NKSU8GZIF"
            ),
            donor,
        )


if __name__ == "__main__":
    unittest.main()
