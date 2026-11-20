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
## Staging integral por handles, primeira integração

Foi adicionada a função `stage_verified_release_by_handle()`.

Contrato:
- Valida novamente o pacote ZIP contra o manifesto autenticado e rejeita colisões de caixa e conflitos entre arquivo e diretório antes de criar a árvore.
- Exige handle pai privado, regular, sem reparse point ou DeletePending.
- Revalida owner, DACL, diretório vazio e direitos Authz pelo mesmo handle antes de iniciar.
- Cria diretório raiz exclusivo com nome aleatório por handle relativo e SECURITY_DESCRIPTOR explícito.
- Cria cada subdiretório da release por handle relativo, com ACL aplicada durante a criação.
- Cria cada arquivo por `write_verified_file_component()`, sem construir caminhos de destino.
- Mantém os handles de diretórios pais abertos durante as gravações e fecha os handles filhos após a extração.
- Retorna o handle da raiz de staging ao chamador. O chamador deve fechá-lo.
- Em falha, preserva a árvore parcial e fecha os handles. Não remove arquivos nem diretórios.
- A função path-based antiga continua disponível como implementação intermediária, mas não é o fluxo de staging por handles.

Foi incluída a função `validate_empty_private_directory_handle()` para exigir ACL/Authz válidas e diretório pai vazio antes de iniciar a operação. O contrato atual prevê um pai privado vazio por operação de staging.

### Testes e evidência CI

- Run `44394857061`, commit `0ccfa72dbe0fd6272c2997d0caa96a43d3fc8c4a`.
- Windows Server 2025, Python 3.14.10, pywin32.
- 71 testes aprovados em oito grupos:
  - escritor por handle: 6;
  - staging e staging por handles: 9;
  - leitor de segurança: 5;
  - inspeção/política de `_update`: 11;
  - criação e validação da área privada: 19;
  - inspeção ACL: 5;
  - política ACL: 15;
  - integração nativa da política ACL: 1.
