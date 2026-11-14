"""Validação integral de pacotes ZIP de release SERMAX, sem extração.

A função valida a correspondência exata entre ZIP e manifesto já autenticado.
Não grava arquivos, não cria staging e não instala componentes.
"""
from __future__ import annotations

import hashlib
import io
import stat
import zipfile
from dataclasses import dataclass

from sermax_update_inventory import InventoryError, _normalize_relative
from sermax_update_manifest import ValidatedManifest

MAX_ARCHIVE_BYTES = 512 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 4 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000
READ_CHUNK_SIZE = 1024 * 1024
_ALLOWED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}


class PackageError(ValueError):
    """Pacote ZIP incompatível, adulterado ou inseguro."""


@dataclass(frozen=True)
class VerifiedPackage:
    release_version: str
    manifest_sha256: str
    archive_sha256: str
    file_count: int
    total_uncompressed_size: int


def _archive_member_name(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if not isinstance(name, str) or not name or name.endswith("/"):
        raise PackageError("Diretórios e nomes vazios não são permitidos no pacote.")
    try:
        normalized = _normalize_relative(name)
    except (InventoryError, TypeError) as exc:
        raise PackageError("O pacote contém caminho inseguro.") from exc
    if normalized != name:
        raise PackageError("O caminho do pacote não está normalizado.")
    return normalized


def _reject_special_file(info: zipfile.ZipInfo) -> None:
    unix_mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(unix_mode)
    if file_type not in (0, stat.S_IFREG):
        raise PackageError("Links e objetos especiais não são permitidos no ZIP.")
    dos_attributes = info.external_attr & 0xFFFF
    if dos_attributes & 0x0400:
        raise PackageError("Atributo de dispositivo/reparse não é permitido.")


def validate_release_archive(
    archive: bytes,
    manifest: ValidatedManifest,
    *,
    max_archive_bytes: int = MAX_ARCHIVE_BYTES,
    max_total_uncompressed: int = MAX_TOTAL_UNCOMPRESSED,
) -> VerifiedPackage:
    """Confere conjunto, caminhos, metadados, tamanho e SHA-256 do ZIP.

    O manifesto precisa ter sido autenticado previamente por
    validate_signed_manifest. A entrada ZIP é recebida como bytes imutáveis.
    Nenhum conteúdo é extraído ou gravado no filesystem.
    """
    if not isinstance(archive, bytes) or not archive:
        raise PackageError("O pacote precisa ser um bloco de bytes não vazio.")
    if isinstance(max_archive_bytes, bool) or not isinstance(max_archive_bytes, int) or max_archive_bytes < 1:
        raise PackageError("Limite de tamanho compactado inválido.")
    if isinstance(max_total_uncompressed, bool) or not isinstance(max_total_uncompressed, int) or max_total_uncompressed < 1:
        raise PackageError("Limite de tamanho descompactado inválido.")
    if len(archive) > max_archive_bytes:
        raise PackageError("Pacote excede o limite de tamanho compactado.")

    expected = {item.path: item for item in manifest.files}
    expected_folded = {path.casefold(): path for path in expected}
    seen: set[str] = set()
    total_size = 0
    archive_digest = hashlib.sha256(archive).hexdigest()

    try:
        with zipfile.ZipFile(io.BytesIO(archive), "r") as package:
            infos = package.infolist()
            if not infos:
                raise PackageError("Pacote ZIP vazio.")
            if len(infos) != len(expected):
                raise PackageError("Quantidade de entradas ZIP diverge do manifesto.")

            for info in infos:
                name = _archive_member_name(info)
                folded = name.casefold()
                if folded in seen:
                    raise PackageError("O ZIP contém caminhos duplicados ou colisão de caixa.")
                seen.add(folded)
                if folded not in expected_folded:
                    raise PackageError("O ZIP contém arquivo ausente do manifesto.")
                canonical_name = expected_folded[folded]
                if canonical_name != name:
                    raise PackageError("A capitalização do caminho diverge do manifesto.")
                if info.is_dir():
                    raise PackageError("Entradas de diretório não são permitidas.")
                _reject_special_file(info)
                if info.flag_bits & 0x1:
                    raise PackageError("Arquivos ZIP criptografados não são aceitos.")
                if info.compress_type not in _ALLOWED_COMPRESSION:
                    raise PackageError("Método de compressão ZIP não permitido.")
                if info.file_size < 0 or info.compress_size < 0:
                    raise PackageError("Metadados de tamanho ZIP inválidos.")

                declared = expected[canonical_name]
                if info.file_size != declared.size:
                    raise PackageError("Tamanho declarado no ZIP diverge do manifesto.")
                total_size += info.file_size
                if total_size > max_total_uncompressed:
                    raise PackageError("Conteúdo descompactado excede o limite configurado.")
                if info.file_size and info.compress_size == 0:
                    raise PackageError("Razão de compressão inválida.")
                if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
                    raise PackageError("Razão de compressão excede o limite de segurança.")

                digest = hashlib.sha256()
                measured_size = 0
                try:
                    with package.open(info, "r") as stream:
                        while True:
                            chunk = stream.read(READ_CHUNK_SIZE)
                            if not chunk:
                                break
                            measured_size += len(chunk)
                            if measured_size > declared.size:
                                raise PackageError("Arquivo excedeu o tamanho autenticado.")
                            digest.update(chunk)
                except (OSError, RuntimeError, zipfile.BadZipFile, EOFError) as exc:
                    raise PackageError("Falha ao ler ou descompactar entrada ZIP.") from exc

                if measured_size != declared.size:
                    raise PackageError("Tamanho efetivo diverge do manifesto.")
                if digest.hexdigest() != declared.sha256:
                    raise PackageError("SHA-256 do arquivo diverge do manifesto.")

            if seen != {path.casefold() for path in expected}:
                raise PackageError("O conjunto de arquivos ZIP não corresponde ao manifesto.")
    except PackageError:
        raise
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile, ValueError) as exc:
        raise PackageError("Estrutura ZIP inválida ou corrompida.") from exc

    return VerifiedPackage(
        release_version=manifest.release_version,
        manifest_sha256=manifest.manifest_sha256,
        archive_sha256=archive_digest,
        file_count=len(expected),
        total_uncompressed_size=total_size,
    )
