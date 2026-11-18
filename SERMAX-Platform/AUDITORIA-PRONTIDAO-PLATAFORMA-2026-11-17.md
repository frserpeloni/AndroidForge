# Auditoria de prontidao da Plataforma SERMAX
Data: 2026-11-17
Branch de trabalho: `sermax-platform-readiness-20261117-r4`
Base: `sermax-cleanup-20261117`
Estado: auditoria inicial; desenvolvimento funcional autorizado por Fabiano em 2026-11-17.

## 1. Preservacao e estrategia de branches

- A branch de trabalho foi criada a partir de `sermax-cleanup-20261117`.
- A branch `sermax-cleanup-20261117` esta 18 commits a frente de `sermax-windows-integration-20261029`, sem commits atras.
- A branch antiga `sermax-platform-prototype-20261115` diverge da branch de limpeza: 261 commits a frente e 46 atras em relacao a `sermax-cleanup-20261117`.
- Nao foi feito merge, rebase ou force push.
- PR #5 e PR #6 permanecem sem merge.
- `main`, `C:\SERMAX`, memoria pessoal, historico local e backups nao foram alterados.

A continuidade sera feita na nova branch para evitar incorporar os 46 commits ausentes por um merge amplo e sem revisao. A branch antiga sera mantida como referencia historica ate a revisao das diferencas.

## 2. Evidencia da validacao automatizada existente

No commit de codigo `cadcd1fc3fc6e7c7798f2f851759a2dc576e2e7f`:

- Windows CI, run `44108333243`: sucesso. O job `validate-and-build` concluiu compilacao, testes configurados, build do executavel e smoke test do Terminal original.
- Platform CI, run `44108334492`: sucesso. Foram concluidos os jobs `windows-validation`, `frontend-interaction`, `frontend-check`, `backend-tests (3.12)` e `backend-tests (3.14)`.
- O Platform CI cobre API com FakeCore, testes de interface com DOM simulado, launcher e testes do prototipo do instalador.
- O CI nao comprova conversa com Ollama real, worker OpenJarvis real, navegador real, instalacao no computador do usuario ou atualizacao segura.

## 3. Estado confirmado por componente

| Componente | Estado observado | Lacuna |
|---|---|---|
| Interface de conversa | Implementada | Sem streaming; erros exibidos como mensagem simples |
| Historico SQLite | Implementado | Sem exportacao, busca ou gestao avancada |
| Projetos | CRUD basico, arquivamento e associacao implementados | Sem permissao por projeto; memoria geral continua compartilhada |
| Contexto de conversa | Sessao temporaria reconstruida e sessao global restaurada | Validacao ainda usa FakeCore |
| API FastAPI | Implementada, loopback, verificacao de Host, Origin e IP | Sem autenticacao local por token; nao expor em rede |
| Tela Tarefas | Gerenciador persistente implementado na branch de prontidao | Sem execucao automatica ou em segundo plano |
| Tela Memória | Painel somente leitura implementado na branch de prontidão | Aguarda validação CI e homologação local do caminho real de memória |
| Diagnóstico de motores | Endpoint e painel local implementados na branch de prontidão | Aguarda CI e conversa real de homologação |
| Seletor de modelo | Opcoes visiveis na interface | Alteracao nao altera o roteamento; mostra somente aviso |
| Anexos | Botao informativo | Nenhum upload ou leitura implementado |
| Launcher | Script Python de desenvolvimento | Nao integrado ao SERMAX.exe |
| Instalador/atualizador | Prototipo e documentacao | Bloqueado por riscos de seguranca, assinatura, transacao e rollback |
| Integracao com nucleo real | Adaptador tardio implementado | Nao homologado com o ambiente real e motores locais |

## 4. Achados tecnicos da leitura do codigo

### 4.1 Integracao do nucleo
O backend importa `sermax_core.py` sob demanda. Durante a chamada, substitui `core.sessao` pelo contexto reconstruido da conversa e restaura a sessao anterior no bloco `finally`. O bloqueio global serializa as chamadas.

A API de conversa ainda e testada principalmente com FakeCore. O smoke test separado comprova a importacao do nucleo real sem executar modelo e sem tocar na memoria pessoal. Ainda nao existe evidencia de uma conversa real da Plataforma respondida por OpenJarvis ou Ollama.

A memoria persistente geral do SERMAX continua compartilhada e segue as regras do nucleo. Esse comportamento esta documentado e nao sera alterado sem decisao expressa.

### 4.2 Interface
O seletor apresenta “Automatico”, “Ollama local” e “OpenJarvis”, mas o evento de mudanca informa que o roteamento permanece automatico. Nenhum valor e enviado a API. A interface sugere uma selecao manual que ainda nao existe.

A tela Tarefas possui cadastro e acompanhamento persistente. A tela Memória consulta somente a lista já carregada no núcleo, sem importar o núcleo, abrir arquivos ou gravar dados ao entrar no painel.

### 4.3 Inicializacao e dependencias
`backend/run_local.bat` executa `pip install -r requirements.txt` em toda inicializacao. As dependencias estao declaradas por faixas de versao, sem lockfile. Isso permite alteracao de versoes resolvidas entre inicializacoes e exige acesso ao indice de pacotes.

