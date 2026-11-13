# Enumeração nativa por handle e comparação de snapshots

Arquivos:
- `sermax_windows_directory_enum.py`: parsers puros de buffers `FILE_ID_BOTH_DIR_INFO` e `FILE_ID_EXTD_DIR_INFO`.
- `sermax_windows_directory_handle.py`: enumeração nativa isolada por handle.
- `sermax_windows_directory_snapshot.py`: comparação pura de duas enumerações.

## Enumeração nativa

A função `enumerate_directory_handle` usa `GetFileInformationByHandleEx` com:
- classe 20 (`FileIdExtdDirectoryRestartInfo`) para reiniciar a enumeração;
- classe 19 (`FileIdExtdDirectoryInfo`) para continuar os lotes.

O parser usa `FILE_ID_EXTD_DIR_INFO`, com cabeçalho de 88 bytes e FileId de 128 bits. Isso permite comparar a identidade completa do item enumerado com `FILE_ID_INFO.FileId` obtido ao abrir o filho, sem reduzir a comparação ao identificador de 64 bits da estrutura anterior. A enumeração estendida exige suporte do sistema de arquivos e do Windows; falha nativa deve abortar a operação, sem fallback silencioso para identidade de 64 bits.

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

`enumerate_stable_directory_handle(handle)` executa duas enumerações completas e independentes no mesmo handle, reiniciando a consulta nativa em cada passagem. Em seguida, exige igualdade por nome NFKC + casefold, FileId de 128 bits, atributos, tamanhos, alocação, timestamps, EA size e alias curto. Qualquer diferença aborta com `HandleIoError`.

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



## Identidade de 128 bits na enumeração

A enumeração nativa foi migrada das classes 10/11 (`FILE_ID_BOTH_DIR_INFO`,
FileId de 64 bits) para as classes 19/20 (`FILE_ID_EXTD_DIR_INFO`, FileId
de 128 bits), conforme a tabela oficial de `GetFileInformationByHandleEx`.
O parser estendido valida o cabeçalho de 88 bytes, o alinhamento de
`NextEntryOffset`, os limites do nome UTF-16, os tamanhos e os 16 bytes do
FileId.

Essa alteração prepara a próxima etapa: abrir cada filho pelo handle pai e
comparar o FileId de 128 bits do item enumerado com o FileId obtido do handle
aberto. Até essa comparação existir e passar em testes nativos, a caminhada
recursiva e a leitura de conteúdo não devem ser integradas ao inventário.



## Abertura vinculada à entrada enumerada

`open_verified_child_component(parent_handle, entry)` abre o nome relativo
ao handle pai e valida o objeto aberto antes de devolvê-lo. Exige FileId de
128 bits igual ao informado pela enumeração estendida, mesmo volume do pai,
atributos, tipo e tamanho compatíveis. Rejeita reparse points e objetos
marcados para exclusão. Para diretórios, solicita também
`FILE_LIST_DIRECTORY`. Em falha de validação, fecha o handle filho.

`hash_file_component` agora recebe a própria `DirectoryEntry`, não um nome
livre. A leitura SHA-256 ocorre somente depois da validação de identidade,
volume, atributos e tamanho. Isso fecha a lacuna entre enumerar um nome e
abrir um objeto substituto com o mesmo nome. A validação física em NTFS e
testes concorrentes ainda são necessários antes de qualquer integração ao
inventário de produção.



## Inventário recursivo por handles

O módulo `sermax_windows_handle_inventory.py` acrescenta uma rotina de
inventário somente de leitura a partir de um handle raiz já aberto e validado.
A rotina enumera cada diretório duas vezes, abre subdiretórios relativamente
ao handle pai, verifica o FileId de 128 bits e calcula SHA-256 dos arquivos
pela função de hash vinculada à entrada enumerada.

Reparse points são registrados como `blocked` e nunca percorridos. Objetos
de dispositivo também são bloqueados. Há limites explícitos de profundidade
e quantidade de registros. Após processar os filhos, cada diretório é
enumerado novamente e comparado com o estado inicial; divergências abortam
o inventário completo.

Limites conhecidos: esta rotina não abre a raiz por caminho, não substitui
`sermax_update_inventory.py` e não está conectada ao atualizador. Ela não
cria snapshot transacional do volume. O compartilhamento conservador protege
cada arquivo enquanto seu handle de leitura permanece aberto, mas alterações
posteriores ao fechamento e antes do fim global não equivalem a uma fotografia
atômica. Homologação em Windows 11/NTFS e testes concorrentes continuam
obrigatórios antes de qualquer integração de produção.


## Proteção de arquivos de memória pessoal

O inventário por handles consulta a mesma lista `PROTECTED_FILES` do
inventário legado. Arquivos como `memoria_sermax.json` e
`memoria_neural_pestinha.json` são registrados com classificação
`protected`, sem tamanho, conteúdo ou SHA-256. A rotina não abre esses
arquivos para leitura. Um teste dedicado confirma que nomes com diferença
entre maiúsculas e minúsculas também permanecem protegidos.


## Exclusão de dados pessoais e diretórios protegidos

A política compartilhada em `sermax_update_inventory.py` define arquivos
protegidos de memória e segmentos de diretório como `backup`, `backups`,
`historico`, `history`, `memoria`, `memory`, `config`, `voz`,
`voice`, `models` e `modelos`, incluindo variações listadas no código.

Os inventários legado e por handles registram diretórios protegidos sem
percorrê-los. Arquivos protegidos recebem classificação `protected`, sem
leitura, tamanho ou hash. O validador de manifesto compartilha a mesma lista
de segmentos e rejeita qualquer destino dentro dessas áreas. A allowlist de
arquivos gerenciados não sobrepõe essa proteção.

Essa regra reduz o risco de coletar memória, configurações, modelos locais,
históricos, backups e dados pessoais durante uma futura preparação de
atualização. Os testes automatizados cobrem o bloqueio em ambos os
inventários e a rejeição de destinos protegidos no manifesto.
