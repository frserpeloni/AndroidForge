# Enumeração nativa por handle e comparação de snapshots

Arquivos:
- `sermax_windows_directory_enum.py`: parser puro de buffers `FILE_ID_BOTH_DIR_INFO`.
- `sermax_windows_directory_handle.py`: enumeração nativa isolada por handle.
- `sermax_windows_directory_snapshot.py`: comparação pura de duas enumerações.

## Enumeração nativa

A função `enumerate_directory_handle` usa `GetFileInformationByHandleEx` com:
- classe 11 (`FileIdBothDirectoryRestartInfo`) para reiniciar a enumeração;
- classe 10 (`FileIdBothDirectoryInfo`) para continuar os lotes.

Antes da enumeração, consulta metadados pelo handle e exige diretório regular, sem reparse point e sem `DeletePending`. O buffer padrão é 64 KiB. Tamanhos aceitos: 4 KiB a 1 MiB, múltiplos de 8. Rejeita erro de buffer, lote vazio sem término, nomes duplicados e limites excessivos.

## Comparação de duas enumerações

`compare_directory_snapshots(first, second)` canonicaliza cada enumeração por nome NFKC + casefold. Rejeita colisões Unicode, colisões de alias curto 8.3, registros de tipo inesperado, entrada criada/removida/renomeada e mudanças em atributos, tamanho, alocação, timestamps, EA size, short name ou FileId.

`FileIndex` fica fora da assinatura porque não representa identidade estável. O retorno contém os registros da primeira enumeração em ordem determinística.

A comparação detecta alterações observáveis entre as duas passagens. Não fornece snapshot transacional, não elimina a possibilidade de mutação transitória entre leituras e não substitui abertura e validação de cada objeto pelo handle.

## Limites de segurança e próximos passos

Os componentes permanecem isolados. Ainda faltam:
- executar duas enumerações nativas sequenciais e comparar os resultados;
- abrir cada filho relativamente ao handle pai com direitos e compartilhamento restritos;
- comparar volume/FileId e metadados antes/depois da leitura;
- calcular hash pelo mesmo handle aberto;
- tratar hardlinks explicitamente, inicialmente rejeitando `NumberOfLinks > 1`;
- testes reais NTFS com criação, remoção, rename, reparse points, hardlinks e concorrência.

Não conectar ao inventário de produção nem implementar staging/rollback antes da conclusão desses controles. Testes com mocks não substituem validação nativa no Windows x64.


## Enumeração estável em duas passagens

`enumerate_stable_directory_handle(handle)` executa duas enumerações completas e independentes no mesmo handle, reiniciando a consulta nativa em cada passagem. Em seguida, exige igualdade por nome NFKC + casefold, FileId, atributos, tamanhos, alocação, timestamps, EA size e alias curto. Qualquer diferença aborta com `HandleIoError`.

Essa etapa reduz a janela de inconsistência do namespace, mas não oferece snapshot transacional e não resolve, sozinha, TOCTOU durante abertura/leitura dos filhos. A função permanece isolada do inventário de produção. Ainda faltam abertura e hash pelo mesmo handle, comparação de volume/FileId e metadados antes/depois da leitura, política efetiva de hardlinks e enumeração final após leitura.


## Hash de arquivo pelo handle

`sermax_windows_file_hash.py` adiciona uma etapa isolada para abrir um filho
relativamente ao handle do diretório pai e calcular SHA-256 usando
`ReadFile` no mesmo handle. A abertura solicita `FILE_READ_DATA` e mantém
o compartilhamento conservador já definido em `open_relative_component`,
que permite leitura compartilhada e recusa compartilhamento de escrita e
exclusão enquanto o handle estiver aberto.

Antes da leitura, exige arquivo regular, sem reparse point, sem
`DeletePending` e com `NumberOfLinks == 1`. Depois da leitura, consulta
novamente os metadados e compara volume, FileId de 128 bits, tamanho,
quantidade de links, atributos e estado do objeto. Também exige que a
quantidade de bytes lidos seja igual ao tamanho inicial. O handle é fechado
em bloco `finally`.

A política rejeita hardlinks em vez de tentar inferir qual caminho adicional
aponta para o mesmo objeto. A etapa não está conectada ao inventário de
produção. Os testes atuais simulam a API de leitura e validam hash, tamanho,
mudança de identidade, leitura truncada, hardlinks e fechamento do handle.
Eles não substituem testes nativos em Windows x64/NTFS.

Ainda falta integrar essa leitura a uma caminhada de diretórios inteiramente
por handles, validar a enumeração final após a leitura e executar testes reais
de concorrência, rename, substituição e reparse points no Windows.