O launcher Python da Plataforma nao esta integrado ao executavel principal.

### 4.4 Instalacao e atualizacao
Os documentos de auditoria existentes registram risco TOCTOU, ausencia de assinatura/autenticidade comprovada, ausencia de transacao global e rollback garantido, alem de lacunas de preservacao e recuperacao. Nenhum instalador sera liberado nesta etapa.

## 5. Plano de execucao

### Fase A, homologacao da integracao
1. Criar teste de importacao controlada do nucleo real, sem chamada a modelo e sem gravacao de memoria.
2. Verificar dependencias reais do nucleo em Windows.
3. Criar teste de contrato do adaptador para confirmar restauracao de sessao em sucesso e excecao.
4. Executar CI em Windows e registrar exatamente quais verificacoes foram aprovadas.
5. Preparar procedimento de teste local que nao toque na instalacao `C:\SERMAX`.

### Fase B, funcionalidades de trabalho
1. Implementar tarefas persistentes com estados, datas, prioridade e historico.
2. Ligar a tela Tarefas a API e SQLite.
3. Implementar consulta de memória com leitura controlada, sem editar ou apagar arquivos de memória. Implementação concluída na branch de prontidão, aguardando CI.
4. Tornar o estado do nucleo e dos motores explicito na interface.

### Fase C, conversa
1. Implementar streaming com cancelamento seguro e persistencia de estado.
2. Projetar anexos com allowlist de formatos, limite de tamanho, armazenamento isolado e validacao de conteudo.
3. Testar retomada de conversa e falha durante streaming.

### Fase D, modelos e ferramentas
1. Definir contrato real de selecao manual e automatica.
2. Implementar override sem quebrar a selecao automatica atual.
3. Exibir disponibilidade verificada, nunca presumida, dos motores.

### Fase E, distribuicao
1. Fixar dependencias e gerar inventario/SBOM.
2. Fechar avisos e obrigacoes das licencas de terceiros.
3. Concluir instalador/atualizador com protecao baseada em handles, plano imutavel, assinatura, journal e rollback validado.
4. Integrar launcher sem substituir o Terminal original.

### Fase F, homologacao Windows
Executar instalacao limpa e atualizacao em ambiente Windows descartavel, testes de interrupcao, recuperacao, preservacao de dados, inicializacao, encerramento e reinicio. Somente depois avaliar pacote candidato.

## 6. Criterios de conclusao

A Plataforma so sera declarada pronta para uso quando:
- a integracao com o nucleo real for validada;
- as telas anunciadas tiverem funcionalidades reais ou forem explicitamente removidas/identificadas como indisponiveis;
- os fluxos de conversa, historico, projetos e tarefas passarem por testes;
- o comportamento de memoria estiver documentado e comprovado;
- o launcher iniciar e encerrar corretamente;
- instalador e atualizador passarem por testes de seguranca e recuperacao no Windows;
- nenhuma alteracao comprometer o Terminal original, memoria pessoal, historico ou backups.


## 7. Atualização de execução, 2026-11-17

Após a auditoria inicial, a branch recebeu a primeira entrega funcional da Fase B:

- Criada tabela SQLite `tasks`, com migração aditiva e estados `pending`, `in_progress`, `completed` e `cancelled`.
- API para criar, listar, consultar e editar tarefas, atualizar estado, filtrar por estado e ordenar por prioridade/prazo.
- Validação de título, descrição, prioridade e data ISO 8601.
- Tela Tarefas conectada à API, com formulário, prioridade, prazo, filtro e atualização de estado.
- Não há exclusão física, execução de comandos ou execução em segundo plano.
- Testes adicionados para criação, ordenação, edição, conclusão, filtros, data inválida, campos nulos e persistência após reabertura do SQLite.
- Teste de interface adicionado para criação e atualização do estado.

A execução CI `44131386495` concluiu com sucesso. Foram aprovados os jobs `backend-tests (3.12)`, `backend-tests (3.14)`, `frontend-check`, `frontend-interaction` e `windows-validation`. Nos ambientes Python 3.12, Python 3.14 e Windows passaram os testes da API de tarefas, importação do núcleo real sem executar modelo, restauração da sessão original inclusive quando nula, testes da API, instalador, gerador de pacotes e launcher. Os testes de interação da interface passaram em Linux e Windows.\n\nA execução `44131614436`, disparada após atualização documental, está em andamento para validar o HEAD documental mais recente. A execução `44131386495` valida o código funcional da entrega de tarefas. Nenhuma dessas execuções comprova conversa com Ollama/OpenJarvis real, navegador real, instalação no computador do usuário ou atualização segura.


## 8. Atualização de execução, painel Memória, 2026-11-17

A segunda entrega funcional da Fase B foi implementada na branch de prontidão:

- Endpoint `GET /api/memory` consulta somente a lista `historico` já carregada em `CORE_MODULE`.
- O endpoint não chama `load_core()`, não abre `memoria_sermax.json`, não chama `salvar_memoria()` e não altera a lista.
- Se o núcleo ainda não estiver carregado na sessão da API, a rota retorna `core_not_loaded` e não tenta carregar arquivo algum.
- A consulta aceita filtro textual e limite entre 1 e 100 registros. Retorna somente itens de usuário.
- A interface exibe aviso de somente leitura, busca, quantidade e registros. O conteúdo é inserido por `textContent`, sem interpretação como HTML.
- Não existem controles de inclusão, edição ou exclusão.
- Foram adicionados testes da API para estado sem núcleo carregado, leitura de registros, filtro, limite e validação.
- Foi adicionado teste de interface para estado inicial, consulta, busca e indicação de somente leitura.
- O CI foi atualizado para executar os novos testes em Python 3.12, Python 3.14 e Windows.

A execução CI `44137981040` aprovou os testes de memória em Python 3.12, Python 3.14 e Windows. O painel só exibe dados depois que uma conversa carregar o núcleo na sessão da API. A configuração do caminho de memória no ambiente de instalação continua precisando de homologação local, sem acesso ou alteração em `C:\SERMAX` durante esta etapa.


## 9. Atualização de execução, diagnóstico dos motores, 2026-11-17

Foi implementado um painel de diagnóstico local para preparar a homologação dos motores:

- A rota `GET /api/engines/status` consulta `http://127.0.0.1:11434/api/tags`, com timeout de 1,5 segundo.
- Verifica a presença do executável Python configurado e do worker OpenJarvis esperado, sem iniciar subprocessos.
- Informa se o núcleo está carregado e qual foi o último backend registrado, sem expor o conteúdo da sessão.
- Não envia prompts, não inicia inferência e não altera configurações.
- A interface mostra o estado do núcleo, Ollama, OpenJarvis e último roteamento.
- Testes automatizados foram adicionados para resposta positiva/negativa do endpoint Ollama, restrição ao loopback, ausência de inferência e proteção do conteúdo da sessão.
- Teste de interface adicionado para exibição do diagnóstico.
- CI atualizado para Python 3.12, Python 3.14 e Windows.

Limites: encontrar os arquivos do OpenJarvis não comprova execução do worker. Responder a `/api/tags` não comprova geração de texto. A homologação operacional exige conversa autorizada e registro de resposta real. A execução CI `44137981040` aprovou os testes do diagnóstico nos ambientes Python 3.12, Python 3.14 e Windows.


## 10. Evidência CI consolidada, 2026-11-17

A execução GitHub Actions `44137981040`, no commit `1b50fedc3df84112068afc29f8479c1d197cb3bf`, concluiu com sucesso nos cinco jobs:

- `backend-tests (3.12)`: sucesso.
- `backend-tests (3.14)`: sucesso.
- `windows-validation`: sucesso.
- `frontend-check`: sucesso.
- `frontend-interaction`: sucesso.

Os testes incluíram API, tarefas, memória somente leitura, diagnóstico local dos motores, importação do núcleo real sem executar modelo, contrato de restauração de sessão, instalador, gerador de pacotes, launcher e interação da interface em Windows e Linux.

Após o commit validado, foi feita uma alteração visual pequena no commit `f4a6d3e26b1d45e4c9e91bf42d7e6789f5777759`, para mostrar o índice original de cada memória na lista filtrada. Essa alteração ainda aguarda uma execução CI própria.

A execução não comprova conversa real com Ollama/OpenJarvis, teste em navegador real ou homologação no computador do usuário. Nenhum arquivo de `C:\SERMAX` foi acessado ou alterado.

Nenhum teste físico no computador do usuário foi realizado nesta auditoria. Nenhum arquivo de `C:\SERMAX` foi acessado ou alterado.


## 11. Streaming de conversa, 2026-11-17

Foi adicionada a rota `POST /api/chat/stream`, baseada em Server-Sent Events. A rota reutiliza o ciclo existente de conversa, o isolamento temporário da sessão, o bloqueio global `CHAT_LOCK` e a persistência SQLite. A rota síncrona `POST /api/chat` permanece disponível para compatibilidade.

A fila de eventos é limitada a 16 snapshots. Quando há acúmulo, eventos intermediários antigos são substituídos por snapshots mais recentes, que contêm o texto acumulado. Isso limita o consumo de memória sem perder o estado final da resposta. Uma reserva impede duas solicitações de streaming simultâneas. Se o navegador desconectar, o processamento continua no servidor e a reserva é liberada ao término. Não há cancelamento de inferência.

O núcleo atual chama o callback com snapshots acumulados durante a geração do Ollama. O adaptador OpenJarvis chama o callback uma única vez, ao entregar a resposta completa. Portanto, o streaming gradual está disponível para a rota Ollama; OpenJarvis ainda responde em bloco.

Foram adicionados testes de API para snapshots, persistência da resposta final, restauração da sessão, falha do núcleo e mensagem vazia. A interface consome os eventos SSE e atualiza o texto progressivamente. A validação CI inicial encontrou falhas nos testes porque o primeiro commit emitia separadores SSE escapados incorretamente. A codificação foi corrigida nos commits seguintes. A execução CI `44191365375` aprovou a revisão corrigida nos cinco jobs, conforme seção 12.

Nenhuma inferência real foi iniciada. Nenhum arquivo de `C:\SERMAX`, memória pessoal ou backup foi acessado ou alterado.


## 12. Evidência CI do streaming, 2026-11-17

