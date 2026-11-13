"""Enumeração nativa isolada de diretório por handle, Windows x64.

A função não modifica o filesystem. Cada chamada inicia uma enumeração nova.
A API do Windows não fornece snapshot transacional; o chamador deve repetir
a enumeração e comparar resultados antes de confiar no namespace.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from sermax_windows_directory_enum import (
    DirectoryBufferError,
    DirectoryEntry,
    parse_file_id_extd_dir_info,
)
from sermax_windows_directory_snapshot import (
    DirectorySnapshotError,
    compare_directory_snapshots,
)
from sermax_windows_handle_io import (
    HandleIoError,
    _native_api,
    close_handle,
    open_relative_component,
    query_handle_metadata,
)

FILE_ID_EXTD_DIRECTORY_INFO_CLASS = 19
FILE_ID_EXTD_DIRECTORY_RESTART_INFO_CLASS = 20
ERROR_NO_MORE_FILES = 18
ERROR_MORE_DATA = 234
DEFAULT_BUFFER_SIZE = 64 * 1024
MAX_BATCHES = 1_000_000
MAX_ENTRIES = 10_000_000


def enumerate_directory_handle(
    handle,
    *,
    buffer_size: int = DEFAULT_BUFFER_SIZE,
) -> tuple[DirectoryEntry, ...]:
    """Enumera um diretório já aberto, sempre reiniciando a consulta.

    Falha fechada para handle não diretório, reparse point, erros Win32,
    buffer inválido, falta de progresso e limites excessivos.
    """
    if os.name != "nt" or ctypes.sizeof(ctypes.c_void_p) != 8:
        raise HandleIoError("Enumeração nativa exige Windows x64.")
    if isinstance(buffer_size, bool) or not isinstance(buffer_size, int):
        raise HandleIoError("buffer_size deve ser inteiro.")
    if buffer_size < 4096 or buffer_size > 1024 * 1024 or buffer_size % 8:
        raise HandleIoError("buffer_size fora dos limites ou desalinhado.")

    metadata = query_handle_metadata(handle)
    if not metadata["is_directory"] or metadata["is_reparse_point"]:
        raise HandleIoError("Enumeração exige diretório regular, sem reparse point.")
    if metadata["delete_pending"]:
        raise HandleIoError("Diretório marcado para exclusão.")

    _, query, _ = _native_api()
    buffer = ctypes.create_string_buffer(buffer_size)
    results: list[DirectoryEntry] = []
    seen_names: set[str] = set()

    info_class = FILE_ID_EXTD_DIRECTORY_RESTART_INFO_CLASS
    for _ in range(MAX_BATCHES):
        ctypes.memset(buffer, 0, buffer_size)
        ok = query(handle, info_class, ctypes.byref(buffer), buffer_size)
        if not ok:
            error = ctypes.get_last_error()
            if error == ERROR_NO_MORE_FILES:
                return tuple(results)
            if error == ERROR_MORE_DATA:
                raise HandleIoError("Buffer insuficiente durante enumeração.")
            raise HandleIoError(f"GetFileInformationByHandleEx falhou, WinError={error}")

        try:
            batch = parse_file_id_extd_dir_info(buffer.raw)
        except DirectoryBufferError as exc:
            raise HandleIoError(f"Buffer de enumeração inválido: {exc}") from exc
        if not batch:
            raise HandleIoError("Enumeração retornou lote vazio sem término.")
        for entry in batch:
            # A enumeração pode expor nomes duplicados em volumes ou cenários
            # inconsistentes. Não escolher silenciosamente uma das entradas.
            folded = entry.name.casefold()
            if folded in seen_names:
                raise HandleIoError("Nome duplicado na enumeração do diretório.")
            seen_names.add(folded)
            results.append(entry)
            if len(results) > MAX_ENTRIES:
                raise HandleIoError("Limite máximo de entradas excedido.")

        info_class = FILE_ID_EXTD_DIRECTORY_INFO_CLASS

    raise HandleIoError("Limite de lotes excedido; enumeração abortada.")



def enumerate_stable_directory_handle(
    handle,
    *,
    buffer_size: int = DEFAULT_BUFFER_SIZE,
) -> tuple[DirectoryEntry, ...]:
    """Exige duas enumerações completas e independentes com estado idêntico.

    Cada passagem reinicia a consulta nativa no mesmo handle. Qualquer
    divergência de namespace, identidade ou metadados aborta a operação.
    Isso reduz a janela de TOCTOU, mas não cria snapshot transacional e
    ainda não valida a identidade dos filhos durante leitura de conteúdo.
    """
    first = enumerate_directory_handle(handle, buffer_size=buffer_size)
    second = enumerate_directory_handle(handle, buffer_size=buffer_size)
    try:
        return compare_directory_snapshots(first, second)
    except DirectorySnapshotError as exc:
        raise HandleIoError(f"Diretório mudou entre enumerações: {exc}") from exc



FILE_LIST_DIRECTORY = 0x0001


def open_verified_child_component(
    parent_handle,
    entry: DirectoryEntry,
    *,
    desired_access: int | None = None,
):
    """Abre um filho e vincula o handle ao FileId enumerado de 128 bits.

    O handle do pai deve permanecer aberto durante a operação. Reparse points,
    troca de volume, FileId divergente, atributos divergentes e tamanho
    divergente causam falha fechada. Em erro, o handle filho é fechado.
    """
    if not isinstance(entry, DirectoryEntry):
        raise HandleIoError("Entrada de diretório inválida.")
    if entry.is_reparse_point:
        raise HandleIoError("Entrada reparse rejeitada antes da abertura.")
    if not isinstance(entry.file_id, str) or len(entry.file_id) != 32:
        raise HandleIoError("A entrada não contém FileId estendido de 128 bits.")
    try:
        int(entry.file_id, 16)
    except ValueError as exc:
        raise HandleIoError("FileId estendido contém caracteres inválidos.") from exc

    parent_metadata = query_handle_metadata(parent_handle)
    if (
        not parent_metadata["is_directory"]
        or parent_metadata["is_reparse_point"]
        or parent_metadata["delete_pending"]
    ):
        raise HandleIoError("Handle pai não é um diretório regular validado.")

    access = desired_access
    if entry.is_directory:
        access = FILE_LIST_DIRECTORY if access is None else access | FILE_LIST_DIRECTORY

    child_handle = open_relative_component(
        parent_handle,
        entry.name,
        directory=entry.is_directory,
        desired_access=access,
    )
    try:
        child_metadata = query_handle_metadata(child_handle)
        if child_metadata["is_reparse_point"] or child_metadata["delete_pending"]:
            raise HandleIoError("Objeto filho reparse ou marcado para exclusão.")
        if child_metadata["volume_serial_number"] != parent_metadata["volume_serial_number"]:
            raise HandleIoError("O filho aberto pertence a outro volume.")
        if child_metadata["file_id_128"].lower() != entry.file_id.lower():
            raise HandleIoError("FileId do handle não corresponde à entrada enumerada.")
        if child_metadata["attributes"] != entry.attributes:
            raise HandleIoError("Atributos do filho mudaram desde a enumeração.")
        if child_metadata["end_of_file"] != entry.end_of_file:
            raise HandleIoError("Tamanho do filho mudou desde a enumeração.")
        if bool(child_metadata["is_directory"]) != entry.is_directory:
            raise HandleIoError("Tipo do filho diverge da entrada enumerada.")
        return child_handle
    except Exception:
        try:
            close_handle(child_handle)
        except Exception:
            pass
        raise
