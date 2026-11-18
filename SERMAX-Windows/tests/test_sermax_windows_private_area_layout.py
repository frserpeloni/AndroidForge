from __future__ import annotations

import ctypes
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock


import sermax_windows_private_area as private_area


LAYOUT = ("staging", "backups", "journal", "logs", "locks")


def entry(name, *, is_directory=True, is_reparse_point=False):
    return SimpleNamespace(
        name=name,
        is_directory=is_directory,
        is_reparse_point=is_reparse_point,
        file_id="a" * 32,
        attributes=0x10 if is_directory else 0x80,
        end_of_file=0,
    )


def metadata(file_id):
    return {
        "is_directory": True,
        "is_reparse_point": False,
        "delete_pending": False,
        "volume_serial_number": 123,
        "file_id_128": file_id,
        "attributes": 0x10,
        "end_of_file": 0,
    }


class ExistingPrivateAreaLayoutTests(unittest.TestCase):
    def setUp(self):
        self.parent_meta = metadata("0" * 32)
        self.update_meta = metadata("1" * 32)
        self.child_meta = [metadata(str(i) * 32) for i in range(2, 7)]
        self.handles = [200, 201, 202, 203, 204, 205]
        self.api = SimpleNamespace(
            GetCurrentProcess=mock.Mock(return_value=999),
            CloseHandle=mock.Mock(return_value=None),
        )
        self.security = SimpleNamespace(
            TOKEN_QUERY=0x0008,
            TokenUser=1,
            OpenProcessToken=mock.Mock(return_value=777),
            GetTokenInformation=mock.Mock(return_value=("token-user",)),
            ConvertSidToStringSid=mock.Mock(return_value="S-1-5-21-100"),
        )
        self.modules = mock.patch.dict(
            "sys.modules",
            {"win32api": self.api, "win32security": self.security},
        )
        self.modules.start()
        self.addCleanup(self.modules.stop)

    def _run_success(self, *, staging_entries=()):
        parent_entries = (entry("_update"),)
        update_entries = tuple(entry(name) for name in LAYOUT)
        child_entries = [
            tuple(staging_entries) if name == "staging" else tuple()
            for name in LAYOUT
        ]
        query_values = [
            self.parent_meta,
            self.update_meta,
            *self.child_meta,
        ]
        open_values = iter(self.handles)
        with (
            mock.patch.object(
                private_area, "query_handle_metadata", side_effect=query_values
            ),
            mock.patch(
                "sermax_windows_directory_handle.enumerate_stable_directory_handle",
                side_effect=[parent_entries, update_entries, *child_entries],
            ),
            mock.patch(
                "sermax_windows_directory_handle.open_verified_child_component",
                side_effect=lambda *args, **kwargs: next(open_values),
            ) as opener,
            mock.patch.object(
                private_area, "_validate_created_private_directory",
                return_value={"valid": True, "mutated": False},
            ) as validator,
            mock.patch.object(private_area, "close_handle") as closer,
        ):
            layout = private_area.open_existing_private_area_layout(100)
            self.assertEqual(layout.update_handle, 200)
            self.assertEqual(set(layout.directories), set(LAYOUT))
            self.assertEqual(validator.call_count, 6)
            self.assertEqual(opener.call_count, 6)
            layout.close()
        self.assertEqual(
            closer.call_args_list,
            [mock.call(206), mock.call(205), mock.call(204),
             mock.call(203), mock.call(202), mock.call(201), mock.call(200)],
        )
        self.api.CloseHandle.assert_called_once_with(777)

    def test_opens_and_validates_complete_persistent_layout(self):
        self._run_success()

    def test_accepts_only_exclusive_staging_directories(self):
        self._run_success(
            staging_entries=(entry("stage-" + "a" * 24),)
        )

    def test_rejects_unrecognized_staging_object_and_closes_all_handles(self):
        parent_entries = (entry("_update"),)
        update_entries = tuple(entry(name) for name in LAYOUT)
        child_entries = [tuple(), (entry("unexpected.bin", is_directory=False),),
                         tuple(), tuple(), tuple()]
        query_values = [self.parent_meta, self.update_meta, *self.child_meta]
        open_values = iter(self.handles)
        with (
            mock.patch.object(private_area, "query_handle_metadata", side_effect=query_values),
            mock.patch(
                "sermax_windows_directory_handle.enumerate_stable_directory_handle",
                side_effect=[parent_entries, update_entries, *child_entries],
            ),
            mock.patch(
                "sermax_windows_directory_handle.open_verified_child_component",
                side_effect=lambda *args, **kwargs: next(open_values),
            ),
            mock.patch.object(
                private_area, "_validate_created_private_directory",
                return_value={"valid": True},
            ),
            mock.patch.object(private_area, "close_handle") as closer,
        ):
            with self.assertRaisesRegex(private_area.PrivateAreaError, "staging"):
                private_area.open_existing_private_area_layout(100)
        self.assertEqual(closer.call_count, 2)
        self.assertCountEqual(
            closer.call_args_list, [mock.call(201), mock.call(200)]
        )
        self.api.CloseHandle.assert_called_once_with(777)

    def test_rejects_incomplete_layout_before_opening_children(self):
        with (
            mock.patch.object(
                private_area, "query_handle_metadata",
                side_effect=[self.parent_meta, self.update_meta],
            ),
            mock.patch(
                "sermax_windows_directory_handle.enumerate_stable_directory_handle",
                side_effect=[(entry("_update"),), (entry("staging"),)],
            ),
            mock.patch(
                "sermax_windows_directory_handle.open_verified_child_component",
                return_value=200,
            ) as opener,
            mock.patch.object(
                private_area, "_validate_created_private_directory",
                return_value={"valid": True},
            ),
            mock.patch.object(private_area, "close_handle") as closer,
        ):
            with self.assertRaisesRegex(private_area.PrivateAreaError, "exatamente"):
                private_area.open_existing_private_area_layout(100)
        opener.assert_called_once()
        closer.assert_called_once_with(200)
        self.api.CloseHandle.assert_called_once_with(777)