- O grupo de staging inclui teste nativo end-to-end: cria `_update` temporário, valida a ACL, cria a árvore de release por handles, grava arquivos com ACL/Authz e confirma o conteúdo final.
- [Execução CI](https://github.com/frserpeloni/AndroidForge/actions/runs/44394857061).

Os testes nativos foram executados em diretórios temporários no Windows Server 2025, com o token do processo do runner. Não substituem homologação no Windows 11 local nem testes com sessões separadas de usuário padrão, Administradores e SYSTEM.

### Próximo gate

O staging integral por handles passou no CI. Ainda não existe instalação transacional. Próximas etapas: validar a raiz `_update` preexistente em fluxo de atualização, backup verificável por handles, journal durável, troca controlada, recuperação e rollback em sandbox. A allowlist oficial da chave pública de release continua pendente. Nenhum arquivo foi instalado em `C:\\SERMAX`.
## Validação da estrutura persistente e staging reutilizável

Foi adicionada `open_existing_private_area_layout()`, que:
- Abre `_update` por handle relativo ao diretório SERMAX.
- Exige exatamente `staging`, `backups`, `journal`, `logs` e `locks`.
- Abre cada pasta pelo FileId enumerado de 128 bits.
- Revalida owner, DACL protegida e Authz pelo mesmo handle.
- Mantém os handles retidos em `ExistingPrivateAreaLayout` e fecha em ordem inversa.
- Preserva referências a handles cujo fechamento falhou, permitindo nova tentativa de limpeza.
- Rejeita estrutura incompleta, arquivos inesperados, reparse points e nomes de staging fora do padrão.

A política ACL agora separa a validação de segurança da exigência de diretório vazio. O padrão continua exigindo vazio para novas áreas. Diretórios persistentes usam `require_empty=False`, sempre com validação separada e estrita do conteúdo.

`stage_verified_release_by_handle()` passou a aceitar a pasta `staging` persistente, desde que a ACL/Authz seja válida e os itens existentes sejam diretórios `stage-<24 hex>` sem reparse point. Cada nova extração continua usando nome exclusivo por `FILE_CREATE`.

## Backup verificável por handles

Foi adicionado `sermax_windows_backup.py`, com `backup_existing_files_by_handle()`.

Contrato implementado:
- Valida caminhos do manifesto e bloqueia destinos protegidos, inclusive `_update` e nomes reservados.
- Exige que destinos `create` estejam ausentes e destinos `replace` existam.
- Abre arquivos ativos por handles relativos, vinculados ao FileId enumerado.
- Rejeita reparse points, hardlinks, volumes divergentes e arquivos marcados para exclusão.
- Exige `READ_CONTROL` para preservar o descritor de segurança original.
- Calcula SHA-256 da origem, grava por `write_verified_file_component()` e relê a origem para confirmar estabilidade.
- Grava o backup com ACL protegida, `FlushFileBuffers`, readback e verificação de hash.
- Persiste `__sermax_backup_catalog__.json`, com FileId, volume, atributos, tamanho, hash e descritor de segurança original em Base64.
- O catálogo também é gravado e relido pelo escritor verificado.
- Falhas preservam a área de backup parcial para inspeção. Não removem nem alteram arquivos ativos.

Limites atuais do backup: o catálogo preserva conteúdo, atributos e descritor de segurança. Ainda não registra timestamps originais, não implementa restauração e não substitui o journal transacional. A instalação ativa permanece somente leitura.

### CI consolidado

- Run `44410616224`, commit `c0118ee1ccffa5d2286a6bcc6a03d773d081cac8`.
- Windows Server 2025, Python 3.14.10, pywin32.
- 88 testes aprovados em nove grupos:
  - backup por handles: 9;
  - escritor por handles: 7;
  - staging: 10;
  - segurança de handles: 5;
  - inspeção/política de `_update`: 11;
  - criação e validação da área privada: 19;
  - layout persistente: 5;
  - inspeção ACL: 5;
  - política ACL: 17.
- Inclui testes nativos end-to-end de staging e backup em diretórios temporários Windows.
- [Execução CI](https://github.com/frserpeloni/AndroidForge/actions/runs/44410616224).

Os testes nativos foram executados em Windows Server 2025, com token do processo do runner. Ainda faltam homologação no Windows 11 local e testes com contas Windows distintas.

### Próxima etapa

Implementar journal durável append-only com sequência monotônica, hash encadeado, eventos de transação, leitura de recuperação e validação por handles. Depois integrar backup, journal e staging em um fluxo transacional de instalação/rollback em sandbox. Nenhuma instalação em `C:\\SERMAX`, alteração em `main` ou merge foi realizada.
## Journal transacional append-only

Foi adicionado `sermax_windows_journal.py`.

Contrato implementado:
- Cria diretório exclusivo `txn-<24 hex>` dentro de `_update/journal`, com ACL privada.
- Cada evento é um arquivo `event-000001.json`, `event-000002.json` etc., criado por `FILE_CREATE`. Não há sobrescrita de evento.
- Cada registro usa JSON canônico, rejeita chaves duplicadas e constantes não finitas.
- Cada evento contém schema, transaction_id, sequência, tipo, payload, hash anterior e hash próprio SHA-256.
- A leitura valida FileId, volume, hardlinks, tamanho, nome, sequência, cadeia hash, schema, payload e transição de estado.
- A máquina de estados restringe a ordem: PREPARED, BACKUP_COMPLETE, STAGING_COMPLETE, INSTALL_STARTED, FILE_REPLACED, COMMITTED e os eventos de rollback/recuperação.
- Limites: 4.096 eventos por transação, 1 MiB por evento e 64 MiB por journal.
- `scan_journal_transactions_by_handle()` enumera transações sem mutação e identifica registros incompletos ou não terminais que exigem recuperação.
- Cada evento é gravado com ACL protegida, FlushFileBuffers e readback pelo escritor verificado.

O hash encadeado detecta corrupção e inconsistências da cadeia. Não equivale a assinatura criptográfica contra um processo com a mesma identidade e controle total sobre os arquivos. A autenticação da release continua dependendo da chave pública oficial, ainda pendente.

Foi corrigido também `open_verified_child_component()`: diretórios podem mudar de tamanho quando recebem conteúdo. A comparação de tamanho agora se aplica somente a arquivos. FileId, volume, atributos, tipo e reparse point continuam validados.

### CI consolidado com journal

- Run `44411616395`, commit de código/testes `01ded92cd4e0f311280d5333b28db35becd4abfe`.
- Windows Server 2025, Python 3.14.10, pywin32.
- 108 testes aprovados em onze grupos:
  - handles de diretório: 11;
  - journal: 9;
  - backup: 9;
  - escritor por handles: 7;
  - staging: 10;
  - segurança de handles: 5;
  - inspeção/política de `_update`: 11;
  - área privada: 19;
  - layout persistente: 5;
  - inspeção ACL: 5;
  - política ACL: 17.
- O teste nativo do journal cria, grava, fecha, reabre, valida a cadeia e detecta adulteração de evento.
- [Execução CI](https://github.com/frserpeloni/AndroidForge/actions/runs/44411616395).

### Próxima etapa

Implementar verificação independente de backups após reabertura, rotina de restauração de conteúdo/ACL e integração do journal com o staging e o backup. Depois desenvolver instalação transacional e rollback em sandbox. O journal ainda não executa recuperação automática nem altera a instalação ativa.

## Verificação independente de backup, 2026-11-19

Foi adicionada `verify_backup_by_handle()` em `sermax_windows_backup.py`.

A rotina reabre o componente de backup pelo handle do diretório `backups`. Não depende do objeto `BackupSnapshot` produzido na criação. Exige `expected_catalog_sha256`, que deverá ser obtido de evento validado do journal pelo fluxo integrador.

A rotina valida:
- Hash SHA-256 do catálogo contra o hash externo esperado.
- JSON UTF-8 canônico, sem chaves duplicadas ou constantes não padronizadas.
- Versão, componente, campos e tipos do catálogo.
- Caminhos normalizados, sem caminhos protegidos, duplicados ou colisão arquivo/diretório.
- Namespace completo, rejeitando arquivos e diretórios ausentes ou extras.
- FileId de 128 bits, volume, número de links e tamanho dos arquivos.
- SHA-256 de cada arquivo de backup.
- ACL e Authz de diretórios, subdiretórios, catálogo e arquivos.
- Reparse points e objetos não regulares.

A operação é somente leitura. Não executa restauração nem altera a instalação ativa.

O teste nativo de integração fecha o handle original do snapshot e verifica o backup por nova abertura. A execução CI 44611351890 completou todas as etapas com sucesso em Windows.

**Limite atual:** o hash esperado é recebido como argumento. A integração que lê e fornece esse hash a partir do journal ainda está pendente. A rotina de restauração também permanece pendente.


## Restauração de backup por handle, 2026-11-19

Foi adicionada `restore_backup_files_by_handle()` em `sermax_windows_backup.py`.

A rotina:
- Exige sessão de journal em estado `ROLLBACK_STARTED` ou continuação com `FILE_RESTORED`.
- Obtém o componente e o SHA-256 do catálogo a partir do evento `BACKUP_COMPLETE` validado.
- Verifica integralmente o backup antes de escrever no destino.
- Reabre cada arquivo do backup e confere seu SHA-256.
- Restaura conteúdo por handle, com escrita em blocos, FlushFileBuffers e readback.
- Restaura owner, group, DACL e estado de proteção da DACL a partir do descritor original.
- Restaura atributos de arquivo dentro de uma allowlist explícita.
- Confere novamente conteúdo, ACL e atributos.
- Registra cada arquivo concluído como `FILE_RESTORED`.
- Suporta repetição: arquivos já registrados precisam continuar íntegros e são conferidos sem reescrita.

O teste nativo Windows simula alteração de um arquivo, executa rollback, confere o conteúdo original e repete a chamada para testar idempotência.

**Limites e bloqueios:**
- A escrita em arquivo existente é in-place, não atômica. Uma interrupção pode deixar o arquivo parcial. O journal fica sem `FILE_RESTORED` para esse arquivo e o chamador deve registrar `RECOVERY_REQUIRED`.
- A rotina restaura destinos `replace`. A remoção segura dos arquivos introduzidos por ações `create` ainda não foi implementada.
- Diretórios pais ausentes interrompem a restauração; a rotina não recria hierarquias.
- Atributos especiais fora da allowlist são recusados antes de iniciar a restauração.
- Timestamps originais ainda não estão no catálogo e não são restaurados.
- A função não é chamada por um instalador ativo. A integração completa do fluxo de instalação/rollback permanece pendente.


## Preparação transacional integrada, 2026-11-19

Novo módulo: `sermax_update_transaction.py`.

A função `prepare_update_transaction_by_handle()` coordena as etapas já existentes:
1. Valida o ZIP completo contra o manifesto recebido.
2. Cria uma transação no journal e grava `PREPARED`.
3. Preserva os destinos `replace` e grava `BACKUP_COMPLETE`, incluindo o hash do catálogo.
4. Extrai e verifica a release no staging privado.
5. Grava `STAGING_COMPLETE`, com componente e hash do pacote.
6. Devolve os handles e objetos de backup, staging e journal para a próxima fase.

Em falha, tenta registrar `RECOVERY_REQUIRED`, fecha os handles e preserva as árvores parciais. Não executa rollback automático.

A classe `PreparedUpdateTransaction` mantém os recursos abertos. Seu método `begin_install()` grava `INSTALL_STARTED`, mas não executa instalação.

O teste nativo Windows confirma a sequência PREPARED, BACKUP_COMPLETE, STAGING_COMPLETE, depois INSTALL_STARTED. Também confirma que o arquivo ativo permanece inalterado e que arquivos da nova release não aparecem na instalação.

**Limite:** a preparação está integrada. A substituição real dos arquivos, a confirmação COMMITTED e a recuperação automática após interrupção ainda não foram implementadas.


## Instalação por renomeação atômica, 2026-11-19

Foi adicionada `install_prepared_update_by_handle()` ao módulo `sermax_update_transaction.py`.

A rotina exige `INSTALL_STARTED` persistido e executa:
1. Revalida o backup pelo hash do catálogo registrado em `BACKUP_COMPLETE`.
2. Confere os FileIds, tamanhos e hashes dos arquivos no staging.
3. Confere os destinos e os diretórios pais, sem seguir reparse points.
4. Exige destino existente para ação `replace` e destino ausente para ação `create`.
5. Rejeita hardlinks, volume divergente e destinos somente leitura.
6. Move cada arquivo do staging para a pasta ativa por `NtSetInformationFile(FileRenameInformation)`, usando handles relativos.
7. Confere FileId, tamanho e SHA-256 após a renomeação.
8. Registra `FILE_REPLACED` por arquivo.
9. Relê todos os destinos e registra `COMMITTED` ao final.

A renomeação é atômica por arquivo no sistema de arquivos. A atualização inteira, com vários arquivos, não é uma única operação atômica. Se houver falha parcial, a rotina tenta registrar `RECOVERY_REQUIRED` e mantém o backup para rollback.

O teste integrado em Windows Server 2025 prepara uma release com um arquivo `replace` e outro `create`, executa a instalação em diretório temporário, confere os dois conteúdos e confirma `COMMITTED`. O teste também confirma que a preparação, antes da chamada de instalação, não alterou a instalação ativa.

**Limites ainda pendentes:**
- Teste nativo integrado do novo rollback, incluindo interrupções entre exclusão, restauração e gravação dos eventos.
- Recuperação automática após queda do processo ou energia. A rotina atual exige os objetos e handles da transação ainda abertos.
- Protocolo específico para interrupção durante a restauração in-place.
- Homologação local no Windows 11.
- Chave pública oficial de release e validação com pacote assinado de produção.
- Preservação de timestamps originais.

## Rollback integral inicial, 2026-11-19

Foram adicionados ao journal:
- Evento `FILE_REMOVED`, com caminho, SHA-256 e FileId de 128 bits.
- Transições para permitir alternância entre `FILE_REMOVED` e `FILE_RESTORED` até `ROLLED_BACK`.
- Obrigatoriedade de FileId nos eventos `FILE_REPLACED`, vinculando o registro à identidade do arquivo instalado.

A rotina `rollback_prepared_update_by_handle()` foi adicionada ao módulo `sermax_update_transaction.py`. Ela:
1. Exige uma transação em estado recuperável, sem aceitar `COMMITTED`.
2. Inicia ou continua o rollback pelo journal.
3. Para cada ação `create` registrada como instalada, confere FileId, SHA-256, tamanho, volume, tipo regular, ausência de reparse point e quantidade de hardlinks.
4. Marca exclusão pelo handle e confirma que o destino deixou de existir.
5. Registra `FILE_REMOVED` após a confirmação.
6. Restaura ações `replace` pelo backup verificado e registra `FILE_RESTORED`.
7. Registra `ROLLED_BACK` somente após conferir todos os destinos previstos.

A rotina também trata repetição após evento de remoção já persistido. Se encontrar um objeto diferente no destino, interrompe o rollback.

**Validação disponível:** o CI `44631569467`, no commit `2d7d19c6efe3df12255fe10be84efa2b29257e82`, concluiu com sucesso. Todas as etapas do workflow passaram, incluindo compilação dos módulos, testes do journal, backup, staging, preparação transacional e políticas ACL.

**Limite importante:** o CI atual compila o novo orquestrador e valida a máquina de estados do journal, mas ainda não executa um teste nativo de ponta a ponta da nova rotina de rollback. Essa homologação permanece pendente. A recuperação após reinício do processo também não está implementada.

**Segurança operacional:** a função foi exercitada em diretório temporário de CI. Não foi chamada em `C:\SERMAX`, não houve instalação real, merge ou publicação.


## Testes nativos do rollback integral, 2026-11-19

A suíte tests/test_sermax_update_transaction.py agora executa três cenários nativos em diretórios temporários no Windows:

1. **Instalação parcial e rollback completo:** instala um destino replace e um create, injeta interrupção depois dos dois eventos FILE_REPLACED, executa rollback, confirma restauração do conteúdo anterior, remoção do arquivo novo e sequência final FILE_REMOVED, FILE_RESTORED, ROLLED_BACK.
2. **Interrupção entre exclusão e journal:** injeta falha depois da exclusão física do destino create, mas antes da gravação de FILE_REMOVED. A segunda chamada retoma o rollback, registra o evento ausente, restaura o destino replace e termina em ROLLED_BACK.
3. **Objeto externo no caminho create:** substitui o arquivo instalado por outro objeto com conteúdo diferente. O rollback rejeita a identidade/hash divergente, preserva o objeto externo e mantém a transação em RECOVERY_REQUIRED.

### Evidência CI

- Commit: 1a81c33ab5c053971cfe94fa9b2c47e4ff54374c.
- Run: 44635507877.
- Windows Server 2025, Python 3.14.
- Compilação dos módulos e todas as etapas do workflow concluídas com sucesso.
- Os três testes nativos de rollback passaram.
- Execução CI: https://github.com/frserpeloni/AndroidForge/actions/runs/44635507877.

### Limites ainda pendentes

- Recuperação automática depois de reinício do processo ou queda de energia. A função atual exige os objetos e handles da transação ainda abertos.
- Recuperação de uma restauração in-place interrompida no meio da escrita.
- Testes de falhas em todos os pontos de restauração, inclusive entre gravação de conteúdo, ACL, atributos e evento FILE_RESTORED.
- Preservação e restauração de timestamps originais.
- Testes com identidades Windows distintas e homologação no Windows 11.
- Chave pública oficial e pacote assinado de produção.

Os testes ocorreram somente em diretórios temporários do runner Windows. Nenhuma instalação foi executada em C:\\SERMAX. Não houve merge ou publicação.



## Intenção prévia e recuperação por reabertura, 2026-11-19

Foi adicionado o evento append-only FILE_INSTALL_INTENT. Antes de cada renomeação, o instalador registra caminho, SHA-256 e FileId do arquivo no staging. FILE_REPLACED continua sendo gravado depois da renomeação e da confirmação do destino.

A intenção persistida fecha a janela em que a renomeação já ocorreu, mas FILE_REPLACED ainda não foi gravado. O rollback passou a reconhecer essa intenção:
- Para create, remove o destino somente se FileId, hash, volume e metadados corresponderem à intenção.
- Para replace, aceita somente o FileId original registrado no catálogo de backup ou o FileId da intenção. Outros objetos interrompem a recuperação.
- Se uma intenção create não tiver FILE_REPLACED e o destino estiver ausente, não inventa um evento de remoção.

Foi adicionada recover_interrupted_update_by_handle(). A função recebe o identificador da transação, um ValidatedManifest reautenticado pelo chamador e handles das áreas privadas já abertas. Ela:
1. Reabre e valida o journal pelo transaction_id.
2. Confere release_version e manifest_sha256 contra PREPARED.
3. Confere BACKUP_COMPLETE e STAGING_COMPLETE.
4. Verifica o catálogo e os arquivos do backup pelo hash ancorado no journal.
5. Reabre o staging pelo componente registrado, valida ACL/Authz, namespace, hashes e FileIds dos arquivos ainda presentes.
6. Classifica cada destino ativo pelo FileId original do backup ou pelo FileId da intenção persistida.
7. Reconstrói os objetos necessários e chama o rollback existente.

A função é limitada à recuperação por rollback. Não retoma a instalação, não aceita transações COMMITTED ou ROLLED_BACK e não escolhe automaticamente transações. O chamador ainda precisa consultar scan_journal_transactions_by_handle(), resolver o manifesto autenticado correspondente e decidir quais transações elegíveis recuperar.

### Validação CI

- Run 44640770702, commit 576ee40f960042ef39957623414b7c0ea28c35c9.
- Windows Server 2025, Python 3.14.
- Compilação e todas as etapas do workflow concluídas com sucesso.
- O teste nativo fecha os objetos e handles da transação original, reabre journal, staging e backup por handles independentes e recupera o rollback após uma interrupção entre renomeação e FILE_REPLACED.
- Execução CI: https://github.com/frserpeloni/AndroidForge/actions/runs/44640770702.

A validação simula a perda dos objetos e handles anteriores no mesmo runner. Não executa um processo filho separado nem comprova recuperação após desligamento físico. Também não cobre interrupção durante a restauração in-place. Esse protocolo segue pendente e a recuperação não deve ser tratada como automática ou pronta para produção.



### Validação adicional de recuperação fail-closed, 2026-11-19

Foi ampliado o teste nativo para reabrir a transação depois do encerramento dos handles anteriores e substituir o destino create por um objeto externo. A recuperação interrompe o preflight, não remove nem sobrescreve o objeto externo e mantém o journal em RECOVERY_REQUIRED.

- Run 44641017113, commit de código/testes bfac8232cfea02d01b533bd1c32efef26853353c.
- Windows Server 2025, Python 3.14.
- Compilação e todas as etapas do workflow concluídas com sucesso.
- Os quatro testes nativos da suíte transacional passaram, incluindo recuperação após reabertura e rejeição de objeto externo.
- Execução CI: https://github.com/frserpeloni/AndroidForge/actions/runs/44641017113.

A recuperação continua sendo uma operação explícita chamada com transaction_id e manifesto autenticado. O início automático na inicialização, a política de seleção de transações e a recuperação de escrita in-place interrompida seguem pendentes.


## Preservação de timestamps no backup, 2026-11-20

A branch `sermax-backup-timestamps-20261120` acrescenta metadados temporais ao catálogo de backup.

- Catálogos novos usam `schema_version: 2`.
- Cada arquivo registra `CreationTime`, `LastAccessTime` e `LastWriteTime` obtidos por `GetFileInformationByHandleEx(FileBasicInfo)`.
- A restauração aplica esses três campos por `SetFileInformationByHandle(FileBasicInfo)`, depois de restaurar conteúdo, descritor de segurança e atributos.
- A conferência final relê os valores pelo mesmo handle.
- A verificação de idempotência considera os timestamps. Se conteúdo, ACL e atributos já estiverem corretos, reaplica os timestamps originais sem regravar o conteúdo. Isso também neutraliza eventual atualização de `LastAccessTime` causada pela própria leitura de verificação.
- O validador mantém leitura de catálogos `schema_version: 1`. Esses backups antigos continuam restauráveis sem timestamps, pois não contêm os valores históricos.
- `ChangeTime` não é armazenado nem restaurado. O Windows administra esse campo como horário de alteração de metadados e não é tratado como timestamp preservável neste fluxo.
- Valores zero são recusados, pois zero em `FILE_BASIC_INFO` significa não alterar o campo. O fluxo falha fechado em vez de declarar restauração temporal sem confirmação.

A alteração está em branch isolada. A validação CI e a homologação local ainda precisam ser executadas. Nenhum arquivo de `C:\\SERMAX` foi tocado.
