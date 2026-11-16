# Matriz provisória de pacote e dependências do SERMAX Platform
Data: 2026-11-15
Branch: sermax-platform-prototype-20261115
Status: auditoria documental; não autoriza empacotamento ou distribuição.

## 1. Escopo e limites

Esta matriz registra os arquivos e declarações de dependência inspecionados na branch. Não é inventário de um executável final, não é auditoria jurídica e não substitui a resolução completa das dependências transitivas. Nenhum pacote oficial foi montado nesta etapa.

A branch da Plataforma permanece isolada. Não alterar `main`, núcleo original, Terminal, memórias, históricos ou backups.

## 2. Dependências identificadas

| Componente | Declaração encontrada | Papel identificado | Tratamento provisório |
|---|---|---|---|
| SERMAX Platform backend | `fastapi>=0.115,<1.0` | Runtime da API local | Incluir somente após fixar versões e inventariar dependências transitivas/licenças |
| SERMAX Platform backend | `uvicorn[standard]>=0.30,<1.0` | Runtime do servidor ASGI | Mesmo tratamento; extra `standard` exige inventário transitivo |
| SERMAX Platform backend | `httpx>=0.27,<1.0` | Cliente HTTP | Mesmo tratamento |
| Interface de testes | `jsdom ^26.1.0` em `devDependencies` | Testes automatizados de UI | Não incluir no runtime do usuário; manter em ambiente de desenvolvimento/CI |
| Scripts de automação | `PyYAML>=6.0` | Dependência dos scripts | Não incluir no runtime sem identificar quais scripts serão distribuídos/executados |
| SERMAX Windows | Python 3.14, Pestinha e PyInstaller indicados na documentação/spec | Núcleo, integração e build | Dependências e versões exatas precisam ser fechadas por lockfile/manifesto do build |
| OpenJarvis | Worker separado em Python 3.13, commit upstream fixado na auditoria de licenças | Integração isolada | Não presumir que o ambiente está incluído no executável; inventariar dependências efetivamente instaladas e avisos Apache-2.0 |

Os arquivos `SERMAX-Platform/backend/requirements.txt`, `SERMAX-Platform/package.json` e `scripts/requirements.txt` usam faixas de versão, não um lock completo. Os arquivos consultados não fornecem uma lista fechada de dependências transitivas nem um SBOM.

## 3. Licenças e avisos verificados

### Projeto e arquivos da raiz
- A raiz contém `LICENSE` com MIT License e copyright indicado como AndroidForge, 2026.
- Essa licença da raiz não comprova, por si só, a licença de cada diretório, dependência ou componente de terceiros.
- Antes de distribuir o produto SERMAX, confirmar titularidade e aplicabilidade do aviso MIT aos arquivos efetivamente incluídos.

### Pestinha
- A documentação de auditoria registra upstream `mille-okws/pestinha`, commit `1b16bd21bb5ba9dd4c460c153f865824f53d05c8` e licença GPL-3.0-or-later.
- O texto integral GPLv3 e o aviso de origem estão em `SERMAX-Windows/THIRD_PARTY_NOTICES/`.
- `SERMAX-Windows/SERMAX.spec` chama `collect_all("pestinha")` e inclui os dois avisos no bundle.
- A auditoria documenta que a pasta upstream `assets/` contém imagens e textos não cobertos pela GPL indicada para o código. Não incluir `assets/` ou `pets/` sem comprovação de direitos.
- A auditoria existente deixa pendente a verificação de Corresponding Source exato, fonte das modificações, mecanismo de fornecimento junto ao binário e análise da combinação do código GPL com os demais componentes.
- Não declarar a distribuição binária pronta até resolver esses itens com revisão especializada.

### OpenJarvis
- A auditoria existente registra commit fixado `c6c782b924c9040d7c35f76ff693d4057bc0032f`, licença Apache-2.0 e execução em ambiente Python 3.13 separado.
- O `SERMAX.spec` inclui o worker, mas a auditoria diz que o ambiente Python separado não é empacotado no executável.
- Falta incluir aviso Apache-2.0/atribuição no processo de instalação quando o componente for distribuído, além de inventariar dependências transitivas resolvidas e avisos NOTICE aplicáveis.

## 4. Matriz provisória de inclusão

| Grupo | Exemplos | Decisão nesta fase |
|---|---|---|
| Plataforma | `SERMAX-Platform/index.html`, `styles.css`, `app.js`, backend e launcher | Candidatos a pacote da Plataforma, após testes e definição de runtime |
| Núcleo Windows | `SERMAX-Windows/sermax_core.py` e dependências funcionais | Não incluir automaticamente; exigir matriz explícita e reconciliação da versão oficial |
| Terminal | `SERMAX_terminal/` e launcher original | Preservar; inclusão somente com validação de integração e sem substituir a experiência funcional |
| Pestinha | Adaptador e pacote Python necessário à rede LIF | Exigir fonte correspondente, avisos e análise de licença; excluir assets sem autorização |
| OpenJarvis | Worker e ambiente Python separado | Não declarar incluído pelo executável; pacote de ambiente exige manifesto e avisos próprios |
| Testes e ferramentas de desenvolvimento | `tests/`, jsdom, PyYAML, ferramentas CI | Excluir do runtime, salvo ferramenta administrativa explicitamente aprovada |
| Dados do usuário | memórias, SQLite, histórico, configurações, anexos | Nunca incluir como payload de atualização; preservar e tratar por migração/backup separado |
| Backups e logs locais | `.sermax-backups/`, logs e cópias de segurança | Nunca coletar automaticamente no pacote; não apagar durante instalação/atualização |
| Credenciais e modelos | chaves, tokens, modelos Ollama, arquivos privados | Excluir do pacote e de logs/artefatos |

Esta tabela é uma classificação preliminar. O pacote builder exige mapeamentos explícitos e não varre diretórios, mas ainda não existe manifesto oficial que represente uma instalação completa e autorizada do SERMAX.

## 5. Lacunas do instalador observadas no código

