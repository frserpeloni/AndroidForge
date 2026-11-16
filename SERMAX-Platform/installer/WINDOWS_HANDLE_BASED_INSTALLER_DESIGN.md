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


## 11.21 Durable transaction journal and crash-recovery contract

**Audit date:** 2026-11-16.  
**Status:** specification only. No journal writer, coordinator, broker, installer, rollback engine or recovery command was implemented or tested.

### 11.21.1 Purpose and authority boundary

The journal records transaction intent, verified operations and durable phases. It is not a source of package authority. It must never authorize an unverified package, expand the signed file list, change the destination root, authorize user-data migration, recreate InventorySnapshot handles, revive a ConfirmedPlan, or trigger blind replay of an ambiguous operation.

The journal belongs to the future broker/transaction owner. A client process must not write, replace, truncate, delete or select its storage path.

### 11.21.2 Versioned record envelope

The journal format has an explicit integer journal_format_version, independent of package schema and transaction protocol version. Unknown versions and unknown critical fields fail closed.

Each transaction uses a cryptographically random transaction ID with at least 128 bits of entropy. IDs are never reused. Each framed record contains:
- format version, transaction ID, strictly increasing sequence number, previous-record digest;
- record type, prior/new state, UTC audit timestamp and nonsecret process correlation metadata;
- product/release identity and sequence from the authenticated manifest;
- exact manifest, archive/staged-package and confirmed-plan digests;
- transaction protocol and policy versions, protected root identity and target references;
- per-target expected before/after identity, type, size and SHA-256;
- broker-owned staging/backup identifiers, relative names, sizes, hashes and verification status;
- operation intent, result, verification result and stable error code;
- checksum/digest over a deterministic, versioned encoding.

Reject duplicate keys, malformed encodings, invalid types, unsupported critical fields, oversized records and trailing bytes. Canonicalization and digest algorithms must be explicit. Ordinary JSON serialization is not assumed canonical across runtimes.

A previous-record digest detects gaps and edits in a chain, but is not tamper-proof if an attacker can rewrite the entire journal. MAC/signature choice and key custody remain open. Until approved, trust depends on broker ownership, restrictive ACLs and independent artifact verification. If ownership or ACL integrity is uncertain, enter RECOVERY_REQUIRED.

### 11.21.3 Transaction state machine

| State | Meaning | Permitted next states |
|---|---|---|
| PREPARED | Exact package, manifest, plan and preconditions are bound; journal initialized before protected mutation | STAGING_VERIFIED, ABORTED, RECOVERY_REQUIRED |
| STAGING_VERIFIED | Staged payload read back and matched authenticated sizes/hashes | BACKUP_VERIFIED, ABORTED, RECOVERY_REQUIRED |
| BACKUP_VERIFIED | Every replacement target has a verified backup, or is explicitly absent | COMMITTING, ABORTED, RECOVERY_REQUIRED |
| COMMITTING | Per-target write-ahead intents and verified operations are processed | COMMITTED, ROLLBACK_REQUIRED, RECOVERY_REQUIRED |
| COMMITTED | All targets and final marker passed verification; commit record is durable | terminal |
| ROLLBACK_REQUIRED | Commit cannot safely continue | ROLLING_BACK, RECOVERY_REQUIRED |
| ROLLING_BACK | Per-target rollback intents and verified restorations are processed | ROLLED_BACK, RECOVERY_REQUIRED |
| ROLLED_BACK | Prior targets and marker were restored and verified; backups remain retained | terminal pending retention policy |
| RECOVERY_REQUIRED | Journal, artifacts, namespace or operation outcome is ambiguous | reviewed recovery only |
| ABORTED | Transaction ended before protected mutation, with no target changes | terminal |

Transitions are validated and monotonic. COMMITTED, ROLLED_BACK and ABORTED are terminal for ordinary processing. A separately authorized recovery transaction is required for further changes.

COMMITTING and ROLLING_BACK do not prove that every operation in that phase completed. Recovery inspects the last verified per-target record and actual filesystem state.

### 11.21.4 Write-ahead protocol

Every destructive or namespace-changing operation follows this order:

1. Revalidate transaction, exact package snapshot, root policy, target parent and expected object under the approved filesystem security contract.
2. Persist an operation-intent record with target, action, before-state, after-state, backup reference and unique operation ID.
3. Flush and verify the journal record before starting the filesystem operation.
4. Perform exactly one bounded operation through the approved broker-owned, handle-safe backend.
5. Query the resulting object through the approved handle-bound method. Verify identity/type, size and SHA-256.
6. Persist and flush an operation-completed record only after successful verification.
7. On failure, or if actual state matches neither expected before-state nor after-state, stop in RECOVERY_REQUIRED. Never guess or blindly retry.

No write without a durable intent. No completion record before post-operation verification. The installation marker/version record is last. If marker publication fails, the transaction is not COMMITTED.

### 11.21.5 Journal durability and Windows I/O limits

The journal uses broker-owned storage, restrictive ACLs and explicit handle ownership. It must not use the current path-based installer primitives for protected objects.

For each update, the future writer must:
- create a uniquely named temporary object in the same broker-owned journal directory;
- detect short writes and disk-full errors;
- call FlushFileBuffers on the file handle and treat failure as fatal;
- publish the record with a primitive whose atomicity and handle/namespace semantics are documented for the selected Windows/filesystem contract;
- reopen/read back the published record and verify framing, sequence, digest and transaction ID;
- retain the prior valid journal generation until the new generation is verified.

FlushFileBuffers flushes buffered information for the specified file. It does not, by itself, prove atomicity of a multi-file transaction or persistence of every directory metadata update. Journal publication, directory-entry durability, filesystem behavior, storage-controller cache and power-loss guarantees require separate validation.

MoveFileExW with MOVEFILE_WRITE_THROUGH documents write-through behavior for the move/copy operation, but it is path-based and does not resolve the namespace-race blocker. This reference does not authorize its use for protected installer operations.

If publication or read-back cannot be proven, stop before the next protected mutation. A torn tail, missing sequence, digest-chain break or conflicting generations requires RECOVERY_REQUIRED with all artifacts preserved.

### 11.21.6 Staging and backup

Staging and backups live under broker-owned roots with restrictive ACLs, unique transaction-scoped names and exclusive ownership. The client cannot modify them after intake.

Before BACKUP_VERIFIED, every existing replacement target must have a backup copied from the exact admitted object, read back and checked against pre-state identity/size/hash evidence. Absent targets are recorded as absent, but still require commit-time collision checks. The prior installation marker is backed up if it will change. Required space for staging, backups, journal growth and rollback must be checked under an approved policy.

A successful copy return is not proof of a verified backup. Never overwrite another transaction's backup. Missing, altered or unreadable backup blocks commit/rollback and requires recovery.

Staging becomes immutable after verification. Any package, manifest, staged-file or policy digest mismatch invalidates the transaction. Install only from the exact broker-owned staged bytes that were validated.

### 11.21.7 Startup classification and recovery

At startup, before accepting a new install:
1. Open the fixed journal root under the broker identity. Verify ownership, ACL policy, object types and supported filesystem.
2. Enumerate records without following reparse points. Reject unexpected entries and volume crossings.
3. Validate framing, format, transaction ID, sequence continuity, previous-record digest, checksum and allowed state transitions.
4. Verify package/manifest/plan digests and release identity against broker-owned transaction metadata.
5. Verify every referenced staging and backup object by broker-owned identity, size and hash, not name alone.
6. Reacquire destination handles and revalidate root, parent and target identities. Never reuse old handles or confirmation state.
7. Classify each operation as verified-before, verified-after or ambiguous by comparing actual objects with journal evidence.
8. Continue only if the state machine and all before/after evidence yield one safe deterministic action. Otherwise enter RECOVERY_REQUIRED and preserve all artifacts.

Recovery inspection is idempotent. Repeating it without filesystem changes must not mutate targets or advance state. A replayed intent must not repeat a destructive operation if the target already matches the verified after-state. A content hash alone may not establish object identity where identity is required.

No automatic rollback when journal integrity, ACL, backup, target, package digest, root identity or prior operation outcome is uncertain.

### 11.21.8 Retention and user-data preservation

Backups and recovery artifacts remain broker-owned after COMMITTED or ROLLED_BACK until a separate retention policy is approved and the release is independently verified healthy.