@unittest.skipUnless(
    os.name == "nt" and ctypes.sizeof(ctypes.c_void_p) == 8,
    "Integração nativa exige Windows x64.",
)
class ExistingPrivateAreaLayoutWindowsTests(unittest.TestCase):
    def test_opens_real_persistent_layout_and_existing_stage_by_handles(self):
        import shutil
        from sermax_windows_handle_io import close_handle

        with tempfile.TemporaryDirectory(prefix="sermax-private-layout-") as parent_path:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            create_file = kernel32.CreateFileW
            create_file.argtypes = [
                ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_void_p,
            ]
            create_file.restype = ctypes.c_void_p
            close = kernel32.CloseHandle
            close.argtypes = [ctypes.c_void_p]
            close.restype = ctypes.c_int
            invalid = ctypes.c_void_p(-1).value
            parent = create_file(
                parent_path,
                0x0001 | 0x0004 | 0x0080 | 0x00100000,
                0x00000001 | 0x00000002 | 0x00000004,
                None, 3, 0x02000000 | 0x00200000, None,
            )
            self.assertNotIn(parent, (None, 0, invalid))
            update_handle = None
            children = []
            layout = None
            try:
                update_handle = private_area.create_private_directory_component(
                    parent, "_update"
                )
                for name in LAYOUT:
                    child = private_area.create_private_directory_component(
                        update_handle, name
                    )
                    children.append(child)
                stage = private_area.create_staging_directory_component(
                    children[0], "stage-" + "a" * 24
                )
                close_handle(stage)
                for child in reversed(children):
                    close_handle(child)
                children.clear()
                close_handle(update_handle)
                update_handle = None

                layout = private_area.open_existing_private_area_layout(parent)
                self.assertTrue(layout.validation["valid"])
                self.assertEqual(set(layout.directories), set(LAYOUT))
                self.assertEqual(
                    layout.validation["owner_sid"],
                    layout.validation["update"]["owner_sid"],
                )
            finally:
                if layout is not None:
                    layout.close()
                for child in reversed(children):
                    close_handle(child)
                if update_handle is not None:
                    close_handle(update_handle)
                self.assertTrue(close(parent))
                shutil.rmtree(parent_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