A execução GitHub Actions `44191365375`, no commit `0804396d2a28c2b4709c149fd388cf8efb3ceb5b`, concluiu com sucesso nos cinco jobs:

- `backend-tests (3.12)`: sucesso, incluindo os testes de streaming.
- `backend-tests (3.14)`: sucesso, incluindo os testes de streaming.
- `windows-validation`: sucesso, incluindo API, streaming, interface, instalador, pacote e launcher.
- `frontend-check`: sucesso.
- `frontend-interaction`: sucesso.

A primeira execução da revisão, `44191163899`, falhou nos novos testes porque a serialização inicial usava separadores SSE escapados em excesso. A correção foi aplicada, a revisão foi aberta em PR #12 e a execução `44191365375` validou o commit corrigido. PR #11 foi fechado como supersedido, sem merge e sem apagar código.

A validação é automatizada em CI. Não comprova inferência real com Ollama/OpenJarvis no computador do usuário, teste visual em navegador real ou homologação em `C:\SERMAX`. Nenhuma inferência real foi iniciada nesta etapa.


## 13. Compatibilidade de streaming OpenJarvis, 2026-11-17

Foi feita revisão da API pública do SDK OpenJarvis para determinar como habilitar streaming sem alterar a semântica dos agentes SERMAX. A documentação oficial descreve `Jarvis.ask_stream(query, model, temperature, max_tokens, context)` como gerador assíncrono de tokens. Essa assinatura não recebe `agent` nem `tools`. A integração SERMAX atual chama `sdk.ask(..., agent=..., tools=...)`, inclusive com o agente `orchestrator` e ferramentas restritas a `calculator` e `think`.

Decisão técnica: não substituir a chamada atual por `ask_stream`, pois isso removeria o fluxo de agente e suas ferramentas. O streaming OpenJarvis exige uma solução compatível com o modo de agente, ou alteração explícita e testada da arquitetura de roteamento. Até essa solução existir, OpenJarvis mantém resposta em bloco e o fallback Ollama segue transmitindo snapshots.

Referências consultadas:
- https://open-jarvis.github.io/OpenJarvis/api-reference/openjarvis/sdk/
- https://github.com/open-jarvis/OpenJarvis/blob/main/docs/user-guide/python-sdk.md

A documentação pública consultada não comprova qual versão do pacote está instalada no ambiente local do usuário. Nenhuma inferência ou instalação foi executada.


## 14. Teste de integração do callback do núcleo, 2026-11-17

Foi adicionado `backend/test_core_stream_integration.py`. O teste importa o `sermax_core.py` real em diretório temporário, bloqueia a gravação da memória pessoal, simula falha do OpenJarvis e injeta eventos NDJSON de Ollama. Verifica que o núcleo emite snapshots acumulados (`"Olá "`, depois `"Olá MAX"`), retorna a resposta final, registra o fallback para Ollama e não cria `memoria_sermax.json` no diretório isolado.

O teste não inicia inferência real nem depende de Ollama ou OpenJarvis instalados. Foi incluído nos jobs Python 3.12, Python 3.14 e Windows. A nova execução CI `44193324857` aprovou o teste adicional em Python 3.12, Python 3.14 e Windows.


## 15. CI após integração do teste do núcleo, 2026-11-17

A execução GitHub Actions `44193324857`, associada ao commit `32064162c96d29dc1a74609161632bcde0946708`, concluiu com sucesso nos cinco jobs:

- `backend-tests (3.12)`: sucesso, incluindo o teste do núcleo real com Ollama simulado.
- `backend-tests (3.14)`: sucesso, incluindo o teste do núcleo real com Ollama simulado.
- `windows-validation`: sucesso, incluindo o teste do núcleo real com Ollama simulado.
- `frontend-check`: sucesso.
- `frontend-interaction`: sucesso.

O teste adicional também foi executado em Windows e confirmou o callback progressivo do núcleo sem iniciar inferência real ou gravar a memória pessoal. O commit posterior `ea5936c7b1052abde278273cc52d431ef3b154ea` ajustou somente os gatilhos de CI para permitir execução também em pushes na branch de streaming.


## 16. Primeira implementação de anexos locais, 2026-11-17

A branch `sermax-platform-attachments-20261117` foi aberta sobre o head da PR #12 para manter o trabalho de anexos isolado e empilhado sobre o streaming. A PR #13 está em rascunho, sem merge.

Implementado:
- Serviço `backend/attachment_service.py`, router separado do fluxo principal de chat.
- Migração SQLite para metadados e associação obrigatória a uma conversa.
- Upload multipart, listagem, download como attachment, consulta de texto extraído e exclusão explícita.
- Diretório privado `DATA_DIR/attachments`, nomes físicos UUID, arquivo temporário, flush/fsync e substituição atômica.
- Allowlist PDF, DOCX, TXT UTF-8, JPEG e PNG, com validação de assinatura e parser.
- Limites de 10 MiB por arquivo, 5 anexos e 25 MiB por conversa; PDF até 100 páginas, extração até 100.000 caracteres e imagens até 20 milhões de pixels.
- Interface para seleção, fila, envio, listagem, download e exclusão.
- Testes de upload TXT, PNG, extensão divergente, tipo bloqueado, arquivo vazio/grande, conversa inexistente, isolamento entre conversas, exclusão e limite de quantidade.
- CI atualizado para executar testes de anexos em Python 3.12, Python 3.14 e Windows.

