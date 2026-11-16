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

### Root-handle bootstrap is a separate security boundary

Do not implement `open_root(path)` as a single full-path `CreateFileW` call and then assume the resulting handle proves that every ancestor was traversed without following a reparse point. A retained handle stabilizes the object that was opened; it does not, by itself, prove that the initial path resolution selected the intended directory.

The bootstrap design must establish a trusted starting directory handle and resolve the selected installation path one component at a time relative to retained parent handles, applying `OBJ_DONT_REPARSE` to each name parse. The trusted starting point and the policy for drive roots, volume mount points, UNC paths, and user-selected directories must be explicit. If the implementation cannot establish that starting handle under the supported threat model, it must fail closed rather than fall back to ordinary full-path resolution.

Microsoft documents that `OBJECT_ATTRIBUTES.RootDirectory` makes a name relative to an existing directory handle and that `OBJ_DONT_REPARSE` rejects reparse traversal. A Microsoft Q&A response from November 3, 2026 reports successful user-mode, directory-relative testing on Windows 11 build 26200, but also notes that the documentation does not provide a complete user-mode recipe for safely acquiring an arbitrary initial root handle. Treat that report as corroborating implementation evidence, not as a platform-wide contractual guarantee. The bootstrap path therefore requires its own design review and Windows adversarial tests before the backend is considered complete.

References:
- https://learn.microsoft.com/windows/win32/api/ntdef/ns-ntdef-_object_attributes
- https://learn.microsoft.com/windows/win32/api/winternl/nf-winternl-ntcreatefile
- https://learn.microsoft.com/en-us/answers/questions/6059091/is-ntcreatefile-with-rootdirectory-race-safe-again

## 4A. API-contract blocker: do not promote the proposed NT path to a security guarantee

The proposed `NtCreateFile` + filesystem `RootDirectory` + `OBJ_DONT_REPARSE` combination is a candidate for controlled experiments, not a confirmed user-mode security contract.

Microsoft's user-mode `NtCreateFile` page documents directory-relative resolution, but its `OBJECT_ATTRIBUTES.Attributes` description lists zero or `OBJ_CASE_INSENSITIVE`. The general `OBJECT_ATTRIBUTES` page documents `OBJ_DONT_REPARSE`, but the published material does not explicitly confirm that exact flag combination as a supported, version-stable user-mode contract. A Microsoft External Staff moderator states that this remains a documentation gap and advises against relying on it as a security boundary without explicit confirmation. Successful tests on one Windows build are compatibility evidence only.

A separate Microsoft Q&A answer also states that the public documentation does not establish atomic ordering between a relative open and concurrent rename, directory replacement, or reparse-point mutation. It does not promise that the operation always resolves to the original parent or fails under every interleaving. Handle-based inspection after open is useful evidence about the object actually opened, but it does not retroactively prove safe name resolution or establish a namespace snapshot.

Consequences for SERMAX:

1. Do not mark the installer P0 as fixed solely because a prototype uses `RootDirectory` and `OBJ_DONT_REPARSE`.
2. Keep the current path-based implementation blocked for production distribution.
3. Isolate the native calls behind a backend interface and label experimental behavior explicitly. Never silently fall back to path-based operations.
4. Before claiming a security boundary, obtain a documented Microsoft support position for the required user-mode API combination and concurrency guarantees, or select a different supported architecture whose guarantees can be established.
5. Test the initial root admission, descendant opens, concurrent renames, reparse changes, sharing modes, and handle inspection independently. Passing tests demonstrate tested behavior, not an undocumented cross-version guarantee.
6. If the required guarantee cannot be established with a supported user-mode contract, stop the installer hardening effort at that boundary and report the residual risk. Do not disguise it with additional path checks.

References:
- https://learn.microsoft.com/windows/win32/api/winternl/nf-winternl-ntcreatefile
- https://learn.microsoft.com/windows/win32/api/ntdef/ns-ntdef-_object_attributes
- https://learn.microsoft.com/en-us/answers/questions/6056645/does-user-mode-ntcreatefile-support-obj-dont-repar
- https://learn.microsoft.com/en-us/answers/questions/6059091/is-ntcreatefile-with-rootdirectory-race-safe-again
- https://learn.microsoft.com/en-us/answers/questions/6052628/documented-user-mode-ntcreatefile-contract-for-fil

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


## 11. Alternative architecture under evaluation: protected destination and narrow broker

The NT handle-relative design remains blocked by the user-mode API-contract and concurrency questions in section 4A. Evaluate a different trust model before implementing native filesystem wrappers.

### 11.1 Proposed trust boundary

Separate the ordinary SERMAX user interface and package preparation process from a small Windows installation broker:

- The UI and package builder run as the interactive user and have no write permission to the protected installation directory.
- A narrowly scoped broker performs the final installation transaction against a destination whose ACL denies modification to the interactive user and ordinary untrusted processes.
- The broker runs under a dedicated service identity with only the rights required for its fixed installation directory and transaction data. Do not default to LocalSystem. Any need for LocalSystem or administrator privileges requires an explicit design justification and approval.
- The broker accepts requests over a named pipe with an explicit security descriptor. Restrict access to the intended local logon/session identity. Do not rely on the default named-pipe DACL: Microsoft documents that its default grants read access to Everyone and anonymous users.
- The broker exposes a small fixed command set. It must not accept arbitrary paths, arbitrary commands, arbitrary executable payloads, or caller-selected destination roots.
- The package is staged outside the protected destination, then independently validated by the broker before commit. Validation includes a strict manifest, allowed relative paths, file types, hashes, package identity/version, and rejection of traversal, alternate data streams, reparse points, and unexpected entries.
- The broker owns all destination paths and derives them from a fixed root plus validated manifest-relative names. The caller cannot choose a destination path.
- Service configuration and executable files are protected from modification by untrusted users. Do not grant untrusted callers SERVICE_CHANGE_CONFIG, SERVICE_STOP, or rights to modify service binaries.

This architecture changes the threat model: the primary defense against a concurrent unprivileged path attacker is that the attacker cannot modify the protected destination namespace. It does not automatically solve races in a user-writable staging area, malicious package content, broker parser bugs, compromised administrators, kernel compromise, or unsafe service configuration.

### 11.2 Windows security facts supporting the model

Windows checks requested file access against the caller's access token and the object's security descriptor. File and directory ACLs govern access, and child objects may inherit ACEs from their parent. A newly created object's default security descriptor is inherited from its parent unless explicitly supplied. These facts support a protected destination, but they do not by themselves prove that a particular installation ACL is correct or immutable against administrators.

Named pipes support explicit security descriptors and access checks against the pipe DACL. Microsoft documents that the default named-pipe DACL is broader than this broker requires, so the broker must set an explicit DACL. Microsoft also documents using the logon SID to prevent access from other logon sessions.

Microsoft recommends running a service with the minimum permissions required and using LocalSystem only when the service requires administrative privileges or must act as part of the operating system. Service rights such as SERVICE_CHANGE_CONFIG and SERVICE_STOP must not be granted to untrusted callers.

References:
- https://learn.microsoft.com/windows/win32/fileio/file-security-and-access-rights
- https://learn.microsoft.com/windows/win32/ipc/named-pipe-security-and-access-rights
- https://learn.microsoft.com/windows/win32/ad/guidelines-for-selecting-a-service-logon-account
- https://learn.microsoft.com/windows/win32/services/service-security-and-access-rights

### 11.3 Questions that must be answered before implementation

1. What exact directory is protected? A machine-wide location such as Program Files, a dedicated ProgramData location, or a per-user protected location have different ownership and update semantics.
2. Which principal owns the destination and its parent directories? Which principals receive read, execute, write, delete, WRITE_DAC, and WRITE_OWNER rights?
3. Is the attacker an unprivileged process running as the same interactive user, another local user, or both? Are administrators and kernel compromise explicitly outside scope?
4. Who creates and updates the broker service? How is its binary protected against replacement and DLL search-order attacks?
5. How does the broker authenticate the client beyond a pipe DACL? Define client token/session checks, protocol versioning, replay handling, request size limits, and authorization for each operation.
6. How does the broker verify package provenance and integrity? A hash supplied by the same untrusted caller is not an authenticity guarantee. Define whether signed packages or a separately trusted release manifest are required.
7. How are user data, configuration, memory, logs, backups, and rollback data separated from replaceable program files?
8. How are interrupted transactions recovered without following attacker-controlled staging or destination paths?

### 11.4 Required security tests

- Verify effective ACLs on the destination, every parent, broker executable, service configuration, pipe, staging area, backup area, and rollback data.
- Run a concurrent unprivileged attacker as the same interactive user and as a second local user. Confirm that destination entries and protected parent ACLs cannot be changed by either identity.
- Attempt pipe access from another user, another logon session, an anonymous client, and a process with an unexpected token.
- Fuzz the broker protocol and package manifest. Test oversized messages, malformed encodings, duplicate paths, traversal, alternate data streams, reparse points, hard links, and unexpected file types.
- Replace or mutate staged package files during validation and commit. The broker must validate the exact content it installs, not trust a prior caller-side check.
- Attempt service binary replacement, service configuration changes, unauthorized stop/start, and DLL planting.
- Inject process termination and I/O failures at every transaction phase. Verify rollback, recovery, and preservation of user data.
- Record Windows version/build, effective ACLs, test identity/SID, attack method, expected result, actual result, logs, and commit SHA.

### 11.5 Decision status

Status: architecture candidate for threat-model review only. No implementation authorized by this design note. Do not replace section 4A's API-contract blocker with an assumption that ACLs or a broker automatically make installation race-free. The protected-root premise must be demonstrated on the supported Windows configurations, including parent-directory ownership and permissions. If the intended installation destination remains writable by the same untrusted identity, this architecture does not remove the original race and must not be accepted.

No change to the original C:\\SERMAX installation, core, Terminal, memory, backups, SERMAX Control, or Drive Connect is authorized by this evaluation.


### 11.6 Refined service identity and package intake

The service identity must be selected by a least-privilege review, not by convenience. Evaluate a dedicated virtual service account such as `NT SERVICE\\SermaxInstallerBroker` and a per-service SID. Evaluate `SERVICE_SID_TYPE_RESTRICTED` where compatible with the service's required access. Microsoft documents that a restricted service SID is added to the restricted SID list and enables access control to service resources without relying on LocalSystem. This is a candidate configuration, not a pre-approved setting: validate all required file, registry, event-log, pipe, and service-control operations under the actual token.

The broker must not trust a path or hash supplied by the client as proof of package identity. Package intake must follow this sequence:

1. Authenticate and authorize the client request before accepting a package.
2. Accept a bounded package stream or open a client-supplied source under a narrowly defined policy. Do not accept arbitrary destination paths.
3. Copy the bytes into a broker-owned staging directory that the client cannot modify.
4. Compute the digest while copying, then close and reopen the broker-owned staged object under broker control and verify its size and digest.
5. Parse and validate only the broker-owned staged copy. Reject duplicate normalized paths, traversal, alternate data streams, reparse points, unsupported file types, and manifest ambiguity.
6. Verify authenticity against a trust anchor independent of the submitting client, such as a signed release manifest whose signing key is not stored in the client-writable area. A digest alone proves byte consistency, not publisher identity.
7. Install from that same broker-owned validated snapshot. Do not return to the caller's source path after validation.

The staging directory itself requires a documented owner and DACL. The broker must create it beneath a parent that untrusted clients cannot replace. If the service cannot prove that the validated bytes are the bytes later installed, package intake fails closed.

### 11.7 Provisional destination decision matrix

Do not select Program Files, ProgramData, or a per-user directory by name alone. Select based on the actual SERMAX deployment model and supported threat boundary.

| Candidate | Advantages | Risks and required proof |
|---|---|---|
| Machine-wide application directory, e.g. Program Files | Standard location for machine-wide program binaries; ordinary users should not receive write access | Requires an elevated, controlled service installation/update path; verify owner and effective ACLs for every parent and child; define admin threat exclusion |
| Dedicated machine-wide ProgramData subdirectory | Separates SERMAX data from binaries and supports service-owned state | ProgramData itself is shared; the dedicated child must have explicit protected ownership and DACL; never store executable code beside broadly writable data |
| Per-user protected directory | Avoids a machine-wide service for a single-user product | If the interactive user owns or can change the directory DACL, a compromised process under that same identity may defeat the boundary; define a distinct protected principal or reject this model |

Provisional recommendation: if the intended release is machine-wide, evaluate a dedicated service identity and a protected machine-wide application root, with user data kept in a separate user-data directory. Do not settle the exact path or ACL until the installer scope, update privilege model, and administrator threat boundary are approved. If the product is strictly per-user and the same user is in scope as an attacker, do not claim protection based solely on a directory ACL that the user can change.

### 11.8 Required evidence before architecture approval

The review package must include:

- A written adversary model naming identities in scope and explicitly excluded.
- A proposed SDDL/DACL for the service object, service executable directory, protected install root and every parent, broker staging, backup/rollback, user data, and named pipe.
- Effective access-check results for the interactive user, another standard user, the service SID, administrators, and SYSTEM.
- Service token evidence: account, service SID type, enabled privileges, restricted SIDs, and filesystem/registry access required at runtime.
- A package provenance design with a separately protected signing key or trusted release manifest, key rotation and revocation policy.
- A protocol specification with bounded framing, authentication, authorization, replay protection, and denial-of-service limits.
- Windows adversarial test logs on every supported Windows build.

Approval of this architecture is a separate decision. Documentation and research do not authorize implementation, service installation, privilege elevation, or changes to the original SERMAX environment.


### 11.9 Provisional threat model

The first supported security target for evaluation is a machine-wide Windows installation. The threat model must be explicit:

**In scope**
- A malicious or compromised process running as a standard, non-elevated interactive user.
- A different standard local user.
- A process in another logon session attempting to connect to the broker pipe.
- Concurrent modification of client-writable package input and staging locations.
- Malformed, oversized, replayed, or unauthorized broker requests.
- Attempts to modify the service binary, service configuration, protected install tree, backup tree, or transaction state without authorization.

**Out of scope for this initial target, and not claimed to be resisted**
- A local administrator or process holding equivalent administrative privileges.
- Kernel compromise, boot compromise, offline disk modification, or physical attacks.
- Compromise of the trusted release-signing key or the trusted build/release pipeline.
- A compromised Windows kernel or filesystem driver.

The administrator exclusion is material. Administrators and SYSTEM can normally take ownership or change security configuration. The product must not claim protection from a hostile administrator. If resisting administrators becomes a requirement, this broker/ACL design is insufficient by itself and requires a separate platform security architecture.

**Security objective**
An in-scope unprivileged process must not be able to modify the installed executable tree, replace a parent directory, alter broker configuration, substitute the package after validation, or influence the broker into writing outside the fixed installation root. The broker must not provide a generic privileged file-write or command-execution primitive.

### 11.10 Provisional access-control matrix

This matrix is a design target for a machine-wide installation, not an approved SDDL and not evidence of effective permissions. Replace role names with resolved SIDs only during implementation and verify the resulting security descriptors on every supported Windows build.

| Object | SYSTEM | Administrators | Broker service SID | Standard interactive users |
|---|---|---|---|---|
| Service executable and configuration | Full control | Full control for administration | Read/execute only | Read/execute only |
| Protected application root and program files | Full control | Full control for administration | Modify only where transaction requires it | Read/execute; no create, write, delete, WRITE_DAC or WRITE_OWNER |
| Broker-owned staging and transaction workspace | Full control | Full control for administration | Full control | No direct access |
| Backup and rollback workspace | Full control | Full control for administration | Minimum read/write/delete required for transaction and recovery | No direct access |
| User configuration and user documents | OS/admin policy | OS/admin policy | No broad access; explicit narrow access only if a migration requires it | User's normal per-user access |
| Broker named pipe | System administration | No implicit access unless explicitly required | Server endpoint | Current authorized logon SID receives only client connection/read/write rights needed by the protocol; no pipe-instance creation right |

Do not grant standard users ownership of the protected application root or its parents. Do not grant them WRITE_DAC, WRITE_OWNER, DELETE, FILE_DELETE_CHILD, FILE_ADD_FILE, or FILE_ADD_SUBDIRECTORY on protected directories. Audit inherited ACEs and explicit ACEs on every ancestor: a secure child DACL is not sufficient if an untrusted user can replace or rename an ancestor. Verify the owner as well as the DACL.

The service SID must receive only the rights required for the broker's operations. A restricted service SID token may require access to be granted through both the normal and restricted SID checks; test the real service token and effective access rather than assuming that adding one ACE is sufficient. The service must not share a process with unrelated services if restricted-token behavior would broaden their impact or create compatibility coupling.

For the pipe, avoid granting generic write if it also grants FILE_CREATE_PIPE_INSTANCE. Grant the precise client rights required by the protocol and reserve pipe-instance creation for the service. The server must authenticate each connection, verify the client token and logon session, authorize each request, and fail closed if impersonation or token inspection fails. If impersonating the client, always revert to the service identity in a guaranteed cleanup path before performing an authorized broker operation. Never continue privileged work after an impersonation failure.

### 11.11 Broker authorization invariants

- The destination root is a compile-time or securely provisioned installation identity, not a request field.
- The protocol contains operation identifiers and bounded data, never shell commands or arbitrary filesystem paths.
- Every request is checked against an allowlist of operations and package policy.
- The broker independently authenticates package publisher identity using a trust anchor unavailable to the interactive user. A caller-supplied hash is not a trust anchor.
- The broker copies input into service-owned staging and then validates, hashes, and installs from that exact staged snapshot.
- The broker rejects symbolic links, junctions, other reparse tags, hard-link cases not explicitly supported, alternate data streams, path traversal, duplicate normalized names, reserved device names, unsupported file types, and manifest ambiguity.
- The broker has strict message-size, file-count, total-uncompressed-size, nesting-depth, CPU-time, and transaction-time limits.
- Every transaction has a unique identifier, durable phase journal, explicit commit point, and recovery policy. The journal and recovery data are not client-writable.
- The broker does not expose a generic read-file, write-file, delete-file, move-file, or execute-file endpoint.
- Every denied request and transaction failure is logged without recording secrets or trusting caller-provided log paths.

### 11.12 Architecture approval gate

Before implementation is authorized, reviewers must approve all of the following:

1. The machine-wide threat model and administrator exclusion.
2. The exact destination path and owner/ACL design for every parent and protected object.
3. The service account, service SID type, enabled privileges, restricted SIDs, service-object DACL, and service binary protection.
4. The named-pipe protocol, DACL, logon-session validation, impersonation failure behavior, and per-operation authorization.
5. The independent package-signing trust anchor and key lifecycle.
6. The user-data separation and migration/rollback policy.
7. Windows adversarial test cases, test identities, supported OS builds, and acceptance thresholds.

Until all seven items are reviewed and explicitly approved, this remains a design proposal. No service, installer, ACL, privilege, or original SERMAX environment changes are authorized.


### 11.13 Gap audit against the current installer code

A source review of the current branch at commit `78ff8109b052492ad5f5b037a7994f0f6d65cc53` was performed against sections 11.9–11.12. This is a static code review, not a runtime test.

**The current implementation is not the broker architecture described above.**

1. `installer_gui.py` runs the installation directly in a worker thread by calling `install_package(package, destination, ...)`. The user selects both the package directory and destination directory. There is no Windows service, named-pipe server, client-token validation, service SID, or broker authorization layer in this path.
2. The GUI defaults the destination to `Path.home() / "SERMAX"`. That is a per-user destination, not the machine-wide protected root assumed by the provisional threat model.
3. `sermax_installer_core.py` accepts caller-selected `package_dir` and `install_dir` paths. It performs path-based validation and then uses `Path`, `os.open`, `shutil.copy2`, `tempfile.mkstemp`, `Path.write_text`, `Path.read_bytes`, `os.replace`, and path-based unlink operations for protected transaction objects. Rechecking paths does not bind later operations to the objects previously checked.
4. The package manifest is JSON with SHA-256 and file-size values. The current loader verifies those values against files in the package directory, but the inspected code has no signature verification, publisher identity check, trusted release manifest, or independent signing trust anchor. The hashes provide package-internal consistency, not publisher authenticity.
5. The current package builder creates the manifest and hashes, but the inspected implementation has no signing step or protected release-key workflow.
6. The current README explicitly identifies the GUI as a development preview, states that the installer is not distributable, and records that package signing and publisher verification are absent.
7. The current package format supports a caller-selected file mapping and a `preserve_paths` field. Preservation rules must be independently enforced by the trusted broker; the broker must not treat a client-authored manifest as authority to overwrite protected data or decide which user data is preserved.
8. The installer currently backs up and replaces individual files and attempts rollback. Its README correctly states that this is not a globally atomic transaction. The broker design still needs a durable transaction journal and recovery implementation.

**Required transition; do not implement until the architecture approval gate is passed**

- Treat the current GUI and core as an untrusted client/package-preparation layer. They must not receive elevated rights or write access to the protected application root.
- Introduce a separate broker executable/service only after the service identity, installation root, DACLs, pipe protocol, package trust anchor, and recovery model are approved.
- Move all privileged destination operations behind the broker. The existing Python core must not be elevated as-is and must not be exposed as a generic privileged path API.
- Have the broker copy the package into broker-owned staging, validate a strict signed release manifest and publisher identity, then install only from the validated broker-owned snapshot.
- Define a signed package schema and key lifecycle before producing release packages. Do not accept a hash or signature-verification result supplied by the client.
- Define a migration policy for existing per-user `%USERPROFILE%\\SERMAX` installations and any future machine-wide destination. Do not move, overwrite, delete, or merge an existing `C:\\SERMAX` installation, Terminal, memory, configuration, or backups automatically. Migration requires explicit user authorization and a tested preservation/rollback plan.
- Keep the current GUI labeled as a development preview until a separate broker implementation, signed package pipeline, Windows adversarial tests, and recovery tests satisfy the acceptance gates.

