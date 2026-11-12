"""Parser defensivo para buffers FILE_ID_BOTH_DIR_INFO.

Não chama APIs nativas, não enumera diretórios e não altera arquivos.
Recebe bytes produzidos por GetFileInformationByHandleEx e valida limites,
alinhamento e codificação antes de expor registros.
"""
from __future__ import annotations

import struct
import unicodedata
from dataclasses import dataclass

HEADER_SIZE = 104
FILE_NAME_OFFSET = 104
MAX_NAME_UTF16_UNITS = 255
ALIGNMENT = 8
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400


class DirectoryBufferError(ValueError):
    """Buffer de enumeração inválido ou inconsistente."""


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    file_index: int
    creation_time: int
    last_access_time: int
    last_write_time: int
    change_time: int
    end_of_file: int
    allocation_size: int
    attributes: int
    ea_size: int
    short_name: str
    file_id: int

    @property
    def is_directory(self) -> bool:
        return bool(self.attributes & FILE_ATTRIBUTE_DIRECTORY)

    @property
    def is_reparse_point(self) -> bool:
        return bool(self.attributes & FILE_ATTRIBUTE_REPARSE_POINT)


def _u32(buffer: memoryview, offset: int) -> int:
    return struct.unpack_from("<I", buffer, offset)[0]


def _i64(buffer: memoryview, offset: int) -> int:
    return struct.unpack_from("<q", buffer, offset)[0]


def _decode_utf16(buffer: memoryview, start: int, length: int, field: str) -> str:
    if length == 0 or length % 2:
        raise DirectoryBufferError(f"{field}: comprimento UTF-16 inválido.")
    try:
        value = bytes(buffer[start:start + length]).decode("utf-16-le", errors="strict")
    except UnicodeDecodeError as exc:
        raise DirectoryBufferError(f"{field}: UTF-16 inválido.") from exc
    if "\x00" in value:
        raise DirectoryBufferError(f"{field}: NUL embutido.")
    return value


def parse_file_id_both_dir_info(data: bytes | bytearray | memoryview) -> tuple[DirectoryEntry, ...]:
    """Valida e decodifica uma cadeia de FILE_ID_BOTH_DIR_INFO.

    O chamador deve passar exatamente a região preenchida pela API. Para
    entradas intermediárias, NextEntryOffset precisa ser >= tamanho do
    cabeçalho mais o nome, alinhado em 8 bytes e dentro do buffer.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("data deve ser bytes-like.")
    view = memoryview(data).cast("B")
    if not view:
        return ()
    if len(view) < HEADER_SIZE:
        raise DirectoryBufferError("Buffer menor que o cabeçalho de 104 bytes.")

    entries: list[DirectoryEntry] = []
    offset = 0
    visited: set[int] = set()

    while True:
        if offset in visited:
            raise DirectoryBufferError("Ciclo detectado na cadeia de entradas.")
        visited.add(offset)
        remaining = len(view) - offset
        if remaining < HEADER_SIZE:
            raise DirectoryBufferError("Cabeçalho final truncado.")

        entry = view[offset:]
        next_offset = _u32(entry, 0)
        file_index = _u32(entry, 4)
        creation_time = _i64(entry, 8)
        last_access_time = _i64(entry, 16)
        last_write_time = _i64(entry, 24)
        change_time = _i64(entry, 32)
        end_of_file = _i64(entry, 40)
        allocation_size = _i64(entry, 48)
        attributes = _u32(entry, 56)
        name_length = _u32(entry, 60)
        ea_size = _u32(entry, 64)
        short_name_length = int(entry[68])

        if short_name_length > 24 or short_name_length % 2:
            raise DirectoryBufferError("ShortNameLength inválido.")
        if name_length == 0 or name_length % 2:
            raise DirectoryBufferError("FileNameLength deve ser positivo e par.")
        if name_length > MAX_NAME_UTF16_UNITS * 2:
            raise DirectoryBufferError("FileName excede 255 unidades UTF-16.")
        minimum_size = FILE_NAME_OFFSET + name_length
        if minimum_size > remaining:
            raise DirectoryBufferError("Nome ultrapassa o limite do buffer.")
        if next_offset:
            if next_offset % ALIGNMENT:
                raise DirectoryBufferError("NextEntryOffset não está alinhado em 8 bytes.")
            if next_offset < minimum_size:
                raise DirectoryBufferError("NextEntryOffset sobrepõe o nome ou cabeçalho.")
            if next_offset > remaining:
                raise DirectoryBufferError("NextEntryOffset ultrapassa o buffer.")
            if remaining - next_offset < HEADER_SIZE:
                raise DirectoryBufferError("Próximo cabeçalho está truncado.")

        name = _decode_utf16(entry, FILE_NAME_OFFSET, name_length, "FileName")
        if unicodedata.normalize("NFC", name) != name:
            raise DirectoryBufferError("Nome não está normalizado em Unicode NFC.")

        short_name = ""
        if short_name_length:
            short_name = _decode_utf16(entry, 70, short_name_length, "ShortName")

        file_id = _i64(entry, 96)
        if end_of_file < 0 or allocation_size < 0:
            raise DirectoryBufferError("Tamanho de arquivo negativo.")

        entries.append(DirectoryEntry(
            name=name,
            file_index=file_index,
            creation_time=creation_time,
            last_access_time=last_access_time,
            last_write_time=last_write_time,
            change_time=change_time,
            end_of_file=end_of_file,
            allocation_size=allocation_size,
            attributes=attributes,
            ea_size=ea_size,
            short_name=short_name,
            file_id=file_id,
        ))

        if next_offset == 0:
            break
        offset += next_offset

    return tuple(entries)