Limitações deliberadas:
- O conteúdo dos anexos ainda não é passado ao núcleo SERMAX.
- OCR de imagens não implementado.
- Não houve inferência real, instalação local ou teste em `C:\SERMAX`.
- Não houve alteração em memória pessoal, núcleo original, Terminal ou backups.

A primeira execução CI `44197305925` encontrou falha nos testes porque o setup isolado não criava a tabela `attachments`. A falha foi reproduzida pelo log e corrigida no teste para inicializar explicitamente o schema. A execução de correção `44197404930` está em andamento; a etapa de testes de anexos já passou nos jobs Linux Python 3.12 e 3.14, conforme os jobs avançaram para as verificações finais. A validação Windows ainda precisa concluir antes de registrar aprovação geral.


## 17. Resultado da primeira validação dos anexos, 2026-11-17

A execução CI `44197404930` concluiu com sucesso nos cinco jobs:
- `backend-tests (3.12)`: sucesso, incluindo `test_attachments_api.py`.
- `backend-tests (3.14)`: sucesso, incluindo `test_attachments_api.py`.
- `windows-validation`: sucesso, incluindo testes da API de anexos em Windows e interação da interface.
- `frontend-check`: sucesso.
- `frontend-interaction`: sucesso.

A primeira execução `44197305925` falhou porque os testes não inicializavam o schema de anexos no banco isolado. O teste foi corrigido para criar o schema explicitamente. A execução `44197404930` passou depois dessa correção.

Após essa execução, foi corrigida a renderização da interface para preservar a lista de anexos já salvos ao atualizar a fila de arquivos pendentes. Esse ajuste entrou no commit `6fd8b4a9162f658158d1b5eb5d1af72a19434063`, posterior à execução acima. Portanto, a execução `44197404930` não valida esse último ajuste de interface. Uma nova execução CI é necessária antes de declarar a revisão final aprovada.


## 18. Revisão posterior ao primeiro CI de anexos, 2026-11-17

Após a execução `44197404930`, a revisão técnica adicionou:
- Preservação da lista de anexos persistidos ao renderizar a fila pendente na interface.
- Limpeza do arquivo físico também quando a confirmação da transação SQLite falha.
- Exclusão com tombstone, restaurando o arquivo se a transação do banco falhar e deixando eventual tombstone residual inerte se a remoção física final falhar.
- Parsing multipart manual com `max_files=1` e `max_fields=0`, aceitando o tipo `UploadFile` do Starlette.
- Testes adicionais para DOCX válido, PDF válido, DOCX corrompido e PDF criptografado.

Esses ajustes estão no head atual da PR #13, commit `9ac29e4d13550888f0a69e3c31b635bf0bde76d5`. A execução `44197404930` não cobre esses commits posteriores. A PR #13 segue aberta, em rascunho e sem merge. A comparação da branch confirmou que a PR está empilhada sobre o head da PR #12 e o GitHub informa `mergeable=true`. A validação CI do head atual permanece pendente de confirmação por evidência de execução.


## 19. Validação final da implementação de anexos, 2026-11-17

A execução GitHub Actions `44198316805`, no commit de código/testes `074d9f85b45748ee7114fe6221ed1083d5b2a63f`, concluiu com sucesso nos cinco jobs:
- `backend-tests (3.12)`: sucesso, incluindo os 10 testes de anexos.
- `backend-tests (3.14)`: sucesso, incluindo os 10 testes de anexos.
- `windows-validation`: sucesso, incluindo os testes de anexos em Windows, integração simulada do núcleo e testes de interface.
- `frontend-check`: sucesso.
- `frontend-interaction`: sucesso.

A execução anterior `44198199167` falhou em Python 3.12 e 3.14 porque o fixture de DOCX corrompido não representava a assinatura ZIP binária esperada. O fixture foi corrigido para iniciar com os bytes reais `50 4B 03 04`. A execução posterior `44198316805` passou integralmente.

A branch de anexos foi realinhada sobre a base atual da PR #12. A branch anterior foi preservada em `sermax-platform-attachments-20261117-pre-rebase`. O head de código/testes validado é `074d9f85b45748ee7114fe6221ed1083d5b2a63f`. A atualização deste relatório é documental e não altera o código validado.

PR #13 permanece aberta, em rascunho e sem merge. A implementação continua sem integração automática dos anexos ao prompt do núcleo e sem OCR. Nenhuma instalação local, inferência real, alteração em `C:\SERMAX`, memória pessoal ou backup foi realizada.


## 20. Contexto temporário dos anexos, 2026-11-17

A PR #14 adiciona integração controlada dos anexos textuais com o contexto temporário do MAX:
- Consulta somente anexos vinculados à conversa atual, até cinco registros.
- Seleciona trechos com base na sobreposição lexical entre a pergunta e os parágrafos extraídos.
- Limite agregado de 2.600 caracteres, com limite de 650 caracteres por arquivo.
- Insere o material em uma mensagem de sistema temporária, identificada como dado não confiável. O texto instrui o modelo a ignorar comandos embutidos nos arquivos, citar o nome do arquivo e informar quando os trechos forem insuficientes.
- Anexos de imagem entram somente como metadados e informam que OCR/análise visual não estão disponíveis.
- O contexto não é gravado nas mensagens SQLite. O núcleo recebe a pergunta original e o conteúdo de anexo fica somente na sessão temporária reconstruída pela Plataforma.
- A sessão global original do núcleo é restaurada ao final da chamada.
- O arquivo `SERMAX-Windows/sermax_core.py` não foi alterado.