Journal cleanup must never remove memories, SQLite databases, histories, logs, preferences, attachments, Ollama models, Python environments, external service data, original Terminal, user backups or files outside the explicit signed program payload.

Retention duration, quotas, operator approval and secure deletion semantics remain open. Do not invent a duration or delete automatically to recover disk space. If capacity is insufficient, reject a new transaction before mutation.

### 11.21.9 Decisions still open

Before implementation, approve:
1. Journal root, service identity, owner, ACL and inheritance policy.
2. Record framing/publication model and atomic publication primitive for every supported filesystem.
3. Deterministic encoding and hash/checksum algorithm.
4. Whether MAC/signature is required, with key source, protection, rotation and recovery.
5. Maximum journal/record size, transaction count, staging/backup quotas and retention.
6. Supported Windows builds/filesystems and power-loss guarantees.
7. Operator procedure for RECOVERY_REQUIRED and evidence preservation.

No production key, MAC key, ACL, quota, retention period or power-loss guarantee is selected here.

### 11.21.10 Fault-injection and adversarial tests

Run on supported Windows runners and disposable test roots. Record Windows build, filesystem, commit, command and result.

Inject termination or I/O failure before/after every journal write, flush, publish and read-back; every staging write/flush/verification; each backup/copy/verification; after intent but before mutation; during/after rename or replace; after post-state verification but before completion record; after completion before next target; around marker publication; at every rollback phase; and during recovery.

Also test disk full, quota exhaustion, access denied, sharing violation, device removal, filesystem error, abrupt process termination, simulated power loss/VM reset, truncated/corrupt/reordered/duplicated/replayed records, missing sequence, altered digest, wrong transaction ID, tampered/missing backup, changed staging bytes, stale package, changed root, substituted target, file-ID reuse, concurrent updater and repeated recovery.

Acceptance requires no target write without a verified intent; no completion without post-state verification; no automatic continuation from ambiguity; each crash point ends in a verified committed state, verified restored state or preserved RECOVERY_REQUIRED; repeated recovery inspection is idempotent; user data and unrelated files remain unchanged.

### 11.21.11 Acceptance decision

The journal is not accepted for production until storage/ACL, record integrity, publication semantics, write-ahead protocol, backup verification, crash recovery and fault-injection tests pass on every declared Windows/filesystem configuration.

**Decision:** state machine and recovery contract specified; execution remains unimplemented. Section 4A still blocks the handle-based backend. Section 11.1 broker trust boundaries remain proposals requiring approval. No installer, broker, rollback engine, recovery utility, package or production release was created or authorized.

### 11.21.12 Microsoft references reviewed

- FlushFileBuffers: https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-flushfilebuffers
- Flushing system-buffered I/O data to disk: https://learn.microsoft.com/windows/win32/fileio/flushing-system-buffered-i-o-data-to-disk
- File caching and metadata behavior: https://learn.microsoft.com/windows/win32/fileio/file-caching
- CreateFile write-through behavior: https://learn.microsoft.com/windows/win32/api/fileapi/nf-fileapi-createfilew
- MoveFileExW and MOVEFILE_WRITE_THROUGH: https://learn.microsoft.com/windows/win32/api/winbase/nf-winbase-movefileexw


## 11.22 Per-file rollback protocol and restoration evidence

**Audit date:** 2026-11-16.  
**Status:** rollback protocol specification only. No restore/delete code, transaction engine, broker, installer or rollback test was implemented.

### 11.22.1 Scope and rollback boundary

Rollback is a compensating transaction for a release that has not reached the durable COMMITTED state. It reverses only operations recorded in that transaction, in reverse order of their verified application.

COMMITTED remains terminal. A failure discovered after COMMITTED does not rewrite the historical transaction as rolled back. It requires a new, separately authorized repair/recovery transaction with its own journal and confirmation policy.

Rollback may touch only explicit program targets in the authenticated release plan and the transaction's own installation marker. It must never include memories, SQLite databases, conversation history, preferences, logs, attachments, Ollama models, Python environments, external services, original Terminal files outside the allowlist, user backups or arbitrary files.

This protocol does not authorize automatic rollback. Whether a deterministic failure triggers automatic compensation or requires operator confirmation remains a policy decision.

### 11.22.2 Per-target state model

Each target has its own journaled state, separate from the overall transaction state:

| Per-target state | Meaning | Permitted next states |
|---|---|---|
| NOT_STARTED | No operation intent exists for this target | APPLY_INTENT, NO_CHANGE_VERIFIED |
| APPLY_INTENT | Durable write-ahead intent exists; mutation outcome not yet proven | APPLIED_VERIFIED, NO_CHANGE_VERIFIED, RECOVERY_REQUIRED |
| APPLIED_VERIFIED | New target object and expected post-state were verified | RESTORE_INTENT, RECOVERY_REQUIRED |
| RESTORE_INTENT | Durable rollback intent exists; restoration outcome not yet proven | RESTORED_VERIFIED, RECOVERY_REQUIRED |
| RESTORED_VERIFIED | Prior approved content/metadata restored and verified | terminal for this target |
| NO_CHANGE_VERIFIED | Inspection proves the original target remains unchanged, or an originally absent target remains absent | terminal for this target |
| RECOVERY_REQUIRED | Actual object does not match a uniquely safe before/after state | manual/reviewed recovery only |

A target cannot move from RESTORED_VERIFIED or NO_CHANGE_VERIFIED back to an apply state in the same transaction. A new release transaction is required for another change.

### 11.22.3 Classify before changing anything

Before rollback, inspect each target using the approved handle-bound namespace contract and compare it with the journal's expected before-state and after-state. Classify it as exactly one of:

1. BEFORE: the original object is still present and matches the recorded pre-state identity and required metadata/content evidence. No restoration is needed; record NO_CHANGE_VERIFIED.
2. AFTER: the target is exactly the object installed by this transaction and matches its recorded post-state identity, type, size and hash. It is eligible for a compensating restore, subject to backup verification.
3. AMBIGUOUS: the target is missing unexpectedly, has a different identity, type, parent, content or metadata, or the required namespace proof is unavailable. Stop and record RECOVERY_REQUIRED.

Do not classify by path string or content hash alone where object identity is required. Do not overwrite an unexpected object, even if its contents resemble the package. A third-party modification after the updater's write must be preserved for review, not silently replaced.

If the process crashed after a durable apply intent but before the apply-completed record, the same classification applies. If the target is exactly BEFORE, record NO_CHANGE_VERIFIED. If it is exactly AFTER, it is eligible for rollback. If neither can be proven, require recovery.

### 11.22.4 Reverse-order restoration

Rollback processes targets in the exact reverse order of their verified apply-completed sequence numbers. It does not sort by path or infer dependency order. The journal sequence is the authoritative operation order.

For each target classified AFTER:

1. Verify the broker-owned backup reference, object identity, size, digest and required metadata against the pre-state backup record.
2. Verify the backup belongs to this transaction and has not been reused by another target or transaction.
3. Revalidate the current target and parent under the approved namespace contract.
4. Persist and flush a RESTORE_INTENT record containing the target operation ID, installed-object identity/hash, backup identity/hash and expected restored content/metadata.
5. Restore from the verified broker-owned backup using the approved handle-safe primitive.
6. Read back the restored target through an admitted handle and verify its content hash, size, type and every metadata field included in the approved preservation contract.
7. Record the new restored object's identity. A copy-based restore may create a new file ID; it must not falsely claim that the original pre-update file ID was recreated.
8. Persist and flush RESTORED_VERIFIED only after every required check succeeds.

If the target was originally absent and the transaction created it, rollback may remove it only when the exact transaction-created object is still present and matches the recorded post-state identity/type/hash. Persist a delete/restore intent first, perform the bounded removal, verify that the name is absent relative to the admitted parent, then record completion. If the object identity or namespace cannot be proven, do not delete it; enter RECOVERY_REQUIRED.

If the original target was replaced and its backup is missing, corrupt, inaccessible or fails verification, do not attempt reconstruction from the release package. The package contains the new version, not the prior version. Preserve the installed target and all remaining evidence for reviewed recovery.

### 11.22.5 Metadata and restoration equivalence

The transaction must define, before implementation, which metadata is part of the restore contract for each managed file class. Candidate fields requiring an explicit decision include file attributes, timestamps, security descriptor/ACL, owner, alternate data streams, hard-link relationships, compression/encryption attributes and other filesystem-specific metadata.

