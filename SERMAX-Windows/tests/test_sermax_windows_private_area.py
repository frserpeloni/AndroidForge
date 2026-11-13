from __future__ import annotations

import ctypes
import unittest
from unittest import mock

import sermax_windows_private_area as private_area


class PrivateAreaCreationTests(unittest.TestCase):
    def setUp(self):
        self.platform = mock.patch.object(private_area.os, "name", "nt")
        self.platform.start()
        self.addCleanup(self.platform.stop)
        self.pointer_size = mock.patch.object(
            private_area.ctypes, "sizeof", return_value=8
        )
        self.pointer_size.start()
        self.addCleanup(self.pointer_size.stop)

    def _metadata(self, **overrides):
        value = {
            "is_directory": True,
            "is_reparse_point": False,
            "delete_pending": False,
            "volume_serial_number": 1234,
            "file_id_128": "a" * 32,
        }
        value.update(overrides)
        return value

    def test_rejects_component_outside_fixed_allowlist_before_native_call(self):
        with (
            mock.patch.object(private_area, "query_handle_metadata",
                              return_value=self._metadata()),
            mock.patch.object(private_area, "_native_api") as native,
        ):
            with self.assertRaisesRegex(
                private_area.PrivateAreaError, "lista privada"
            ):
                private_area.create_private_directory_component(
                    object(), "arbitrary"
                )
        native.assert_not_called()

    def test_rejects_parent_reparse_point(self):
        with (
            mock.patch.object(
                private_area, "query_handle_metadata",
                return_value=self._metadata(is_reparse_point=True),
            ),
            mock.patch.object(private_area, "_native_api") as native,
        ):
            with self.assertRaisesRegex(
                private_area.PrivateAreaError, "diretório regular"
            ):
                private_area.create_private_directory_component(
                    object(), "_update"
                )
        native.assert_not_called()

    def test_rejects_parent_not_directory(self):
        with (
            mock.patch.object(
                private_area, "query_handle_metadata",
                return_value=self._metadata(is_directory=False),
            ),
            mock.patch.object(private_area, "_native_api") as native,
        ):
            with self.assertRaises(private_area.PrivateAreaError):
                private_area.create_private_directory_component(
                    object(), "_update"
                )
        native.assert_not_called()

    def test_creates_component_exclusively_relative_to_parent_handle(self):
        parent_handle = 100
        child_handle = 200
        calls = []

        def native_create(out_handle, access, attributes, io_status,
                          allocation, file_attributes, share, disposition,
                          options, ea, ea_length):
            calls.append({
                "access": access,
                "root": attributes._obj.RootDirectory,
                "name": attributes._obj.ObjectName.contents.Buffer,
                "attributes": file_attributes,
                "share": share,
                "disposition": disposition,
                "options": options,
            })
            out_handle._obj.value = child_handle
            return 0

        with (
            mock.patch.object(
                private_area, "query_handle_metadata",
                side_effect=[
                    self._metadata(),
                    self._metadata(file_id_128="b" * 32),
                ],
            ),
            mock.patch.object(
                private_area, "_native_api",
                return_value=(native_create, None, None),
            ),
            mock.patch.object(private_area, "close_handle") as closer,
        ):
            result = private_area.create_private_directory_component(
                parent_handle, "_update"
            )

        self.assertEqual(result.value, child_handle)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["root"], parent_handle)
        self.assertEqual(calls[0]["name"], "_update")
        self.assertEqual(calls[0]["disposition"], private_area.FILE_CREATE)
        self.assertEqual(
            calls[0]["options"],
            private_area.FILE_DIRECTORY_FILE
            | private_area.FILE_OPEN_REPARSE_POINT
            | private_area.FILE_SYNCHRONOUS_IO_NONALERT,
        )
        closer.assert_not_called()

    def test_closes_handle_when_created_object_fails_validation(self):
        child_handle = 200

        def native_create(out_handle, *args):
            out_handle._obj.value = child_handle
            return 0

        with (
            mock.patch.object(
                private_area, "query_handle_metadata",
                side_effect=[
                    self._metadata(),
                    self._metadata(is_reparse_point=True),
                ],
            ),
            mock.patch.object(
                private_area, "_native_api",
                return_value=(native_create, None, None),
            ),
            mock.patch.object(private_area, "close_handle") as closer,
        ):
            with self.assertRaisesRegex(
                private_area.PrivateAreaError, "objeto criado"
            ):
                private_area.create_private_directory_component(
                    100, "_update"
                )
        closer.assert_called_once()

    def test_rejects_created_directory_on_different_volume(self):
        child_handle = 200

        def native_create(out_handle, *args):
            out_handle._obj.value = child_handle
            return 0

        with (
            mock.patch.object(
                private_area, "query_handle_metadata",
                side_effect=[
                    self._metadata(),
                    self._metadata(volume_serial_number=9999),
                ],
            ),
            mock.patch.object(
                private_area, "_native_api",
                return_value=(native_create, None, None),
            ),
            mock.patch.object(private_area, "close_handle") as closer,
        ):
            with self.assertRaisesRegex(
                private_area.PrivateAreaError, "volume divergente"
            ):
                private_area.create_private_directory_component(
                    100, "_update"
                )
        closer.assert_called_once()

    def test_native_failure_is_reported_without_closing_invalid_handle(self):
        def native_create(out_handle, *args):
            return 0xC0000035  # STATUS_OBJECT_NAME_COLLISION

        with (
            mock.patch.object(
                private_area, "query_handle_metadata",
                return_value=self._metadata(),
            ),
            mock.patch.object(
                private_area, "_native_api",
                return_value=(native_create, None, None),
            ),
            mock.patch.object(private_area, "close_handle") as closer,
        ):
            with self.assertRaisesRegex(
                private_area.PrivateAreaError, "NTSTATUS=0xC0000035"
            ):
                private_area.create_private_directory_component(
                    100, "_update"
                )
        closer.assert_not_called()


if __name__ == "__main__":
    unittest.main()