**Current conclusion:** the proposed broker is a new architecture, not a small hardening patch to the existing installer. The existing GUI/core cannot be made privileged by changing its launch level. The gap audit is evidence for planning only; no code was modified by this review.


### 11.13 Gap audit against current installer code

Static source review of commit `78ff8109b052492ad5f5b037a7994f0f6d65cc53` found that the current installer is not the broker architecture in sections 11.9–11.12.

1. `installer_gui.py` calls `install_package(package, destination, ...)` directly in a worker thread. It lets the user select both package and destination. No Windows service, named-pipe server, client-token validation, service SID, or broker authorization exists in this path.
2. The GUI defaults to `Path.home() / "SERMAX"`, a per-user destination, not the machine-wide protected root assumed by the provisional threat model.
3. `sermax_installer_core.py` accepts caller-selected package and install paths. It validates paths, then uses path-based `Path`, `os.open`, `shutil.copy2`, `tempfile.mkstemp`, `Path.write_text`, `Path.read_bytes`, `os.replace`, and unlink operations. Rechecking does not bind later operations to the objects previously checked.
4. The package loader checks JSON manifest hashes and sizes against files in the package directory. The inspected code has no signature verification, publisher identity check, trusted release manifest, or independent signing trust anchor. Hashes provide internal consistency, not publisher authenticity.
5. The package builder has no signing step or protected release-key workflow.
6. The README labels the GUI a development preview, says the installer is not distributable, and records that signing and publisher verification are absent.
7. The client-authored manifest and `preserve_paths` must not be treated as authority by a future privileged broker to overwrite protected data or decide what user data is preserved.
8. The current engine backs up and replaces files individually and attempts rollback. Its README correctly states this is not a globally atomic transaction. Durable journaling and crash recovery remain unimplemented.

**Required transition; no implementation until the approval gate passes**

- Treat the current GUI and core as an untrusted client/package-preparation layer. They must not receive elevated rights or write access to the protected application root.
- Build a separate broker only after approval of service identity, destination, DACLs, pipe protocol, package trust anchor, and recovery model.
- Move all privileged destination operations behind the broker. Do not elevate the existing Python core as-is or expose a generic privileged path API.
- Broker must copy input into broker-owned staging, validate a strict signed release manifest and publisher identity, then install from that same snapshot.
- Define package signing and key lifecycle before release packages. Never trust a hash or verification result supplied by the client.
- Define migration for existing per-user `%USERPROFILE%\\SERMAX` and any future machine-wide destination. Never automatically move, overwrite, delete, or merge existing `C:\\SERMAX`, Terminal, memory, configuration, or backups. Require explicit authorization and tested preservation/rollback.
- Keep the GUI marked development preview until broker, signed package pipeline, Windows adversarial tests, and recovery tests pass.

**Conclusion:** the broker is a new architecture, not a small hardening patch. The current GUI/core must not be made privileged by changing its launch level. This audit is planning evidence only; no code was modified.


### 11.14 Named-pipe protocol specification, version 1 proposal

This section defines a protocol candidate for review. It does not authorize implementation. A named-pipe DACL controls who can open the endpoint; it does not prove that the connecting process is the intended SERMAX GUI. Any process running under an identity granted pipe access may attempt to submit requests. The broker must therefore treat the client as untrusted even after the Windows access check succeeds.

#### Transport and endpoint

- Use a fixed local endpoint name under `\\.\\pipe\\`, provisionally `\\.\\pipe\\SERMAX.InstallerBroker.v1`. The final name must be versioned and owned by the broker service.
- Create the pipe with an explicit security descriptor. Never pass a NULL security descriptor.
- Set `PIPE_REJECT_REMOTE_CLIENTS`. Additionally deny network identities in the pipe DACL. Do not expose the broker over SMB or another network transport.
- Use message mode or a documented length-prefixed framing protocol. The selected mode must define exact handling of partial reads, partial writes, disconnects, oversized frames, and malformed UTF-8.
- Do not assume a single pipe read returns a complete request. Parse bounded frames and reject truncation, extra trailing bytes, invalid encodings, duplicate JSON keys, unknown critical fields, and unsupported protocol versions.
- Limit concurrent clients and outstanding requests. One installation transaction per protected root is allowed at a time.
- The broker owns pipe creation, instance creation rights, connection lifecycle, and cleanup. A client must not receive rights to create additional pipe instances.

#### Connection authentication

For every connection, the broker must:

1. Complete the Windows pipe access check using the explicit pipe DACL.
2. Obtain the client access token through a checked impersonation or documented token-query sequence. If impersonation fails, execute no client request.
3. Read and validate the token user SID, logon SID, session ID, integrity level, and relevant group/elevation state. Reject anonymous, network, unexpected, or unsupported identities.
4. Compare the pipe client session with the approved interactive session policy. Obtain the client PID only as diagnostic context; PID alone is not authentication.
5. Bind the authenticated token facts to the connection and revalidate them for each privileged operation where the design requires it. Never trust user name, SID, PID, session, or elevation claims sent in JSON.
6. If impersonation is used, revert before privileged broker work. Check `RevertToSelf`; if it fails, stop processing, close the connection, and terminate the broker process/service according to Microsoft's documented fail-safe guidance. Do not continue in an unknown thread security context.

A logon SID restriction distinguishes logon sessions, not individual applications. The protocol must explicitly acknowledge that another process in the same authorized logon session can connect. Do not claim that the pipe DACL authenticates the GUI binary. The broker remains safe against such a client because it accepts only narrowly authorized operations and independently validates signed packages.

#### Message framing and schema

Each control message is UTF-8 JSON preceded by a fixed-width unsigned 32-bit little-endian byte length. The length counts only the JSON payload, not the prefix. A frame exceeding the configured maximum is rejected before allocating its full payload. Package bytes are transferred in separate bounded binary chunk frames; they are never embedded as base64 in JSON.

Every control request includes:
- `protocol_version`: integer, initially 1.
- `request_id`: random 128-bit identifier, unique per connection.
- `operation`: one allowlisted operation.
- `client_nonce`: random per connection/request value for correlation, not a substitute for authentication.
- `payload`: operation-specific object with strict schema.

Every response includes:
- `protocol_version`
- `request_id`
- `status`: `ok`, `rejected`, `busy`, or `error`
- `error_code`: stable machine-readable code when not successful.
- `message`: bounded, non-sensitive diagnostic text.
- `payload`: operation-specific result.

Reject unknown operations, duplicate request IDs, replayed transaction submissions, unknown critical fields, and unsupported schema versions. Do not echo secrets or arbitrary attacker-controlled text into privileged logs.

#### Initial operation allowlist

| Operation | Purpose | Authorization and restrictions |
|---|---|---|
| `GetBrokerStatus` | Return broker version, protocol version, readiness, and current transaction state | Read-only; disclose no secrets or filesystem paths beyond approved product metadata |
| `BeginPackageUpload` | Start a package intake transaction | Enforce connection identity, quotas, one active transaction per root, and independent publisher policy |
| `WritePackageChunk` | Stream bounded package bytes into broker-owned staging | Valid transaction ID, strict sequence number, bounded chunk, exact byte count; no caller-selected staging path |
| `FinalizePackageUpload` | Close intake and validate the broker-owned snapshot | Verify total size, digest, signed manifest, publisher identity, package policy, version and anti-rollback rules |
| `RequestInstall` | Request installation of the validated transaction | Only validated, trusted package; fixed destination; idempotency key; transaction lock; no arbitrary target path |
| `GetTransactionStatus` | Read status for an opaque transaction ID owned by the authenticated session | No arbitrary file reads; disclose only transaction metadata |
| `Disconnect` | Close the client session | No effect on a committed transaction; incomplete uploads are marked abandoned and cleaned by broker recovery policy |

No generic `ReadFile`, `WriteFile`, `DeleteFile`, `MoveFile`, `RunCommand`, `Execute`, `SetDestination`, `SetAcl`, or `RollbackToCallerPath` operation is permitted. Cancellation semantics are deferred until the transaction journal and safe cancellation points are designed. A client disconnect must not interrupt an already committed transaction or cause arbitrary rollback.

#### Package upload and authenticity

- The client sends a package stream, not a filesystem destination path.
- The broker creates a unique staging object under a broker-owned directory with a restrictive DACL and exclusive ownership.
- Each chunk carries transaction ID, monotonically increasing sequence number, declared chunk length, and bytes. Reject gaps, duplicates, reordering, overrun, and unexpected end-of-stream.
- Enforce configured maximum package bytes, manifest bytes, file count, per-file size, total expanded size, path length, compression ratio, and processing time. Set concrete limits only after measuring the approved SERMAX release composition; until then, the limits are unresolved approval inputs.
- The broker computes the digest while receiving and verifies it again from the closed broker-owned object.
- Validate a signed release manifest against a trust anchor protected from interactive-user modification. Verify signer identity, signature algorithm policy, key validity/revocation policy, product identity, version, file list, hashes, and sizes.
- Enforce anti-rollback using broker-owned installed-version state. A client cannot request downgrade by changing JSON fields or a local marker. Emergency rollback requires a separate privileged administrative policy and audited approval.
- Install from the exact validated broker-owned package snapshot. Never reopen or read from the client source path after intake.

#### Replay, concurrency, and availability

- Use random request IDs and transaction IDs, per-connection sequencing, and idempotency keys. These prevent accidental duplicate processing; they do not authenticate the caller.
- Persist transaction state before reporting a phase as durable. Recover incomplete uploads as abandoned; never treat partial data as installable.
- Serialize installs against one destination root using a broker-owned lock and transaction journal.
- Enforce connection, upload, disk-space, CPU, and time quotas. Reserve enough space for staging, backup, and rollback before beginning installation.
- Rate-limit failed authentication and malformed requests. Log stable error codes and security events without secrets.
- A client timeout or disconnect must return no implication that installation failed or succeeded. The client queries transaction status using the opaque transaction ID.

#### Protocol acceptance tests