A backup hash proves content bytes, not complete filesystem equivalence. A successful rollback claim must state exactly which content and metadata dimensions were restored and verified. If a required metadata field cannot be captured or restored on a supported filesystem, that file class is not eligible for automated rollback on that filesystem.

The pre-update file ID may differ after a copy-based restore. The journal must record the new identity and separately prove the restored content/metadata contract. It must not use the old ID as evidence that the same object was recreated.

### 11.22.6 Installation marker and release identity

The installation marker/version state is restored after all payload targets, in the reverse of its final publication order. It must never advertise the old release while any payload file remains in the new or ambiguous state.

If marker restoration fails, the transaction remains ROLLING_BACK or enters RECOVERY_REQUIRED; it cannot be ROLLED_BACK. The marker's own prior bytes, identity and required metadata must have a verified backup.

A rollback does not reset or lower a broker-owned anti-rollback sequence. Reinstalling an older signed package is a separate policy-controlled recovery action. Restoring program files and changing trusted release sequence state are distinct operations with separate authorization and audit.

### 11.22.7 Crash recovery during rollback

On restart, never trust an in-memory rollback cursor. Re-read and validate the journal, reacquire handles, verify backup artifacts and classify every target again.

For a target with a durable RESTORE_INTENT but no completion record:
- if the target matches the verified restored state, record RESTORED_VERIFIED after independent read-back;
- if it still matches the exact installed AFTER state and the backup remains valid, resume only if the approved recovery policy permits repeating the restore operation;
- if it matches neither state, or the backup is uncertain, enter RECOVERY_REQUIRED.

Recovery must not assume a failed API call means no mutation occurred. It must inspect actual state. Repeated inspection without changes is idempotent. No backup or journal artifact is deleted during recovery.

The transaction reaches ROLLED_BACK only when every target is RESTORED_VERIFIED or NO_CHANGE_VERIFIED, the installation marker is restored and verified, and the final rollback record is durably published and read back.

### 11.22.8 Failure matrix

| Condition | Required action |
|---|---|
| Target still equals original before-state | Record NO_CHANGE_VERIFIED; do not rewrite |
| Target equals exact transaction-installed after-state and backup is valid | Restore under write-ahead protocol |
| Target is missing or differs from both known states | RECOVERY_REQUIRED; preserve it |
| Backup missing, corrupt or wrong transaction | RECOVERY_REQUIRED; do not synthesize old content |
| Backup content valid but required metadata cannot be restored | RECOVERY_REQUIRED; do not claim full rollback |
| Created target still matches exact transaction-created object | Remove under durable intent, then verify absence |
| Created target was replaced or modified by another actor | RECOVERY_REQUIRED; do not delete |
| Crash after restore intent | Reacquire and classify; never assume outcome |
| Crash after restore but before completion record | Verify restored content/metadata and new identity, then record completion |
| Marker restore fails | Keep transaction nonterminal or RECOVERY_REQUIRED |
| Journal or namespace validation fails | RECOVERY_REQUIRED; preserve all artifacts |

### 11.22.9 Required rollback tests

On disposable Windows roots and every declared supported filesystem:
- rollback after each target position in a multi-file commit;
- reverse ordering is exact and recorded;
- crash before/after restore intent, file restore/delete, read-back, completion record and marker restore;
- target remains BEFORE, is exact AFTER, is missing, or is externally modified;
- backup missing, truncated, tampered, substituted or associated with another transaction;
- restore content matches but metadata differs;
- ACL/owner/alternate-stream preservation according to the approved per-class contract;
- newly created file removal, including replacement by a different object before rollback;
- file ID changes after copy-based restoration;
- disk full, access denied, sharing violation, volume removal and filesystem errors during rollback;
- recovery repeated multiple times and after process/machine restart;
- no rollback operation touches user data, original Terminal outside the allowlist, unrelated files or another transaction's artifacts.

Every test records Windows build, filesystem, commit, command, before/after identities and hashes, journal sequence and result. A passing test is limited to the tested OS/filesystem configuration.

### 11.22.10 Acceptance decision

Per-file rollback is not accepted until object classification, backup ownership/integrity, restore metadata contract, write-ahead ordering, reverse sequencing, marker handling, crash recovery and fault-injection tests pass on all declared supported configurations.

**Decision:** rollback behavior is specified, not implemented. The Windows namespace-resolution blocker in section 4A remains open. Journal trust/ACL decisions in section 11.21.9 and broker authorization in section 11.1 remain open. No automatic rollback policy, installer implementation, privileged operation or production release is approved by this section.


## 11.23 Post-install health verification and the durable COMMITTED boundary

**Audit date:** 2026-11-16.  
**Status:** design specification only. No health-check implementation, updater orchestration, broker, installer, migration, or runtime test was added.

### 11.23.1 Existing behavior observed

The current Platform source exposes GET /api/health. It returns status, service identifier, API version, core load state, and timestamp. The endpoint does not run a database integrity check, load the core, send a chat request, or verify Ollama/OpenJarvis availability.

The current launcher polls that endpoint for up to 30 seconds, with a 1.5-second request timeout and 0.25-second retry sleep. It accepts the response when HTTP status is 200 and the service identifier equals sermax-platform-api. The launcher then opens the browser. Its acceptance condition does not bind the responding process to the package digest or release being installed.

The API initializes its SQLite schema during application startup. The core is loaded lazily on a chat request. The API reports core as not_loaded before that first load. The current health endpoint is therefore a basic API liveness signal, not proof that every Platform or SERMAX capability is ready.

These observed development values are not approved installer timeouts or production acceptance criteria. Do not copy the 30-second launcher timeout into a privileged updater policy without a separate measurement and approval.

### 11.23.2 Separate health dimensions

The future installer must report distinct results. A single green health flag is insufficient.

1. **Payload integrity:** every installed payload target matches the authenticated manifest's exact path, size, digest, type, and required metadata. Verify through the approved object-bound filesystem backend. This is an installation integrity check, not an application health probe.
2. **Process startup:** the intended candidate process starts and remains alive through the configured stabilization interval. Bind evidence to the process instance, not PID alone. PID reuse, a pre-existing server, or a process serving another release must not satisfy the check.
3. **API liveness:** the local API responds and identifies itself as the SERMAX Platform API. The existing GET /api/health is currently suitable only for this limited signal.
4. **API readiness:** required routes and dependencies for the selected release are initialized. Readiness must be defined separately from liveness. A successful TCP connection or HTTP 200 alone does not prove readiness.
5. **Persistence integrity:** if the release requires Platform persistence, perform an approved read-only check of the existing database and required schema. Do not run migrations, write probe rows, checkpoint or rewrite the user's database as part of a health probe. Any migration must be a separately authorized, journaled, reversible operation.
6. **Core integration:** report whether the existing SERMAX core is available and whether the release requires it for the declared installation profile. Do not force-load the core merely to make a health flag green. The current lazy-load behavior means not_loaded is not by itself a startup failure.
7. **Optional engines and integrations:** Ollama, OpenJarvis, Pestinha, and other optional components are checked only when the selected release/profile explicitly declares them required. Otherwise report unavailable, skipped, or not configured as a capability status, not as base installation corruption.

The release policy must declare required capabilities before installation. The installer must not silently change an optional dependency into a mandatory one, or accept a missing required component.

### 11.23.3 Release-bound health evidence

A health result is valid only for the exact candidate transaction. The evidence record must bind:
- transaction ID and journal generation;
- product, channel, release identifier and signed manifest digest;
- exact installed payload inventory digest;
- process instance identity, including a non-reusable process creation identity and verified executable image identity;
- probe name, result, start/end monotonic timestamps, attempt count and stable failure code;
- API-reported product/build identity where an endpoint is selected;
- required-capability policy version and the list of required, optional, skipped and failed checks.

A PID, URL, status code, service name, or timestamp by itself is not release identity. The current /api/health response does not return a manifest digest or transaction identity. Extending the endpoint or defining a broker-authenticated probe channel is an unresolved interface decision. Do not claim the current endpoint provides release-bound evidence.

Health logs must exclude tokens, credentials, private keys, chat contents, memory contents, and unnecessary personal paths. Store bounded diagnostic codes and sanitized messages in broker-owned transaction evidence.

### 11.23.4 Readiness sequence before marker publication

The proposed order is:

1. Verify the authenticated package snapshot and every staged file.
2. Apply the approved payload operations using the accepted filesystem security boundary.
3. Read back every target and verify post-state identity, content, type, size and approved metadata. Record each target as APPLIED_VERIFIED.
4. Start or attach to the exact candidate process under a documented deployment model. Prove that the process serves the candidate release, not an old process or unrelated service.
5. Run the required liveness, readiness, persistence and capability probes for the selected release profile. Use monotonic deadlines, bounded attempts and explicit per-probe and overall time limits. Concrete values remain approval inputs and must come from measurements on supported Windows configurations.
6. Require the process to remain healthy through the approved stabilization interval. Any crash, identity change, timeout, failed required probe or changed payload invalidates the health evidence.
7. Persist and verify a HEALTH_VERIFIED journal milestone containing the release-bound evidence digest. This milestone does not mean the transaction is committed.
8. Revalidate the transaction lock, root, targets, payload digest, health evidence freshness and marker preconditions.
9. Persist and flush a marker-publication intent. Publish the installation marker/version record using the approved handle-safe operation, then read it back and verify its exact release identity, digest and metadata.
10. Persist and flush the final COMMITTED record. Read it back and verify its sequence, integrity and state transition. Only then report the transaction as committed.

The marker is the final protected payload publication. The journal's final COMMITTED record necessarily follows marker verification. This distinction preserves the rule that the marker never advertises a release whose payload or required health checks have not passed.

The health probe must not depend on reading the new marker as its only proof of candidate identity, because the marker is deliberately unpublished until after health verification. Candidate identity must come from the broker-owned transaction and independently verified process/image evidence. The exact mechanism remains an interface and deployment-model decision.

### 11.23.5 Failure, timeout and crash behavior

- A failed required check before COMMITTED prevents marker publication.
- A deterministic failure may enter ROLLBACK_REQUIRED only under an explicitly approved rollback policy. This section does not authorize automatic rollback.
- If process identity, namespace, payload state, health evidence, journal integrity or rollback eligibility is ambiguous, enter RECOVERY_REQUIRED and preserve staging, backups and logs.
- A crash after HEALTH_VERIFIED but before marker publication requires reacquisition of handles and fresh validation. Do not trust an old process, old health result or old in-memory state.
- A crash after marker publication but before the durable COMMITTED record is not a committed transaction. Re-read the journal, revalidate all payload targets and marker, reacquire the candidate process, and rerun required health checks. Complete COMMITTED only if the approved recovery policy proves every condition. Otherwise follow the approved rollback/recovery policy or stop in RECOVERY_REQUIRED.
- After the durable COMMITTED record is verified, COMMITTED is terminal. A later crash, degraded service or failed operational check is handled as a separately authorized repair transaction, not retroactive rollback.

Health verification is a bounded installation gate. It does not guarantee future uptime or replace ongoing operational monitoring.

### 11.23.6 User-data and persistence protection

The installer payload and rollback allowlist must exclude user memories, SQLite databases, conversation history, preferences, logs, attachments, Ollama models, Python environments, external service data, original Terminal files outside the approved payload, and user backups.

A health probe must not send a real chat prompt, alter memory, write a test conversation, run project migrations, or mutate user configuration. Persistence checks must be read-only. If the current runtime startup performs schema initialization, that behavior must be distinguished from installer activity and reviewed separately; the updater itself must not claim a byte-for-byte preservation result without evidence covering database, WAL and SHM files.

No automatic cleanup or migration is authorized by this section.

### 11.23.7 Required verification and fault-injection tests

On each declared Windows build and filesystem, test:
- valid and invalid payload read-back, missing/extra files, wrong digest, wrong file identity and metadata mismatch;
- old server already listening, wrong service identity, wrong executable image, PID reuse, candidate process exit, restart and crash during stabilization;
- API liveness success with readiness failure, malformed response, wrong release identity, stale response, timeout and endpoint unavailable;
- database missing, unreadable, corrupt, locked, schema-incompatible and WAL/SHM present, proving probes do not mutate user data;
- core unavailable, core not yet loaded, core load failure, and optional engines absent or unhealthy under both required and optional profiles;
- failure before and after HEALTH_VERIFIED, marker intent, marker publication, marker read-back and final COMMITTED journal publication;
- process termination, service crash, disk full, access denied, journal truncation, stale evidence, package substitution and repeated recovery inspection;
- proof that no required check can be skipped by a missing field, unknown capability, malformed result or unrecognized policy version.

Record OS build, filesystem, commit, release digest, test command, journal sequence, probe evidence digest and result. Passing results apply only to the tested configuration.

### 11.23.8 Decisions and acceptance gate

Before implementation, approve the health profile schema, required capability policy, process identity mechanism, release-bound probe interface, deployment/startup topology, read-only database check, stabilization and timeout values, evidence retention, and deterministic failure/rollback policy.

The health gate is accepted only when the candidate process is proven to match the signed release, every required probe passes, evidence is durably bound to the transaction, the marker is published and verified last, and the final COMMITTED journal record is durable and read back.

**Decision:** post-install health and the COMMITTED boundary are specified only. The existing endpoint proves API liveness at a basic level and does not prove full readiness. No endpoint, health runner, installer, broker, transaction engine, migration, rollback policy or production release was implemented or authorized. The namespace-resolution blocker in section 4A, journal decisions in section 11.21.9, broker approval in section 11.1 and rollback policy in section 11.22 remain open.


## 11.24 Power-loss recovery around marker publication and COMMITTED

**Audit date:** 2026-11-16.  
**Status:** recovery protocol specification only. No journal writer, marker publisher, recovery broker, installer, power-loss test or production operation was implemented.

### 11.24.1 Scope and invariant

This section defines recovery classification when Windows, the process, the storage device or power fails around the installation marker and final COMMITTED journal record.

The authoritative success condition remains: the exact authenticated payload is verified, required health evidence is valid for that transaction, the marker is published and read back, and a valid final COMMITTED record is durably published and read back.

The marker alone never proves COMMITTED. A successful API return, a process exit code, a browser opening, a journal intent, or an in-memory state never proves COMMITTED.

Recovery runs under the broker identity before the candidate application is exposed to normal use or a new installation is accepted. If the recovery authority is unavailable or cannot establish a unique safe state, block normal startup of the candidate and preserve all transaction artifacts. Do not let an ordinary client process repair or rewrite the marker or journal.

### 11.24.2 Required write-ahead records

The journal must distinguish these immutable, transaction-bound events:
- MARKER_PUBLISH_INTENT, containing transaction ID, marker target identity, verified old marker evidence, exact new marker bytes/digest, backup reference, release/manifest digest and operation ID;
- MARKER_PUBLISHED_VERIFIED, recorded only after independent read-back proves the exact new marker bytes, identity and approved metadata;
- COMMIT_RECORD_INTENT, identifying the unique final COMMITTED record sequence, previous-record digest and exact record digest;
- COMMITTED, the complete final record published using the approved journal protocol, flushed, reopened and validated.

Each event uses the existing journal envelope, strict sequence, transaction ID and hash-chain rules from section 11.21. A duplicate or conflicting intent, sequence gap, unknown event or invalid digest fails closed. The final COMMITTED record is terminal and must not be rewritten to make recovery appear successful.

The journal publication primitive and its power-loss semantics must be approved for every supported filesystem. A temporary-file pattern, FlushFileBuffers call or rename name alone is not a proof of atomicity or directory-entry durability.

### 11.24.3 Recovery evidence reacquisition

After restart, discard all in-memory handles, cursors, process references, confirmations, health results and cached filesystem observations.

The broker must:
1. Verify its own identity, fixed journal root, ACLs, supported volume and filesystem contract.
2. Parse the complete journal chain, validate framing, transaction ID, record sequence, previous digests, record digests and allowed transitions.
3. Locate the latest valid marker intent and any matching marker completion and commit records.
4. Reacquire the installation root, marker, payload targets, backup and staging objects through the approved handle-safe backend.
5. Independently verify target identities, types, content hashes and required metadata against the signed release and journal.
6. Verify the marker as one of: exact OLD state, exact NEW state, or AMBIGUOUS. Compare identity, bytes, digest and approved metadata; a filename or parseable version string is insufficient.
7. Revalidate the signed manifest, package digest, release policy, required health evidence and transaction lock. A health result from a process that no longer exists is stale. Start a fresh candidate process and rerun required probes when the policy requires it.
8. Record a recovery classification before any new protected mutation.

No previous handle or old health result is reused. Repeated inspection without external changes must be idempotent.

### 11.24.4 Marker classification and permitted response