Testes adicionados em `backend/test_chat_stream.py` verificam isolamento entre conversas, presença do aviso de conteúdo não confiável, ausência de persistência do conteúdo extraído e limites do contexto. O teste de integração do núcleo foi ampliado para verificar que `registrar_memoria` recebe somente a mensagem original do usuário, mesmo com conteúdo de anexo presente na sessão.

A execução CI `44198960420` passou nos cinco jobs antes da inclusão da asserção adicional sobre a chamada de memória. O commit `beb17c4b521a7bf21ba5250260c9c6b2c505532e` e os ajustes documentais/workflow posteriores aguardam uma nova execução CI. Nenhuma inferência real ou gravação de memória pessoal foi executada.


## 21. Validação do contexto temporário de anexos, 2026-11-17

A execução GitHub Actions `44199209648`, no commit de código/testes `beb17c4b521a7bf21ba5250260c9c6b2c505532e`, concluiu com sucesso nos cinco jobs:
- `backend-tests (3.12)`: sucesso.
- `backend-tests (3.14)`: sucesso.
- `windows-validation`: sucesso, incluindo teste de streaming com anexos e integração do núcleo.
- `frontend-check`: sucesso.
- `frontend-interaction`: sucesso.

Os testes de contexto verificam que somente anexos da conversa atual entram no contexto, que o material é marcado como dado não confiável, que o texto extraído não é persistido nas mensagens e que imagens informam a ausência de OCR/análise visual. O teste de integração do núcleo verifica que `registrar_memoria` recebe somente a pergunta original do usuário, mesmo quando a sessão temporária contém texto de anexo.

A execução não inicia inferência real. O conteúdo de anexo permanece em contexto temporário, limitado a 2.600 caracteres agregados e 650 por arquivo. O núcleo original não foi alterado. PR #14 permanece aberta, em rascunho e sem merge.


## 22. Separação de autoridade do conteúdo dos anexos, 2026-11-17

A revisão de segurança separou a instrução de proteção do conteúdo documental em mensagens distintas do contexto:
- Mensagem `system`: contém as regras para tratar anexos como dados não confiáveis, ignorar comandos embutidos e citar o nome do arquivo.
- Mensagem `user`: contém o JSON com os trechos extraídos e metadados dos anexos.

O texto enviado pelo usuário dentro de arquivos deixa de ocupar o papel `system`. O teste de API verifica a separação dos papéis e a ausência de anexos de outra conversa. A nova execução CI do head atualizado ainda precisa confirmar os ajustes.


## 23. CI da separação de autoridade dos anexos, 2026-11-17

A execução GitHub Actions `44199605658`, no commit de código/testes `546844df5e4741e989f7775ed79465d5e8badd9d`, concluiu com sucesso nos cinco jobs:
- `backend-tests (3.12)`: sucesso.
- `backend-tests (3.14)`: sucesso.
- `windows-validation`: sucesso.
- `frontend-check`: sucesso.
- `frontend-interaction`: sucesso.

A revisão confirmou que as instruções de segurança permanecem em uma mensagem `system` separada e o JSON com o conteúdo dos anexos entra como mensagem `user`. Os testes verificam essa separação, o isolamento entre conversas e a não persistência do conteúdo documental na tabela de mensagens. O teste de integração do núcleo também verifica que a rotina de memória recebe somente a pergunta original.

A atualização posterior deste relatório é documental. Nenhuma inferência real, instalação local ou gravação de memória pessoal foi executada. PR #14 permanece aberta, em rascunho e sem merge.


## 24. OCR local para imagens e PDFs digitalizados, 2026-11-17

Foi iniciada a etapa de OCR local na branch sermax-platform-ocr-20261117, empilhada sobre a branch da PR #14. A implementação mantém os anexos locais e não chama serviços externos.

### Arquitetura

- backend/ocr_service.py isola a integração com Tesseract e PDFium.
- pytesseract chama o executável Tesseract instalado localmente.
- pypdfium2 renderiza páginas PDF sem texto nativo.
- O idioma configurado é por+eng.
- A variável opcional SERMAX_TESSERACT_CMD aponta para o executável local. Sem ela, a aplicação procura tesseract no PATH.
- OCR de imagem ocorre após a validação de assinatura, formato e dimensão.
- Em PDF, a extração nativa continua primeiro. Somente páginas sem texto nativo seguem para renderização e OCR.
- O resultado de OCR é marcado como origem ocr ou mixed e recebe aviso de possível erro.
- O conteúdo permanece não confiável no contexto temporário do MAX.

### Limites de execução