1. A GUI executa `preflight()`, mostra resumo e pede confirmação. Depois, a thread chama `install_package()`, que faz nova validação. A confirmação não fica vinculada a um snapshot imutável do pacote, manifesto, hashes e destino.
2. O pacote pode mudar entre a confirmação e a execução. A segunda validação reduz o risco, mas não comprova que o usuário confirmou exatamente o mesmo conteúdo.
3. Os campos de pacote e destino não são desativados enquanto a operação está ativa. A thread recebe objetos `Path` já copiados, mas a interface ainda permite alteração visual durante o processo.
4. O motor faz backup dos arquivos de programa listados que serão substituídos. Não faz backup integral de dados, memórias, histórico, configurações ou arquivos não listados.
5. `preserve_paths` no manifesto é informativo. A proteção real depende das regras internas do motor e da lista de caminhos protegidos, não desse campo isoladamente.
6. A instalação substitui arquivos individualmente com `os.replace`. Não há transação atômica do conjunto inteiro.
7. As verificações de symlink/junction/reparse point e a revalidação reduzem riscos, mas não eliminam TOCTOU entre inspeção e operações de arquivo. O lock de instalação coordena processos cooperantes; não impede um processo externo de alterar diretórios.
8. A GUI não tem teste automatizado de interação real. Os testes atuais verificam a política de fechamento enquanto a operação está ativa.
9. Não há PyInstaller para a GUI da Plataforma, executável instalador, assinatura digital, desinstalador ou pacote completo validado.

## 6. Próximos critérios técnicos antes de empacotar

- Definir a matriz oficial de arquivos por instalação inicial e atualização, com origem, destino, finalidade, versão e regra de preservação.
- Fixar versões de runtime e gerar inventário de dependências transitivas e licenças.
- Definir como instalar/validar Python, Ollama e modelos sem sobrescrever dados existentes.
- Implementar plano imutável de instalação: snapshot dos arquivos, hashes, versão, destino e modo; exigir que o worker confirme o mesmo snapshot antes de alterar qualquer arquivo.
- Bloquear edição dos campos e seletores durante a operação.
- Projetar backup e restauração de dados do usuário em fluxo separado, com confirmação e verificação de integridade. Não tratar backup de arquivos substituídos como backup completo.
- Definir recuperação após falha no meio da atualização e comprovar restauração em testes Windows.
- Concluir avisos e fonte correspondente Pestinha, avisos Apache-2.0 OpenJarvis e inventário das dependências efetivamente distribuídas.
- Testar GUI real, instalação limpa, atualização, interrupção, falha de disco, bloqueio concorrente, rollback e preservação de dados em Windows.
- Só então montar pacote candidato e validar em ambiente Windows limpo e em instalação de teste.

## 7. Conclusão de estado

O CI da Plataforma no commit `2b7378050c37ea434a549ba71c9ce9b4e71d2438` concluiu com sucesso. Isso valida os jobs automatizados declarados no workflow, não uma instalação no computador do usuário.

O instalador segue em protótipo. Não existe instalador distribuível nem atualização segura completa. Esta matriz é documentação de auditoria e não altera arquivos funcionais, dados ou instalação local.


## 8. Revalidação da composição e reconciliação com o atualizador Windows, 2026-11-16

A inspeção da árvore da branch identificou um segundo conjunto de módulos, em `SERMAX-Windows/`, que não constava como pipeline de instalação integrado na matriz anterior. A composição abaixo é uma classificação de auditoria, não um manifesto de release.

### 8.1 Dois formatos existentes, sem integração comprovada

| Trilha | Formato atual | Situação observada |
|---|---|---|
| `SERMAX-Platform/installer` | Diretório com `manifest.json` schema v1 e `payload/` | Construtor e motor de desenvolvimento. Manifesto sem assinatura. |
| `SERMAX-Windows/sermax_update_*` | ZIP + JSON schema 1 assinado Ed25519 | Validador de manifesto, backend de assinatura, validador ZIP, inventário e plano em memória. Não instala nem faz rollback. |

Não converter automaticamente um formato no outro. A arquitetura detalhada está na seção 11.17 de `installer/WINDOWS_HANDLE_BASED_INSTALLER_DESIGN.md`.

### 8.2 Composição candidata por grupo

| Grupo | Arquivos observados | Regra de pacote |
|---|---|---|
| Interface Plataforma | `SERMAX-Platform/index.html`, `styles.css`, `app.js` | Candidatos ao runtime. Exigem validação do caminho quando empacotados. |
| API Plataforma | `SERMAX-Platform/backend/server.py` | Candidato ao runtime. Exige ambiente Python e dependências fixadas. |
| Launcher Plataforma | `SERMAX-Platform/sermax_platform_launcher.py` | Launcher Python de desenvolvimento. Não há executável congelado validado para a Plataforma. |
| Dependências Plataforma | `SERMAX-Platform/backend/requirements.txt` | FastAPI, Uvicorn com extra standard e HTTPX em faixas de versão. Falta lockfile e inventário transitivo. |
| Núcleo | `SERMAX-Windows/sermax_core.py`, `sermax_planejador.py`, `sermax_executor.py`, `sermax_tarefas.py`, `ferramenta_windows.py`, `sermax_jarvis_adapter.py`, `sermax_widget_state.py`, `sermax_pestinha_adapter.py` | Candidatos condicionados à reconciliação com a candidata aprovada e ao fechamento de imports/dependências. |
| Terminal original | `SERMAX-Windows/SERMAX_terminal/sermax_terminal.py`, `sermax_voz.py`, `sermax_integracao_comandos.py`, `sermax_launcher.py` | Preservar identidade visual e comportamento. Inclusão exige teste visual e funcional. |
| Pestinha | Dependência upstream fixada e coletada pelo `SERMAX.spec` | Condicionado à resolução de GPL-3.0-or-later e fonte correspondente. Excluir `assets/` e `pets/` sem direitos comprovados. |
| OpenJarvis | `sermax_jarvis_worker.py` e adaptador, com ambiente Python 3.13 externo | Worker é incluído no spec atual; ambiente OpenJarvis não é empacotado no executável. Exige pacote/instalador próprio e avisos Apache-2.0. |
| Ollama e modelos | Serviço local em `127.0.0.1:11434` e modelos do usuário | Pré-requisito externo. Nunca incluir nem substituir modelos locais. |
| Dados do usuário | `memoria_sermax.json`, `memoria_neural_pestinha.json`, banco `%USERPROFILE%\\.sermax-platform\\platform.sqlite3`, logs, preferências e históricos | Fora do payload. Preservar byte a byte. Migração em plano separado, autorizado e reversível. |
| Desenvolvimento | Testes, workflows, documentação, backups, `.deps`, ambientes virtuais, logs e segredos | Excluir do runtime. |

### 8.3 Dependências efetivamente observadas

- Workflow Windows prepara Python 3.14 com PyInstaller, NumPy, psutil, pywin32 e `cryptography==50.0.2`.
- Pestinha é obtido em commit upstream fixado e exposto ao ambiente de build via `PYTHONPATH`; o spec usa `collect_all("pestinha")`.
- OpenJarvis é instalado em Python 3.13 separado, em commit upstream fixado. O executável atual inclui o worker, mas não inclui o ambiente Python 3.13.
- A Plataforma declara FastAPI, Uvicorn[standard] e HTTPX sem versões fechadas. `package.json` mantém jsdom em `devDependencies`, portanto não pertence ao runtime.
- A presença de dependências no ambiente de CI não comprova que todas estejam incorporadas ao executável ou disponíveis no computador do usuário. É necessário SBOM/lockfile e inspeção do artefato final.

