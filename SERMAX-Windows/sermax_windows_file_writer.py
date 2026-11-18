"""Criação e verificação de arquivos de staging por handles relativos.

O arquivo é criado exclusivamente sob um diretório pai já validado. A ACL é
aplicada na própria criação. A função não recebe caminhos e não remove arquivos
parciais em caso de falha, preservando evidências para inspeção.
"""
from __future__ import annotations

import ctypes
import hashlib
import os
from ctypes import wintypes

from sermax_windows_handle_io import (
    FILE_READ_ATTRIBUTES,
    SYNCHRONIZE,
    _native_api,
    _validate_component,
    close_handle,
    query_handle_metadata,
)

FILE_CREATE = 0x00000002
FILE_NON_DIRECTORY_FILE = 0x00000040
FILE_OPEN_REPARSE_POINT = 0x00200000
FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_SHARE_READ = 0x00000001
FILE_READ_DATA = 0x0001
FILE_WRITE_DATA = 0x0002
READ_CONTROL = 0x00020000
FILE_ALL_ACCESS = 0x001F01FF
TOKEN_QUERY = 0x0008
OBJECT_INHERIT_ACE = 0x01
CONTAINER_INHERIT_ACE = 0x02
DEFAULT_CHUNK_SIZE = 1024 * 1024
MAX_CHUNK_SIZE = 16 * 1024 * 1024


class HandleFileWriterError(RuntimeError):
    """Falha fechada ao criar ou verificar arquivo de staging por handle."""


