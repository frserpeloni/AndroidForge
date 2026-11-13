# Auditoria do atualizador transacional SERMAX

Data: 2026-11-13
Branch: `sermax-windows-integration-20261029`
HEAD de referência: `dab9735a1fcadb3134cdd8d94bdbe2463ece7a39`
CI de referência: [run 410](https://github.com/frserpeloni/AndroidForge/actions/runs/43486851133), conclusão success.

## 1. Evidências recentes

- CI 409 validou o commit `77e308059e221bbbf15bb8c5ec893d4d9229bf91`.
- CI 410 validou o commit `dab9735a1fcadb3134cdd8d94bdbe2463ece7a39`.
- CI 410: 262 testes aprovados em 7,644 segundos.
- PyInstaller concluiu a compilação de `SERMAX.exe`.
- Smoke test alcançou o prompt do terminal original e processou `/sair`.
- Artefato CI 410: ID `14068535428`, 22.832.704 bytes, SHA-256 do ZIP `0ad2af63e8500299b11b240066abed52446971e4e9daec3431c6bd6af93d5ef9`.
- O artefato é experimental. Não é instalador nem release assinada.

## 2. Componentes encontrados

### Inventário legado

`sermax_update_inventory.py` continua usando `os.scandir`, `entry.stat(follow_symlinks=False)`, `Path.open("rb")` e uma consulta posterior de tamanho pelo caminho.

Risco confirmado por inspeção estática: TOCTOU entre inspeção e abertura. O objeto aberto não é comprovadamente o mesmo objeto inspecionado. Esse inventário não deve autorizar backup ou instalação.

### Inventário por handles

`sermax_windows_handle_inventory.py` percorre descendentes relativamente a um handle raiz já validado, verifica FileId de 128 bits na abertura de filhos, calcula hashes por handle e compara enumerações dos diretórios antes/depois.

Limites:
- Não abre nem valida a raiz por si próprio. O chamador precisa fornecer um handle de diretório seguro e mantê-lo aberto.
- Classifica arquivos comuns como `unknown`; ainda não recebe uma allowlist de componentes gerenciados do manifesto.
- Não produz snapshot atômico do volume. Alterações detectáveis abortam a operação, mas isso não equivale a uma fotografia transacional.
- Não copia arquivos, não faz staging, não cria backup, não escreve journal, não instala e não executa rollback.
- Não está integrado ao atualizador de produção, que ainda não existe.

### Abertura da raiz

`sermax_windows_root.py` fornece `open_drive_root`, `open_managed_directory` e `open_sermax_directory`. O inventário por handles depende do chamador para validar e manter o handle raiz. A CI valida compilação e testes, não a semântica real de handles/ACL em Windows 11 físico.

### Manifesto e assinatura

`sermax_update_manifest.py` valida schema, caminhos, destinos protegidos e assinatura Ed25519 por callback injetado. `sermax_update_signature.py` cria o verificador a partir de uma allowlist externa de chaves públicas raw.

A allowlist de produção permanece vazia e nenhuma chave de release foi aprovada. Testes com chaves efêmeras demonstram o backend criptográfico, mas não autenticam uma release real.

## 3. Bloqueios para atualização segura

1. Não existe implementado um motor transacional de atualização.
2. Não existe staging de pacote autenticado.
3. Não existe backup verificável da instalação.
4. Não existe journal durável de operações.
5. Não existe substituição atômica controlada de arquivos.
6. Não existe recuperação automática após interrupção.
7. Não existe rollback implementado e testado.
8. Não existe allowlist de chave pública de release aprovada.
9. O inventário por handles não está integrado ao manifesto nem à matriz managed/protected/unknown.
10. O inventário legado mantém risco TOCTOU e não deve ser usado como autoridade para escrita.
11. Não há homologação no Windows 11 do mantenedor.

## 4. Observação sobre a área reservada _update

A política de inventário classifica o segmento `_update` como protegido e não percorre seu conteúdo. A especificação transacional propõe staging, backups, journal e logs sob `_update`.

Isso exige contrato explícito: `_update` deve ser uma área privada, reservada e controlada pelo próprio atualizador, nunca um destino permitido pelo manifesto de release. Antes de usá-la, o atualizador deverá abrir e validar o diretório por handle, verificar ACL e reparse points, impedir junctions/redirecionamentos e separar seus subdiretórios de staging/backup/journal. Não presumir que um diretório existente com esse nome é confiável.

## 5. Próxima sequência segura

1. Definir contrato de inventário que associe o inventário por handles à allowlist de caminhos gerenciados, sem ler dados protegidos.
2. Definir e testar a validação da área reservada `_update`, inclusive ACL, reparse points, hardlinks, permissões e concorrência.
3. Implementar somente a camada de staging isolada, sem escrita na instalação, com validação do arquivo compactado, rejeição de Zip Slip, entradas duplicadas, colisões case-insensitive e conteúdo não declarado.
4. Implementar cópia de backup em sandbox temporária, com hashes antes/depois e injeção de falhas. Não usar `C:\\SERMAX`.
5. Implementar journal durável e máquina de estados, com testes de interrupção em cada transição.
6. Implementar restauração/rollback na sandbox e validar byte a byte.
7. Só depois integrar substituição controlada, health check e recuperação após reinício.
8. Provisionar chave pública de release por processo formal e documentar rotação. Não criar chave fictícia nem armazenar chave privada no repositório.
9. Homologar em Windows 11 físico/VM antes de qualquer atualização real.

## 6. Decisão

O inventário por handles é uma base técnica de leitura mais segura que o inventário legado, mas ainda é componente de diagnóstico. O manifesto autenticável está parcialmente implementado, mas sem chave confiável de release não valida pacotes reais.

**Status: atualizador transacional NÃO IMPLEMENTADO. Backup/rollback NÃO IMPLEMENTADOS. Release instalável NÃO DISPONÍVEL.**

Nenhuma instalação local foi acessada ou modificada nesta auditoria. Nenhum artefato experimental deve ser instalado em `C:\\SERMAX`.
