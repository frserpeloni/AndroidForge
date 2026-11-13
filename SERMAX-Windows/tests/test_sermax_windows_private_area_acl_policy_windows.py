from __future__ import annotations

import ctypes
import os
import tempfile
import unittest
from ctypes import wintypes

from sermax_windows_acl_inspection import inspect_directory_acl
from sermax_windows_directory_handle import enumerate_stable_directory_handle
from sermax_windows_handle_io import close_handle, query_handle_metadata
from sermax_windows_private_area_acl_policy import validate_private_area_acl

@unittest.skipUnless(os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
                     "Exige Windows x64 nativo.")
class PrivateAreaAclPolicyWindowsIntegrationTests(unittest.TestCase):
    """Valida leitura da política em diretório descartável, nunca na instalação."""

    def test_reads_back_exact_protected_acl_from_same_retained_handle(self):
        import win32security

        with tempfile.TemporaryDirectory(prefix="sermax-acl-policy-") as parent:
            directory = os.path.join(parent, "private-area")
            os.mkdir(directory)

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                wintypes.HANDLE,
            ]
            create_file.restype = wintypes.HANDLE
            close = kernel32.CloseHandle
            close.argtypes = [wintypes.HANDLE]
            close.restype = wintypes.BOOL

            access = (
                0x0001       # FILE_LIST_DIRECTORY
                | 0x0080     # FILE_READ_ATTRIBUTES
                | 0x00020000 # READ_CONTROL
                | 0x00040000 # WRITE_DAC, somente no diretório temporário
                | 0x00100000 # SYNCHRONIZE
            )
            handle = create_file(
                directory, access,
                0x00000001 | 0x00000002 | 0x00000004,
                None, 3, 0x02000000 | 0x00200000, None,
            )
            invalid = ctypes.c_void_p(-1).value
            self.assertNotEqual(handle, invalid)

            try:
                native = handle.value if isinstance(handle, ctypes.c_void_p) else handle
                initial = win32security.GetSecurityInfo(
                    native,
                    win32security.SE_FILE_OBJECT,
                    win32security.OWNER_SECURITY_INFORMATION,
                )
                owner = initial.GetSecurityDescriptorOwner()
                owner = owner[0] if isinstance(owner, tuple) else owner
                owner_sid = win32security.ConvertSidToStringSid(owner)

                system_sid = win32security.ConvertStringSidToSid("S-1-5-18")
                admins_sid = win32security.ConvertStringSidToSid("S-1-5-32-544")
                dacl = win32security.ACL()
                flags = 0x01 | 0x02  # OBJECT_INHERIT | CONTAINER_INHERIT
                for sid in (owner, system_sid, admins_sid):
                    dacl.AddAccessAllowedAceEx(
                        win32security.ACL_REVISION,
                        flags,
                        0x001F01FF,  # FILE_ALL_ACCESS
                        sid,
                    )

                win32security.SetSecurityInfo(
                    native,
                    win32security.SE_FILE_OBJECT,
                    (
                        win32security.DACL_SECURITY_INFORMATION
                        | win32security.PROTECTED_DACL_SECURITY_INFORMATION
                    ),
                    None, None, dacl, None,
                )

                # Todas as consultas usam o mesmo handle, mantido aberto.
                inspection = inspect_directory_acl(handle)
                metadata = query_handle_metadata(handle)
                entries = [
                    entry
                    for entry in enumerate_stable_directory_handle(handle)
                    if entry.name not in {".", ".."}
                ]
                identity = {
                    "volume_serial_number": metadata["volume_serial_number"],
                    "file_id_128": metadata["file_id_128"],
                }

                result = validate_private_area_acl(
                    inspection,
                    expected_owner_sid=owner_sid,
                    expected_volume_serial=metadata["volume_serial_number"],
                    expected_file_id_128=metadata["file_id_128"],
                    directory_identity=identity,
                    directory_entries=entries,
                )

                self.assertTrue(result["valid"])
                self.assertTrue(result["directory_empty"])
                self.assertTrue(result["dacl_protected"])
                self.assertFalse(result["effective_access_evaluated"])
                self.assertFalse(result["mutated"])
                self.assertEqual(len(result["trustee_sids"]), 3)
            finally:
                self.assertTrue(close(handle))


if __name__ == "__main__":
    unittest.main()