def _write_apis():
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise HandleFileWriterError("A escrita por handle exige Windows x64.")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    write_file = kernel32.WriteFile
    write_file.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    write_file.restype = wintypes.BOOL
    read_file = kernel32.ReadFile
    read_file.argtypes = [
        wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p,
    ]
    read_file.restype = wintypes.BOOL
    flush = kernel32.FlushFileBuffers
    flush.argtypes = [wintypes.HANDLE]
    flush.restype = wintypes.BOOL
    seek = kernel32.SetFilePointerEx
    seek.argtypes = [wintypes.HANDLE, ctypes.c_longlong,
                     ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
    seek.restype = wintypes.BOOL
    return write_file, read_file, flush, seek


def _native_handle(handle):
    value = handle.value if isinstance(handle, ctypes.c_void_p) else handle
    if value is None or value == 0:
        raise HandleFileWriterError("Handle nulo.")
    return value


def _validate_file_metadata(metadata, parent_metadata):
    if metadata["is_directory"]:
        raise HandleFileWriterError("O objeto criado é diretório.")
    if metadata["is_reparse_point"] or metadata["delete_pending"]:
        raise HandleFileWriterError("Arquivo reparse ou marcado para exclusão.")
    if metadata["number_of_links"] != 1:
        raise HandleFileWriterError("Arquivo com hardlinks rejeitado.")
    if metadata["volume_serial_number"] != parent_metadata["volume_serial_number"]:
        raise HandleFileWriterError("Arquivo criado em volume divergente.")
    if not metadata["file_id_128"] or len(metadata["file_id_128"]) != 32:
        raise HandleFileWriterError("FileId de 128 bits ausente ou inválido.")
    if metadata["end_of_file"] < 0:
        raise HandleFileWriterError("Tamanho de arquivo inválido.")


def _validate_file_acl(handle, token_handle, expected_owner_sid):
    try:
        import win32security
        from sermax_windows_effective_access import (
            evaluate_access_for_token,
            read_security_descriptor_binary,
        )
        native = _native_handle(handle)
        descriptor = win32security.GetSecurityInfo(
            native,
            win32security.SE_FILE_OBJECT,
            win32security.OWNER_SECURITY_INFORMATION
            | win32security.DACL_SECURITY_INFORMATION,
        )
        owner = descriptor.GetSecurityDescriptorOwner()
        if isinstance(owner, tuple):
            owner = owner[0]
        owner_sid = win32security.ConvertSidToStringSid(owner)
        if owner_sid != expected_owner_sid:
            raise HandleFileWriterError("Owner ACL do arquivo diverge do token criador.")
        dacl = descriptor.GetSecurityDescriptorDacl()
        if dacl is None or dacl.GetAceCount() != 3:
            raise HandleFileWriterError("DACL do arquivo ausente ou com ACEs divergentes.")
        observed = set()
        for index in range(dacl.GetAceCount()):
            ace = dacl.GetAce(index)
            ace_type, ace_flags = ace[0]
            if ace_type != win32security.ACCESS_ALLOWED_ACE_TYPE:
                raise HandleFileWriterError("DACL contém ACE fora da política.")
            if ace_flags != (OBJECT_INHERIT_ACE | CONTAINER_INHERIT_ACE):
                raise HandleFileWriterError("Flags de herança ACL divergentes.")
            if int(ace[1]) != FILE_ALL_ACCESS:
                raise HandleFileWriterError("Máscara ACL divergente.")
            observed.add(win32security.ConvertSidToStringSid(ace[2]))
        expected = {expected_owner_sid, "S-1-5-18", "S-1-5-32-544"}
        if observed != expected:
            raise HandleFileWriterError("Trustees ACL do arquivo divergentes.")

        binary = read_security_descriptor_binary(handle)
        access = evaluate_access_for_token(token_handle, binary, FILE_ALL_ACCESS)
        if (
            access.get("api_success") is not True
            or access.get("granted") is not True
            or access.get("desired_access") != FILE_ALL_ACCESS
            or access.get("token_source") != "real_kernel_token"
            or access.get("mutated") is not False
            or access.get("performed_io") is not False
        ):
            raise HandleFileWriterError("Authz não confirmou FILE_ALL_ACCESS.")
    except HandleFileWriterError:
        raise
    except Exception as exc:
        raise HandleFileWriterError(f"Falha na validação ACL/Authz do arquivo: {exc}") from exc


def _write_all(handle, data, write_file):
    buffer = ctypes.create_string_buffer(data, len(data))
    offset = 0
    while offset < len(data):
        written = wintypes.DWORD()
        pointer = ctypes.cast(ctypes.byref(buffer, offset), ctypes.c_void_p)
        if not write_file(handle, pointer, len(data) - offset,
                          ctypes.byref(written), None):
            raise HandleFileWriterError(
                f"WriteFile falhou, WinError={ctypes.get_last_error()}"
            )
        count = int(written.value)
        if count <= 0 or count > len(data) - offset:
            raise HandleFileWriterError("WriteFile retornou progresso inválido.")
        offset += count


def _readback(handle, expected_size, read_file, seek):
    zero = ctypes.c_longlong(0)
    position = ctypes.c_longlong()
    if not seek(handle, zero, ctypes.byref(position), 0) or position.value != 0:
        raise HandleFileWriterError(
            f"SetFilePointerEx falhou, WinError={ctypes.get_last_error()}"
        )
    digest = hashlib.sha256()
    total = 0
    buffer_size = min(DEFAULT_CHUNK_SIZE, max(4096, expected_size or 4096))
    buffer = ctypes.create_string_buffer(buffer_size)
    while True:
        count = wintypes.DWORD()
        if not read_file(handle, ctypes.byref(buffer), buffer_size,
                         ctypes.byref(count), None):
            raise HandleFileWriterError(
                f"ReadFile de confirmação falhou, WinError={ctypes.get_last_error()}"
            )
        amount = int(count.value)
        if amount == 0:
            break
        if amount > buffer_size:
            raise HandleFileWriterError("ReadFile excedeu o buffer.")
        total += amount
        if total > expected_size:
            raise HandleFileWriterError("Readback excedeu o tamanho autenticado.")
        digest.update(buffer.raw[:amount])
    return digest.hexdigest(), total


def write_verified_file_component(
    parent_handle,
    name: str,
    source,
    *,
    expected_size: int,
    expected_sha256: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> dict[str, object]:
    """Cria, grava, sincroniza e relê um arquivo por handle relativo.

    source deve oferecer read(n) e retornar bytes. O chamador mantém aberto o
    handle pai validado. O arquivo recebe DACL explícita durante NtCreateFile.
    Falhas preservam o objeto parcial para inspeção, sem exclusão automática.
    """
    try:
        _validate_component(name)
    except Exception as exc:
        raise HandleFileWriterError(f"Nome de arquivo inválido: {exc}") from exc
    if isinstance(expected_size, bool) or not isinstance(expected_size, int) or expected_size < 0:
        raise HandleFileWriterError("expected_size deve ser inteiro não negativo.")
    if (
        not isinstance(expected_sha256, str)
        or len(expected_sha256) != 64
        or any(ch not in "0123456789abcdefABCDEF" for ch in expected_sha256)
    ):
        raise HandleFileWriterError("SHA-256 esperado inválido.")
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int):
        raise HandleFileWriterError("chunk_size deve ser inteiro.")
    if chunk_size < 4096 or chunk_size > MAX_CHUNK_SIZE:
        raise HandleFileWriterError("chunk_size fora dos limites.")

    parent_metadata = query_handle_metadata(parent_handle)
    if (
        not parent_metadata["is_directory"]
        or parent_metadata["is_reparse_point"]
        or parent_metadata["delete_pending"]
    ):
        raise HandleFileWriterError("Handle pai não é diretório regular validado.")

    token = None
    close_token = None
    file_handle = None
    try:
        from sermax_windows_private_area import _prepare_private_security_descriptor
        token, close_token, security_buffer, owner_sid = _prepare_private_security_descriptor()
        create, _, _ = _native_api()
        name_buffer = ctypes.create_unicode_buffer(name)
        encoded_length = len(name.encode("utf-16-le"))
        from sermax_windows_handle_abi import (
            IO_STATUS_BLOCK, OBJECT_ATTRIBUTES, OBJ_CASE_INSENSITIVE, UNICODE_STRING,
        )
        unicode_name = UNICODE_STRING(
            Length=encoded_length,
            MaximumLength=encoded_length + 2,
            Buffer=ctypes.cast(name_buffer, wintypes.LPWSTR),
        )
        attributes = OBJECT_ATTRIBUTES()
        attributes.Length = ctypes.sizeof(OBJECT_ATTRIBUTES)
        attributes.RootDirectory = parent_handle
        attributes.ObjectName = ctypes.pointer(unicode_name)
        attributes.Attributes = OBJ_CASE_INSENSITIVE
        attributes.SecurityDescriptor = ctypes.cast(security_buffer, ctypes.c_void_p)

        result_handle = wintypes.HANDLE()
        io_status = IO_STATUS_BLOCK()
        access = (
            FILE_READ_DATA | FILE_WRITE_DATA | FILE_READ_ATTRIBUTES
            | READ_CONTROL | SYNCHRONIZE
        )
        options = (
            FILE_NON_DIRECTORY_FILE | FILE_OPEN_REPARSE_POINT
            | FILE_SYNCHRONOUS_IO_NONALERT
        )
        status = create(
            ctypes.byref(result_handle), access, ctypes.byref(attributes),
            ctypes.byref(io_status), None, FILE_ATTRIBUTE_NORMAL,
            FILE_SHARE_READ, FILE_CREATE, options, None, 0,
        )
        if status < 0:
            raise HandleFileWriterError(
                f"NtCreateFile(FILE_CREATE) falhou, NTSTATUS=0x{status & 0xffffffff:08X}"
            )
        file_handle = result_handle
        metadata = query_handle_metadata(file_handle)
        _validate_file_metadata(metadata, parent_metadata)
        _validate_file_acl(file_handle, token, owner_sid)

        write_file, read_file, flush, seek = _write_apis()
        source_digest = hashlib.sha256()
        measured = 0
        while True:
            chunk = source.read(chunk_size)
            if not isinstance(chunk, bytes):
                raise HandleFileWriterError("A origem deve fornecer blocos bytes.")
            if not chunk:
                break
            measured += len(chunk)
            if measured > expected_size:
                raise HandleFileWriterError("Origem excedeu tamanho autenticado.")
            source_digest.update(chunk)
            _write_all(file_handle, chunk, write_file)
        if measured != expected_size or source_digest.hexdigest().lower() != expected_sha256.lower():
            raise HandleFileWriterError("Tamanho ou SHA-256 da origem diverge do manifesto.")

        if not flush(file_handle):
            raise HandleFileWriterError(
                f"FlushFileBuffers falhou, WinError={ctypes.get_last_error()}"
            )
        after_write = query_handle_metadata(file_handle)
        _validate_file_metadata(after_write, parent_metadata)
        if after_write["file_id_128"] != metadata["file_id_128"]:
            raise HandleFileWriterError("FileId mudou após a gravação.")
        if after_write["end_of_file"] != expected_size:
            raise HandleFileWriterError("Tamanho no handle diverge após FlushFileBuffers.")

        readback_hash, readback_size = _readback(
            file_handle, expected_size, read_file, seek
        )
        final = query_handle_metadata(file_handle)
        _validate_file_metadata(final, parent_metadata)
        if (
            final["file_id_128"] != metadata["file_id_128"]
            or final["end_of_file"] != expected_size
            or readback_size != expected_size
            or readback_hash.lower() != expected_sha256.lower()
        ):
            raise HandleFileWriterError("Readback, identidade ou hash final divergente.")

        return {
            "name": name,
            "volume_serial_number": final["volume_serial_number"],
            "file_id_128": final["file_id_128"],
            "size": readback_size,
            "sha256": readback_hash,
            "number_of_links": final["number_of_links"],
            "acl_validated": True,
            "authz_validated": True,
            "flushed": True,
            "readback_validated": True,
        }
    except HandleFileWriterError:
        raise
    except Exception as exc:
        raise HandleFileWriterError(
            f"Falha na criação/gravação; arquivo parcial preservado se criado: {exc}"
        ) from exc
    finally:
        close_error = None
        if file_handle is not None:
            try:
                close_handle(file_handle)
            except Exception as exc:
                close_error = exc
        if token is not None and close_token is not None:
            try:
                close_token(token)
            except Exception as exc:
                if close_error is None:
                    close_error = exc
        if close_error is not None:
            raise HandleFileWriterError(f"Falha ao fechar recurso nativo: {close_error}") from close_error
