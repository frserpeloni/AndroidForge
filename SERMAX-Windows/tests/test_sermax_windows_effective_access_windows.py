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


    def test_distinct_standard_user_token_is_denied_by_authz_and_windows(self):
        import secrets
        import string
        import win32api
        import win32net
        import win32security

        file_list_directory = 0x0001
        file_add_file = 0x0002
        file_add_subdirectory = 0x0004
        read_control = 0x00020000
        write_dac = 0x00040000
        write_owner = 0x00080000
        synchronize = 0x00100000

        username = "smx" + secrets.token_hex(6)
        alphabet = string.ascii_letters + string.digits
        password = (
            secrets.choice(string.ascii_uppercase)
            + secrets.choice(string.ascii_lowercase)
            + secrets.choice(string.digits)
            + "Aa1!"
            + "".join(secrets.choice(alphabet) for _ in range(24))
        )
        account_created = False
        token_handle = wintypes.HANDLE()

        try:
            win32net.NetUserAdd(
                None,
                1,
                {
                    "name": username,
                    "password": password,
                    "priv": 1,  # USER_PRIV_USER
                    "flags": 0x0001,  # UF_SCRIPT, conta padrão
                    "comment": "Conta temporária de teste SERMAX ACL",
                },
            )
            account_created = True

            advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
            logon_user = advapi32.LogonUserW
            logon_user.argtypes = [
                wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE),
            ]
            logon_user.restype = wintypes.BOOL
            if not logon_user(
                username, ".", password, 2, 0, ctypes.byref(token_handle)
            ):
                raise OSError(
                    ctypes.get_last_error(),
                    "LogonUserW não conseguiu obter token da conta padrão",
                )

            with tempfile.TemporaryDirectory(
                prefix="sermax-standard-user-access-"
            ) as parent:
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
                    | read_control | write_dac | write_owner | synchronize
                )
                directory_handle = create_file(
                    directory, access,
                    0x00000001 | 0x00000002 | 0x00000004,
                    None, 3, 0x02000000 | 0x00200000, None,
                )
                self.assertNotEqual(
                    directory_handle, ctypes.c_void_p(-1).value
                )
                try:
                    native = (
                        directory_handle.value
                        if isinstance(directory_handle, ctypes.c_void_p)
                        else directory_handle
                    )
                    process_token = win32security.OpenProcessToken(
                        win32api.GetCurrentProcess(),
                        win32security.TOKEN_QUERY,
                    )
                    try:
                        process_user = win32security.GetTokenInformation(
                            process_token, win32security.TokenUser
                        )[0]
                    finally:
                        win32api.CloseHandle(process_token)

                    standard_user = win32security.GetTokenInformation(
                        token_handle, win32security.TokenUser
                    )[0]
                    self.assertNotEqual(process_user, standard_user)

                    win32security.SetSecurityInfo(
                        native,
                        win32security.SE_FILE_OBJECT,
                        win32security.OWNER_SECURITY_INFORMATION,
                        process_user, None, None, None,
                    )

                    system_sid = win32security.ConvertStringSidToSid(
                        "S-1-5-18"
                    )
                    admins_sid = win32security.ConvertStringSidToSid(
                        "S-1-5-32-544"
                    )
                    dacl = win32security.ACL()
                    for sid in (process_user, system_sid, admins_sid):
                        dacl.AddAccessAllowedAceEx(
                            win32security.ACL_REVISION,
                            0x01 | 0x02,
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

                    descriptor = read_security_descriptor_binary(
                        directory_handle
                    )
                    for name, mask in {
                        "list_directory": file_list_directory,
                        "add_file": file_add_file,
                        "add_subdirectory": file_add_subdirectory,
                        "read_control": read_control,
                        "write_dac": write_dac,
                    }.items():
                        result = evaluate_access_for_token(
                            token_handle, descriptor, mask
                        )
                        self.assertTrue(result["api_success"], name)
                        self.assertFalse(result["granted"], name)
                        self.assertEqual(
                            result["token_source"], "real_kernel_token"
                        )

                    # A tentativa real ocorre sob impersonação do token
                    # distinto, sem executar processos auxiliares.
                    win32security.ImpersonateLoggedOnUser(token_handle)
                    try:
                        with self.assertRaises(PermissionError):
                            os.listdir(directory)
                        with self.assertRaises(PermissionError):
                            os.mkdir(os.path.join(directory, "denied-child"))
                    finally:
                        self.assertTrue(win32security.RevertToSelf())

                    self.assertEqual(os.listdir(directory), [])
                finally:
                    self.assertTrue(close(directory_handle))
        finally:
            if token_handle:
                win32api.CloseHandle(token_handle)
            if account_created:
                win32net.NetUserDel(None, username)


if __name__ == "__main__":
    unittest.main()
