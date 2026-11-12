# Enumeração nativa por handle, primeira implementação isolada

Arquivo: `sermax_windows_directory_handle.py`.

A função `enumerate_directory_handle` usa `GetFileInformationByHandleEx` com:
- classe 11 (`FileIdBothDirectoryRestartInfo`) para reiniciar a enumeração;
- classe 10 (`FileIdBothDirectoryInfo`) para continuar os lotes.

Antes da enumeração, consulta metadados pelo handle e exige diretório regular, sem reparse point e sem `DeletePending`. O buffer padrão é 64 KiB. Tamanhos aceitos: 4 KiB a 1 MiB, múltiplos de 8. Rejeita erro de buffer, lote vazio sem término, nomes duplicados e limites excessivos.

## Limites de segurança

A API não garante snapshot transacional. O código ainda não faz duas passagens independentes, não abre cada filho relativamente ao handle pai, não compara FileId com identidade reaberta e não calcula hash. O tratamento de colisões Unicode completo ainda não foi integrado. Portanto esta função é um componente experimental e não deve alimentar o inventário de produção até os testes de mutação do namespace e a validação completa de cada objeto.

A implementação deve ser validada em runner Windows x64. Testes com mocks verificam a sequência de classes e as condições de falha, mas não substituem testes nativos em NTFS.
