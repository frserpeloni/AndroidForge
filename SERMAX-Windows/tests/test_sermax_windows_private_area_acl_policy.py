from __future__ import annotations

import copy
import unittest

from sermax_windows_private_area_acl_policy import (
    FILE_ALL_ACCESS,
    PrivateAreaAclPolicyError,
    validate_private_area_acl,
)


OWNER = "S-1-5-21-100-200-300-1001"
SYSTEM = "S-1-5-18"
ADMINS = "S-1-5-32-544"
VOLUME = 123456789
FILE_ID = "0123456789abcdef0123456789abcdef"


def valid_inspection():
    return {
        "owner_sid": OWNER,
        "group_sid": "S-1-5-32-544",
        "dacl_state": "present",
        "dacl_protected": True,
        "dacl_auto_inherited": False,
        "dacl_auto_inherit_requested": False,
        "effective_access_evaluated": False,
        "mutated": False,
        "aces": [
            {"type": 0, "flags": 3, "mask": FILE_ALL_ACCESS, "sid": OWNER},
            {"type": 0, "flags": 3, "mask": FILE_ALL_ACCESS, "sid": SYSTEM},
            {"type": 0, "flags": 3, "mask": FILE_ALL_ACCESS, "sid": ADMINS},
        ],
    }


class PrivateAreaAclPolicyTests(unittest.TestCase):
    def validate(self, inspection=None, entries=None, **overrides):
        args = {
            "expected_owner_sid": OWNER,
            "expected_volume_serial": VOLUME,
            "expected_file_id_128": FILE_ID,
            "directory_entries": [] if entries is None else entries,
        }
        args.update(overrides)
        return validate_private_area_acl(
            valid_inspection() if inspection is None else inspection,
            **args,
        )

    def test_accepts_exact_protected_policy_and_empty_directory(self):
        result = self.validate()
        self.assertTrue(result["valid"])
        self.assertTrue(result["directory_empty"])
        self.assertFalse(result["effective_access_evaluated"])
        self.assertFalse(result["mutated"])

    def test_rejects_null_or_absent_dacl(self):
        inspection = valid_inspection()
        inspection["dacl_state"] = "null_or_absent"
        with self.assertRaisesRegex(PrivateAreaAclPolicyError, "presente"):
            self.validate(inspection)

    def test_rejects_unprotected_dacl(self):
        inspection = valid_inspection()
        inspection["dacl_protected"] = False
        with self.assertRaisesRegex(PrivateAreaAclPolicyError, "protegida"):
            self.validate(inspection)

    def test_rejects_wrong_owner(self):
        inspection = valid_inspection()
        inspection["owner_sid"] = SYSTEM
        with self.assertRaisesRegex(PrivateAreaAclPolicyError, "proprietário"):
            self.validate(inspection)

    def test_rejects_unexpected_broad_trustee(self):
        inspection = valid_inspection()
        inspection["aces"][2]["sid"] = "S-1-1-0"
        with self.assertRaises(PrivateAreaAclPolicyError):
            self.validate(inspection)

    def test_rejects_extra_ace(self):
        inspection = valid_inspection()
        inspection["aces"].append(copy.deepcopy(inspection["aces"][0]))
        with self.assertRaises(PrivateAreaAclPolicyError):
            self.validate(inspection)

    def test_rejects_deny_ace(self):
        inspection = valid_inspection()
        inspection["aces"][0]["type"] = 1
        with self.assertRaisesRegex(PrivateAreaAclPolicyError, "ACCESS_ALLOWED"):
            self.validate(inspection)

    def test_rejects_inherited_or_inherit_only_ace(self):
        for flags in (3 | 0x10, 3 | 0x08, 0):
            inspection = valid_inspection()
            inspection["aces"][0]["flags"] = flags
            with self.subTest(flags=flags):
                with self.assertRaisesRegex(PrivateAreaAclPolicyError, "herança"):
                    self.validate(inspection)

    def test_rejects_non_full_control_mask(self):
        inspection = valid_inspection()
        inspection["aces"][0]["mask"] = 0x00120089
        with self.assertRaisesRegex(PrivateAreaAclPolicyError, "Máscara"):
            self.validate(inspection)

    def test_rejects_duplicate_trustee(self):
        inspection = valid_inspection()
        inspection["aces"][2]["sid"] = SYSTEM
        with self.assertRaisesRegex(PrivateAreaAclPolicyError, "Trustee"):
            self.validate(inspection)

    def test_rejects_nonempty_directory(self):
        with self.assertRaisesRegex(PrivateAreaAclPolicyError, "vazio"):
            self.validate(entries=[{"name": "unexpected.dat"}])

    def test_rejects_volume_mismatch(self):
        with self.assertRaisesRegex(PrivateAreaAclPolicyError, "Volume"):
            self.validate(expected_volume_serial=VOLUME + 1)

    def test_rejects_file_id_mismatch(self):
        with self.assertRaisesRegex(PrivateAreaAclPolicyError, "FileId"):
            self.validate(expected_file_id_128="f" * 32)

    def test_rejects_missing_identity(self):
        inspection = valid_inspection()
        with self.assertRaisesRegex(PrivateAreaAclPolicyError, "Identidade"):
            self.validate(inspection, directory_identity=None)

    def test_rejects_invalid_file_id_format(self):
        with self.assertRaisesRegex(PrivateAreaAclPolicyError, "128 bits"):
            self.validate(expected_file_id_128="not-a-file-id")


if __name__ == "__main__":
    unittest.main()