### 8.4 Limites do atualizador assinado existente

Os módulos `sermax_update_manifest.py`, `sermax_update_signature.py`, `sermax_update_package.py`, `sermax_update_inventory.py` e `sermax_update_inventory_contract.py` implementam validação e planejamento sem escrita. O backend Ed25519 aceita allowlist de chaves públicas fornecida pelo chamador; não há chave pública de release aprovada ou provisionada. Os testes geram chaves efêmeras. O validador ZIP não extrai arquivos nem instala.

O manifesto atual usa serialização JSON determinística própria, com `sort_keys=True` e separadores compactos. Não rotular como RFC 8785/JCS. O `SERMAX.spec` atual não declara esses módulos do atualizador em sua lista de imports ocultos, nem há evidência de que o executável congelado os invoque.

### 8.5 Decisão e pendências

1. Manter as duas trilhas identificadas, sem declarar compatibilidade entre os formatos.
2. Tratar Ed25519 + schema 1 + ZIP como candidato de continuidade para o atualizador Windows existente, sujeito a chave de produção, anti-rollback e integração com transação segura.
3. Não adotar CMS/PKCS #7 + diretório schema v2 como segundo formato paralelo sem decisão arquitetural expressa.
4. Definir se a futura Plataforma e o núcleo Windows serão um pacote único ou componentes versionados separadamente.
5. Fechar versões de dependências, dependências transitivas, SBOM e avisos de licenças.
6. Resolver Corresponding Source Pestinha e avisos/dependências OpenJarvis antes de distribuição binária.
7. Validar o launcher da Plataforma em layout congelado e provar que ele encontra backend e núcleo sem alterar o launcher original.
8. Produzir allowlist de arquivos com origem, destino, proprietário funcional, versão, dependência, licença, classificação de dados e ação permitida.
9. Integrar validação, staging, backup, journal, instalação e rollback somente após aprovação do desenho de segurança.

**Conclusão atualizada:** não existe composição oficial fechada, pacote completo ou instalador distribuível. Esta seção documenta os arquivos e lacunas observados na branch em 2026-11-16.


## 9. Auditoria estática da integração inventário/manifesto/plano, 2026-11-16

Foi identificada uma incompatibilidade que impede ligar os módulos atuais:

1. `build_inventory_plan()` exige `file_id` de 128 bits para cada destino `replace`.
2. `inventory_directory()` não retorna `file_id`, volume, nem handle retido. Retorna caminho, tipo, tamanho, SHA-256 e classificação.
3. Os testes do planejador fabricam `file_id` em seus registros auxiliares. Portanto, não provam que o inventário real atende ao contrato.
4. O inventário verifica entradas com `stat(follow_symlinks=False)`, mas calcula hash por `Path.open()` e tamanho por `Path.stat()`. São operações de caminho separadas, sujeitas a troca concorrente após a verificação. A admissão da raiz também não mantém handles dos ancestrais.
5. O planejador recebe mappings comuns e não prova que foram produzidos pelo inventário confiável. A procedência é uma precondição textual, não uma garantia da interface.
6. O planejador exige diretórios ancestrais existentes. O manifesto não possui operação explícita de criação de diretórios.
7. O validador ZIP retorna contagens e hashes, mas não cria snapshot imutável em staging. O futuro instalador deverá consumir exatamente os bytes validados, sem reabrir caminho controlado pelo cliente.
8. Não existe coordenador que vincule os bytes exatos do manifesto, ZIP, inventário, plano, staging e journal em uma única transação durável.

**Classificação:** bloqueadores de integração e segurança. Os módulos permanecem protótipos de validação e leitura. Não conectar ao instalador, não elevar privilégios e não executar contra a instalação ativa. A auditoria detalhada consta na seção 11.18 de `installer/WINDOWS_HANDLE_BASED_INSTALLER_DESIGN.md`.

**Próxima tarefa permitida:** especificar o contrato do inventário Windows baseado em handles, incluindo identidade de volume/arquivo, retenção de handles, procedência do resultado e testes de concorrência. Não implementar serviço privilegiado nem instalação até aprovação arquitetural.


## 10. Contrato proposto para inventário Windows vinculado a handles, 2026-11-16

**Status:** especificação documental. Não há implementação nativa, serviço privilegiado, alteração no instalador ou teste executado nesta etapa.

A auditoria da seção 9 identificou que o planejador exige `file_id`, mas o inventário real não o produz. A seção 11.19 de `installer/WINDOWS_HANDLE_BASED_INSTALLER_DESIGN.md` define o contrato proposto para corrigir a procedência e a identidade dos objetos.

### 10.1 Identidade de objeto

- Consultar `FILE_ID_INFO` por `GetFileInformationByHandleEx(FileIdInfo)` no handle aberto.
- Registrar o par `VolumeSerialNumber` + os 16 bytes do `FileId`.
- Não tratar o ID como permanente. Sistemas de arquivos podem reutilizar IDs após exclusão.
- Não substituir a identidade por `st_ino`, caminho, timestamp ou identificador fabricado.
- Se a consulta falhar, o filesystem não suportar 128 bits ou o ID vier zerado, falhar fechado para o fluxo confiável.
- Reter o handle do objeto e dos diretórios ancestrais relevantes durante todo o uso do snapshot. A identidade numérica não substitui o handle.

A documentação Microsoft define o par volume/ID para comparar handles abertos e registra limitações de reutilização de IDs. Isso não resolve a segurança da resolução do caminho nem a corrida de troca de diretórios.

### 10.2 Snapshot com procedência

O inventário confiável deverá produzir um objeto opaco `InventorySnapshot`, instanciável somente pelo backend Windows. O objeto retém handles, identidade da raiz, identidade de cada arquivo/diretório, relação com o diretório pai, metadados e SHA-256 lido do próprio handle.

Registros comuns, JSON exportado, cache serializado ou dicionários fornecidos pelo chamador não terão autoridade. O planejador aceitará somente snapshot vivo, íntegro, não invalidado e associado à raiz/política esperadas.

Ações `replace` referenciam o handle/entrada do arquivo existente. Ações `create` referenciam o handle do diretório pai e a ausência observada do nome. A ausência deverá ser revalidada no commit sob contrato de namespace aprovado. Sem operações explícitas de diretório, todos os diretórios de destino deverão existir.

### 10.3 Limites que continuam abertos