- Access from an unauthorized SID, anonymous identity, network identity, different logon SID, wrong session, and same-session non-GUI process.
- Failed impersonation and failed `RevertToSelf`, proving that no request executes under an unintended service token.
- PID reuse and client exit/restart during authentication and upload.
- Partial headers, partial payloads, oversized frames, malformed UTF-8/JSON, duplicate keys, unknown operations, unsupported versions, and trailing data.
- Duplicate/replayed request IDs, transaction IDs, sequence numbers, chunks, and idempotency keys.
- Client disconnect at every upload and install phase, service crash, machine restart, disk full, and concurrent install requests.
- Same-session malicious client attempting every allowlisted operation, path traversal, destination override, package substitution, downgrade, and quota exhaustion.
- Verify that no request can cause arbitrary command execution, arbitrary file access, arbitrary destination selection, or modification of protected user data.

**Decision status:** protocol proposal only. The transport, DACL, client identity checks, operation allowlist, package trust policy, quota values, and recovery semantics require review and explicit approval before implementation.


Protocol references reviewed:
- https://learn.microsoft.com/windows/win32/ipc/named-pipe-security-and-access-rights
- https://learn.microsoft.com/windows/win32/ipc/named-pipes
- https://learn.microsoft.com/windows/win32/api/namedpipeapi/nf-namedpipeapi-impersonatenamedpipeclient
- https://learn.microsoft.com/windows/win32/api/securitybaseapi/nf-securitybaseapi-reverttoself
- https://learn.microsoft.com/windows/win32/ipc/impersonating-a-named-pipe-client
- https://learn.microsoft.com/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid
- https://learn.microsoft.com/windows/win32/api/winbase/nf-winbase-getnamedpipeclientsessionid
- https://learn.microsoft.com/windows/win32/api/winbase/nf-winbase-createnamedpipea


## 11.15 Package authenticity, signing, and publisher trust

**Status:** design proposal only. No signing code, release key, certificate, CI secret, broker, or installation behavior is being created or changed by this section.

### 11.15.1 Separate package integrity from publisher authenticity

The package format should retain a strict manifest and per-file SHA-256 digests, and add a detached digital signature over the exact manifest bytes.

The checks have distinct purposes:

- The detached signature establishes that the manifest was authorized by a signing key accepted by the broker trust policy and that the signed manifest bytes were not changed.
- Each SHA-256 entry binds a manifest-listed relative path and expected file content to the signed manifest.
- The broker must hash every staged payload file and compare the result with the signed manifest before installation.
- A digest without a trusted signature is not proof of publisher identity. A valid signature over a manifest does not excuse missing, extra, duplicate, or mismatched payload entries.

The broker must validate and install from the same broker-owned immutable staging snapshot. It must not validate one copy and later reopen a client-controlled source path.

### 11.15.2 Candidate signature container

Candidate format: detached CMS/PKCS #7 SignedData signature for the exact manifest byte sequence, stored as a separate signature file beside the manifest.

The manifest should use strict UTF-8 JSON with a documented schema. The release signer emits one deterministic byte representation. The verifier rejects a byte sequence that violates encoding or schema rules, including duplicate JSON keys, invalid UTF-8, unsupported critical fields, ambiguous path encodings, and trailing data. Signature verification operates on the exact received manifest bytes, not a parsed-and-reserialized approximation.

Windows CryptoAPI documents decoding signed messages through CryptMsgOpenToDecode and CryptMsgUpdate, retrieving signer information, and checking the signature with CryptMsgControl/CMSG_CTRL_VERIFY_SIGNATURE. SignTool documents detached PKCS #7 output and a PKCS #7 verification mode. These are candidate building blocks, not a completed implementation decision. The broker's own policy must additionally check the expected publisher identity and trust anchor; a generic successful PKCS #7 signature check is insufficient by itself.

Authenticode/WinVerifyTrust is appropriate to evaluate signatures on supported Windows executable objects. It must not be assumed that verifying an EXE with Authenticode automatically verifies a separate JSON manifest. The exact detached-manifest verification API and policy require a Windows prototype and security review before implementation.

### 11.15.3 Signed manifest fields

The signed manifest should contain, at minimum:

- Fixed product identifier and package format/schema version.
- Release channel, such as stable or beta, with broker policy deciding which channels are accepted.
- Product version and monotonically increasing release sequence.
- Unique release identifier.
- Minimum supported broker version and supported operating-system policy.
- Complete allowlisted payload file list, each with normalized relative path, exact byte size, and SHA-256 digest.
- Explicit package creation/issuance metadata and optional expiration policy.
- Any migration metadata, subject to broker-owned policy. The manifest must never grant authority to overwrite or delete user data, memory, Terminal files, backups, or arbitrary paths.

The broker, not the package, defines protected destinations, preserve rules, rollback authority, and permitted migration behavior. Client-supplied preserve lists are not authorization.

### 11.15.4 Publisher trust and certificate policy

The broker must use a trust anchor protected from standard-user modification. Candidate approaches are a pinned publisher public-key/SPKI identity or a pinned signing certificate with a controlled rollover mechanism. Relying solely on a user-writable certificate store or on a publisher name string is insufficient.

At verification time, the broker must check all of the following:

1. Cryptographic signature validity over the exact manifest bytes.
2. Signer identity against the broker's protected publisher pin set.
3. Certificate chain and applicable code-signing usage/policy, where certificates are used.
4. Certificate validity at the applicable signing or trusted timestamp time.
5. Revocation status under an explicit policy.
6. Approved digest and signature algorithms, rejecting deprecated or disallowed algorithms.
7. Release channel, product identity, broker compatibility, and anti-rollback policy.

Microsoft documents WinVerifyTrust as a trust-provider operation for supported objects, and CertGetCertificateChain as a way to build a certificate chain and request revocation checks. The design must distinguish signature mathematics, certificate-chain trust, publisher pinning, and package authorization. They are separate checks.

### 11.15.5 Timestamp and revocation behavior

The release process should request a trusted RFC 3161 timestamp where the selected signature format and verification implementation support it. Timestamp validation must establish that the signature existed while the signing certificate was valid; it does not make a compromised signing key safe and does not replace revocation policy.

Revocation handling must be specified for both connected and offline installations. The broker must not silently treat an unavailable CRL/OCSP response as a clean certificate. Proposed default: fail closed when required revocation status cannot be established, with a separately reviewed and narrowly scoped offline policy if SERMAX must support disconnected installations. The offline policy, cache age, trusted status data, and user-visible failure behavior remain undecided.

### 11.15.6 Signing-key custody and release separation

- The private release-signing key must never be committed to Git, included in a ZIP, stored in the installer package, or placed in ordinary build artifacts.
- The build/test pipeline must not gain signing authority by default.
- Release signing should be a separate, access-controlled stage, preferably backed by an HSM or managed signing service. If that is unavailable, key custody and operator controls require an explicit documented risk decision.
- Developer workstations and pull-request jobs must not have access to production signing credentials.
- Signing access must be limited, logged, reviewed, and revocable.
- A test key may be used for isolated tests only. Test-key signatures must never be accepted by production broker policy.

### 11.15.7 Rotation, compromise, and anti-rollback

The broker trust policy must support planned key rotation without accepting arbitrary new keys. A transition should require authorization by an already trusted key or by a separately protected recovery trust anchor. The design must define overlap periods, key identifiers, activation sequence, retirement, and emergency revocation.

The broker must persist the highest accepted release sequence and product/channel identity in broker-protected state. It rejects older or replayed releases. Reinstalling an equal or older version for recovery requires a separate administrative recovery policy, not a package flag. A signed timestamp or valid signature alone does not prevent replay of an old, legitimately signed package.

### 11.15.8 Required negative and lifecycle tests

Before production approval, test:

- Invalid, missing, truncated, detached-content-mismatched, and altered signatures.
- Unknown, unpinned, expired, revoked, wrong-purpose, and wrong-product signers.
- Unsupported or weak digest/signature algorithms.
- Certificate-chain failures, unavailable revocation endpoints, stale cached revocation data, and timestamp failures.
- Duplicate manifest keys, malformed UTF-8, alternate path spellings, traversal, ADS, reserved names, duplicate paths, hard links/reparse entries, extra unlisted files, missing files, and size/hash mismatches.
- Payload mutation during upload, after finalization, between validation and installation, and after service restart.
- Old signed package replay, lower release sequence, channel downgrade, broker-version mismatch, and key rotation/revocation.
- Signing key unavailable, compromised-key response, recovery-key rotation, and interrupted release publication.

Every failure must reject the package before protected destination changes. Logs record release ID, signer key identifier, package digest, decision code, and transaction ID, without private keys, credentials, or sensitive user data.

### 11.15.9 Decision gates still open

No implementation should begin until the following are approved:

1. Exact package/archive format and canonical manifest byte rules.
2. Detached CMS/PKCS #7 format and Windows verification API, including exact signer pinning behavior.
3. Publisher identity and protected trust-anchor storage.
4. Certificate issuance, code-signing EKU, algorithm policy, timestamping, and revocation behavior.
5. Signing-key custody, release separation, audit, rotation, and emergency recovery.
6. Broker-owned anti-rollback state and recovery exception policy.
7. Full negative test matrix on supported Windows versions.

**Decision status:** candidate architecture only. No production signing identity or trust anchor exists in this change. No installer or broker implementation is authorized by this document.

### 11.15.10 Microsoft references reviewed

- https://learn.microsoft.com/windows/win32/seccrypto/signtool
- https://learn.microsoft.com/windows/win32/seccrypto/decoding-signed-data
- https://learn.microsoft.com/windows/win32/api/wincrypt/nf-wincrypt-cryptmsgcontrol
- https://learn.microsoft.com/windows/win32/api/wincrypt/nf-wincrypt-cryptmsgopentodecode
- https://learn.microsoft.com/windows/win32/api/wincrypt/nf-wincrypt-cryptmsgopentoencode
- https://learn.microsoft.com/windows/win32/api/wintrust/nf-wintrust-winverifytrust
- https://learn.microsoft.com/windows/win32/api/wincrypt/nf-wincrypt-certgetcertificatechain
- https://learn.microsoft.com/windows/win32/seccrypto/using-signtool-to-verify-a-file-signature


## 11.16 Proposed package layout and manifest schema v2

**Status:** proposed format only. The current builder and installer still implement unsigned schema v1. This section does not change runtime behavior and does not authorize a format migration or installer implementation.

### 11.16.1 Current observed format

The current `sermax_package_builder.py` writes a directory package containing `manifest.json` and `payload/`. Its schema v1 manifest contains `schema_version`, `version`, `package_type`, `created_by`, `preserve_paths`, and `files`. Each file record contains `source`, `target`, `sha256`, and `size_bytes`.

The current builder serializes ordinary indented JSON and does not create a detached signature. The current loader accepts schema v1 and verifies file size and SHA-256, but does not verify a publisher signature. Its `preserve_paths` comes from the package manifest. This is not an authority model suitable for a privileged broker.

The current README accurately labels the installer as a development prototype, unsigned, not distributable, and not a complete SERMAX package. These facts remain unchanged.

### 11.16.2 Candidate directory layout

