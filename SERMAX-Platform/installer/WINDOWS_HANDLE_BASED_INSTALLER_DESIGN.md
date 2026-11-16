# Windows handle-based installer hardening

Status: design decision, not implementation. The installer remains blocked for distribution until the implementation and Windows validation criteria below pass.

## 1. Problem

The current installer validates paths with `lstat`, `Path.is_symlink`, and repeated path-based checks, then performs writes through `pathlib`, `shutil`, `tempfile`, and `os.replace`. An attacker able to change directory entries concurrently can replace a checked component before a later path-based operation. Rechecking narrows the race window but does not bind the operation to the object that was checked.

This affects the installation root, nested destination directories, lock file, backup tree, staging files, rollback files, and installation marker.

## 2. Decision

On Windows, implement a dedicated handle-based filesystem backend. Do not treat another path validation pass or a leaf-only `CreateFileW(FILE_FLAG_OPEN_REPARSE_POINT)` wrapper as closure of the issue.

The backend must:

1. Open and retain a handle to the installation root.
2. Resolve each child component relative to its already-open parent directory handle.
3. Set `OBJ_DONT_REPARSE` when resolving each relative name. Fail closed on any reparse traversal.
4. Open the leaf without following a reparse point, inspect its attributes/tag through the handle, and reject unexpected reparse points and object types.
5. Keep directory handles alive for the duration of the transaction. Do not reopen protected paths by concatenating absolute path strings.
6. Read, write, copy, flush, and query metadata through handles. Do not use `shutil.copy2`, `Path.write_text`, `Path.read_bytes`, `tempfile.mkstemp`, or path-based `os.replace` for protected transaction objects on Windows.
7. Rename staged files and restore backups relative to a retained destination directory handle, using `SetFileInformationByHandle` and a directory handle in `FILE_RENAME_INFO.RootDirectory`.
8. Apply the same rules to the lock, backup directory, temporary files, marker, and rollback. A partial handle-based implementation is not sufficient.
9. Keep the existing non-Windows backend separate. Do not silently downgrade Windows to the path-based backend if a native operation is unavailable or fails.

## 3. Windows API basis

The documented APIs support the required primitives:

- `NtCreateFile` accepts `OBJECT_ATTRIBUTES.RootDirectory`, allowing a name to be resolved relative to an already-open directory handle. Its `CreateOptions` includes `FILE_OPEN_REPARSE_POINT`.
- `OBJECT_ATTRIBUTES` defines `OBJ_DONT_REPARSE`. Microsoft documents that name parsing fails with `STATUS_REPARSE_POINT_ENCOUNTERED` if a reparse point is encountered.
- `CreateFileW` documents `FILE_FLAG_OPEN_REPARSE_POINT` for opening the reparse point itself, and `FILE_FLAG_BACKUP_SEMANTICS` for opening directories. This is useful for handle inspection, but a full-path `CreateFileW` call alone does not provide the required parent-handle-relative traversal.
- `SetFileInformationByHandle` supports rename operations. `FILE_RENAME_INFO.RootDirectory` accepts a directory handle when the new name is relative.

References:
- https://learn.microsoft.com/windows/win32/api/winternl/nf-winternl-ntcreatefile
- https://learn.microsoft.com/windows/win32/api/ntdef/ns-ntdef-_object_attributes
- https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-createfilew
- https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle
- https://learn.microsoft.com/windows/win32/api/winbase/ns-winbase-file_rename_info
- https://learn.microsoft.com/windows/win32/fileio/reparse-point-operations

## 4. Implementation boundaries

Create a Windows-only module, for example `windows_safe_fs.py`, with a small handle-oriented interface:

- `open_root(path)`
- `open_child_directory(parent_handle, component, create_if_missing=False)`
- `open_regular_file(parent_handle, name, access, create_mode)`
- `create_temp_file(parent_handle, prefix)`
- `copy_handle_to_handle(source_handle, destination_handle)`
- `rename_handle(source_handle, destination_directory_handle, new_name, replace_existing)`
- `delete_handle_or_entry(parent_handle, name)`
- `query_file_identity_and_attributes(handle)`
- `flush_file(handle)`

Use explicit handle ownership and deterministic close semantics. Wrap native handles in context managers. Convert NTSTATUS values to actionable installer errors. Validate all structure sizes, pointer widths, Unicode lengths, and returned handles. Keep the ctypes declarations isolated and unit-testable.

