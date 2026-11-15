import hashlib
import multiprocessing
import json
import tempfile
import unittest
import os
import subprocess
from pathlib import Path

from sermax_installer_core import PackageError, _installation_lock, _revalidate_install_path, detect_installation, install_package, load_package, package_snapshot, preflight


def write_package(root: Path, files: dict[str, str], preserve=None):
    entries = []
    for name, content in files.items():
        path = root / "payload" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        entries.append({
            "source": f"payload/{name}",
            "target": name,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "size_bytes": len(content.encode("utf-8")),
        })
    (root / "manifest.json").write_text(json.dumps({
        "schema_version": 1,
        "version": "0.1.0-test",
        "files": entries,
        "preserve_paths": preserve or ["data", "memoria_sermax.json"],
    }), encoding="utf-8")


def _hold_installation_lock_for_test(root, acquired, release):
    from pathlib import Path
    from sermax_installer_core import _installation_lock
    with _installation_lock(Path(root)):
        acquired.set()
        release.wait(10)


class InstallerCoreTests(unittest.TestCase):
    def test_installation_lock_blocks_another_process_and_releases_on_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "SERMAX"
            destination.mkdir()
            context = multiprocessing.get_context("spawn")
            acquired = context.Event()
            release = context.Event()
            worker = context.Process(
                target=_hold_installation_lock_for_test,
                args=(str(destination), acquired, release),
            )
            worker.start()
            try:
                self.assertTrue(acquired.wait(8), "processo auxiliar não adquiriu o lock")
                with self.assertRaisesRegex(PackageError, "outra instalação"):
                    with _installation_lock(destination):
                        pass
            finally:
                release.set()
                worker.join(8)
                if worker.is_alive():
                    worker.terminate()
                    worker.join(3)
            self.assertEqual(worker.exitcode, 0)
            with _installation_lock(destination):
                self.assertTrue((destination / ".sermax-install.lock").is_file())

    def test_existing_malformed_lock_metadata_is_replaced_after_lock_acquisition(self):
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "SERMAX"
            destination.mkdir()
            lock_path = destination / ".sermax-install.lock"
            lock_path.write_bytes(b"stale non-json metadata")
            with _installation_lock(destination):
                self.assertTrue(lock_path.is_file())
            metadata = json.loads(lock_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["pid"], os.getpid())
            self.assertIn("started_at_utc", metadata)

    def test_installation_lock_rejects_symlink_lock_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            destination = base / "SERMAX"
            outside = base / "outside.lock"
            destination.mkdir()
            outside.write_text("external", encoding="utf-8")
            lock_path = destination / ".sermax-install.lock"
            try:
                lock_path.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("O sistema não permite criar links simbólicos neste ambiente.")
            with self.assertRaises(PackageError):
                with _installation_lock(destination):
                    pass
            self.assertEqual(outside.read_text(encoding="utf-8"), "external")

    def test_preflight_validates_package_without_installing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/start.txt": "SERMAX"})
            result = preflight(package, destination)
            self.assertEqual(result["file_count"], 1)
            self.assertFalse((destination / "app/start.txt").exists())

    def test_install_rejects_package_changed_after_confirmation_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/start.txt": "confirmed"})
            snapshot = package_snapshot(package, destination)
            (package / "payload" / "app" / "start.txt").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(PackageError, "mudou depois da confirmação"):
                install_package(package, destination, expected_snapshot=snapshot)
            self.assertFalse((destination / "app" / "start.txt").exists())

    def test_install_rejects_destination_changed_after_confirmation_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/start.txt": "confirmed"})
            snapshot = package_snapshot(package, destination)
            other_destination = root / "OTHER"
            with self.assertRaisesRegex(PackageError, "mudou depois da confirmação"):
                install_package(package, other_destination, expected_snapshot=snapshot)
            self.assertFalse((other_destination / "app" / "start.txt").exists())

    def test_install_copies_only_manifest_files_and_preserves_user_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/start.txt": "new version"})
            (destination / "data").mkdir(parents=True)
            (destination / "data" / "history.db").write_text("keep", encoding="utf-8")
            (destination / "memoria_sermax.json").write_text("memory", encoding="utf-8")
            result = install_package(package, destination)
            self.assertEqual(result["status"], "success")
            self.assertEqual((destination / "app/start.txt").read_text(), "new version")
            self.assertEqual((destination / "data" / "history.db").read_text(), "keep")
            self.assertEqual((destination / "memoria_sermax.json").read_text(), "memory")

    def test_existing_program_file_is_backed_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/core.txt": "new"})
            target = destination / "app/core.txt"
            target.parent.mkdir(parents=True)
            target.write_text("old", encoding="utf-8")
            result = install_package(package, destination)
            self.assertEqual(target.read_text(), "new")
            backup = Path(result["backup_directory"]) / "app/core.txt"
            self.assertEqual(backup.read_text(), "old")

    def test_revalidate_rejects_path_outside_install_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "SERMAX"
            outside = Path(tmp) / "outside"
            root.mkdir()
            outside.mkdir()
            with self.assertRaisesRegex(PackageError, "saiu da pasta"):
                _revalidate_install_path(root, outside / "file.txt")

    def test_revalidate_rejects_symlink_in_destination_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "SERMAX"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            link = root / "linked"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("O sistema não permite criar links simbólicos neste ambiente.")
            with self.assertRaises(PackageError):
                _revalidate_install_path(root, link / "file.txt")

    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package"
            package.mkdir()
            write_package(package, {"app.txt": "x"})
            manifest = json.loads((package / "manifest.json").read_text())
            manifest["files"][0]["target"] = "../outside.txt"
            (package / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(PackageError):
                load_package(package)

    def test_rejects_modified_package_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package"
            package.mkdir()
            write_package(package, {"app.txt": "original"})
            (package / "payload" / "app.txt").write_text("tampered")
            with self.assertRaises(PackageError):
                load_package(package)

    def test_rejects_installer_metadata_as_package_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = root / "package"
            package.mkdir()
            write_package(package, {"app.txt": "x"})
            manifest = json.loads((package / "manifest.json").read_text())
            manifest["files"][0]["target"] = ".sermax-install.json"
            (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(PackageError):
                load_package(package)

    def test_failure_after_marker_replace_restores_program_and_previous_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/core.txt": "new"})
            target = destination / "app/core.txt"
            target.parent.mkdir(parents=True)
            target.write_text("old", encoding="utf-8")
            marker = destination / ".sermax-install.json"
            marker.write_text('{"schema_version": 1, "version": "old"}', encoding="utf-8")
            previous_marker = marker.read_text(encoding="utf-8")

            def fail_after_marker(phase, current, total, name):
                if phase == "complete":
                    raise RuntimeError("simulated post-marker failure")

            with self.assertRaisesRegex(RuntimeError, "simulated post-marker failure"):
                install_package(package, destination, progress=fail_after_marker)

            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            self.assertEqual(marker.read_text(encoding="utf-8"), previous_marker)

    def test_failure_during_file_replacement_rolls_back_all_completed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/one.txt": "new-one", "app/two.txt": "new-two"})
            first = destination / "app/one.txt"
            second = destination / "app/two.txt"
            first.parent.mkdir(parents=True)
            first.write_text("old-one", encoding="utf-8")
            second.write_text("old-two", encoding="utf-8")

            def fail_after_first_replacement(phase, current, total, name):
                if phase == "installing" and current == 1:
                    raise RuntimeError("simulated replacement failure")

            with self.assertRaisesRegex(RuntimeError, "simulated replacement failure"):
                install_package(package, destination, progress=fail_after_first_replacement)

            self.assertEqual(first.read_text(encoding="utf-8"), "old-one")
            self.assertEqual(second.read_text(encoding="utf-8"), "old-two")


    def test_os_replace_failure_on_second_program_file_restores_first(self):
        from unittest.mock import patch
        import sermax_installer_core

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/one.txt": "new-one", "app/two.txt": "new-two"})
            first = destination / "app/one.txt"
            second = destination / "app/two.txt"
            first.parent.mkdir(parents=True)
            first.write_text("old-one", encoding="utf-8")
            second.write_text("old-two", encoding="utf-8")
            real_replace = os.replace
            calls = {"count": 0}

            def fail_second_replace(source, target):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("simulated second os.replace failure")
                return real_replace(source, target)

            with patch.object(sermax_installer_core.os, "replace", side_effect=fail_second_replace):
                with self.assertRaisesRegex(OSError, "second os.replace failure"):
                    install_package(package, destination)

            self.assertEqual(first.read_text(encoding="utf-8"), "old-one")
            self.assertEqual(second.read_text(encoding="utf-8"), "old-two")

    def test_rejects_manifest_size_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "package"
            package.mkdir()
            write_package(package, {"app.txt": "content"})
            manifest = json.loads((package / "manifest.json").read_text())
            manifest["files"][0]["size_bytes"] += 1
            (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(PackageError, "Tamanho divergente"):
                load_package(package)

    def test_rejects_non_hex_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "package"
            package.mkdir()
            write_package(package, {"app.txt": "content"})
            manifest = json.loads((package / "manifest.json").read_text())
            manifest["files"][0]["sha256"] = "z" * 64
            (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(PackageError, "SHA-256 inválido"):
                load_package(package)

    def test_rejects_windows_reserved_target_names(self):
        for target in ("CON.txt", "folder/NUL", "bad:name.txt", "trailing./file"):
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                package = Path(tmp) / "package"
                package.mkdir()
                write_package(package, {"app.txt": "content"})
                manifest = json.loads((package / "manifest.json").read_text())
                manifest["files"][0]["target"] = target
                (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(PackageError):
                    load_package(package)

    def test_rejects_conflicting_parent_and_child_targets_case_insensitively(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp) / "package"
            package.mkdir()
            write_package(package, {"one.txt": "one", "two.txt": "two"})
            manifest = json.loads((package / "manifest.json").read_text())
            manifest["files"][0]["target"] = "App"
            manifest["files"][1]["target"] = "app/child.txt"
            (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(PackageError, "conflitante"):
                load_package(package)

    def test_failed_rollback_keeps_recovery_backup_and_reports_it(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/core.txt": "new"})
            target = destination / "app/core.txt"
            target.parent.mkdir(parents=True)
            target.write_text("old", encoding="utf-8")
            original_copy2 = __import__("shutil").copy2
            calls = {"count": 0}

            def fail_during_restore(source, dest, *args, **kwargs):
                calls["count"] += 1
                if calls["count"] == 3:
                    raise OSError("simulated restore disk failure")
                return original_copy2(source, dest, *args, **kwargs)

            def fail_after_replace(phase, current, total, name):
                if phase == "installing":
                    raise RuntimeError("simulated post-replacement failure")

            with patch("sermax_installer_core.shutil.copy2", side_effect=fail_during_restore):
                with self.assertRaisesRegex(RuntimeError, "post-replacement") as caught:
                    install_package(package, destination, progress=fail_after_replace)

            backups = list((destination / ".sermax-backups").rglob("core.txt"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "old")
            self.assertTrue(any("rollback incompleto" in note for note in getattr(caught.exception, "__notes__", [])))


    def test_staging_failure_keeps_original_target_and_backup(self):
        from unittest.mock import patch
        import shutil

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/core.txt": "new"})
            target = destination / "app/core.txt"
            target.parent.mkdir(parents=True)
            target.write_text("old", encoding="utf-8")
            original_copy2 = shutil.copy2
            calls = {"count": 0}

            def fail_source_staging(source, dest, *args, **kwargs):
                calls["count"] += 1
                if calls["count"] == 2:
                    raise OSError("simulated staging failure")
                return original_copy2(source, dest, *args, **kwargs)

            with patch("sermax_installer_core.shutil.copy2", side_effect=fail_source_staging):
                with self.assertRaisesRegex(OSError, "staging failure"):
                    install_package(package, destination)

            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            backups = list((destination / ".sermax-backups").rglob("core.txt"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(encoding="utf-8"), "old")

    def test_marker_write_failure_restores_replaced_program_file_and_marker(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / "package", root / "SERMAX"
            package.mkdir()
            write_package(package, {"app/core.txt": "new"})
            target = destination / "app/core.txt"
            target.parent.mkdir(parents=True)
            target.write_text("old", encoding="utf-8")
            destination.mkdir(exist_ok=True)
            marker = destination / ".sermax-install.json"
            original_marker = '{"schema_version":1,"version":"old"}'
            marker.write_text(original_marker, encoding="utf-8")
            original_write_text = Path.write_text

            def fail_marker_write(path, data, *args, **kwargs):
                if path.name == ".sermax-install.json.tmp":
                    raise OSError("simulated marker write failure")
                return original_write_text(path, data, *args, **kwargs)

            with patch.object(Path, "write_text", fail_marker_write):
                with self.assertRaisesRegex(OSError, "marker write failure"):
                    install_package(package, destination)

            self.assertEqual(target.read_text(encoding="utf-8"), "old")
            self.assertEqual(marker.read_text(encoding="utf-8"), original_marker)

    def test_rejects_installation_marker_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / 'package', root / 'SERMAX'
            package.mkdir()
            destination.mkdir()
            write_package(package, {'app.txt': 'new'})
            outside = root / 'outside-marker.json'
            outside.write_text('{"schema_version":1,"version":"external"}', encoding='utf-8')
            marker = destination / '.sermax-install.json'
            try:
                marker.symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest('O sistema não permite criar links simbólicos neste ambiente.')
            with self.assertRaises(PackageError):
                detect_installation(destination)

    @unittest.skipUnless(os.name == 'nt', 'Junction é específico do Windows.')
    def test_rejects_windows_junction_in_install_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package, destination = root / 'package', root / 'SERMAX'
            package.mkdir()
            write_package(package, {'app/child.txt': 'new'})
            external = root / 'external'
            external.mkdir()
            junction = destination / 'app'
            destination.mkdir()
            result = subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(external)], capture_output=True, text=True, check=False)
            if result.returncode != 0:
                self.skipTest('Runner Windows não permitiu criar junction.')
            with self.assertRaises(PackageError):
                install_package(package, destination)

    def test_rejects_package_targets_that_overwrite_user_data(self):
        protected_targets = [
            "memoria_sermax.json",
            "memoria_neural_pestinha.json",
            "data/history.sqlite3",
            "config/settings.json",
            "credentials/token.json",
            "secrets/api-key.txt",
            ".sermax-install.lock",
        ]
        for target in protected_targets:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                package = root / "package"
                package.mkdir()
                write_package(package, {"payload.txt": "x"})
                manifest = json.loads((package / "manifest.json").read_text())
                manifest["files"][0]["target"] = target
                (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(PackageError):
                    load_package(package)


if __name__ == "__main__":
    unittest.main()