Keep the existing directory-based package for the first signed-format proposal. Do not introduce ZIP or another archive container in this phase; that would add archive extraction, entry-name normalization, duplicate-entry, and decompression resource risks without solving a current requirement.

Proposed layout:

```text
SERMAX-PACKAGE/
  manifest.json
  manifest.p7s
  payload/
    <explicit relative files>
```

- `manifest.json`: exact UTF-8 bytes covered by the detached signature.
- `manifest.p7s`: detached CMS/PKCS #7 SignedData object.
- `payload/`: only the regular files enumerated in the signed manifest.
- No symlink, junction, reparse point, hard link, alternate data stream, device, socket, or other non-regular object is permitted.
- No unlisted file or directory is permitted under `payload/`. The package root contains only the two manifest files and `payload/`.
- The broker stages the received package into a broker-owned location, validates that staged copy, and installs from that same staged snapshot.

This proposal intentionally avoids claiming that a directory tree is immutable by filesystem convention. The broker must own and protect its staging area and must prevent post-validation mutation using the approved handle-based or broker-owned snapshot design.

### 11.16.3 Proposed schema v2

The following is an illustrative schema shape, not a production manifest and not a signed package:

```json
{
  "schema_version": 2,
  "package_type": "sermax",
  "product_id": "SERMAX",
  "release_id": "release-unique-id",
  "channel": "stable",
  "version": "version-string",
  "release_sequence": "monotonic-decimal-string",
  "minimum_broker_version": "version-string",
  "created_at_utc": "RFC3339-UTC-timestamp",
  "files": [
    {
      "source": "payload/SERMAX-Platform/example.dat",
      "target": "SERMAX-Platform/example.dat",
      "file_type": "regular",
      "size_bytes": 1234,
      "sha256": "64-lowercase-hex-characters"
    }
  ]
}
```

Schema rules:

- Reject unknown schema versions and unknown critical fields. Define extension behavior explicitly before adding optional fields.
- `product_id` is a fixed broker-accepted identifier, not a free-form destination selector.
- `release_id` is unique for a published release.
- `channel` is an allowlisted value. The broker's local policy decides which channels it accepts.
- `release_sequence` is a decimal string containing a positive integer with no sign or leading zero. A string avoids cross-runtime integer precision differences. The broker stores the highest accepted sequence per product/channel in protected state.
- `version` remains a display and compatibility identifier. It does not replace the monotonic sequence check.
- `created_at_utc` is informational and subject to strict timestamp parsing. It is not a substitute for a trusted timestamp or anti-rollback state.
- `minimum_broker_version` prevents packages requiring a newer verifier or transaction protocol from being installed by an older broker.
- Every file record has one normalized source path under `payload/`, one normalized destination-relative path, exact byte size, SHA-256, and an explicit regular-file type.
- File paths use forward slashes, UTF-8, and one documented normalization policy. Reject absolute paths, traversal, empty/dot components, alternate separators, drive/UNC prefixes, ADS syntax, trailing dots/spaces, Windows reserved names, case-insensitive duplicates, Unicode-normalization collisions, and file/directory prefix conflicts.
- Sort the file list by the normalized destination path using an explicitly defined ordinal comparison. Do not use locale-sensitive ordering.
- Reject duplicate JSON property names before canonicalization. Reject invalid UTF-8, a BOM, invalid Unicode scalar sequences, NaN/Infinity, and numeric values outside the schema's permitted ranges.
- Reject duplicate file entries, unlisted payload files, missing files, and all unsupported filesystem object types.
- The package manifest does not contain `preserve_paths`, arbitrary destination roots, ACL instructions, commands, scripts, or rollback authorization. Those decisions belong to broker policy.

### 11.16.4 Exact bytes to sign

Candidate canonicalization: RFC 8785 JSON Canonicalization Scheme (JCS), applied to the validated schema v2 JSON object. The signing input is the UTF-8 byte sequence produced by JCS. The verifier parses with duplicate-key detection, validates the schema, canonicalizes according to the same JCS rules, and verifies the detached CMS signature over those exact canonical bytes.

This is preferable to signing the current pretty-printed JSON output because JSON whitespace and property ordering can vary without changing the logical object. JCS defines deterministic property ordering and UTF-8 output for cryptographic use. It is an informational RFC, so the project must pin a tested implementation and conformance vectors rather than assume any generic JSON serializer is JCS-compliant.

The package may store canonical bytes directly in `manifest.json`, which simplifies review and ensures the on-disk signed object is also the verifier input. If this option is selected, require byte-for-byte canonical form and reject noncanonical input rather than silently accepting multiple representations.

No timestamp, whitespace, line ending, encoding conversion, or reserialization step may occur between the final signing operation and verification. Any manifest change requires a new signature.

### 11.16.5 Validation order

The broker's proposed validation sequence is:

1. Authenticate and authorize the local client under the approved pipe protocol.
2. Receive a bounded package stream into broker-owned staging. The client must not retain write access to the staged copy.
3. Validate package-root and payload object types, allowed names, path normalization, entry count, total byte count, and resource limits.
4. Parse manifest bytes with strict UTF-8 and duplicate-key rejection; validate schema v2 and canonical JCS representation.
5. Verify the detached CMS signature over canonical manifest bytes.
6. Validate signer pin, certificate policy, signing purpose, timestamp, revocation policy, product identity, channel, broker compatibility, and release sequence.
7. Compare the exact payload inventory with the signed file list. Reject missing, extra, duplicate, or unsupported entries.
8. Hash and size-check every staged payload file against the signed manifest.
9. Bind the verified staged snapshot to a durable transaction record. Installation must consume that exact snapshot, not reopen the original client path.
10. Recheck transaction state and protected destination preconditions before any protected write.

A failure at any step rejects the package before protected destination changes. Recovery and rollback remain governed by the separately approved transaction design.

### 11.16.6 Schema v1 compatibility and migration

- Schema v1 remains the current development-only format until a reviewed implementation and migration are explicitly approved.
- A future production broker should reject unsigned schema v1 by default.
- Do not silently interpret a v1 manifest as v2 or infer missing publisher, channel, sequence, or trust fields.
- Any temporary legacy import path must be a separate, explicit, non-privileged development operation. It must never be callable as a privileged install fallback.
- A schema v2 implementation requires dedicated positive and negative tests, cross-version canonicalization vectors, signature interoperability tests, and Windows verification tests.
- No existing package, installation directory, `C:\SERMAX`, Terminal, memory, configuration, or backup is modified by this proposal.

### 11.16.7 Required acceptance tests

- JCS canonicalization vectors match the selected reference implementation byte-for-byte.
- Reordered JSON properties produce the same canonical signing input; altered values do not.
- Duplicate keys, invalid UTF-8, BOM, invalid Unicode, noncanonical input, NaN/Infinity, and malformed timestamps are rejected.
- Signature verification fails after any signed manifest field is changed.
- File size/hash changes, missing files, extra files, duplicate entries, path case collisions, Unicode collisions, traversal, ADS, reparse objects, hard links, and unsupported object types are rejected.
- Release sequence replay, downgrade, channel mismatch, wrong product, insufficient broker version, expired package policy, revoked signer, and untrusted signer are rejected.
- Client mutation attempts after upload finalization cannot alter the broker-owned staged snapshot.
- Crash/restart during upload, verification, and install leaves a recoverable transaction state and never treats an unverified package as installed.

**Decision status:** schema v2 and package layout are proposals. They require review and explicit approval. No schema migration, signing implementation, broker implementation, package publication, or installation is authorized by this section.

### 11.16.8 References

- RFC 8785, JSON Canonicalization Scheme: https://www.rfc-editor.org/rfc/rfc8785.html
- Microsoft Learn, Decoding Signed Data: https://learn.microsoft.com/windows/win32/seccrypto/decoding-signed-data
- Microsoft Learn, CryptMsgOpenToDecode: https://learn.microsoft.com/windows/win32/api/wincrypt/nf-wincrypt-cryptmsgopentodecode
- Microsoft Learn, CryptMsgControl: https://learn.microsoft.com/windows/win32/api/wincrypt/nf-wincrypt-cryptmsgcontrol
- Microsoft Learn, CryptMsgOpenToEncode: https://learn.microsoft.com/windows/win32/api/wincrypt/nf-wincrypt-cryptmsgopentoencode


## 11.17 Reconciliation with the existing SERMAX Windows update pipeline

**Audit date:** 2026-11-16.  
**Status:** reconciliation and architecture decision record. No updater, installer, package, or key was implemented by this section.

### 11.17.1 Existing implementation discovered

The repository already contains a separate, partially implemented signed-update validation pipeline under `SERMAX-Windows/`:

- `sermax_update_manifest.py`: strict JSON schema 1 parser and manifest validator. The top-level fields are exactly `schema_version`, `release_version`, `files`, and `signature`. Each file declares `path`, `size`, `sha256`, `classification`, and `action`.
- `sermax_update_signature.py`: Ed25519 verifier using the `cryptography` library. It accepts a trusted public-key mapping from its caller. It does not load a key from the manifest.
- `sermax_update_package.py`: validates a ZIP archive against an already authenticated manifest, entirely in memory, without extracting or writing files.
- `sermax_update_inventory.py`: read-only filesystem inventory, with protected/unknown/managed/blocked classification.
- `sermax_update_inventory_contract.py`: creates an in-memory plan by comparing an inventory with a validated signed manifest. It does not write to the filesystem.
- `ARQUITETURA-ATUALIZADOR-TRANSACIONAL.md`: the transaction, staging, backup, journal, health-check and rollback architecture remains a specification, not an implemented updater.

The current signed-manifest algorithm is Ed25519, not CMS/PKCS #7. The current package validator accepts ZIP, not the directory package proposed in section 11.16. Do not implement a second CMS/JCS package format for the Windows updater without a new architecture decision.

### 11.17.2 Exact limits of the existing signature implementation

The current manifest validator builds its signature payload by removing the `signature` field and serializing the remaining JSON with Python `json.dumps(ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)`. This is a project-specific deterministic serialization rule. It is not declared or tested as RFC 8785 JCS. The earlier JCS proposal in section 11.16 must not be treated as the implemented format.

The Ed25519 verifier is a real cryptographic verifier, but trust is supplied by the caller. The current code and tests do not establish a production release key or a production public-key allowlist. Tests generate ephemeral test keys. The Windows CI pins `cryptography==50.0.2` for signature tests; the current `SERMAX.spec` does not list the updater modules or `cryptography` in its hidden imports/data. Therefore the existing frozen `SERMAX.exe` build is not proven to contain or invoke this update verifier.

The ZIP validator receives the archive as bytes, checks exact file membership, paths, sizes, compression policy, and SHA-256, and returns metadata. It does not extract, stage, install, back up, journal, roll back, or prove crash recovery.

### 11.17.3 Separate the two current installer tracks

There are currently two distinct development tracks. They must not be conflated:

