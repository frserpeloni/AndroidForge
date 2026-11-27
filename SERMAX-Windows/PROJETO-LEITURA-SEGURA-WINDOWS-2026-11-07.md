# Projeto da camada Windows de leitura segura do inventário SERMAX

Data: 2026-11-07
Branch: `sermax-windows-integration-20261029`
Base técnica: `2f5058770526049fc79b70e3a6a9bd705cd706dc`
Status: especificação de engenharia, não implementação.

## 1. Decisão

O inventário atual permanece somente diagnóstico. Não autoriza backup, staging, instalação ou rollback.

A próxima implementação Windows deve abandonar a sequência `stat(path) -> open(path) -> stat(path)`. Essa sequência permite troca de objeto entre inspeção e leitura.

A implementação de produção deverá trabalhar com handles mantidos abertos e operações relativas ao handle do diretório pai. Qualquer dúvida sobre identidade, tipo, reparse tag, estabilidade ou contenção deve abortar o inventário.

## 2. Base documental

Documentação Microsoft consultada:

- `NtCreateFile` em Win32 documenta `OBJECT_ATTRIBUTES.RootDirectory` e nomes relativos ao handle do diretório. Também descreve `FILE_OPEN_REPARSE_POINT` e opções de abertura. https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntcreatefile
- `CreateFileW` documenta `FILE_FLAG_OPEN_REPARSE_POINT`, abertura de diretórios com `FILE_FLAG_BACKUP_SEMANTICS` e regras de compartilhamento. https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilea
- A documentação de criação/abertura de arquivos explica como o compartilhamento solicitado é comparado com os handles já existentes. https://learn.microsoft.com/en-us/windows/desktop/FileIO/creating-and-opening-files

A documentação de `NtCreateFile` consultada é a documentação Win32 de `winternl.h`. A API requer validação de compatibilidade nas versões Windows suportadas e revisão cuidadosa das estruturas ABI. Não assumir que a existência da documentação elimina riscos de compatibilidade.

## 3. Arquitetura proposta

### 3.1 Abertura da raiz

1. Validar a raiz textual e rejeitar caminhos ambíguos.
2. Abrir a raiz uma única vez como diretório, sem seguir reparse point no objeto final.
3. Consultar atributos e identidade pelo handle aberto.
4. Rejeitar qualquer raiz com atributo de reparse point ou tipo incompatível.
5. Manter o handle da raiz aberto durante toda a enumeração.
6. Não converter a raiz em caminho resolvido para reabrir descendentes.

A resolução inicial da raiz ainda exige cuidado com componentes ancestrais. A implementação deverá definir e testar a política para junctions/reparse points em todos os componentes do caminho, não somente no último componente.

### 3.2 Enumeração relativa a handles

1. Enumerar entradas a partir do handle do diretório, sem reconstruir caminho absoluto para consultar cada objeto.
2. Abrir cada entrada com nome de um único componente relativo ao handle pai.
3. Usar opções de abertura que não processem reparse points normalmente.
4. Consultar tipo, atributos, reparse tag, volume serial e file ID no handle efetivamente aberto.
5. Se for diretório regular, manter seu handle aberto e enumerar seus filhos relativamente a ele.
6. Se for reparse point, registrar como bloqueado e nunca percorrer.
7. Se a operação não estiver disponível ou retornar informação incompleta, abortar.

A API de enumeração escolhida deve operar sobre o handle do diretório. Uma enumeração por caminho completo reintroduziria a janela de troca e não atende ao requisito.

### 3.3 Leitura de arquivos

1. Abrir o arquivo relativamente ao handle pai, sem seguir reparse point.
2. Solicitar acesso de leitura e atributos, sem permissões de escrita.
3. Escolher modo de compartilhamento restritivo. A opção inicial de engenharia é permitir leitura compartilhada e negar compartilhamento de escrita e exclusão.
4. Se houver handle concorrente incompatível, falhar fechado. Não relaxar silenciosamente o compartilhamento.
5. Consultar pelo handle tipo, atributos, reparse tag, tamanho, volume serial e file ID.
6. Ler e calcular SHA-256 pelo mesmo handle, nunca reabrindo o caminho.
7. Consultar novamente pelo mesmo handle tamanho e identidade. Abortar se houver divergência.
8. Manter os handles necessários abertos até a conclusão do inventário, ou documentar precisamente a janela de estabilidade que ainda existir.

O modo de compartilhamento restritivo é uma barreira contra alterações concorrentes comuns, mas não deve ser descrito como snapshot transacional universal. Comportamento de filesystem, drivers de filtro, compartilhamentos de rede e privilégios especiais exigem testes específicos.

### 3.4 Identidade e classificação

O registro de cada arquivo deverá incluir, além dos campos atuais:

- identificador do volume;
- identificador do arquivo;
- tipo obtido do handle;
- atributos e reparse tag, quando aplicável;
- tamanho validado;
- SHA-256 calculado pelo handle.

A identidade do objeto aberto será a fonte de verdade. O nome relativo será somente o nome observado na enumeração.

A classificação continuará deny-by-default:
- `protected`: memórias e dados explicitamente protegidos;
- `managed`: somente allowlist explícita;
- `unknown`: todo o restante;
- `blocked`: reparse points, objetos especiais e entradas não verificáveis.

Nenhum caminho desconhecido será promovido automaticamente a gerenciado.

## 4. Requisitos de implementação