- A admissão segura da raiz e a resolução de filhos por diretório ainda dependem de contrato Windows documentado e de garantias sobre mutações concorrentes. A seção 4A do desenho mantém esse bloqueio.
- O identificador de arquivo não é permanente e não substitui o handle retido.
- Mudança de volume, reparse point, tipo inesperado, falha de hash, enumeração incompleta ou fechamento de handle invalidam o snapshot.
- O snapshot não é journal durável. Após reinício, a autoridade deve ser readquirida e revalidada.
- A implementação não está autorizada por esta especificação.

### 10.4 Testes exigidos

Testar no Windows: comparação de handles, IDs zerados/indisponíveis, reuso de IDs, troca de arquivo e diretório durante enumeração/hash, junctions e symlinks, renomeação e remoção com handles retidos, volume crossing, hard links, colisões de nomes Unicode/case, limites de handles, interrupções e rejeição de snapshots serializados ou fabricados.

Cada resultado deverá registrar build do Windows, filesystem, commit, comando, resultado e evidência. Testes em um filesystem não comprovam suporte a outro.

**Decisão:** contrato de dados especificado; segurança da resolução de nomes permanece bloqueada. Nenhuma instalação, integração privilegiada ou liberação foi autorizada.


## 11. Validade do snapshot, confirmação e retomada transacional, 2026-11-16

**Status:** especificação documental. Nenhum temporizador, journal, coordenador ou instalador foi implementado.

A seção 11.20 do desenho do instalador separa três objetos que não devem ser confundidos:

1. `InventorySnapshot`, estado efêmero em memória que mantém handles abertos.
2. `ConfirmedPlan`, plano imutável vinculado ao pacote, manifesto, destino e escolhas exibidas ao usuário.
3. `TransactionRecord`, journal durável de fases. Não preserva autoridade de handles após reinício.

### 11.1 Estados e expiração

O snapshot segue estados monotônicos: `ACQUIRING`, `VALID`, `PLAN_BOUND`, `INVALID`, `EXPIRED` e `DISPOSED`. Snapshot inválido ou expirado não volta a ser válido. Nova aquisição gera novo ID e geração.

A validade temporal deverá usar relógio monotônico e limite máximo de planejamento definido por medição. O prazo é proteção de ciclo de vida e recursos, não prova de segurança. Ausência de evento do File Watcher não comprova ausência de alteração.

### 11.2 Confirmação vinculada ao plano

O digest de confirmação deverá incluir, no mínimo, identidade da release, hash exato do manifesto e ZIP, ID/geração do snapshot, identidade da raiz, destinos, ações, identidades esperadas dos arquivos existentes, política e modo de instalação.

Qualquer alteração depois da confirmação invalida o digest. O processo deverá abortar antes de qualquer escrita e exigir novo preflight e nova confirmação. O digest não substitui assinatura, chave confiável ou handles vivos.

### 11.3 Handoff e recuperação

Antes da primeira mutação, o futuro coordenador deverá adquirir lock, verificar validade e identidade dos handles, confirmar o mesmo pacote imutável, revalidar precondições e persistir o journal. Se o processo reiniciar, os handles e a confirmação antiga perdem validade. A recuperação deverá adquirir novos handles e validar novamente, sem reconstruir autoridade a partir de IDs serializados.

A espera pelo lock também consome o prazo do snapshot. Se expirar durante a espera, abortar sem escrita. A revalidação de namespace continua bloqueada pela seção 4A.

### 11.4 Testes exigidos

Testar expiração durante preflight, diálogo de confirmação, espera do lock e antes da escrita; mudanças no relógio do sistema; descarte concorrente de handles; alteração de pacote/destino/modo após confirmação; replay de confirmação; crash antes e depois do journal; journal adulterado; retomada após reinício; e silêncio de File Watcher com alteração concorrente.

**Decisão:** a política de ciclo de vida e confirmação está especificada. Não existe transação segura implementada, nem autorização para conectar o protótipo ao instalador.


## 12. Journal transacional e recuperação após falhas, 2026-11-16

**Status:** especificação documental. Nenhum journal, serviço, instalador, backup transacional, rollback ou mecanismo de recuperação foi implementado ou testado.

A seção 11.21 de installer/WINDOWS_HANDLE_BASED_INSTALLER_DESIGN.md define o contrato proposto.

### 12.1 Máquina de estados

Estados: PREPARED, STAGING_VERIFIED, BACKUP_VERIFIED, COMMITTING, COMMITTED, ROLLBACK_REQUIRED, ROLLING_BACK, ROLLED_BACK, RECOVERY_REQUIRED e ABORTED. As transições são monotônicas e validadas. Estados terminais não retornam ao fluxo normal. Estado ambíguo não autoriza repetição automática.

### 12.2 Registro durável

Cada registro vincula versão do formato, ID aleatório da transação, sequência monotônica, digest do registro anterior, estado, intenção/resultado, release, hashes do manifesto/pacote/plano, raiz protegida, alvos, hashes/identidades anteriores e posteriores, referências de staging/backup e código de erro.

O hash encadeado detecta alterações e lacunas, mas não impede adulteração completa por quem controla o journal. ACL, proprietário, identidade do serviço, formato, checksum/MAC/assinatura e custódia de chaves permanecem decisões abertas.

### 12.3 Regra write-ahead

Para cada alteração:
1. Revalidar pacote, raiz, alvo e precondições.
2. Persistir intenção da operação.
3. Confirmar flush e leitura/verificação do registro.
4. Executar uma operação delimitada.
5. Verificar identidade, tipo, tamanho e hash do resultado.
6. Persistir conclusão somente após a verificação.

Sem intenção durável, nenhuma escrita. Sem verificação posterior, nenhuma conclusão. Divergência entre estado anterior e posterior leva a RECOVERY_REQUIRED.

### 12.4 Backup e recuperação

- Cada arquivo substituído exige backup independente, leitura de retorno e validação de hash.
- O marcador da instalação é publicado por último.
- A recuperação readquire handles e valida todos os objetos. Nunca reutiliza handles, snapshot ou confirmação de processo anterior.
- Journal corrompido, sequência ausente, backup alterado, pacote divergente ou resultado ambíguo bloqueiam retomada automática.
- Backups e artefatos de recuperação permanecem preservados até política de retenção aprovada.
- Memórias, SQLite, histórico, Terminal, configurações, modelos Ollama, ambientes Python e arquivos fora do payload autorizado ficam fora da transação.

### 12.5 Limites de durabilidade

A documentação Microsoft descreve FlushFileBuffers como flush dos buffers do arquivo indicado. Isso não comprova atomicidade de uma transação com vários arquivos nem persistência de toda alteração de diretório após perda de energia. O método de publicação do journal, filesystem, metadados e cache físico precisam de validação separada. Não há garantia de power-loss aprovada.

### 12.6 Testes exigidos