| Observed state after restart | Interpretation | Required response |
|---|---|---|
| Exact OLD marker, exact verified payload BEFORE | Marker publication did not take effect; transaction is not committed | Record classification. Abort or rollback only under approved policy. Do not claim success. |
| Exact OLD marker, payload is exact verified NEW | Marker was not published or did not persist; transaction is not committed | Keep candidate unavailable. Revalidate health and policy. Re-publication requires explicit recovery authorization and a new durable marker intent if the original intent cannot be safely resumed. Otherwise RECOVERY_REQUIRED. |
| Exact NEW marker, payload exact NEW, health evidence fresh and valid, no valid COMMITTED record | Marker publication likely completed but final commit record is absent | Transaction remains non-COMMITTED. Recovery may finish only if an approved deterministic policy authorizes it, all evidence is independently reacquired, and a valid COMMIT_RECORD_INTENT can be established. Otherwise RECOVERY_REQUIRED. |
| Exact NEW marker, payload exact NEW, valid complete COMMITTED record and valid journal chain | Commit record survived and validates after restart | Treat as COMMITTED only after full independent verification of the final record, payload, marker, release identity and journal chain. Do not rewrite the terminal record. |
| Exact NEW marker, payload missing, mixed, changed or ambiguous | Marker advertises a release whose payload cannot be proven | RECOVERY_REQUIRED. Keep candidate unavailable. Do not repair by copying from an unverified source or silently lower the marker. |
| Marker missing, truncated, malformed, wrong identity or metadata mismatch | Marker state is ambiguous or damaged | RECOVERY_REQUIRED. Preserve marker bytes, backup, journal and payload. Do not infer OLD or NEW from partial contents. |
| Journal chain broken, torn final record, conflicting generations or unknown critical field | Commit authority cannot be established | RECOVERY_REQUIRED. Do not accept a COMMITTED state from an isolated record or filename. Preserve all generations and evidence. |
| Valid COMMITTED record but payload or marker no longer matches | Post-commit tampering, storage failure or later damage | Historical transaction remains COMMITTED. Block normal use and require a separately authorized repair transaction. Never rewrite history as rollback. |

The table classifies evidence; it does not grant automatic rollback or marker republishing authority.

### 11.24.5 Power loss at each publication boundary

- **Before MARKER_PUBLISH_INTENT is durable:** no marker mutation is allowed to have started. Recovery verifies payload and marker before deciding whether the transaction is still safely abortable.
- **After intent, before marker operation:** inspect the marker. If exact OLD, no publication is proven. Do not blindly repeat the operation.
- **During marker replacement:** treat any state other than exact OLD or exact NEW as AMBIGUOUS. A partially written, missing, substituted or metadata-mismatched marker enters RECOVERY_REQUIRED.
- **After marker operation, before MARKER_PUBLISHED_VERIFIED:** independently inspect the marker. Exact NEW can be recorded as verified only after all identity/content/metadata checks pass. Exact OLD means no publication is proven. Anything else is ambiguous.
- **After MARKER_PUBLISHED_VERIFIED, before COMMIT_RECORD_INTENT:** transaction is still not committed. Revalidate all targets and health evidence. Continue only under approved recovery policy.
- **After COMMIT_RECORD_INTENT, before final record publication:** transaction is still not committed. Verify whether the exact final record exists and validates. If absent, recovery must follow the approved journal protocol; it must not invent or skip sequence numbers.
- **During final record publication or flush:** a partial/torn record is not COMMITTED. Preserve it and enter RECOVERY_REQUIRED unless the journal's approved recovery rules unambiguously establish a valid prior state and safe continuation.
- **After a complete COMMITTED record is published, before the writer receives read-back confirmation:** on restart, independently parse and verify the full journal chain and final record, then verify marker and payload. A complete valid final record that survives restart may be recognized as COMMITTED only if the approved durability contract proves the publication requirements. If durability cannot be established, RECOVERY_REQUIRED.
- **After COMMITTED is verified:** the transaction is terminal. Subsequent failures require a new repair transaction.

Do not assume an interrupted filesystem call had no effect. Inspect actual state through reacquired handles.

### 11.24.6 No blind replay and no false success

Recovery must never:
- replay marker replacement because the caller did not receive a success response;
- append a second COMMITTED record to hide an uncertain first publication;
- accept a marker without matching the exact signed manifest/release digest;
- accept a COMMITTED record without the full preceding valid journal chain;
- declare success from the presence of a version file, executable, process, URL or HTTP status alone;
- run rollback or delete backups when the before/after classification is ambiguous;
- expose a mixed or unverified candidate to the user.

Every recovery action is a new durable intent followed by one bounded operation, independent read-back and a completion record. A unique operation ID prevents duplicate logical actions, but it does not replace inspection of the actual filesystem state.

### 11.24.7 Startup gate and user-data isolation

The recovery broker must classify unfinished transactions before the candidate application accepts requests. If the broker cannot run, the journal cannot be read, or the root/marker/payload is ambiguous, fail closed and present a recovery-required status through a separate trusted recovery path. Do not launch a possibly mixed candidate just to expose its own health endpoint.

Recovery is restricted to the signed program payload, its transaction-owned marker and broker-owned transaction artifacts. Memories, SQLite databases, conversation history, preferences, logs, attachments, Ollama models, Python environments, external services, original Terminal outside the allowlist and user backups remain excluded.

No recovery probe may write a test conversation, alter memory, migrate the database or clean user data. No cleanup occurs as part of power-loss recovery.

### 11.24.8 Required power-loss and storage-fault matrix

Run on every declared Windows build, supported filesystem and storage configuration using disposable test roots and controlled VM power cuts or equivalent fault injection. Test interruption:
- before/after each marker intent write, flush, publication and read-back;
- during marker replacement, including torn data and namespace interruption;
- before/after marker verification and health evidence revalidation;
- before/after COMMIT_RECORD_INTENT, final record write, flush, publication and read-back;
- with full disk, quota exhaustion, write cache enabled, access denied, sharing violation, volume removal, filesystem errors and abrupt VM power-off;
- with exact OLD marker, exact NEW marker, missing marker, corrupt marker, substituted marker, mixed payload, changed target and invalid backup;
- with valid COMMITTED record, missing record, torn tail, duplicate sequence, broken hash chain, conflicting journal generations and wrong transaction ID;
- after restart, during repeated recovery inspection and during every separately authorized recovery action.

Acceptance requires every injected cut to yield exactly one of: independently verified COMMITTED, a policy-authorized and fully verified rollback/abort, or RECOVERY_REQUIRED with all artifacts preserved. No ambiguous case may produce success. Repeated inspection without external changes must not mutate the payload or advance the journal. User data and unrelated files must remain unchanged.

Record machine/VM configuration, Windows build, filesystem, storage configuration, commit, release digest, exact injection point, journal sequence, marker classification, target identities/hashes and recovery result. A test result applies only to the configuration tested.

### 11.24.9 Decisions and acceptance gate

Before implementation, approve:
1. Marker format, exact bytes, identity and metadata contract.
2. Marker publication primitive and power-loss semantics per supported filesystem.
3. Journal record publication, flush, read-back and torn-tail policy.
4. Broker startup gate and recovery interface when the normal application cannot start.
5. Whether exact NEW marker plus valid payload but absent COMMITTED record can ever be finalized automatically, and under which independently verifiable evidence.
6. Operator authorization and audit procedure for RECOVERY_REQUIRED.
7. Supported storage devices, caching configurations, Windows builds and power-loss test method.

**Decision:** power-loss classification around marker and COMMITTED is specified only. No installer, recovery engine, broker, marker publisher, journal writer, automatic rollback policy, power-loss test or production release was implemented or authorized. Section 4A namespace resolution, journal storage/ACL/publication decisions in section 11.21.9, broker approval in section 11.1, rollback policy in section 11.22 and health-profile decisions in section 11.23 remain open.

## 11.25 Broker authorization, service lifecycle and security boundary

**Audit date:** 2026-11-16.  
**Status:** security and authorization contract proposal only. No Windows service, broker executable, named-pipe server, ACL, privilege, consent screen, signing-key deployment or privileged operation was implemented or authorized.

### 11.25.1 Observed implementation boundary

The current Platform installer remains a development preview. The GUI invokes the Python installation engine directly and accepts caller-selected package and destination paths. The engine performs path-based operations. The inspected installer source does not establish a Windows service, broker process, named-pipe endpoint, service SID, client-token authorization or protected privileged-operation boundary.