| Track | Existing package model | Current capability | Missing before release |
|---|---|---|---|
| `SERMAX-Windows` updater | ZIP + signed JSON schema 1 + Ed25519 | Manifest validation, signature callback/backend, ZIP validation, read-only inventory and in-memory plan | Production key trust, key lifecycle, anti-rollback policy, frozen-runtime integration, extraction/staging, handle-safe writes, backup, durable journal, rollback, recovery and Windows acceptance |
| `SERMAX-Platform/installer` | Directory + unsigned `manifest.json` schema 1 + payload folder | Explicit-file package builder, size/hash checks, preflight and path-based file replacement/backup attempts | Signature verification, trust policy, immutable plan, TOCTOU-safe transaction, durable journal/recovery, complete component matrix, dependency lock/SBOM, production installer and Windows acceptance |

The Platform builder's unsigned directory schema v1 is not authenticated by the Windows Ed25519 verifier. The Windows ZIP validator cannot be assumed to accept the Platform builder's directory package. There is no evidence of a shared production package contract or an integrated installer between these tracks.

### 11.17.4 Provisional component composition for a future SERMAX Platform release

This is an audit classification, not an approved release manifest. It describes observed repository paths and the conditions required before each group can enter a release package.

| Group | Observed source paths | Provisional treatment |
|---|---|---|
| Platform UI | `SERMAX-Platform/index.html`, `styles.css`, `app.js` | Candidate runtime files; package only after frozen/installed path resolution and browser smoke tests |
| Platform API | `SERMAX-Platform/backend/server.py` | Candidate runtime file; requires pinned Python runtime and dependency closure |
| Platform launcher | `SERMAX-Platform/sermax_platform_launcher.py` | Candidate runtime file; current Python development launcher, not a validated frozen entry point |
| Platform dependencies | `SERMAX-Platform/backend/requirements.txt` | Current ranges: FastAPI, Uvicorn standard extra, HTTPX. No lockfile or resolved transitive dependency inventory exists in this branch |
| SERMAX core | `SERMAX-Windows/sermax_core.py`, `sermax_planejador.py`, `sermax_executor.py`, `sermax_tarefas.py`, `ferramenta_windows.py`, `sermax_jarvis_adapter.py`, `sermax_widget_state.py`, `sermax_pestinha_adapter.py` | Candidate only after reconciliation against the approved SERMAX baseline and exact import/dependency closure |
| Original Terminal | `SERMAX-Windows/SERMAX_terminal/sermax_terminal.py`, `sermax_voz.py`, `sermax_integracao_comandos.py`, plus `sermax_launcher.py` | Preserve original interface and include only with explicit compatibility and visual regression approval |
| Pestinha code | Upstream pinned dependency collected by `collect_all("pestinha")` in `SERMAX-Windows/SERMAX.spec` | Conditional. GPL-3.0-or-later source correspondence and distribution analysis remain open. Do not include upstream `assets/` or `pets/` without separate rights evidence |
| OpenJarvis worker | `SERMAX-Windows/sermax_jarvis_worker.py` and `sermax_jarvis_adapter.py` | Worker source is included by current spec, but the OpenJarvis Python 3.13 environment is separately installed and is not bundled in the current executable. Requires a separate environment/package contract and Apache-2.0 notices |
| Python 3.14 build/runtime dependencies | CI currently installs PyInstaller, NumPy, psutil, pywin32 and cryptography 50.0.2; Pestinha is checked out at a pinned commit | Build/test evidence only. A production dependency lock, runtime closure and third-party notices are still required |
| External local service | Ollama at `127.0.0.1:11434` and user-selected local model | Prerequisite, not part of the application payload. Never bundle or overwrite user models |
| User data | Core memories; neural memory; Platform SQLite at `%USERPROFILE%\\.sermax-platform\\platform.sqlite3`; logs, preferences and user files | Never part of the update payload. Preserve byte-for-byte; migration requires a separate explicit and reversible plan |
| External environments and caches | Python 3.13/3.14 virtual environments, Ollama model store, caches and local runtime assets | Preserve. Do not replace or delete as a side effect of application update |
| Development-only content | tests, workflows, CI scripts, documentation, backups, `.deps`, virtual environments, logs and local secrets | Exclude from runtime package unless a specific operator document is intentionally approved |

### 11.17.5 Observed packaging mismatch

The current `SERMAX-Windows/SERMAX.spec` builds the original Terminal launcher. It collects Pestinha and includes selected Terminal/core modules and the Jarvis worker. It does not include the Platform UI/backend/launcher, and its hidden-import list does not include the signed updater modules.

Conversely, the Platform launcher and backend are still a Python development layout. The repository does not yet demonstrate a single frozen executable or installer that starts the Platform, loads the approved core, preserves the Terminal as an administrative interface, prepares the separate OpenJarvis environment, and keeps all user data outside the application payload.

This is a composition and integration gap, not a reason to replace the original `SERMAX.spec` or launcher in this branch.

### 11.17.6 Architecture direction and next gates

For the future unified SERMAX release, prefer one reviewed package contract and one transaction engine. Reuse of the existing Ed25519 + ZIP pipeline is the leading candidate because code already exists, but it is not approved as production architecture until the following are closed:

1. Review the project-specific canonical JSON byte rules, publish test vectors, and decide whether to retain them or deliberately migrate schema with compatibility/version gates. Do not silently label the current serializer JCS.
2. Provision no production key until the publisher identity, protected public-key allowlist, private-key custody, rotation, revocation and emergency recovery are approved.
3. Add an explicit anti-rollback sequence and broker-owned state. Current schema 1 only declares SemVer `release_version`; SemVer alone is not durable anti-rollback state.
4. Decide whether Platform files, Windows core, Terminal and worker environments form one release or separately versioned components. Define dependency and compatibility contracts.
5. Resolve Pestinha GPL source correspondence and OpenJarvis Apache-2.0 notices/dependency inventory before binary distribution.
6. Produce a complete allowlist with exact source path, destination path, component owner, version, runtime requirement, license notice, data classification and create/replace policy.
7. Integrate signature verification, ZIP validation, inventory planning and a crash-safe installer only after the broker/handle-based security architecture is approved.
8. Run install/update/rollback tests on clean Windows VMs and on a disposable copy of an existing installation. No test may target the user's live `C:\\SERMAX`.

**Decision:** section 11.15 and 11.16 remain historical exploratory proposals. For the existing SERMAX Windows update track, Ed25519 + signed JSON schema 1 + ZIP is the implementation to audit, not CMS/PKCS #7 + directory schema v2. For the Platform installer track, the unsigned directory schema v1 remains development-only. Neither track is a validated installer or release.


## 11.18 Static integration audit: inventory, manifest and plan

**Audit date:** 2026-11-16.  
**Scope:** static inspection of `SERMAX-Windows/sermax_update_inventory.py`, `sermax_update_inventory_contract.py`, `sermax_update_manifest.py`, `sermax_update_package.py` and their tests. No code was executed or changed in this audit.

### 11.18.1 Blocking contract mismatch: file identity is required but not produced

The plan builder requires every `replace` destination to contain a `file_id` string matching 32 hexadecimal characters. The value is copied to `InventoryPlanEntry.current_file_id`.

The actual `inventory_directory()` output contains `path`, `type`, `size`, `sha256` and `classification`. It does not emit `file_id`, volume identity, or a retained file handle. Therefore the actual inventory output cannot be passed directly to `build_inventory_plan()` for any `replace` action.

The current contract tests conceal this integration gap by constructing inventory dictionaries through a test helper that manually inserts a synthetic `file_id`. The tests prove validation of a supplied identifier, not production of a real Windows file identity.

**Required correction before integration:** define a Windows handle-based inventory record with volume identity and the appropriate file identity obtained from the opened object. Keep the relevant handles alive through the operation that consumes the plan, or explicitly reopen and verify the same object using a documented race-safe contract. A path string plus a fabricated or stale file ID is not sufficient. Do not substitute `st_ino` or another path-derived field without validating its Windows semantics and identity guarantees.

### 11.18.2 Inventory reads remain path-based

The current inventory implementation:
- checks each directory entry with `DirEntry.stat(follow_symlinks=False)`;
- then hashes the file with `Path.open("rb")`;
- then obtains size again with `Path.stat(follow_symlinks=False)`;
- recursively enumerates directories through `os.scandir(Path)`.

The no-follow check and the later open are separate path operations. A concurrent replacement of a file or parent directory can change the object reached between those operations. The root is checked with `lstat`, then canonicalized with `resolve(strict=True)`; this does not prove that every ancestor used to reach the supplied root was admitted without following a reparse point.

Consequently, the current implementation is a useful read-only inventory prototype, but it is not the handle-based, race-resistant inventory described in its contract. Because it reads file contents to calculate hashes, a path race is also a potential unintended read outside the intended root, not merely a stale report.

**Required correction before use on a trusted installation:** root admission, directory enumeration, file opens, metadata queries and hashing must be bound to retained handles under an explicitly approved Windows API contract. Reject reparse points and unexpected volume changes. If the documented API contract cannot provide the required guarantee, do not claim race resistance and keep the inventory out of the trusted installation path.

### 11.18.3 Plan builder trusts caller-supplied inventory records

`build_inventory_plan()` validates record shapes, path collisions, classifications and selected metadata, but accepts ordinary caller-supplied mappings. It does not establish that those records were emitted by `inventory_directory()`, nor that their `classification`, `file_id`, size or hash came from a trusted read operation.

The intended precondition says that inventory must come from a trusted layer. That provenance is currently a convention in a docstring, not an enforced interface. The `classify_inventory()` helper can assign `managed` from an explicit allowlist, but it does not authenticate the underlying filesystem observations or retain object handles.

**Required correction before integration:** use a private/typed inventory result produced only by the trusted handle-based reader, or have one orchestrator own inventory acquisition, classification, manifest verification and plan construction without accepting externally authored dictionaries. Revalidate object identity and required metadata at the point of use. A serialized inventory file must never become authority for privileged writes.

### 11.18.4 Directory creation is not represented by the current plan

For every nested manifest target, `build_inventory_plan()` requires each parent directory to exist in the inventory and be a directory. The manifest supports file actions `create` and `replace`, but has no directory-entry action or explicit directory-creation plan.

This supports new files inside existing directories, as shown by the tests. It does not support a release that introduces a new directory tree. The installer cannot infer permission to create missing ancestors from the file path alone.

**Required correction:** either require every package destination directory to exist and state that limitation in the package contract, or add explicit, authenticated directory operations with collision, protected-path, ACL and rollback rules. Do not silently create missing parent directories in a privileged installer.

### 11.18.5 Package validator boundary

`validate_release_archive()` correctly expects an already validated `ValidatedManifest` and checks the ZIP member set, names, file sizes, content hashes, supported compression methods and selected special-file indicators without extracting the archive. Its tests exercise these validation boundaries.