- Timeout de 8 segundos por imagem ou página.
- Até cinco páginas digitalizadas por PDF.
- Renderização PDF em 150 DPI, limitada a 3.000 pixels no maior lado.
- Imagens preparadas para OCR limitadas a 9 milhões de pixels.
- O limite original de validação de imagem, 20 milhões de pixels, permanece.
- Ausência do Tesseract, do pacote Python, dos dados de idioma ou do renderizador não bloqueia o upload.
- O estado é persistido em extraction_method e extraction_status, com migração aditiva da tabela attachments.
- A interface apresenta o estado de extração.

### Segurança e preservação

- OCR executado localmente, sem transmissão a serviços externos.
- O texto reconhecido permanece sujeito ao limite de contexto de 2.600 caracteres agregados e 650 por arquivo.
- Nenhuma alteração em SERMAX-Windows/sermax_core.py, Terminal, memória pessoal, main, C:\SERMAX ou backups.
- Nenhuma inferência real com Ollama/OpenJarvis foi executada.
- Nenhuma execução real do Tesseract foi realizada nesta etapa.

### Dependências e licenças

pytesseract e pypdfium2 foram adicionados às dependências Python. O executável Tesseract e os arquivos de idioma por e eng precisam existir no computador de execução. Tesseract declara licença Apache-2.0. pypdfium2 declara Apache-2.0/BSD-3-Clause; PDFium e suas dependências exigem revisão e inclusão dos avisos de licença na distribuição binária. Referências consultadas: documentação oficial do Tesseract e documentação do pypdfium2.

### Validação pendente

Os testes automatizados devem confirmar upload sem motor, extração simulada de imagem, renderização de PDF via PDFium com OCR simulado, migração de banco, isolamento entre conversas, contexto e interface. Esses testes não comprovam precisão do OCR nem funcionamento de uma instalação Tesseract real. A homologação local com por+eng, amostras de imagem e PDFs digitalizados permanece pendente.

PR #15 será mantida em rascunho, sem merge. O CI da branch deve validar Python 3.12, Python 3.14, Windows e os testes de interação da interface.


## 25. Validação automatizada do OCR, 2026-11-17

A execução GitHub Actions `44213281399`, evento `pull_request`, commit `60c9f6f9da43d3cbdd0997fa77950d9af5745af9`, concluiu com sucesso nos cinco jobs:
- `backend-tests (3.12)`: sucesso.
- `backend-tests (3.14)`: sucesso.
- `windows-validation`: sucesso.
- `frontend-check`: sucesso.
- `frontend-interaction`: sucesso.

A bateria validou a migração dos metadados de extração, upload quando Tesseract não está disponível, integração simulada de OCR em imagem, renderização PDF pelo PDFium com reconhecimento simulado, limite de cinco páginas OCR, indicação de origem e incerteza do OCR no contexto do MAX, além dos testes anteriores de anexos, conversa, memória, streaming e interface.

A validação não executou o binário Tesseract nem mediu precisão de reconhecimento. A homologação local com Tesseract real e os dados de idioma `por` e `eng` continua pendente. Nenhuma inferência real com Ollama/OpenJarvis foi executada. PR #15 permanece aberta, em rascunho e sem merge.


## 26. Diagnóstico de prontidão do Tesseract, 2026-11-17

O painel Motores da Plataforma passou a apresentar o estado do OCR local. O endpoint GET /api/engines/status chama uma consulta limitada de Tesseract --list-langs, com timeout de 2 segundos, sem processar arquivos ou iniciar reconhecimento.

O diagnóstico diferencia executável ausente, timeout, falha ao listar idiomas e ausência dos dados obrigatórios por e eng. O painel apresenta o estado e os idiomas encontrados. O caminho completo do executável não é exposto na API.

Testes adicionados cobrem executável ausente sem subprocesso, Tesseract pronto com por e eng, ausência do idioma português e timeout. A interface também verifica a apresentação do cartão OCR local. A homologação com binário real permanece pendente.


## 27. CI do diagnóstico OCR no painel Motores, 2026-11-17

A execução GitHub Actions `44213822225`, evento `pull_request`, commit `79c22b7f99d57715a57dac08f529ad03cf6000ff`, concluiu com sucesso nos cinco jobs:
- `backend-tests (3.12)`: sucesso.
- `backend-tests (3.14)`: sucesso.
- `windows-validation`: sucesso.
- `frontend-check`: sucesso.
- `frontend-interaction`: sucesso.

A bateria validou a consulta limitada `Tesseract --list-langs`, os estados de executável ausente, idiomas ausentes e timeout, além da apresentação do cartão OCR local na interface. O diagnóstico não processa arquivos nem inicia inferência. A homologação de reconhecimento com Tesseract real continua pendente.


## 28. Launcher de homologação local isolada, 2026-11-17

Foi adicionado SERMAX-Platform/tools/run_homologation.py para permitir testes locais reais sem apontar a memória ou o banco para a instalação do usuário.

- O launcher define SERMAX_ROOT e SERMAX_PLATFORM_DATA dentro de uma pasta temporária.
- O núcleo é importado do diretório de código do repositório; nenhuma cópia de memoria_sermax.json ou memoria_neural_pestinha.json é feita.
- O worker OpenJarvis é copiado para a pasta temporária. O executável Python OpenJarvis e o caminho Tesseract existentes são preservados por suas variáveis de ambiente.
- O banco SQLite da Plataforma e os arquivos de memória do núcleo ficam na pasta temporária, removida após o encerramento.
- As funções sermax_executor.executar e sermax_tarefas.executar_plano são substituídas em memória por bloqueios, impedindo comandos operacionais e execução de planos durante a homologação.
- Consultas locais somente de leitura continuam habilitadas.
- O launcher desativa gravação de bytecode no processo e nos subprocessos, não instala dependências, não baixa modelos e não altera C:\SERMAX.