The existing named-pipe proposal in section 11.14 and trust-boundary proposal in sections 11.1–11.12 are design material, not evidence that these components exist. The existing signed Windows updater is a separate track and is not integrated with this Platform installer.

Consequently:
- The GUI, package builder and current installer core must remain unprivileged.
- Do not elevate the current Python installer or expose its path-taking functions through an elevated wrapper.
- Do not describe the proposed broker as implemented, available or tested.
- Do not perform installation, rollback, marker or journal writes through the current path-based engine on a protected production installation.

### 11.25.2 Threat model and security objective

The initial target remains a machine-wide installation. The broker must defend against:
- A compromised or malicious unprivileged SERMAX GUI or package-builder process.
- Another process running as the same interactive user, including one in the same logon session.
- A different standard local user or another logon session.
- Pipe squatting, unauthorized pipe instances, client impersonation and service identity confusion.
- Malformed, oversized, duplicate, reordered, replayed or concurrent IPC requests.
- Package substitution between client selection, intake, validation and installation.
- Reparse-point, hard-link, path traversal, alternate data stream, volume and namespace attacks.
- Journal, staging, backup, marker, service configuration or audit-log tampering.
- Downgrade, stale release, replayed transaction, duplicate operation and confused-deputy requests.
- Denial of service through resource exhaustion, stalled uploads, lock retention or repeated malformed requests.

The initial model does not claim resistance against local administrators, SYSTEM, kernel compromise, boot compromise, offline disk modification, physical attacks or compromise of the release-signing/build infrastructure. If administrator resistance becomes a requirement, this design needs a different security architecture.

**Objective:** an in-scope unprivileged process must not gain arbitrary file-write, delete, rename, ACL-change, process-launch or command-execution authority through the broker. The broker may perform only a bounded, explicitly approved release transaction against its provisioned destination and broker-owned transaction state.

### 11.25.3 Service identity and privilege boundary

1. Select a dedicated virtual service account and per-service SID as the leading candidate. Evaluate a restricted service SID only after testing the real service token and every required access.
2. Do not default to LocalSystem. Do not enable administrator privileges merely to simplify file operations. Any privilege must have a documented API need, exact scope, negative tests and explicit approval.
3. Deny interactive logon to the service identity. Do not share the broker process with unrelated services.
4. Grant the service only the access required to its fixed application root, staging, journal and backup locations. It must have no broad access to user documents, memories, conversation history, SQLite databases, credentials, Ollama models or unrelated application data.
5. Protect the service executable, dependent DLLs, configuration, service registry configuration and parent directories against modification by standard users. Do not grant untrusted callers SERVICE_CHANGE_CONFIG, SERVICE_STOP, SERVICE_START, WRITE_DAC, WRITE_OWNER or service-binary write access.
6. The service-object DACL and service-binary ACL must be reviewed separately. A pipe DACL does not protect the service configuration or executable.
7. Do not accept a caller-selected service identity, service name, destination root, staging path, journal path or backup path.
8. Keep the exact service account, service SID type, restricted SID set, enabled privileges, service-object DACL and installation mechanism unresolved until a token/ACL evidence package is reviewed.

A dedicated service SID or virtual account is a candidate, not an approved configuration. The actual token must be captured on every supported Windows build and tested with effective access checks.

### 11.25.4 Client authentication versus operation authorization

The pipe DACL is the first access gate, not proof that the connecting process is the genuine SERMAX GUI. Any process granted access in the same authorized logon session may attempt to connect.

For each connection and each state-changing request, the broker must:
- Validate the Windows client token, user SID, logon SID, session ID, integrity level and required group/elevation facts using trusted OS APIs.
- Reject anonymous, network, unexpected-session and unsupported identities.
- Treat PID and executable path as diagnostic evidence only, not as identity proof.
- Revalidate connection identity and authorization at the operation boundary. Do not trust identity claims inside JSON.
- Use impersonation only for client authentication and token inspection. Revert to the service identity before privileged broker work, check that reversion succeeded, and fail closed if it did not.
- Apply a separate authorization decision to every operation. A successful pipe connection does not authorize package intake, installation, rollback, marker publication or recovery.
- Bind approval to the authenticated interactive user/session, exact release digest, manifest digest, destination identity, operation set and transaction ID. Any change to these fields invalidates the approval.

The versioned, bounded message framing and initial operation allowlist remain specified in section 11.14. No generic path, file, process or command operation is permitted.

### 11.25.5 Explicit user approval and release policy

A normal installation transaction requires a clear user confirmation before the broker begins protected destination mutation. The confirmation display must show:
- Product identity and publisher identity established by broker-side signature verification.
- Release version and broker-computed package and manifest digests, shown in a human-usable form.
- The fixed destination identity and whether this is an initial installation or an update.
- The exact approved operation class and the program-file scope.
- The expected restart/service interruption, if any.
- The user-data preservation boundary and any migration requiring separate approval.

The confirmation must be generated from broker-verified facts, not client-supplied labels. The broker must not accept a Boolean such as `approved: true` from an untrusted client as proof of consent. The approval interaction must be bound to the active transaction and expire if the package, manifest, destination, policy, session or transaction changes.

The broker independently verifies:
1. Product and package identity.
2. Signature against a broker-protected production trust anchor.
3. Signer policy, algorithm policy, key validity and revocation/rotation state.
4. Manifest schema, normalized file list, types, sizes and hashes.
5. Broker-owned staging digest and exact package snapshot to be installed.
6. Release version and anti-rollback sequence against broker-owned state.
7. Destination policy, transaction lock, user-data exclusions and required health/recovery gates.

User consent never overrides a failed signature, revoked key, unsupported schema, downgrade rejection, malformed package, ACL failure, namespace uncertainty, journal inconsistency or RECOVERY_REQUIRED state.

No silent update is authorized by this proposal. Any future unattended-update policy requires a separate explicit decision defining the publisher, release channel, allowed versions, trigger, notification, rollback and recovery behavior. It must not be inferred from a prior interactive approval.

### 11.25.6 Request binding, replay prevention and idempotency

Every state-changing request must bind, at minimum:
- Protocol version and authenticated connection/session identity.
- Unique request ID and transaction ID.
- Unique operation ID and idempotency key.
- Monotonic request/chunk sequence where streaming is used.
- Product identity, release version, signed manifest digest and complete package digest.
- Broker policy version, fixed destination identity and allowlisted action set.
- Explicit user-approval record and its expiry.
- Expected current transaction state and expected journal sequence.

The broker rejects duplicate, stale, out-of-order, replayed, conflicting or cross-session requests. A repeated request ID must return the existing transaction result or a stable rejection; it must never repeat a protected mutation. The broker independently inspects actual filesystem and journal state after a timeout or disconnect. A missing client response does not prove that the operation failed.

Do not serialize InventorySnapshot, ConfirmedPlan, native handles, access tokens or caller-provided path authority across IPC. These are broker-owned in-memory capabilities and must be reacquired after restart under the rules already specified in sections 11.19, 11.20 and 11.24.

### 11.25.7 Filesystem and transaction authority

- The destination is provisioned by the approved installation model. It is not selected by an IPC request.
- The broker accepts package bytes or a narrowly controlled intake stream, copies them into broker-owned staging, closes and reopens the staged object, and verifies the exact bytes it will install.
- The broker does not install from a client-writable source after validation.
- All protected operations must use an accepted filesystem security contract. The namespace-resolution blocker in section 4A remains open. The proposed NT handle-relative approach is not a confirmed cross-version user-mode security guarantee.
- Do not replace the section 4A blocker with a claim that a service, DACL or protected root automatically eliminates namespace races. Demonstrate parent ownership, effective ACLs, supported filesystem semantics and adversarial behavior.
- The broker never falls back to path-based writes if handle-safe operations or namespace admission fail.
- The broker may write only allowlisted program payload targets and its own transaction artifacts. User data remains outside the replaceable payload and rollback scope.
- A single writer owns each protected root. Concurrent transactions are rejected or queued under an approved bounded policy. No second writer may bypass an active journal or recovery gate.
- Cancellation is accepted only at explicitly defined safe points. Disconnect, timeout, GUI exit or service stop does not imply rollback and does not authorize deletion of transaction artifacts.
- On startup, unfinished transactions are classified before normal application requests or new installations are accepted. If recovery cannot establish one safe state, remain RECOVERY_REQUIRED.