Injetar falha antes/depois de cada escrita, flush, publicação, backup, substituição, verificação, marcador e rollback. Testar disco cheio, interrupção, reinício, journal truncado/adulterado/reordenado, replay, backup alterado, pacote antigo, troca de raiz e recuperação repetida. Cada cenário termina em estado comprovado ou RECOVERY_REQUIRED com artefatos preservados.

**Decisão:** contrato documental concluído. A seção 4A continua bloqueando o backend de handles. O broker da seção 11.1 ainda exige aprovação. Não há instalador distribuível nem autorização de implementação nesta etapa.


## 13. Rollback por arquivo e verificação da restauração, 2026-11-16

**Status:** especificação documental. Nenhum código de restauração/exclusão, motor transacional, broker, instalador ou teste de rollback foi executado.

A seção 11.22 de installer/WINDOWS_HANDLE_BASED_INSTALLER_DESIGN.md define o protocolo.

### 13.1 Estados por arquivo

Cada alvo mantém estado próprio: NOT_STARTED, APPLY_INTENT, APPLIED_VERIFIED, RESTORE_INTENT, RESTORED_VERIFIED, NO_CHANGE_VERIFIED ou RECOVERY_REQUIRED. O journal geral não substitui o estado individual de cada arquivo.

### 13.2 Classificação antes da restauração

Cada alvo é classificado como:
- BEFORE: objeto original ainda presente e compatível com identidade e evidências do estado anterior. Registrar NO_CHANGE_VERIFIED.
- AFTER: objeto exato instalado pela transação, com identidade, tipo, tamanho e hash esperados. Elegível à restauração com backup validado.
- AMBIGUOUS: objeto ausente ou diferente, alteração externa, identidade incerta ou falha na prova de namespace. Parar em RECOVERY_REQUIRED.

Não sobrescrever objeto inesperado. Não decidir por caminho ou hash isolado quando a identidade do objeto é exigida.

### 13.3 Ordem e protocolo

Restaurar em ordem inversa aos registros de aplicação verificada. Para cada alvo: validar backup e metadados; revalidar alvo/pai; persistir RESTORE_INTENT; restaurar; ler de volta; verificar conteúdo, tipo, tamanho e metadados aprovados; registrar a nova identidade; persistir RESTORED_VERIFIED.

Para arquivo originalmente ausente, remover somente o objeto exato criado pela transação, após intenção durável e revalidação. Se outro objeto o substituiu, não excluir.

Backup ausente, adulterado ou ilegível bloqueia a restauração. Não reconstruir a versão anterior usando o pacote novo.

### 13.4 Metadados e identidade

Hash confirma bytes, não ACL, proprietário, timestamps, alternate data streams, hard links ou demais atributos. A lista de metadados preservados precisa ser definida por classe de arquivo e filesystem antes da implementação.

Restauração por cópia pode gerar novo file ID. O journal registra a nova identidade e verifica equivalência de conteúdo/metadados aprovados. Não declara que o objeto antigo foi recriado.

### 13.5 Marcador e anti-rollback

Restaurar o marcador da versão depois dos arquivos. Ele nunca deve anunciar a versão anterior enquanto houver arquivo novo ou ambíguo. Falha no marcador impede ROLLED_BACK.

Rollback de arquivos não reduz automaticamente o contador anti-rollback do broker. Recuperação de versão antiga exige política e autorização próprias.

### 13.6 Reinício e falhas

Após reinício, reler journal, readquirir handles e reclassificar todos os alvos. Para RESTORE_INTENT sem conclusão, verificar se o estado restaurado já existe, se o objeto ainda está no estado AFTER ou se há ambiguidade. Nunca presumir que uma chamada interrompida não alterou o arquivo.

ROLLED_BACK exige todos os alvos RESTORED_VERIFIED ou NO_CHANGE_VERIFIED, marcador restaurado, verificação final e registro durável.

### 13.7 Testes exigidos

Testar falhas em cada ponto do rollback, restauração em ordem inversa, arquivos originais/não alterados/alterados externamente, backups ausentes ou adulterados, metadados, arquivos recém-criados, troca de identidade, disco cheio, acesso negado, reinício e repetição da recuperação. Comprovar que dados do usuário e arquivos fora da allowlist permanecem intactos.

**Decisão:** protocolo documental concluído. A seção 4A ainda bloqueia a resolução segura de nomes. ACL/journal e autorização do broker continuam pendentes. Não existe rollback implementado ou instalador distribuível.


## 14. Saúde pós-instalação e limite de COMMITTED, 2026-11-16

**Status:** especificação documental. Nenhum health check novo, endpoint, instalador, broker ou teste foi implementado nesta etapa.

### 14.1 Comportamento atual observado

- A API expõe GET /api/health com status, identificador do serviço, versão, estado de carregamento do núcleo e timestamp.
- O endpoint não verifica integridade do SQLite, não carrega o núcleo e não testa Ollama ou OpenJarvis.
- O núcleo é carregado sob demanda, durante uma solicitação de chat. O estado not_loaded no início não representa, isoladamente, falha de inicialização.
- O launcher de desenvolvimento espera até 30 segundos, com timeout de 1,5 segundo por requisição e intervalo de 0,25 segundo. Ele aceita HTTP 200 e o identificador sermax-platform-api. Isso prova somente uma resposta básica da API, não a identidade da release candidata.
- A inicialização da API executa a inicialização do esquema SQLite. O health check atual não faz leitura de integridade do banco.
- Esses tempos são valores do launcher de desenvolvimento. Não são política aprovada para instalador.

### 14.2 Dimensões separadas

A futura verificação deve separar integridade do payload, identidade e estabilidade do processo, liveness da API, readiness, integridade de persistência, disponibilidade do núcleo e dependências opcionais. Ollama, OpenJarvis e Pestinha só serão obrigatórios quando a política da release declarar explicitamente essa exigência.

A evidência deve vincular transaction ID, release, digest do manifesto, inventário instalado, identidade do processo, versão da política e resultado de cada probe. PID, URL, HTTP 200 ou nome do serviço isolados não identificam a release instalada.

O endpoint atual não retorna digest de manifesto nem ID da transação. Sua extensão ou um canal autenticado do broker permanece decisão de interface, sem implementação nesta etapa.

### 14.3 Ordem exata do commit

1. Aplicar os arquivos autorizados e verificar cada alvo por leitura de retorno.
2. Iniciar ou identificar o processo candidato e provar sua identidade de release.
3. Executar todos os probes obrigatórios e o período de estabilização aprovado.
4. Persistir HEALTH_VERIFIED com digest da evidência. Esse estado ainda não é COMMITTED.
5. Revalidar lock, raiz, alvos, pacote, evidência e precondições do marcador.
6. Persistir intenção de publicação do marcador.
7. Publicar o marcador como última alteração do payload e verificar sua leitura de retorno.
8. Persistir o registro final COMMITTED, fazer flush e ler o registro de volta. Só então informar sucesso.

