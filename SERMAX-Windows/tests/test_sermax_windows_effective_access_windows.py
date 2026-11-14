from __future__ import annotations

import ctypes
import os
import tempfile
import unittest
from ctypes import wintypes

from sermax_windows_effective_access import (
    evaluate_access_for_token,
    read_security_descriptor_binary,
)


@unittest.skipUnless(
    os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
    "Exige Windows x64 nativo.",
)
class EffectiveAccessWindowsIntegrationTests(unittest.TestCase):
    """Compara Authz com operações reais sob o token do processo de teste."""

    def test_current_real_token_matches_directory_operations(self):
        import win32api
        import win32security

        file_list_directory = 0x0001
        file_add_file = 0x0002
        file_add_subdirectory = 0x0004
        file_delete_child = 0x0040
        read_control = 0x00020000
        write_dac = 0x00040000
        write_owner = 0x00080000
        synchronize = 0x00100000

        with tempfile.TemporaryDirectory(prefix="sermax-effective-access-") as parent:
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
                file_list_directory | file_add_file | file_add_subdirectory
                | file_delete_child | read_control | write_dac | write_owner
                | synchronize
            )
            handle = create_file(
                directory, access,
                0x00000001 | 0x00000002 | 0x00000004,
                None, 3, 0x02000000 | 0x00200000, None,
            )
            invalid = ctypes.c_void_p(-1).value
            self.assertNotEqual(handle, invalid)

            token = None
            try:
                native = handle.value if isinstance(handle, ctypes.c_void_p) else handle
                token = win32security.OpenProcessToken(
                    win32api.GetCurrentProcess(), win32security.TOKEN_QUERY
                )
                process_user = win32security.GetTokenInformation(
                    token, win32security.TokenUser
                )[0]

                win32security.SetSecurityInfo(
                    native,
                    win32security.SE_FILE_OBJECT,
                    win32security.OWNER_SECURITY_INFORMATION,
                    process_user, None, None, None,
                )

                system_sid = win32security.ConvertStringSidToSid("S-1-5-18")
                admins_sid = win32security.ConvertStringSidToSid("S-1-5-32-544")
                dacl = win32security.ACL()
                inherit_flags = 0x01 | 0x02
                for sid in (process_user, system_sid, admins_sid):
                    dacl.AddAccessAllowedAceEx(
                        win32security.ACL_REVISION,
                        inherit_flags,
                        0x001F01FF,
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

                descriptor = read_security_descriptor_binary(handle)
                checks = {
                    "list_directory": file_list_directory,
                    "add_file": file_add_file,
                    "add_subdirectory": file_add_subdirectory,
                    "delete_child": file_delete_child,
                    "read_control": read_control,
                    "write_dac": write_dac,
                }
                results = {}
                for name, mask in checks.items():
                    result = evaluate_access_for_token(token, descriptor, mask)
                    self.assertTrue(result["api_success"], name)
                    self.assertTrue(result["granted"], name)
                    self.assertEqual(result["token_source"], "real_kernel_token")
                    self.assertFalse(result["mutated"])
                    self.assertFalse(result["performed_io"])
                    results[name] = result

                # As operações reais abaixo usam o mesmo token do processo
                # que alimentou AuthzInitializeContextFromToken.
                self.assertEqual(os.listdir(directory), [])

                child_directory = os.path.join(directory, "child")
                os.mkdir(child_directory)

                child_file = os.path.join(directory, "probe.bin")
                with open(child_file, "xb") as stream:
                    stream.write(b"SERMAX-ACL-CHECK")
                os.unlink(child_file)
                os.rmdir(child_directory)

                self.assertEqual(os.listdir(directory), [])
                self.assertTrue(results["list_directory"]["granted"])
                self.assertTrue(results["add_file"]["granted"])
                self.assertTrue(results["add_subdirectory"]["granted"])
                self.assertTrue(results["delete_child"]["granted"])
            finally:
                if token is not None:
                    win32api.CloseHandle(token)
                self.assertTrue(close(handle))


if __name__ == "__main__":
    unittest.main()