### 11.25.8 Service lifecycle and recovery behavior

The service lifecycle contract must cover:
- Installation and update of the broker itself through a separately trusted mechanism.
- Startup type, service dependencies, service account provisioning and service binary integrity.
- Startup recovery gate before accepting install requests or releasing the candidate application.
- Single-writer lock ownership and stale-lock recovery.
- Graceful stop, forced termination, system shutdown, restart and service-crash behavior.
- Bounded upload/request concurrency, timeouts, queue length, disk quotas and rate limits.
- Health reporting that distinguishes service process liveness from recovery readiness and transaction readiness.
- A separate trusted operator path for RECOVERY_REQUIRED when the ordinary SERMAX application must remain unavailable.
- Broker uninstall and key/ACL cleanup without deleting user data, transaction evidence or user backups.

A service restart must not reuse old handles, process references, approval tokens, cached inventory or health evidence. It reacquires and verifies state from broker-owned durable records. No new installation is accepted while recovery is unresolved.

### 11.25.9 Audit, secrets and anti-rollback state

The broker owns its audit stream and transaction journal. The client cannot select the log path, alter entries, truncate history or supply authoritative timestamps, identities or outcomes.

Record event ID, transaction ID, operation ID, authenticated SID/session, policy version, release/manifest digest, decision, state transition, result code and evidence references. Bound log size and retention; protect the log directory with broker-only write access and appropriate read access. Detect truncation or integrity failure. Do not log passwords, tokens, private keys, memory contents, chat contents, full user documents or unnecessary personal data.

Production public keys, key allowlists, revocation/rotation state and anti-rollback sequence must be broker-protected and unavailable for modification by the interactive client. Private release-signing keys must never be stored on the user's SERMAX computer. Key provisioning, rotation, emergency revocation and recovery from key compromise require a documented release-security procedure.

### 11.25.10 Deny-by-default failure rules

The broker must reject the request and perform no protected mutation when:
- Client token inspection or impersonation reversion fails.
- The caller is outside the approved user/session policy.
- The protocol, schema, size, sequence, nonce, transaction state or idempotency check fails.
- The package, signature, signer, digest, release policy or anti-rollback check fails.
- User approval is absent, expired or bound to different transaction facts.
- Service identity, protected-root ACL, parent ownership or service binary integrity is uncertain.
- The namespace-resolution guarantee is unavailable or unsupported.
- The journal, backup, marker, package snapshot or recovery classification is ambiguous.
- The broker is already processing another transaction for the same root.
- Required disk quota, staging capacity, evidence retention or health/recovery checks cannot be satisfied.

No fallback to the GUI's direct installer, path-based writes, unsigned directory packages, client-side hash decisions or manual marker edits is permitted. Ambiguity enters RECOVERY_REQUIRED and preserves transaction evidence.

### 11.25.11 Required adversarial verification

Before architecture acceptance, run tests using separate standard-user accounts, multiple logon sessions and the actual broker service token. Include:
- Unauthorized, anonymous, network and same-session malicious IPC clients.
- Pipe squatting, pipe-instance creation attempts, wrong server identity and service spoofing.
- Token/session/integrity mismatch, impersonation failure and RevertToSelf failure handling.
- Malformed UTF-8, duplicate JSON keys, unknown critical fields, oversized frames, partial frames, invalid chunk sequence and slow-client exhaustion.
- Replayed request IDs, transaction IDs, approval records, operation IDs and stale idempotency keys.
- Concurrent install requests, service stop/restart, client disconnect, timeout and process crash at every transaction phase.
- Package replacement during upload, after upload, during validation and before installation; invalid signature, untrusted signer, revoked key, downgrade and replayed release.
- Destination and ancestor ACL changes, owner changes, service-binary/configuration tampering, reparse points, junctions, hard links, ADS, volume changes and namespace races.
- Journal, backup, marker and audit-log tampering, truncation, quota exhaustion and disk-full conditions.
- Attempts to read or modify memory, SQLite, logs, credentials, user documents, Ollama models, Python environments and backups.
- Proof that a client cannot request arbitrary path writes, deletes, renames, ACL changes, process launches or commands.
- Recovery startup gate and repeated inspection after service or machine restart.

For each test, record Windows build, filesystem, service token and SID, client token and SID, effective ACLs, test identity, commit, package digest, transaction/journal sequence, attack, expected result and observed result. A pass applies only to the tested configuration.

### 11.25.12 Decisions required before implementation

The following remain explicit approval decisions:
1. Machine-wide versus per-user product deployment and the exact protected destination.
2. Service account, service SID type, restricted SIDs and minimum enabled privileges.
3. Service installation/update/uninstall authority and protection of service binaries/configuration.
4. Exact service-object, directory, staging, backup, journal, log and pipe DACLs.
5. Supported Windows builds, filesystems, volume types and the namespace-resolution security contract.
6. Client/session policy and whether same-session processes are accepted as possible IPC clients.
7. User confirmation interface, approval lifetime and any future unattended-update policy.
8. Production signing trust anchor, key provisioning, rotation, revocation and anti-rollback state.
9. Package/resource quotas, concurrency, cancellation and service shutdown behavior.
10. RECOVERY_REQUIRED operator procedure and trusted recovery interface.
11. User-data separation, migration scope and preservation evidence.
12. Adversarial test identities, acceptance thresholds and independent review.

**Decision:** broker authorization and service security are specified for review only. The current installer remains an unprivileged development preview. No service, broker, IPC endpoint, ACL, privilege, consent interface, trust key, recovery operation or installer release was implemented or authorized. Sections 4A, 11.14, 11.21, 11.22, 11.23 and 11.24 remain binding unresolved gates.


### 11.26 Service-account selection review, 2026-11-16

**Status:** architecture review only. No Windows service, account, SID, ACL, privilege, installer or broker was created or configured.

#### 11.26.1 Candidate comparison

| Candidate | Isolation and local access | Network behavior | SERMAX broker assessment |
|---|---|---|---|
| Dedicated virtual account, `NT SERVICE\\SermaxInstallerBroker` | Unique managed local service identity; access can be granted directly to its service SID. No administrator-managed password. | If the service accesses domain resources, it uses the computer account credentials. | Preferred candidate for a single-machine broker, subject to actual-token and ACL tests. Deny outbound network access unless a separately approved requirement exists. |
| `NT AUTHORITY\\LocalService` | Low local privilege, but shared base account. A per-service SID can narrow resource ACLs; it does not turn the shared logon account into a unique virtual account. | Anonymous credentials on network access. | Compatibility fallback only if the dedicated virtual account fails a documented requirement. Retain a unique service SID and test cross-service isolation. |
| `NT AUTHORITY\\NetworkService` | Low local privilege, shared base account. A per-service SID can narrow local ACLs. | Presents computer credentials to remote servers. | No justification for a local-only installer broker. Avoid the additional machine-identity network capability. |
| `NT AUTHORITY\\SYSTEM` / LocalSystem | Extensive local access, effectively administrative authority for many local resources. | Uses computer credentials on network access. | Reject as the default. Any exceptional requirement needs a specific API-level justification, threat analysis and separate approval. |
| Ordinary local/domain user account | Dedicated identity is possible, but credential lifecycle and provisioning become operational responsibilities. | Depends on account and domain configuration. | Not preferred for a single-machine product unless a concrete deployment requirement rules out a virtual account. |

#### 11.26.2 Proposed target configuration

1. Use a dedicated own-process Windows service with the virtual account `NT SERVICE\\SermaxInstallerBroker`; do not share its process with unrelated services.
2. Give the service a per-service SID. The service SID is the ACL principal for broker-owned staging, journal, audit and narrowly scoped installation resources.
3. Treat `SERVICE_SID_TYPE_RESTRICTED` as the target to evaluate, not as a proven configuration. Microsoft documents that this mode adds the service SID and additional SIDs to the restricted SID list. Access checks must succeed under both normal and restricted SID evaluation. Capture the real token and verify every required file, registry, event-log, pipe and service-control operation.
4. If restricted mode prevents a required operation, do not silently broaden permissions. Identify the exact failed access, assess whether the operation is necessary, and compare a corrected DACL against the unrestricted service-SID mode. Any fallback requires recorded review and approval.
5. Start with no optional privileges. Add a privilege only when a specific documented Windows API requires it. Record the privilege, API, scope, enabled state and negative test proving that unrelated privileged operations remain unavailable.
6. The broker has no network requirement in the current design. Deny outbound network access at the applicable host/firewall policy boundary. Do not rely on the virtual account's network identity being harmless merely because the application currently has no network feature.
7. Keep service installation, configuration changes, service-object DACL, binary directory and recovery authority under an explicit administrator-controlled setup/update process. The interactive GUI must not be able to reconfigure or replace the broker.
8. Do not grant the broker broad access to user profiles, SERMAX memory, SQLite, chat history, Ollama models, Python environments, credentials or backups. Define separate, minimal resource ACLs.