O marcador não será publicado antes da aprovação de todos os probes obrigatórios. O registro COMMITTED vem depois da verificação do marcador.

### 14.4 Falhas e dados do usuário

Falha obrigatória antes de COMMITTED impede publicação do marcador. Rollback automático continua sem autorização e depende de política explícita. Ambiguidade leva a RECOVERY_REQUIRED com preservação dos artefatos.

Crash após marcador e antes do registro COMMITTED não significa instalação concluída. A recuperação readquire handles, revalida arquivos e marcador, reinicia a verificação de saúde e só conclui se a política aprovada comprovar todas as condições.

Após COMMITTED, falhas posteriores exigem transação de reparo separada.

Memórias, SQLite, histórico, preferências, logs, anexos, modelos Ollama, ambientes Python, serviços externos, Terminal original fora da allowlist e backups permanecem fora do payload e do rollback. Probes de persistência devem ser somente leitura. Não enviar chat real, alterar memória, gravar conversa de teste ou executar migração durante a verificação.

### 14.5 Pendências para implementação

Aprovar schema de health profile, capacidades obrigatórias, identidade de processo, vínculo da probe com a release, topologia de inicialização, teste SQLite somente leitura, tempos de estabilização e timeout, retenção das evidências e política de rollback.

Testes exigidos cobrem processo antigo já ativo, PID reutilizado, identidade incorreta, API online com readiness falha, resposta obsoleta, SQLite corrompido/ocupado, núcleo ausente, motores opcionais, falhas em cada fase do marcador e journal, crash, disco cheio e recuperação repetida.

**Decisão:** contrato de saúde e fronteira COMMITTED documentados. A implementação permanece bloqueada pelas pendências de segurança da seção 4A, decisões do journal, aprovação do broker e política de rollback. Não existe instalador distribuível.


## 15. Recuperação após queda de energia no marcador e em COMMITTED, 2026-11-16

**Status:** especificação documental. Nenhum mecanismo de recuperação, publicador de marcador, journal writer, instalador ou teste de queda de energia foi implementado.

### 15.1 Regra de sucesso

O marcador de versão, isoladamente, nunca comprova COMMITTED. A instalação só recebe esse estado quando payload, evidência de saúde, marcador e registro final do journal forem verificados. A recuperação ocorre antes de liberar a aplicação candidata ou aceitar nova instalação.

Após reinício, handles, cursores, confirmações, processos e resultados de saúde em memória são descartados. O broker relê o journal, valida a cadeia e readquire os objetos por handles seguros.

### 15.2 Classificação do marcador

| Estado encontrado | Ação |
|---|---|
| Marcador antigo e payload antigo | Não houve commit. Abortar ou reverter somente conforme política aprovada. |
| Marcador antigo e payload novo | Não houve commit. Manter aplicação bloqueada. Republicar exige autorização de recuperação e nova validação. |
| Marcador novo, payload novo, sem COMMITTED válido | Continua não confirmado. Finalização depende de política explícita e evidência revalidada; caso contrário RECOVERY_REQUIRED. |
| Marcador novo, payload novo e registro COMMITTED íntegro | Reconhecer COMMITTED após validar cadeia, marcador, payload e release. Não reescrever o registro terminal. |
| Marcador novo com payload misto ou incompleto | RECOVERY_REQUIRED. Não iniciar aplicação. |
| Marcador ausente, truncado, inválido ou com identidade divergente | RECOVERY_REQUIRED. Preservar evidências. |
| Journal truncado, cadeia quebrada ou registros conflitantes | RECOVERY_REQUIRED. Não inferir sucesso. |
| COMMITTED válido com arquivos ou marcador alterados depois | Manter histórico COMMITTED e abrir reparo separado, autorizado. |

### 15.3 Pontos de queda

A matriz técnica distingue interrupção antes/depois da intenção, durante a substituição do marcador, antes/depois da leitura de retorno, durante a publicação do registro final, durante flush e antes da confirmação ao processo escritor.

Uma chamada interrompida nunca significa ausência de alteração. A recuperação inspeciona o estado real. Não repete a publicação do marcador às cegas e não grava um segundo COMMITTED para ocultar uma publicação incerta.

Registro final incompleto ou truncado não é COMMITTED. Se a semântica de durabilidade não for comprovada, o estado é RECOVERY_REQUIRED.

### 15.4 Gate de inicialização e preservação

O broker classifica transações incompletas antes de liberar a aplicação candidata. Se o broker, journal, raiz ou marcador não forem confiáveis, a aplicação permanece bloqueada e a recuperação exige procedimento confiável separado.

Memórias, SQLite, histórico, preferências, logs, anexos, modelos Ollama, ambientes Python, serviços externos, Terminal original fora da allowlist e backups do usuário ficam fora da recuperação.

### 15.5 Testes e decisões pendentes

Testar queda controlada antes e depois de cada gravação, flush, publicação e leitura de retorno do marcador e journal, incluindo disco cheio, remoção de volume, cache de escrita, corrupção, truncamento, duplicação, cadeia quebrada, marcador antigo/novo/ausente/corrompido e recuperação repetida.

Aprovar formato e metadados do marcador, primitiva de publicação por filesystem, regra de journal truncado, gate de inicialização, política de finalização após marcador novo sem COMMITTED, procedimento operador e matriz de armazenamento suportado.

**Decisão:** contrato de recuperação documentado. Sem implementação ou testes de queda de energia. Permanecem os bloqueios de namespace da seção 4A, journal/broker, rollback e política de saúde. Não existe instalador distribuível.

## 16. Limites de autorização e segurança do broker Windows, 2026-11-16

**Estado:** contrato documental proposto. Nenhum serviço, broker, named pipe, ACL, privilégio, tela de consentimento ou operação privilegiada foi implementado.