The installer transaction layer should consume this interface. It should not know or construct native structures itself.

## 5. Locking and directory lifetime

The installation lock must be created/opened relative to the retained root handle. The lock must be a regular file, not a reparse point. Acquire the OS lock on the opened file handle and retain it until commit or rollback finishes.

Retain handles for the root, backup root, timestamped backup directory, each destination parent, and staging directory while those objects are in use. Select share modes deliberately. In particular, do not grant delete sharing on directory handles whose identity must remain stable during the transaction. Document any unavoidable sharing and test it.

## 6. Transaction and recovery requirements

- Stage every new file before replacing any destination.
- Verify staged content by reading it back through the opened handle and hashing the bytes.
- Back up prior files through handles before replacement.
- Replace targets by handle-relative rename within the retained destination parent.
- Commit the marker last, also by handle-relative rename.
- On failure, restore prior files and the previous marker through the same handle-based mechanism.
- Preserve backup material when rollback is incomplete.
- Record enough transaction metadata to identify interrupted staging, backup, replacement, and rollback after process termination.
- On next launch, detect an incomplete transaction and stop for recovery. Do not silently resume or delete recovery material.
- Keep the current user-data preservation rules and package snapshot confirmation.

## 7. Required Windows tests

Run these tests on actual Windows runners, not only POSIX:

1. Repeatedly swap a destination directory with a junction while installation runs. No write may escape the retained installation root.
2. Swap or replace the lock-file entry during acquisition. The external target must remain unchanged and installation must fail closed.
3. Attempt junction substitution in the backup root, timestamped backup directory, staging directory, and marker parent.
4. Replace a destination leaf with a symlink or other reparse point between staging and commit. The installer must not follow it.
5. Rename or remove a held parent directory during the transaction. Verify the chosen sharing policy blocks unsafe replacement or the operation fails without writing outside the root.
6. Inject failures after each transaction phase and verify rollback, marker restoration, and backup retention.
7. Terminate the installer process at each durable phase, restart, and verify incomplete transaction detection and recovery behavior.
8. Verify hard links, ordinary files, directories, junctions, symbolic links, and unsupported reparse tags are handled according to an explicit policy.
9. Run concurrency tests with a second installer process and with an adversarial process.
10. Run the complete installer, package-builder, GUI policy, backend, and launcher test suites on Python 3.12 and 3.14 where supported.

## 8. Acceptance gate

The P0 item is closed only when:

- Every protected Windows filesystem operation uses retained handles and relative resolution.
- No security-sensitive operation falls back to path-based file APIs on Windows.
- All required adversarial tests pass on Windows CI.
- Crash recovery tests pass.
- The test logs and commit SHA are recorded.
- The installer security matrix and user-facing release notes describe the validated guarantees and remaining limits.

Until then, the installer must remain marked unsafe for production distribution. The Platform PR remains draft and must not be merged as a release candidate.

## 9. Explicit non-goals

This work does not authorize changes to `main`, the original `C:\\SERMAX` installation, SERMAX core, Terminal, user memory, backups, SERMAX Control, or Drive Connect. It does not authorize remote access or network exposure of the Platform API.


## 10. Adjacent audit finding: package builder

A separate review of `sermax_package_builder.py` found the same path-based pattern in the package creation pipeline. It validates source and output paths with `lstat` and repeated reparse checks, then reads and copies files through `Path.open`, `shutil.copy2`, `tempfile.mkdtemp`, and `os.replace`. A concurrent directory-entry swap can invalidate a prior check before a later operation.

This is a distinct work item from installer extraction and must not be considered fixed by the installer backend alone.

Required follow-up before treating package production as hardened:

1. Define whether package source trees and output directories are writable by untrusted concurrent processes in the supported threat model.
2. If they are, apply retained-handle and relative-name operations to source reads, staging, manifest writes, and final publication.
3. Add Windows junction/reparse race tests for both source and output trees.
4. Ensure cleanup after failure only removes the exact staging directory object created by the builder, not a path substituted after validation.
5. Record separate acceptance results for package building and package installation.

The GUI source currently labels itself: `Development preview, not a distributable installer.` Keep that status until the installer acceptance gate in section 8 passes. A secure installer backend alone does not validate the package builder.
