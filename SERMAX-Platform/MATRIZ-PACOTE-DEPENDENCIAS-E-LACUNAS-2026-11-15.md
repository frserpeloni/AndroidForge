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
