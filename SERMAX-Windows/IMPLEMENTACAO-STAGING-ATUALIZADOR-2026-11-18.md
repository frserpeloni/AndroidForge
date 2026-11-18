# Implementação inicial de staging do atualizador SERMAX

Data: 18/11/2026  
Branch: `sermax-installer-staging-20261118`  
Base: `sermax-windows-integration-20261029`

## Escopo implementado

Foi adicionado `sermax_update_staging.py`, com a função `stage_verified_release`.

O fluxo:
1. Exige diretório pai de staging já existente e rejeita link simbólico, reparse point ou objeto que não seja diretório.
2. Revalida o ZIP integralmente contra o manifesto previamente autenticado.
3. Reserva diretório exclusivo com nome aleatório.
4. Cria arquivos com modo exclusivo, sem sobrescrever destinos existentes.
5. Recalcula tamanho e SHA-256 durante a escrita e sincroniza cada arquivo.
6. Preserva o staging parcial em caso de falha, para inspeção.
7. Não escreve em `C:\SERMAX`, não executa scripts, não faz backup, não instala e não confirma release.

Foi adicionada a suíte `tests/test_sermax_update_staging.py` para extração exata, pacote inválido, pai reparse/link, pai inválido e ausência de alteração na instalação simulada.

## Limites de segurança

- O diretório pai precisa ser provisionado pelo instalador com ACL restrita. O módulo não cria nem endurece ACLs.
- A criação exclusiva e a rejeição de reparse points reduzem riscos, mas não constituem proteção completa contra um processo concorrente com a mesma identidade e permissão de escrita no diretório pai.
- A operação não é uma transação de instalação. Não substitui arquivos ativos.
- O manifesto precisa ter sido autenticado antes da chamada. A allowlist de chaves públicas de produção continua pendente.
- Testes ainda dependem da execução do CI Windows. Nenhum resultado de CI é antecipado neste documento.

## Próximas etapas

1. Executar a suíte em Windows CI e corrigir falhas observadas.
2. Implementar provisionamento/verificação de ACL e raiz de staging.
3. Implementar inventário por handles e backup verificável.
4. Implementar journal durável, troca controlada e rollback.
5. Injetar falhas em cada transição e testar recuperação após reinicialização.
6. Homologar em VM Windows limpa antes de qualquer release instalável.

## Arquivos desta etapa

- `SERMAX-Windows/sermax_update_staging.py`
- `SERMAX-Windows/tests/test_sermax_update_staging.py`
- `SERMAX-Windows/IMPLEMENTACAO-STAGING-ATUALIZADOR-2026-11-18.md`

## Escrita de arquivos por handle, primeira validação Windows

Foi adicionado `sermax_windows_file_writer.py`, com `write_verified_file_component()`.

Contrato implementado:
- Recebe handle pai validado e um único nome de componente, nunca caminho.
- Cria com `NtCreateFile(FILE_CREATE)`, `FILE_NON_DIRECTORY_FILE` e `FILE_OPEN_REPARSE_POINT`.
- Aplica SECURITY_DESCRIPTOR self-relative na criação, com owner do token real e DACL explícita para owner, SYSTEM e Administradores.
- Valida tipo, volume, FileId de 128 bits, DeletePending e `number_of_links == 1`.
- Confere DACL e direitos Authz pelo handle do arquivo.
- Escreve em blocos, trata escrita parcial, calcula tamanho e SHA-256 durante a gravação.
- Executa `FlushFileBuffers`, reposiciona o ponteiro, relê o arquivo pelo mesmo handle e compara tamanho e hash.
- Em falha, preserva o arquivo parcial para inspeção. Não apaga nem substitui objetos.
- O avaliador de descritor foi ampliado com opção explícita `require_directory=False`; o padrão continua exigindo diretório, preservando o contrato anterior.

### Testes e evidência CI

- Run `44394103673`, commit `36f30cb45b29f976eafd1310f3480b7ca8f37dd8`.
- Windows Server 2025, Python 3.14.10, pywin32.
- Compilação: sucesso.
- Escritor por handle: 6 testes aprovados, incluindo criação nativa com ACL/Authz e leitura exata do arquivo.
- Staging path-based: 5 testes.
- Leitor de segurança: 5 testes.
- Inspeção/política de `_update`: 11 testes.
- Criação e validação da área privada: 19 testes.
- Inspeção ACL: 5 testes.
- Política ACL: 15 testes.
- Integração nativa da política ACL: 1 teste.
- Total: 67 testes aprovados.
- [Execução CI](https://github.com/frserpeloni/AndroidForge/actions/runs/44394103673).

O teste nativo criou arquivo em diretório temporário no runner Windows, validou DACL e Authz e confirmou o conteúdo lido. Isso não homologa o Windows 11 local nem sessões separadas de usuário padrão, Administradores e SYSTEM.

### Próxima etapa

Integrar o escritor ao fluxo de staging por handles. A função antiga `stage_verified_release()` continua baseada em caminhos e não deve ser tratada como fluxo final de produção. Ainda faltam diretórios de staging exclusivos criados por handle, escrita de toda a árvore por handles, backup verificável, journal durável, instalação transacional, recuperação e rollback.