Testes automatizados verificam redirecionamento de memória e banco, preservação dos caminhos de motores, cópia do worker e bloqueio das ações operacionais. A execução real do launcher e a homologação com modelos locais dependem do computador de execução e permanecem pendentes.


## 29. CI do launcher de homologação isolada, 2026-11-17

A execução GitHub Actions `44214557379`, evento `pull_request`, commit `24edb5b7335d60ac242852296e40e8c3033a0d95`, concluiu com sucesso nos cinco jobs:
- `backend-tests (3.12)`: sucesso.
- `backend-tests (3.14)`: sucesso.
- `windows-validation`: sucesso.
- `frontend-check`: sucesso.
- `frontend-interaction`: sucesso.

Os testes do launcher validaram a substituição de SERMAX_ROOT e SERMAX_PLATFORM_DATA por diretórios temporários, preservação dos caminhos configurados para Tesseract e OpenJarvis, cópia do worker, ausência de cópia de arquivos de memória e bloqueio de execução de comandos e planos. A validação CI não iniciou a Plataforma com modelos reais nem executou reconhecimento OCR real.


## 30. Validação final do launcher isolado e proteções de escrita, 2026-11-17

A execução GitHub Actions `44214779229`, evento `pull_request`, commit `fbb191ea8d28924dcffc2e7514cf61a6e51e59d3`, concluiu com sucesso nos cinco jobs:
- `backend-tests (3.12)`: sucesso.
- `backend-tests (3.14)`: sucesso.
- `windows-validation`: sucesso.
- `frontend-check`: sucesso.
- `frontend-interaction`: sucesso.

O teste final incluiu o redirecionamento de memória e banco para diretório temporário, cópia do worker, preservação das variáveis de caminho dos motores, bloqueio de comandos e planos e desativação de gravação de bytecode no processo e nos subprocessos. A validação não executou modelos reais nem OCR real.


## 31. OCR sem bloqueio do event loop e controle de concorrência, 2026-11-17

A revisão de desempenho identificou que o OCR e a extração de documentos eram chamados diretamente dentro da rota assíncrona de upload. Como cada página digitalizada tem timeout de até oito segundos e o PDF admite até cinco páginas OCR, esse processamento síncrono poderia bloquear o event loop e atrasar conversas SSE e outras rotas.

Correção aplicada:
- `_validate_and_extract` agora roda por `starlette.concurrency.run_in_threadpool`.
- O OCR de imagens e PDFs compartilha `OCR_JOB_LOCK`, serializando renderização e reconhecimento para limitar trabalhos simultâneos e picos de memória.
- O bloqueio interno de Tesseract continua protegendo a alteração temporária do caminho do executável.
- Novo teste de API confirma que a extração ocorre em thread diferente da thread do event loop.

CI `44226228270`, commit `59c01cdc224e0f92e583cffd1b59525eb18ed677`, concluiu com sucesso nos cinco jobs: Python 3.12, Python 3.14, Windows, frontend-check e frontend-interaction. A homologação real de OCR e inferência local continua pendente.


## 32. Teste real local de OCR com amostra sintética, 2026-11-17

Foi adicionado `SERMAX-Platform/tools/check_local_ocr.py` como verificação local anterior à homologação da Plataforma.

- Gera uma imagem de teste em memória com texto conhecido.
- Executa o Tesseract instalado localmente na imagem PNG.
- Converte a mesma imagem para PDF digitalizado em memória e testa renderização PDFium mais OCR.
- Confirma os marcadores SERMAX e 12345 no resultado de ambos os caminhos.
- Emite relatório JSON com estado do motor, texto reconhecido e resultado por formato.
- Não abre documentos pessoais, não grava arquivos e não acessa rede.
- Retorna código distinto quando Tesseract/idiomas ou PDFium estão indisponíveis.

O teste automatizado do script simula as respostas do OCR e valida o relatório e a interrupção segura quando o motor está ausente. A execução com Tesseract real continua dependente do computador de homologação. A amostra sintética verifica funcionamento básico, não a qualidade de OCR em documentos reais.


## 33. CI do teste local de OCR sintético, 2026-11-17

A execução GitHub Actions `44226515348`, evento `pull_request`, commit `571f73a6c3f4eea2df4d193461068fc4a4f403e4`, concluiu com sucesso nos cinco jobs:
- `backend-tests (3.12)`: sucesso.
- `backend-tests (3.14)`: sucesso.
- `windows-validation`: sucesso.
- `frontend-check`: sucesso.
- `frontend-interaction`: sucesso.

O CI validou a construção da amostra sintética em memória, o relatório do teste local e o encerramento seguro quando o Tesseract não está disponível, com respostas de OCR simuladas. O teste real com o executável Tesseract e PDFium continua pendente no computador de homologação.