It returns package metadata and an archive digest, not an immutable staged package or a handle to the validated archive. The function receives the complete archive as a `bytes` object, so a future streaming broker cannot simply assume this API provides bounded-memory streaming. The current configured archive cap is 512 MiB and total uncompressed cap is 4 GiB; those are code defaults, not measured release requirements or approved broker quotas.

The caller must preserve the exact validated bytes/snapshot through later staging. Reopening a caller-controlled path after validation would reintroduce a package substitution window.

### 11.18.6 Manifest and plan are not yet one authenticated transaction

The manifest validator authenticates a deterministic JSON payload with an injected verifier. The package validator accepts the resulting validated manifest object. The plan builder independently validates raw manifest bytes and authenticates them again. There is no production orchestrator binding one exact manifest byte sequence, one exact ZIP byte sequence, one inventory snapshot, one package validation result and one plan into a durable transaction identity.

No current module performs staging, backup, journaling, install, rollback or crash recovery. No current test proves that the package bytes validated are the same bytes later installed, or that the file objects planned are the same objects later replaced.

**Required correction:** define one transaction context containing the authenticated manifest digest, archive digest, release identity, inventory generation, retained object identities, plan, and broker-owned staged snapshot. Every later phase must consume that same context or verify a documented immutable equivalent. Persist a durable transaction journal before any mutation.

### 11.18.7 Audit disposition

| Finding | Severity for release | Disposition |
|---|---|---|
| Real inventory omits required file identity | Blocker | Actual inventory cannot plan replacements |
| Inventory hashes and stats by path after no-follow checks | Blocker | Not race-resistant; do not use on trusted installation |
| Root ancestors are not admitted by retained handles | Blocker | Root trust is incomplete |
| Plan accepts ordinary caller-authored mappings | Blocker | Provenance is not enforced |
| Missing parent directories cannot be planned | Functional limitation | Package contract or explicit directory operations required |
| ZIP validation returns metadata, not immutable staged content | Blocker for installer integration | Must bind validated bytes to broker-owned staging |
| No end-to-end transaction coordinator or durable journal | Blocker | No install/rollback capability |

**Decision:** keep all five modules as validation/read-only prototypes. Do not connect them to the Platform installer, elevate them, or point them at the user's live `C:\\SERMAX`. The next safe engineering task is to specify and test a Windows handle-based inventory result contract and its provenance, without implementing privileged installation. This audit does not close any TOCTOU acceptance gate.


## 11.19 Proposed Windows handle-bound inventory contract

**Audit date:** 2026-11-16.  
**Status:** interface and acceptance specification only. No native filesystem code, installer, broker, or privileged operation was implemented by this section.

### 11.19.1 Contract objective

The inventory supplied to the release planner must describe the filesystem objects actually opened and inspected. It must not be a caller-authored collection of path strings and metadata. The inventory must bind together:

- the admitted installation root and its volume/file identity;
- each enumerated directory and regular file object;
- the parent directory object through which each child was admitted;
- metadata and content hash obtained through the same opened file object;
- a live ownership scope that retains the relevant handles until the plan is consumed or explicitly invalidated.

A path is a root-relative name for display, policy matching and manifest comparison. It is not proof of object identity and must never be used as the authority for a later privileged write.

### 11.19.2 Identity source and limits

For a supported Windows filesystem, query `FILE_ID_INFO` from the opened handle through `GetFileInformationByHandleEx(FileIdInfo)`. Record both `VolumeSerialNumber` and all 16 bytes of `FileId`. Microsoft documents that the pair identifies an opened file on one computer and can be compared across two open handles to determine whether they represent the same file.

Do not use the 128-bit identifier by itself. Do not treat a file ID as a permanent identifier: Microsoft documents that file IDs can be reused over time and, in some cases, can change. The identity pair is an object-comparison aid, not a substitute for a live retained handle or safe namespace resolution.

If `FileIdInfo` is unsupported, fails, or returns an all-zero ID on a filesystem that does not provide a 128-bit ID, the trusted inventory must fail closed for operations that require this identity. Do not silently fall back to `st_ino`, a 64-bit file index, timestamps, path strings or a synthetic identifier. Any future filesystem-specific fallback requires a separate documented contract and acceptance suite.

The root and every child record must carry the volume serial and 128-bit file ID obtained from that object's own handle. A child whose volume identity differs from the admitted root is rejected unless an explicitly approved mount/volume policy says otherwise. The default policy for this updater is to reject volume crossings.

### 11.19.3 Proposed opaque object model

The trusted reader should return an in-process, non-serializable `InventorySnapshot` object. Its constructor is private to the Windows inventory backend. Callers must not be able to instantiate an authoritative snapshot from dictionaries, JSON, a database row or a deserialized cache.

Conceptual fields:

| Object | Required data | Authority/lifetime |
|---|---|---|
| Snapshot | random snapshot ID, root identity, volume identity, policy/version, creation time, generation/state | Owns all handles; valid only while open |
| Root/directory entry | root-relative display path, volume serial, 128-bit file ID, attributes, reparse tag, directory handle | Handle retained by snapshot |
| Regular-file entry | root-relative display path, parent entry ID, volume serial, 128-bit file ID, attributes, reparse tag, size, SHA-256, file handle | Handle retained by snapshot; hash and size read from this handle |
| Plan entry | snapshot ID, referenced entry ID, expected object identity, action, manifest file record | Cannot outlive or detach from its snapshot |

The implementation should use opaque internal entry identifiers rather than expose raw native handles as public values. Native handles remain private to the backend and are closed deterministically when the snapshot is disposed. The snapshot is single-owner or explicitly synchronized; concurrent consumers must not close handles while another phase uses them.

No serialization of `InventorySnapshot` conveys authority. A diagnostic export may include paths, IDs, hashes and classifications, but must be marked informational and must never be accepted as input to the privileged planner or broker.

### 11.19.4 Acquisition and observation rules

1. Admit the root under a separately approved root-bootstrap contract. The unresolved API-contract issue in sections 4A and 11.1 remains a blocker. Do not claim that `FILE_ID_INFO` closes the root-path or ancestor-reparse race.
2. Retain the admitted root handle. Record its volume/file identity and verify the expected root policy.
3. Enumerate each directory using the retained directory handle. Resolve each child through the approved directory-relative mechanism. The exact native open primitive remains blocked until the API contract and concurrency semantics are established; a concatenated absolute path is not an acceptable substitute.
4. Open a child without following its reparse point, query attributes and reparse tag through that opened handle, and reject reparse points and unsupported object types according to policy.
5. Query `FILE_ID_INFO`, `FILE_STANDARD_INFO` and `FILE_ATTRIBUTE_TAG_INFO` through the same handle. Confirm expected file/directory type, volume identity and nonzero 128-bit file ID.
6. For regular files, calculate SHA-256 by reading bytes from that same retained file handle. Obtain size from handle metadata, not a later path stat. Record the hash and size only after the read completes successfully.
7. Retain each relevant child and parent directory handle for the entire lifetime of the snapshot. Do not close and later reopen by path to continue planning or installation.
8. If an object is renamed, unlinked, replaced in its parent namespace, changes type, or becomes inaccessible during acquisition, mark the snapshot invalid and abort. Do not silently refresh a subset and combine observations from different generations.
9. Do not assume a retained handle proves that the original name resolution was safe. Root admission, parent-relative opens and namespace mutation behavior remain separate security proof obligations under section 4A.

### 11.19.5 Planner provenance and preconditions

Replace the current public mapping-based trusted-planner boundary with an API that accepts only a live `InventorySnapshot` produced by the trusted Windows backend. The plan builder must reject:

- ordinary mappings or records constructed by callers;
- snapshots from another backend, root, volume, policy version or process generation;
- disposed, invalidated or partially acquired snapshots;
- entries whose parent relationship is absent or inconsistent;
- duplicate/colliding normalized paths;
- unsupported file identity, object type or reparse state;
- manifest actions targeting protected or unknown classifications.

A `replace` action must reference the exact existing regular-file entry and its retained handle. A `create` action must reference the retained parent-directory entry and record that the destination name was absent at inventory time. Absence at inventory time is not a commit-time guarantee; the eventual transaction must recheck the destination relative to the same retained parent under an approved race-safe contract and fail on collision.

Plan entries must carry the snapshot ID and opaque entry ID, not accept a free-form `file_id` as authority. Before any future mutation, the transaction coordinator must verify that the snapshot remains live, the relevant handles remain valid, the observed volume/file identity matches the planned identity, and all transaction preconditions still hold. If the approved API cannot establish the required namespace guarantee, the write must not proceed.

The existing manifest supports file `create` and `replace` only. Until explicit directory operations are approved, every destination parent directory must already exist in the admitted inventory. No implicit parent-directory creation is permitted.

### 11.19.6 Snapshot invalidation and resource lifecycle

Invalidate the entire snapshot on handle closure, failed identity query, volume mismatch, unsupported reparse state, unexpected object type, incomplete enumeration, read/hash failure, or detected mutation that violates the selected policy. A consumer must receive a typed failure and must not continue with a partial plan.

Use deterministic context-manager or equivalent ownership semantics. Close all handles on normal completion, cancellation, exception and process shutdown. Bound the number of retained handles and inventory entries; if a configured bound is reached, abort before producing a trusted snapshot. Quota values must be measured against approved SERMAX installation layouts and explicitly selected, not guessed.

A snapshot is ephemeral process state, not a durable transaction journal. A future transaction record may persist snapshot ID, identities and digests for audit, but after restart it must reacquire and revalidate objects under a newly approved transaction-recovery contract. It must never reconstruct handle authority from serialized IDs.

### 11.19.7 Required Windows adversarial tests

Run on supported Windows versions and explicitly identified filesystem types. At minimum:

- Compare two handles to the same object and two handles to different objects using volume serial plus 128-bit file ID.
- Verify fail-closed behavior when FileIdInfo is unsupported, returns zero, is malformed, or query fails.
- Verify a file ID reused after deletion does not authorize a new object when the original retained handle is gone.
- Replace a file between directory enumeration and open; the resulting record must describe only the object actually opened, or the snapshot must abort.
- Replace/swap a parent directory, junction or symbolic link during child acquisition and hashing. No read may escape the approved root; otherwise the test is a release blocker.
- Change a leaf to a reparse point between enumeration and open. The reparse object must be rejected without following it.
- Rename or unlink files and directories while handles are retained. Verify documented share-mode behavior and snapshot invalidation.
- Introduce a volume mount point or volume crossing beneath the root. Verify default rejection.
- Exercise hard links, case-insensitive name collisions, Unicode normalization collisions, trailing dots/spaces, reserved names and path-prefix conflicts.
- Interrupt enumeration and hashing, exhaust handle quotas, deny sharing, revoke access and simulate disk/filesystem errors. No partial snapshot may be accepted.
- Attempt to pass caller-authored dictionaries, JSON exports, stale snapshots and snapshots from another root into the planner. All must be rejected.
- Verify that a plan cannot be consumed after snapshot disposal or invalidation.
- Run the suite on each supported filesystem/Windows combination. Do not claim NTFS, ReFS, SMB or removable-volume support from tests on a different filesystem.