- Código específico Windows isolado em módulo próprio.
- API portátil atual preservada somente para testes não produtivos, sem autoridade para backup/instalação.
- Estruturas ctypes com tamanhos, alinhamento, tipos e convenções de chamada conferidos para x64.
- Todos os handles fechados em blocos `finally` ou gerenciador de contexto.
- Erros NTSTATUS convertidos em exceções com contexto, sem expor dados pessoais.
- Limites explícitos para profundidade, quantidade de entradas, tamanho de caminho e tempo total.
- Sem fallback para leitura por caminho quando a API segura falhar.
- Sem escrita, cópia, exclusão ou alteração de ACL durante inventário.
- Nenhuma operação sobre `C:\\SERMAX` durante desenvolvimento e CI.

## 5. Matriz mínima de testes Windows

Os testes precisam rodar em Windows real no CI. Testes que dependem de privilégios devem registrar skip explícito e motivo, nunca contar como aprovados.

| Cenário | Resultado exigido |
|---|---|
| Arquivo regular | Hash e tamanho corretos pelo handle |
| Diretório regular | Enumeração relativa ao handle |
| Symlink para arquivo | Bloqueado, alvo não percorrido |
| Symlink para diretório | Bloqueado, descendentes ausentes |
| Junction | Bloqueada, descendentes ausentes |
| Mount point | Bloqueado ou falha fechada |
| Reparse tag não reconhecida | Bloqueado, nunca seguido |
| Hardlink | Identidade registrada; política explícita para aliases |
| Arquivo com ADS | Nome com stream rejeitado |
| Nome reservado Windows | Rejeitado |
| Nome com ponto/espaço final | Rejeitado |
| Unicode não NFC | Rejeitado |
| Troca concorrente por symlink | Abertura segura ou abortada, nunca lê alvo externo |
| Renomeação concorrente | Aborta ou registra o objeto efetivamente aberto sem escapar da raiz |
| Escrita concorrente | Abertura restritiva falha ou leitura permanece estável |
| Exclusão concorrente | Abertura restritiva falha ou objeto permanece fixado |
| Alteração durante hash | Divergência detectada ou escrita impedida |
| Reparse point em ancestral | Rejeitado conforme política de raiz |
| Handle inválido/erro NTSTATUS | Falha fechada, sem fallback |

Os testes de concorrência devem repetir as corridas em laços controlados e verificar conteúdo sentinela externo. Um teste que simplesmente cria symlink antes do inventário não cobre TOCTOU.

## 6. Critérios de aceite

A camada somente será aceita quando:

1. Os testes unitários e de integração Windows passarem na CI do HEAD.
2. A matriz acima tiver resultados registrados, com skips identificados.
3. Os testes concorrentes demonstrarem que nenhum conteúdo externo é lido.
4. Não houver fallback baseado em caminhos para leitura ou enumeração.
5. Os handles forem fechados mesmo diante de exceções.
6. A documentação declarar filesystem e limitações testadas.
7. A revisão estática confirmar que backup/instalador ainda não consomem o inventário inseguro.

Depois disso, a etapa seguinte será backup em sandbox temporária, com comparação byte a byte, injeção de falhas e restauração isolada. Não será executado em `C:\\SERMAX`.

## 7. Limitações conhecidas

- Esta especificação não é código executável nem prova de segurança.
- A semântica de `NtCreateFile`, enumeração por handle e reparse points precisa ser validada no Windows suportado.
- Filesystems de rede, drivers de filtro, antivírus, volumes especiais e privilégios administrativos podem alterar resultados. Até serem testados, devem falhar fechados.
- Hardlinks não são reparse points. A política precisa decidir se aliases dentro/fora da raiz são aceitos, bloqueados ou sinalizados.
- Um inventário com handles estáveis não é, por si só, uma transação atômica do diretório inteiro.

## 8. Próxima tarefa de implementação

Criar o módulo Windows de handles com testes isolados, sem substituir o inventário atual. Integrar ao inventário somente após todos os critérios de aceite. A implementação deve começar pelos protótipos ABI e testes de abertura de raiz e componentes, antes de adicionar hashing recursivo.


## 9. Refinamento da enumeração por handle

Consulta documental adicional:

- `GetFileInformationByHandleEx` aceita classes de informação específicas para diretórios, incluindo `FileIdBothDirectoryInfo` e `FileIdExtdDirectoryInfo`. https://learn.microsoft.com/en-us/windows/desktop/api/winbase/nf-winbase-getfileinformationbyhandleex
- `FILE_ID_BOTH_DIR_INFO` é usado com handles de diretório e a enumeração continua em chamadas subsequentes no mesmo handle. Sua informação de FileId tem limitações de estabilidade e unicidade dependentes do filesystem. https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_both_dir_info
- `FILE_ID_INFO` fornece VolumeSerialNumber e FileId de 128 bits quando suportado; a combinação identifica o arquivo no volume para comparação entre handles. https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_id_info

Consequências para a implementação:

1. Preferir enumeração por `GetFileInformationByHandleEx` no handle do diretório, com buffer alinhado e validação rigorosa de `NextEntryOffset` e `FileNameLength`.
2. Tratar nomes da enumeração como candidatos, não como autorização de leitura.
3. Abrir cada candidato relativamente ao handle pai com `NtCreateFile` e `FILE_OPEN_REPARSE_POINT`.
4. Consultar `FileAttributeTagInfo`, `FileStandardInfo` e `FileIdInfo` no handle filho. Não confiar exclusivamente no FileId de 64 bits retornado na estrutura de enumeração.
5. Comparar a identidade consultada no handle com a informação disponível na enumeração quando o filesystem oferecer identificadores comparáveis. Divergência ou ausência de informação exigida implica bloqueio.
6. Testar explicitamente a classe de enumeração e o comportamento dos buffers em NTFS e ReFS. Filesystems sem suporte compatível não entram em fallback por caminho.

A enumeração por handle reduz a dependência de caminhos, mas não elimina por si só corridas entre enumeração e abertura. A abertura relativa ao handle pai, sem seguir reparse points, e a validação do objeto efetivamente aberto continuam obrigatórias.