| Área | Estado observado | Critério obrigatório antes da implementação |
|---|---|---|
| Cliente gráfico e motor atual | GUI chama diretamente o motor Python e aceita caminhos informados pelo usuário | Permanecer sem elevação. Não expor funções que recebem caminhos por meio de wrapper privilegiado |
| Serviço Windows | Não foi identificado serviço broker no fluxo atual do instalador | Definir identidade dedicada, SID do serviço, privilégios mínimos, instalação e proteção do binário |
| IPC | Seção 11.14 especifica proposta de named pipe; não há servidor broker comprovado no fluxo atual | DACL explícita, rejeição de clientes remotos, autenticação do token/SID/sessão, protocolo limitado e autorização por operação |
| Consentimento | Não há consentimento validado pelo broker | Aprovação explícita vinculada ao digest do pacote, manifesto, destino, conjunto de ações e transação |
| Pacote | Instalador de diretório schema v1 não possui assinatura; atualizador ZIP Ed25519 é trilha separada | Broker valida assinatura, publicador, política, anti-rollback e snapshot de staging sob sua propriedade |
| Destino | GUI aceita caminho de destino selecionado | Destino fixo e provisionado, sem caminho arbitrário em IPC |
| Namespace e handles | Seção 4A continua bloqueando a garantia de resolução segura no Windows | Não aceitar fallback path-based. Demonstrar contrato suportado, ACLs de ancestrais e testes adversariais |
| Journal e recuperação | Contratos documentais nas seções 11.21 a 11.24 | Journal, staging, backup e marcador protegidos; recuperação antes de liberar o aplicativo |
| Dados do usuário | Memórias, SQLite, logs, modelos, configurações e backups estão fora do escopo de payload autorizado | Separação física/lógica e ACLs verificadas. Migração exige aprovação separada |
| Auditoria e chaves | Não há provisionamento de chaves de produção nem trilha de auditoria do broker | Estado de confiança e anti-rollback protegidos; logs sob controle do serviço, sem segredos ou conteúdo de conversa |

### 16.1 Ameaças cobertas pelo contrato

- GUI comprometida, processo malicioso na mesma sessão e outro usuário local.
- Pipe squatting, identidade falsa do servidor, token/sessão inesperados e falha de impersonação.
- Mensagens malformadas, oversized, duplicadas, reordenadas ou reproduzidas.
- Substituição de pacote, downgrade, publicador não confiável e replay de transação.
- Reparse points, hard links, ADS, troca de ancestrais e ataques de namespace.
- Concorrência, negação de serviço, queda do serviço e corrupção de journal, backup, marcador ou logs.

A proposta inicial exclui administrador local, SYSTEM, kernel/boot comprometidos, modificação offline e comprometimento da chave ou pipeline de assinatura. Não declarar proteção contra esses agentes.

### 16.2 Regras de autorização

1. A conexão ao pipe não equivale a autorização para instalar.
2. A identidade do cliente vem do token Windows, nunca de campos JSON ou PID isolado.
3. O serviço não aceita caminho, comando, destino ou operação arbitrária.
4. Aprovação humana é vinculada à versão, digests, destino, ações e transação exatos.
5. Consentimento não supera falha de assinatura, política, ACL, anti-rollback, journal ou estado de recuperação.
6. Requisições repetidas retornam o resultado existente ou rejeição estável, sem repetir mutação.
7. O broker valida e instala o mesmo snapshot de pacote sob sua propriedade.
8. Nenhuma escrita privilegiada ocorre quando a garantia de namespace ou a classificação transacional é ambígua.
9. RECOVERY_REQUIRED bloqueia novas instalações e a inicialização normal do candidato até classificação segura.
10. Dados pessoais, memórias, banco, logs, credenciais, modelos e backups ficam fora do payload e do rollback.

### 16.3 Pendências de aprovação

Identidade e privilégios do serviço; implantação machine-wide ou per-user; destino e DACLs; instalação/atualização/desinstalação do serviço; política de sessão IPC; experiência de consentimento; trust anchor e ciclo de chaves; quotas e concorrência; cancelamento e shutdown; interface de recuperação; suporte a sistemas de arquivos; testes com contas Windows distintas.

**Decisão:** a seção 11.25 do documento técnico especifica o contrato do broker para revisão. Nenhum componente privilegiado foi implementado. O instalador continua não distribuível e a arquitetura não está autorizada para execução.


## 17. Seleção da identidade do serviço Windows, 2026-11-16

**Estado:** revisão documental. Nenhuma conta, serviço, SID, ACL ou privilégio foi configurado.

| Candidato | Avaliação para o broker local |
|---|---|
| Conta virtual exclusiva `NT SERVICE\\SermaxInstallerBroker` | Primeira opção. Identidade gerenciada e exclusiva, sem senha administrada. O SID do serviço permite ACLs próprias. Acesso à rede usa credenciais do computador, portanto a política deve negar saída de rede enquanto não houver requisito aprovado. |
| `NT AUTHORITY\\LocalService` | Alternativa de compatibilidade. Tem poucos privilégios locais e usa credenciais anônimas na rede, mas a conta base é compartilhada. Exigir SID exclusivo do serviço e testes de isolamento. |
| `NT AUTHORITY\\NetworkService` | Sem necessidade identificada. Usa credenciais do computador na rede. Não adotar para um broker local sem requisito de rede aprovado. |
| `NT AUTHORITY\\SYSTEM` | Rejeitado como padrão. Possui acesso local amplo. Exceção exigiria justificativa por API, análise de ameaça e aprovação específica. |
| Conta local/domínio comum | Exige gestão de credenciais e ciclo de vida. Não é a primeira opção para instalação em um único computador. |

### 17.1 Direção técnica

- Avaliar conta virtual dedicada e serviço em processo próprio.
- Testar `SERVICE_SID_TYPE_RESTRICTED` com token real. O Windows aplica verificações com a lista de SIDs restritos; não presumir que uma ACE no SID do serviço, isoladamente, concede o acesso necessário.
- Não habilitar privilégios opcionais sem necessidade comprovada por API.
- Manter instalação, configuração e binários do serviço sob autoridade administrativa separada da GUI.
- Negar acesso do broker a memórias, SQLite, histórico, documentos, credenciais, modelos, ambientes Python e backups, salvo operação específica aprovada.
- Produzir SDDL, token, grupos, privilégios, SID de logon e resultados de acesso efetivo em cada versão Windows suportada.
- Testar operações permitidas e negadas com broker, usuário interativo, segundo usuário padrão, administrador e SYSTEM.
- Testar parada, reinício, falha do serviço e reinício do Windows sem reutilização de autoridade em memória.

**Decisão:** conta virtual dedicada com SID próprio é a candidata principal. SID restrito é alvo de teste, não configuração aprovada. LocalService permanece alternativa condicionada. NetworkService e LocalSystem não se justificam no escopo atual. Nenhuma implementação está autorizada. Os bloqueios da seção 4A e os gates do broker permanecem abertos.


## 18. Decisão sobre a corrida de namespace no Windows, 2026-11-16

**Estado:** decisão de arquitetura proposta para revisão. Nenhum código, ACL, serviço, broker ou instalador foi implementado.

### 18.1 Evidência documentada