Tests must record Windows build, filesystem type, test commit, test command, outcome and relevant diagnostic evidence. A passing test demonstrates behavior on that tested configuration; it does not resolve the undocumented API-contract concerns in section 4A.

### 11.19.8 Acceptance decision

The inventory contract is not accepted for production until all of the following are true:

1. Microsoft-supported API semantics establish safe root admission and child resolution under the declared threat model, including relevant concurrent namespace changes.
2. The implementation obtains identity and metadata from opened handles and hashes content through those same handles.
3. The planner accepts only live, provenance-bearing snapshots and cannot be authorized by serialized or caller-authored records.
4. The Windows adversarial suite passes on every declared supported OS/filesystem combination.
5. Snapshot lifetime, handle quotas, invalidation and cleanup are tested.
6. The transaction coordinator consumes the same snapshot and exact package bytes later used for staging and commit.
7. The release security matrix records the remaining limits and the evidence used to close each gate.

**Decision:** this contract resolves the data-model gap conceptually, not the underlying Windows namespace-resolution security proof. Sections 4A and 11.1 remain controlling blockers. No implementation, privileged broker, installer connection or release approval follows from this specification.

### 11.19.9 Microsoft references reviewed

- `FILE_ID_INFO`: https://learn.microsoft.com/windows/win32/api/winbase/ns-winbase-file_id_info
- `FILE_ID_128`: https://learn.microsoft.com/windows/win32/api/winnt/ns-winnt-file_id_128
- `GetFileInformationByHandleEx`: https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandleex
- `BY_HANDLE_FILE_INFORMATION`, including file-ID reuse limitations: https://learn.microsoft.com/windows/win32/api/fileapi/ns-fileapi-by_handle_file_information
- `FILE_INFO_BY_HANDLE_CLASS`: https://learn.microsoft.com/windows/win32/api/minwinbase/ne-minwinbase-file_info_by_handle_class


## 11.20 Snapshot freshness, confirmation binding and transaction handoff

**Audit date:** 2026-11-16.  
**Status:** lifecycle specification only. No timer, transaction coordinator, installer, broker or filesystem operation was implemented.

### 11.20.1 Separate inventory lifetime from transaction durability

An `InventorySnapshot` is a short-lived, in-process observation that owns live filesystem handles. It is not a durable transaction, a lock, a namespace snapshot, or proof that a later path lookup will reach the same object.

A future implementation must distinguish three objects:

1. **InventorySnapshot:** live handles and observations used to classify the installation and build a plan.
2. **ConfirmedPlan:** immutable description of the exact release and intended operations shown to the user for confirmation.
3. **TransactionRecord:** durable journal for an installation attempt, including phase and recovery metadata. It does not preserve handle authority across process termination.

Do not serialize one object and treat the serialized form as another. In particular, a journal containing file IDs does not recreate the handles held by an earlier process.

### 11.20.2 Snapshot state machine

The proposed snapshot state machine is:

| State | Meaning | Allowed next states |
|---|---|---|
| `ACQUIRING` | Root and entries are being opened and inspected | `VALID`, `INVALID`, `DISPOSED` |
| `VALID` | Complete inventory acquired; all required handles remain owned | `PLAN_BOUND`, `INVALID`, `EXPIRED`, `DISPOSED` |
| `PLAN_BOUND` | A plan has been built against this exact snapshot | `INVALID`, `EXPIRED`, `DISPOSED` |
| `INVALID` | A required invariant failed; no consumer may proceed | `DISPOSED` |
| `EXPIRED` | The configured maximum planning lifetime elapsed | `DISPOSED` |
| `DISPOSED` | Handles closed and ownership released | terminal |

State transitions are monotonic. An invalid or expired snapshot cannot be refreshed in place, reopened, or returned to `VALID`. A new acquisition creates a new snapshot ID and generation.

The snapshot records a monotonic acquisition timestamp and a configured maximum planning lifetime. Use a monotonic clock for elapsed-time decisions; wall-clock changes must not extend or shorten a live snapshot. The duration is an explicit configuration value to be selected after measuring inventory time and handle pressure on supported SERMAX layouts. Do not invent a default TTL in this specification.

The time limit is a resource/lifecycle guard, not a security proof. A snapshot inside its TTL can still be invalid because of namespace mutation, handle errors, changed policy, or an unproven name-resolution race. A snapshot outside its TTL is rejected even if no mutation was observed.

### 11.20.3 Mandatory invalidation conditions

Invalidate the entire snapshot, and every plan derived from it, when any of the following occurs:

- A retained root, parent or file handle is closed, invalid, or no longer queryable.
- The maximum planning lifetime expires.
- Root or child volume/file identity differs from the identity recorded during acquisition.
- A required parent-child relationship or directory entry no longer matches the approved observation.
- A reparse point, unsupported object type, volume crossing, or protected-path collision is detected.
- Enumeration or hashing was incomplete, interrupted, or failed.
- The trusted-reader policy version, managed allowlist, package policy, or supported-filesystem policy changes.
- The package bytes, authenticated manifest digest, release identity, destination root, install mode, or plan contents differ from the values bound at confirmation.
- The process loses ownership of the snapshot or cannot establish that the same in-memory snapshot remains live.

A notification, file watcher event or timestamp change may trigger invalidation, but the absence of such a notification does not prove that the snapshot is unchanged. File watchers are advisory signals, not the authority for security decisions.

### 11.20.4 Bind confirmation to immutable inputs

Before asking the user to confirm, construct a `ConfirmedPlan` digest over a versioned, deterministic representation containing at least:

- product ID, release ID, release version and release sequence when defined by the authenticated manifest;
- exact authenticated manifest digest and exact archive digest;
- inventory snapshot ID and generation;
- root volume/file identity and normalized destination identity;
- every planned relative target, action, expected existing-object identity, expected size/hash, and parent-entry identity;
- package policy version, managed allowlist version, and transaction protocol version;
- install mode and any user-visible data-preservation decisions.

The digest is a correlation/integrity value for the confirmation flow. It is not a signature, trust anchor, authorization token, or substitute for the package signature and live handles.

The UI must display the release identity, destination, operation summary and preservation boundaries derived from the same `ConfirmedPlan`. After confirmation, the worker must compare the confirmed digest with its own still-live plan and package snapshot. If any field changes, abort and require a new preflight and confirmation. The UI must not permit changing package, destination, mode or preservation choices while the confirmed operation is pending.

### 11.20.5 Pre-commit handoff

The future coordinator should use the following ordering:

1. Acquire the trusted inventory and validate the exact package bytes and signed manifest.
2. Build the plan from that live inventory and the authenticated manifest.
3. Produce the deterministic confirmation digest and display the exact plan summary.
4. Receive user confirmation for that digest.
5. Acquire the transaction lock for the fixed installation root. The lock coordinates cooperating updater instances; it does not stop an adversarial process from changing the namespace.
6. Verify that the same snapshot is still live and within its planning lifetime. Revalidate every required handle identity, parent relationship, protected-path rule and plan precondition using the approved handle-bound API.
7. Verify that the exact package snapshot still matches the authenticated manifest digest and archive digest. Never reopen a caller-controlled source path.
8. If any precondition fails, abort before mutation, invalidate the snapshot and return to preflight. Do not silently rebuild the plan under an old confirmation.
9. Persist and flush the transaction journal and the exact staged package/backup metadata required by the separately approved transaction design before the first protected destination mutation.
10. Only then may a separately approved transaction engine begin the first write.

The revalidation in step 6 is not implementable as a safe guarantee until the Windows name-resolution and concurrency blocker in section 4A is resolved. Retaining a handle and comparing its file ID does not prove that the directory entry still names that object or that an attacker cannot substitute the entry around commit.

### 11.20.6 Crash, restart and recovery behavior

- If the process exits before the first protected mutation, close/lose all handles and treat the in-memory snapshot and confirmation as invalid. A later process must reacquire inventory, revalidate package trust and obtain a new confirmation.
- If a process exits after a durable transaction journal has been written, recovery is governed by the journal state machine and backup/rollback design. Do not resume using a serialized inventory snapshot or old handle IDs.
- A recovered transaction must verify the journal, package digest, release identity, protected root policy and durable phase records. It must reacquire filesystem handles and revalidate under the approved recovery contract.
- If the journal is missing, malformed, inconsistent, or cannot prove which mutations completed, fail closed and preserve recovery material for an explicit recovery path.
- A stale or expired snapshot must never authorize automatic continuation after restart.
- The journal is not allowed to expand package authority, alter the signed file list, select a new destination, or authorize writes to user data.

### 11.20.7 Required lifecycle and race tests

- Expire a snapshot before planning, while the confirmation dialog is open, immediately after confirmation, while waiting for the transaction lock, and before the first write. Every case must abort without mutation.
- Change wall-clock time forwards and backwards while a snapshot is live. Monotonic expiry behavior must remain correct.
- Invalidate the snapshot through each mandatory condition and verify all derived plans are rejected.
- Close one retained handle, close the root handle, dispose the snapshot twice, and race disposal against a consumer. No closed or partially owned handle may be used.
- Change the package source after validation and after confirmation. The broker/worker must consume only the exact validated immutable snapshot.
- Change destination, install mode, preservation options or plan data after confirmation. The digest mismatch must abort and require new confirmation.
- Hold the transaction lock with a second updater while the snapshot expires. The waiting process must not commit an expired plan.
- Crash before journal creation, after journal flush, and at each later durable phase. Recovery must not reconstruct snapshot authority from file IDs.
- Tamper with or truncate the journal and verify fail-closed behavior without deleting backup or recovery material.
- Attempt to replay an old confirmation digest with a new snapshot, package, root or transaction ID. Reject the replay.
- Verify that watcher silence does not prevent mandatory handle/namespace revalidation.

### 11.20.8 Acceptance decision

Snapshot lifecycle is accepted only when the implementation proves that:

1. State transitions are monotonic and invalid/expired snapshots cannot be revived.
2. Every plan is bound to one live snapshot and one exact package/manifest digest.
3. User confirmation is bound to the immutable plan digest.
4. Lock waiting, UI delay, package changes, process exit and recovery cannot reuse stale authority.
5. The journal is durable before mutation and does not pretend to preserve handle authority.
6. Windows namespace revalidation has an approved, documented security contract and passes the adversarial suite.

**Decision:** this section defines when a future snapshot and confirmation must be rejected. It does not make the current path-based inventory safe, implement a transaction engine, close section 4A, or authorize installation.
