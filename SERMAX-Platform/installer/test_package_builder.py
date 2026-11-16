import hashlib
import json
import tempfile
import unittest
import subprocess
import os
from pathlib import Path

from sermax_package_builder import BuildError, build_package, parse_mapping


class PackageBuilderTests(unittest.TestCase):
    def test_builds_manifest_with_real_hashes_and_only_selected_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "app.py").write_text("print('SERMAX')", encoding="utf-8")
            (source / "private.db").write_text("must not ship", encoding="utf-8")
            output = root / "package"
            result = build_package(source, output, "1.2.3", [(Path("app.py"), Path("Platform/app.py"))])
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            packaged = output / manifest["files"][0]["source"]
            expected = hashlib.sha256(packaged.read_bytes()).hexdigest()
            self.assertEqual(manifest["files"][0]["sha256"], expected)
            self.assertEqual(result["file_count"], 1)
            self.assertFalse((output / "payload" / "private.db").exists())

    def test_rejects_source_modified_during_staging(self):
        from unittest.mock import patch
        import sermax_package_builder

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            source_file = source / "app.py"
            source_file.write_text("original", encoding="utf-8")
            output = root / "package"
            real_copy = sermax_package_builder.shutil.copy2

            def copy_then_mutate(src, dst, *args, **kwargs):
                result = real_copy(src, dst, *args, **kwargs)
                Path(src).write_text("changed during staging", encoding="utf-8")
                return result

            with patch.object(sermax_package_builder.shutil, "copy2", side_effect=copy_then_mutate):
                with self.assertRaisesRegex(BuildError, "mudou durante a montagem"):
                    build_package(
                        source, output, "1",
                        [(Path("app.py"), Path("app.py"))]
                    )

            self.assertFalse(output.exists())


    @unittest.expectedFailure
    def test_known_toctou_output_parent_swap_must_not_publish_outside_output_parent(self):
        from unittest.mock import patch
        import sermax_package_builder

        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source"
            source.mkdir()
            (source / "app.py").write_text("payload", encoding="utf-8")
            output_parent = base / "staging-parent"
            output_parent.mkdir()
            held_parent = base / "staging-parent-held"
            outside = base / "outside"
            outside.mkdir()
            output = output_parent / "package"
            real_copy = sermax_package_builder.shutil.copy2
            external_write_observed = {"value": False}
            swapped = {"value": False}

            redirected_stage = None

            def swap_output_parent_then_copy(src, dst, *args, **kwargs):
                nonlocal redirected_stage
                if not swapped["value"]:
                    staging_dir = Path(dst).parents[1]
                    output_parent.rename(held_parent)
                    if os.name == "nt":
                        junction = subprocess.run(
                            ["cmd", "/c", "mklink", "/J", str(output_parent), str(outside)],
                            capture_output=True, text=True, check=False,
                        )
                        if junction.returncode != 0:
                            raise unittest.SkipTest("Runner Windows não permitiu criar junction.")
                    else:
                        output_parent.symlink_to(outside, target_is_directory=True)
                    redirected_stage = outside / staging_dir.name / "payload"
                    redirected_stage.mkdir(parents=True)
                    swapped["value"] = True
                result = real_copy(src, dst, *args, **kwargs)
                if Path(dst).resolve().parent == redirected_stage.resolve():
                    external_write_observed["value"] = True
                return result

            try:
                with patch.object(
                    sermax_package_builder.shutil,
                    "copy2",
                    side_effect=swap_output_parent_then_copy,
                ):
                    build_package(
                        source,
                        output,
                        "1",
                        [(Path("app.py"), Path("app.py"))],
                    )
            finally:
                if os.name == "nt" and output_parent.exists():
                    output_parent.rmdir()

            self.assertTrue(swapped["value"], "A troca do diretório de saída não foi executada.")
            self.assertFalse(
                external_write_observed["value"],
                "O gerador escreveu conteúdo no diretório externo após a troca do pai.",
            )

    def test_rejects_output_inside_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "app.py").write_text("x", encoding="utf-8")
            with self.assertRaises(BuildError):
                build_package(source, source / "package", "1", [(Path("app.py"), Path("app.py"))])

    def test_rejects_duplicate_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "a").write_text("a", encoding="utf-8")
            (source / "b").write_text("b", encoding="utf-8")
            with self.assertRaises(BuildError):
                build_package(source, root / "package", "1", [
                    (Path("a"), Path("app/file")),
                    (Path("b"), Path("app/file")),
                ])

    def test_rejects_parent_traversal_mapping(self):
        with self.assertRaises(BuildError):
            parse_mapping("../secrets.txt=secret.txt")


    def test_rejects_source_root_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "app.py").write_text("x", encoding="utf-8")
            alias = root / "source-alias"
            try:
                alias.symlink_to(source, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("O sistema não permite criar links simbólicos neste ambiente.")
            with self.assertRaisesRegex(BuildError, "junction ou reparse point"):
                build_package(alias, root / "package", "1", [
                    (Path("app.py"), Path("app.py"))
                ])

    def test_rejects_nested_source_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            outside = root / "outside.txt"
            source.mkdir()
            (source / "nested").mkdir()
            outside.write_text("outside", encoding="utf-8")
            try:
                (source / "nested" / "link.txt").symlink_to(outside)
            except (OSError, NotImplementedError):
                self.skipTest("O sistema não permite criar links simbólicos neste ambiente.")
            with self.assertRaisesRegex(BuildError, "Links simbólicos"):
                build_package(source, root / "package", "1", [
                    (Path("nested/link.txt"), Path("nested/link.txt"))
                ])

    @unittest.skipUnless(os.name == "nt", "Junction é específico do Windows.")
    def test_rejects_nested_source_junction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            outside = root / "outside"
            source.mkdir()
            outside.mkdir()
            (outside / "payload.txt").write_text("external", encoding="utf-8")
            junction = source / "linked"
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(junction), str(outside)],
                capture_output=True, text=True, check=False
            )
            if result.returncode != 0:
                self.skipTest("Runner Windows não permitiu criar junction.")
            with self.assertRaisesRegex(BuildError, "junctions? ou reparse points?"):
                build_package(source, root / "package", "1", [
                    (Path("linked/payload.txt"), Path("payload.txt"))
                ])

    def test_rejects_parent_child_target_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "a.txt").write_text("a", encoding="utf-8")
            (source / "b.txt").write_text("b", encoding="utf-8")
            with self.assertRaisesRegex(BuildError, "conflitante"):
                build_package(source, root / "package", "1", [
                    (Path("a.txt"), Path("App")),
                    (Path("b.txt"), Path("app/child.txt")),
                ])

    def test_refuses_to_overwrite_existing_package_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "app").write_text("x", encoding="utf-8")
            output = root / "package"
            output.mkdir()
            with self.assertRaises(BuildError):
                build_package(source, output, "1", [(Path("app"), Path("app"))])


if __name__ == "__main__":
    unittest.main()
