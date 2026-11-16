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