- `FILE_FLAG_OPEN_REPARSE_POINT` faz o `CreateFileW` tentar abrir o próprio objeto reparse point no componente final. A documentação não estabelece esse sinalizador como garantia de que todos os componentes intermediários de um caminho arbitrário sejam resolvidos sem seguir reparse points.
- `FILE_FLAG_BACKUP_SEMANTICS` permite abrir um diretório por handle. Não concede privilégio de backup por si só.
- `SetFileInformationByHandle` opera sobre um handle já aberto. `FILE_RENAME_INFO.RootDirectory` aceita nome de destino relativo a um handle de diretório. Isso não prova que a árvore usada para obter os handles estava protegida contra substituição concorrente.
- Share modes permanecem ativos enquanto o handle estiver aberto. Omitir `FILE_SHARE_DELETE` restringe aberturas posteriores que solicitem acesso de exclusão, quando compatível com os handles existentes. Não substitui ACLs e propriedade protegidas.

### 18.2 Direção escolhida para avaliação

A defesa principal contra processos de usuário padrão será impedir que eles alterem o namespace de instalação. O setup confiável provisiona uma raiz fixa e protege todos os ancestrais, desde a raiz do volume até a pasta de instalação.

O broker deve verificar proprietário, DACL, ACEs herdadas e acesso efetivo de cada ancestral e objeto protegido. O usuário interativo e outros usuários padrão não recebem direitos para criar, substituir, renomear, excluir, inserir reparse points, alterar DACL ou assumir propriedade da árvore protegida.

O broker copia o pacote para staging sob sua propriedade, valida os mesmos bytes que instalará e deriva destinos de uma raiz fixa com allowlist estrita. O cliente não escolhe destino, caminho ou comando. Qualquer incerteza sobre raiz, volume, ACL, owner ou identidade do objeto bloqueia a transação.

### 18.3 Testes obrigatórios

- Tentar criação, renomeação, exclusão, reparse point, WRITE_DAC e WRITE_OWNER em cada ancestral, como usuário interativo e segundo usuário padrão.
- Verificar direitos FILE_DELETE_CHILD, FILE_ADD_FILE e FILE_ADD_SUBDIRECTORY.
- Testar troca da origem do pacote durante intake e comprovar que a instalação usa o snapshot sob propriedade do broker.
- Testar staging, backup, journal, marcador e binário do serviço contra substituição.
- Registrar token real, SID, SDDL, owner, acesso efetivo, Windows build, filesystem e resultado.
- Repetir em todas as versões Windows suportadas e testar recuperação após falhas separadamente.

### 18.4 Limites e bloqueios

A proposta exclui administrador local, SYSTEM, kernel comprometido e modificação offline. A proteção não está comprovada até que os testes de ACL e identidade passem em cada configuração suportada.

Permanecem pendentes: destino definitivo, evidência de ACL de todos os ancestrais, token do serviço, assinatura e confiança do pacote, staging, journal, rollback, recuperação e health gate. A seção 4A continua registrada como bloqueio para qualquer componente que dependa da combinação nativa não esclarecida.

**Decisão:** broker com namespace protegido é a direção principal para avaliação. Não há autorização de implementação nem instalador distribuível.

**Referências Microsoft:**
- https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew
- https://learn.microsoft.com/en-us/windows/win32/fileio/reparse-points
- https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileinformationbyhandle
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-file_rename_info
- https://learn.microsoft.com/en-us/windows/win32/fileio/file-security-and-access-rights


## 19. Auditoria estática do instalador e do gerador de pacotes, 2026-11-16

**Estado:** leitura de código. Nenhum código foi alterado ou executado.

### 19.1 Motor do instalador

O arquivo `sermax_installer_core.py` verifica componentes com `Path.lstat()`, `Path.is_symlink()` e atributos Windows. A contenção é verificada com `os.path.abspath()`. Depois, operações críticas continuam por caminhos: leitura de manifesto e marcador, `shutil.copy2`, `tempfile.mkstemp`, hash por abertura de caminho e `os.replace`.

Essas verificações reduzem risco para caminhos estáticos. Não vinculam o objeto inspecionado ao objeto aberto ou substituído depois. Um processo com permissão de escrita na árvore de destino ainda tem janela para tentar troca concorrente. O lock coordena instaladores cooperantes, não um atacante externo.

### 19.2 Gerador de pacotes

O arquivo `sermax_package_builder.py` verifica caminhos, calcula hash/tamanho da origem, copia com `shutil.copy2`, verifica o staging e relê a origem para comparar hash/tamanho. Publica com `os.replace` e remove falhas com `shutil.rmtree`.

As comparações detectam alterações comuns e comprovam que o staging corresponde ao digest capturado. Não provam que todas as leituras vieram do mesmo objeto, não impedem redirecionamento concorrente da origem e não vinculam a limpeza ao mesmo objeto de diretório temporário se o namespace pai for gravável por atacante.

### 19.3 GUI e limite de confiança

A GUI permite escolher pacote e destino e chama diretamente o motor Python. Não foi identificado broker Windows, serviço, IPC autenticado ou raiz fixa protegida nesse fluxo.

**Disposição:** manter como preview de desenvolvimento, sem distribuição para instalação de produção. O gerador de pacotes é uma fronteira separada e precisa de testes próprios.

### 19.4 Gates separados

1. Provisionamento de raiz protegida e ACLs de todos os ancestrais.
2. Identidade/token do serviço e autorização IPC.
3. Intake, staging sob propriedade do broker e autenticidade do pacote.
4. Journal, backup, rollback e recuperação após crash.
5. Proteção do namespace de origem e saída do gerador de pacotes.
6. Testes adversariais em Windows e sistemas de arquivos suportados.

Nenhum código, serviço, ACL, privilégio, pacote ou teste foi implementado ou executado nesta auditoria.


## 20. Matriz de provisionamento e aceitação de ACLs, 2026-11-16

Foi adicionada a especificação documental `SERMAX-Platform/installer/ACL-PROVISIONING-ACCEPTANCE-MATRIX.md`.

O documento organiza:
- Caminhos propostos para aplicação, binário do broker, staging, journal, backups, configuração do serviço e pipe local.
- Proprietário esperado e separação de direitos entre Administradores, SYSTEM, SID do serviço e usuários padrão.
- Direitos NTFS que precisam ser avaliados individualmente, incluindo `FILE_DELETE_CHILD`, `FILE_ADD_FILE`, `WRITE_DAC` e `WRITE_OWNER`.
- Provisionamento administrativo, autenticação IPC e testes negativos com dois usuários padrão.
- Critérios de bloqueio e evidências necessárias para aprovação.

**Status:** especificação, sem SDDL final e sem implementação. Os caminhos são propostas para avaliação, não destinos aprovados. Não houve alteração de ACL, serviço, broker, pipe, privilégio ou instalação. A matriz não autoriza modificar `C:\SERMAX` ou dados existentes.