#### 11.26.3 Acceptance evidence

Before selecting the account or SID mode, produce an evidence package from the actual target Windows client build and each supported build:

- Confirm the virtual account can be configured for the service on the target Windows client editions. The documented minimum for virtual accounts is Windows 7 / Windows Server 2008 R2; this is a platform capability statement, not a substitute for testing the supported product matrix.
- Record service name, configured logon account, service SID type, process token groups, restricted SIDs, enabled and disabled privileges, integrity level and logon SID.
- Capture owner, SDDL and effective access results for the service object, binary/configuration directory, every protected-root ancestor, staging, journal, backups, audit log and named pipe.
- Test access as the broker, the interactive standard user, a second standard user, an administrator and SYSTEM. Include both allowed and denied operations.
- Verify that the broker cannot modify its own binary/configuration, change service configuration, access user data outside explicit policy, access arbitrary paths, launch arbitrary processes or reach network resources.
- Repeat tests with `SERVICE_SID_TYPE_RESTRICTED` and compare the results with the unrestricted service-SID configuration. Record any compatibility failure instead of weakening ACLs by guesswork.
- Verify service stop, restart, crash and machine restart. No stale token, handle, approval, inventory or in-memory authority may survive as trusted state.

#### 11.26.4 Decision

The dedicated virtual account with a per-service SID is the leading design candidate. Restricted SID mode is the preferred test target, not an approved production setting. LocalService is a fallback candidate; NetworkService and LocalSystem are not justified by the current local-only requirements. No account, service, ACL or privilege is authorized for implementation. Sections 4A and 11.25 remain blocking gates.


### 11.27 Namespace-race decision: protect the namespace instead of relying on an undocumented open combination, 2026-11-16

**Status:** architecture decision proposal for review. No implementation, ACL, service, broker or installer was changed or authorized.

#### 11.27.1 What the documented Win32 interfaces establish

- `CreateFileW` opens an object by a path string. `FILE_FLAG_OPEN_REPARSE_POINT` changes handling of the final component being opened: the call attempts to open the reparse-point object itself rather than performing normal reparse processing for that object. This is useful for inspecting or managing that leaf object.
- The documented flag does not establish a general guarantee that every intermediate component in an arbitrary path is resolved without following reparse points. Do not treat it as a path-wide no-reparse switch.
- `FILE_FLAG_BACKUP_SEMANTICS` permits opening a directory handle through `CreateFileW`; it does not itself confer backup privilege or bypass normal security checks.
- `SetFileInformationByHandle` operates on an already opened handle. `FILE_RENAME_INFO.RootDirectory` supports a destination name relative to a directory handle. This documents a handle-based rename interface, but it does not prove that the directory namespace used to acquire the original handles was protected from concurrent replacement.
- Share modes are enforced for the lifetime of each open handle. Omitting `FILE_SHARE_DELETE` can prevent later opens requesting delete access when compatible with existing opens. It is a coordination control, not a substitute for protected ownership and ACLs; existing handles and other access paths must be included in the threat model.

#### 11.27.2 Revised security premise

For the current machine-wide broker proposal, the primary defense against a standard-user namespace attacker should be **absence of attacker write authority over the installation namespace**, not an assumption that a particular native open flag makes an attacker-writable tree race-free.

The trusted setup/update mechanism must provision a fixed installation root and secure every ancestor from the volume root through the installation directory. For every ancestor and protected object, verify owner, DACL, inherited ACEs and effective access. The interactive user and other in-scope standard users must not be able to:
- create, replace, rename or delete directories or files in the protected tree;
- add files or subdirectories to protected ancestors;
- change DACLs or ownership;
- replace the service executable, service configuration, staging, journal, backup or recovery objects;
- introduce junctions, symbolic links or other reparse points into the protected namespace.

The broker must fail closed if any ancestor is writable or replaceable by an in-scope untrusted identity, if ownership or effective access is uncertain, or if the root resolves to an unexpected volume/object. Do not repair an unexpected tree by broadening permissions or deleting entries automatically.

The threat model explicitly excludes a local administrator, SYSTEM, kernel compromise and offline modification. The design must state this exclusion wherever it describes its security guarantees.

#### 11.27.3 Broker operation model

1. A trusted, administrator-controlled provisioning step creates the fixed machine-wide root, service-owned transaction directories and their security descriptors. The ordinary GUI cannot select or change the destination.
2. On service start and before each transaction, the broker verifies the provisioned root identity, volume, owner, DACL and every ancestor's effective access against the approved policy. It rejects unexpected reparse points or a changed root identity.
3. Only the broker identity and trusted system administrators receive the exact write rights required for the protected program tree. Standard interactive users receive read/execute access only. They receive no create, append, delete, delete-child, WRITE_DAC or WRITE_OWNER rights on the root or any ancestor.
4. The broker runs in its own service process under the dedicated service identity described in section 11.26. No unrelated service or user-controlled code runs under that identity.
5. Package input is treated as hostile. The broker copies it into broker-owned staging, validates the staged bytes and manifest, and installs from that same broker-owned snapshot. The GUI cannot modify staging, journal or backups.
6. The broker derives all destination names from a fixed root and a strict manifest allowlist. It rejects absolute paths, traversal, alternate data streams, duplicate normalized names, unsupported types and reparse entries. It exposes no arbitrary path or command operation.
7. Use documented Win32 handle operations for inspection, I/O and rename where their documented semantics fit. Retain handles during each transaction and select share modes deliberately. Handle-relative rename is a useful operation boundary, not proof that namespace admission was safe.
8. If any standard-user write path to the protected namespace is found, stop. Do not attempt to compensate with repeated path checks, sleeps, retries or a fallback to the current direct GUI installer.

#### 11.27.4 Required adversarial evidence

- Inspect and test every ancestor, not only the final installation directory. Include inherited and explicit ACEs, owner, WRITE_DAC, WRITE_OWNER, DELETE, FILE_DELETE_CHILD, FILE_ADD_FILE and FILE_ADD_SUBDIRECTORY.
- As the interactive user and a second standard user, attempt create, rename, delete, reparse-point insertion, DACL change and owner change at every ancestor and protected object. Every unauthorized operation must fail.
- Verify the trusted provisioning path cannot be replaced by a standard user before or during service startup.
- Race package source replacement during intake. The installed bytes must match the broker-owned staged digest, never a later read from the caller's path.
- Race attempts against staging, backup, journal, marker and service binary paths. The attacker must lack mutation authority; unexpected identity or ACL changes must stop the transaction.
- Test the actual service token, service SID mode, service-object DACL, process isolation and absence of user-controlled code under the broker identity.
- Repeat on every supported Windows client build and filesystem. Record OS build, filesystem, volume, SIDs, owner, SDDL, effective access, test identity, commit and observed result.
- Separately test crash recovery and transaction integrity. Passing ACL tests does not close journal, backup, health, rollback or package-signature gates.

#### 11.27.5 Decision and limits

The protected-namespace broker is the leading implementation direction because it removes the standard-user ability to race the destination namespace, rather than depending on an undocumented user-mode `NtCreateFile` flag combination. This is a conditional architecture choice, not proof that the current prototype is safe.

The following remain blocking: exact deployment destination; complete ancestor ACL/owner evidence; service identity and token evidence; package trust and key lifecycle; staging and journal implementation; rollback and recovery; health gate; and the section 4A native API contract if any future component still relies on it. If the protected-root premise cannot be demonstrated on a supported configuration, do not ship the installer.

No installer, service, broker, ACL, privilege, native filesystem wrapper or test was implemented in this review.

References:
- https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
- https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points
- https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info
- https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights
- https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile
- https://learn.microsoft.com/en-us/windows/win32/api/ntdef/ns-ntdef-_object_attributes
- https://learn.microsoft.com/en-us/answers/questions/6056645/does-user-mode-ntcreatefile-support-obj-dont-repar
