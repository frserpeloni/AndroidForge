# SERMAX Platform

Primeira implementação isolada da interface gráfica e do serviço local da Plataforma SERMAX.

## Iniciar no Windows

1. Tenha Python 3.12 ou superior instalado.
2. Abra `SERMAX-Platform/backend`.
3. Execute `run_local.bat`.
4. Aguarde a instalação das dependências no ambiente virtual.
5. Abra no navegador: **http://127.0.0.1:8765**

O serviço permanece vinculado a `127.0.0.1`. Não encaminhe a porta para a internet e não exponha a API em rede pública.

## Componentes

- `index.html`, interface gráfica, incluindo painel de detalhes dos projetos.
- `styles.css`, identidade visual responsiva.
- `app.js`, navegação e comunicação HTTP com a API.
- `backend/server.py`, API FastAPI, persistência SQLite e adaptador de chamada ao núcleo.
- `backend/run_local.bat`, inicializador manual de desenvolvimento.
- `sermax_platform_launcher.py`, supervisor local em desenvolvimento, inicia a API, valida `/api/health`, abre o navegador e encerra o servidor de forma controlada.
- `backend/test_api.py`, testes automatizados da API, projetos e persistência após reinício.
- `tests/ui.test.js`, testes de interação da interface com DOM simulado.
- `tests/test_platform_launcher.py`, testes do health check do launcher, rejeição de outro serviço e encerramento antecipado.
- `package.json`, dependências e comando dos testes de interface.

## Integração com o núcleo

O backend tenta carregar o núcleo existente de `SERMAX-Windows/sermax_core.py` sob demanda. A chamada é serializada por bloqueio global porque o núcleo atual mantém sessão e histórico globais. Antes de cada chamada, o backend reconstrói temporariamente a sessão com o histórico da conversa selecionada e as instruções do projeto, quando houver. Ao final, restaura a sessão global original. Isso separa o contexto transitório das conversas nesta integração, mas não isola a memória persistente geral do núcleo, que continua compartilhada.

O núcleo existente mantém suas regras atuais de memória e roteamento OpenJarvis/Ollama. A Plataforma grava seu próprio histórico em `%USERPROFILE%\\.sermax-platform\\platform.sqlite3`. Não altere nem copie manualmente os arquivos de memória do núcleo.

## Limitações conhecidas

- A primeira versão é local e de usuário único.
- Não há autenticação nem acesso remoto.
- Não há streaming de tokens.
- Projetos persistentes estão disponíveis localmente, com criação, edição, arquivamento, detalhes e associação de conversas. O painel do projeto lista as conversas vinculadas e permite reabri-las. O gerenciador de tarefas persistentes permite criar, consultar, editar, definir prioridade e prazo, filtrar e atualizar o estado. O painel Memória consulta somente registros já carregados em memória pelo núcleo, sem abrir ou alterar arquivos. Execução automática/em segundo plano e anexos seguem pendentes.
- Se dependências do núcleo estiverem ausentes, a API retorna erro explícito e não inventa resposta.
- Compatibilidade real com o ambiente Python do computador precisa ser testada.
- A interface ainda não passou por teste automatizado de interação em navegador.
- Não é hospedagem pública nem instalador validado.

## Inicializador da Plataforma

O novo `sermax_platform_launcher.py` inicia o serviço local em `127.0.0.1:8765`, aguarda a resposta de saúde identificada como `sermax-platform-api`, abre a interface no navegador e registra eventos em `%USERPROFILE%\\.sermax-platform\\logs\\platform-launcher.log`. É um inicializador Python de desenvolvimento. Ainda não está empacotado em `SERMAX.exe`, não gerencia instalação de dependências e não abre o Terminal administrativo.

## Projetos

Os projetos ficam na tabela `projects` do banco local. Cada registro contém nome, descrição, instruções, estado de arquivamento e datas. Conversas guardam uma referência opcional ao projeto. Arquivar não apaga o projeto nem suas conversas. Não há operação de exclusão nesta versão.

Endpoints locais: `GET/POST /api/projects`, `GET/PUT /api/projects/{id}`, `POST /api/projects/{id}/archive` e `GET /api/projects/{id}/conversations`.

As instruções do projeto entram como contexto de sistema em cada solicitação vinculada. A API reconstrói temporariamente a sessão do núcleo com o histórico daquela conversa e restaura a sessão global anterior ao final da chamada. O bloqueio global impede chamadas simultâneas durante essa troca. A memória persistente geral do núcleo continua compartilhada, conforme o comportamento original do SERMAX. Conversas de projetos arquivados preservam o vínculo e as instruções ao serem retomadas. Na interface, a conversa retomada identifica o vínculo como “Projeto arquivado”, mantendo o contexto associado mesmo sem permitir novas conversas nesse projeto.

## Motores

A rota `GET /api/engines/status` apresenta o estado do núcleo na sessão atual, consulta a API de tags do Ollama em `127.0.0.1:11434` com timeout de 1,5 segundo, verifica a presença dos arquivos esperados do ambiente OpenJarvis e informa o último backend registrado pelo núcleo. O diagnóstico não envia prompts, não inicia inferência e não altera configurações.

A presença do executável Python e do worker OpenJarvis não comprova que o worker inicia ou responde. A resposta da API `/api/tags` comprova que o endpoint local do Ollama respondeu, não que uma geração de texto funcione. A homologação real exige uma conversa de teste autorizada, com resposta e backend registrados.

## Memória

A rota `GET /api/memory` consulta exclusivamente a lista `historico` já carregada no módulo do núcleo. A rota não chama `load_core()`, não abre `memoria_sermax.json`, não executa `salvar_memoria()` e não altera registros. Se o núcleo ainda não estiver carregado na sessão da API, retorna `core_not_loaded` e orienta abrir uma conversa antes de atualizar o painel. A consulta aceita busca textual e limite de 1 a 100 registros, retornando somente entradas do usuário.

A interface não oferece operações de criação, edição ou exclusão de memória. Os dados são apresentados com `textContent`, sem interpretar conteúdo armazenado como HTML. O painel é somente leitura e não substitui backup ou ferramenta de manutenção da memória.

## Tarefas

As tarefas são armazenadas na tabela `tasks` do mesmo banco SQLite da Plataforma. Cada registro contém título, descrição, estado, prioridade, prazo e datas de criação/atualização/conclusão. Os estados disponíveis são pendente, em andamento, concluída e cancelada. Não existe exclusão física nem execução automática de tarefas nesta versão.

Endpoints locais: `GET/POST /api/tasks`, `GET/PUT /api/tasks/{id}` e `PATCH /api/tasks/{id}/status`. A tela Tarefas permite registrar, filtrar e atualizar tarefas. O armazenamento persiste após reinício do serviço.

## Testes

No diretório `backend`:

```powershell
python -m pip install -r requirements.txt
python -m unittest -v test_api.py test_chat_stream.py test_attachments_api.py test_core_stream_integration.py test_tasks_api.py test_memory_api.py test_engines_status.py test_core_session_contract.py test_real_core_import.py
```

O GitHub Actions executa testes da API em Python 3.12 e 3.14, verifica a sintaxe JavaScript, executa testes de interação com DOM simulado e roda uma bateria adicional em `windows-latest` com Python 3.12 e Node 22. O teste de persistência fecha e reabre o cliente da aplicação usando o mesmo arquivo SQLite temporário, verificando projetos, conversas e mensagens. Isso valida o comportamento do banco após reabertura no ambiente de CI. Não substitui teste visual em navegador real, execução no computador do usuário, integração com o núcleo real ou validação de instalação.

## Streaming de conversa

A interface usa `POST /api/chat/stream` com Server-Sent Events. O backend transmite snapshots acumulados do texto retornado pelo núcleo, mantém a fila de eventos limitada e preserva o bloqueio global da sessão. O endpoint legado `POST /api/chat` permanece disponível.

O Ollama já fornece atualizações acumuladas durante a geração. O adaptador OpenJarvis atual retorna uma resposta única ao final, portanto ainda não oferece streaming gradual. Se o navegador desconectar, a inferência continua no servidor até terminar. A interface não apresenta um botão de cancelamento enquanto os motores não oferecerem interrupção segura.

Os testes de streaming estão em `backend/test_chat_stream.py` e também são executados no CI para Python 3.12, Python 3.14 e Windows.

## Proteções

A implementação está em branch e diretório separados. Não altera a branch `main`, núcleo, Terminal original, arquivos de memória ou backups. Drive Connect permanece fora do escopo.


## Anexos por conversa

A primeira etapa de anexos está implementada em `backend/attachment_service.py`. Os arquivos ficam em `DATA_DIR/attachments`, fora da pasta pública da interface. O SQLite registra ID, conversa, nome de apresentação, extensão, MIME detectado, tamanho, SHA-256, nome físico UUID e texto extraído.

Formatos aceitos: PDF, DOCX, TXT UTF-8, JPEG e PNG. A validação considera assinatura e parser, não confia no MIME informado pelo navegador. Limites: 10 MiB por arquivo, 5 arquivos por conversa e 25 MiB por conversa. PDF criptografado é rejeitado e limitado a 100 páginas. DOCX verifica a estrutura ZIP, caminhos internos, macros e relacionamentos externos. Imagens têm limite de 20 milhões de pixels. JPEG, PNG e páginas PDF sem texto nativo passam por OCR local opcional, com limites próprios e estado de extração registrado.

A interface permite selecionar arquivos, remover da fila, enviar, listar, baixar e excluir. Downloads são enviados como `application/octet-stream` com disposição de anexo. Os endpoints verificam a associação do ID à conversa. A extração de texto fica disponível para PDF, DOCX e TXT. OCR local atende JPEG, PNG e até cinco páginas digitalizadas por PDF.

Rotas:
- `POST /api/conversations/{conversation_id}/attachments`
- `GET /api/conversations/{conversation_id}/attachments`
- `GET /api/conversations/{conversation_id}/attachments/{attachment_id}`
- `GET /api/conversations/{conversation_id}/attachments/{attachment_id}/content`
- `DELETE /api/conversations/{conversation_id}/attachments/{attachment_id}`

Os conteúdos dos anexos ainda não são enviados ao prompt do núcleo. Essa integração será feita em etapa separada, com limites de contexto e tratamento do texto como dado não confiável. Nenhum arquivo é incorporado à memória pessoal. A homologação real e a revisão de segurança continuam condicionadas à conclusão dos testes CI e à revisão do código.


## Contexto dos anexos no MAX

A integração de contexto consulta até cinco anexos vinculados à conversa atual. O serviço seleciona trechos por relevância lexical à pergunta, com orçamento agregado de 2.600 caracteres e limite de 650 caracteres por arquivo. Os trechos entram em uma mensagem temporária do contexto do núcleo, identificados como dados não confiáveis. O prompt orienta o MAX a ignorar instruções presentes nos arquivos, identificar o nome do documento usado e informar quando os trechos forem insuficientes.

O contexto não é gravado na tabela de mensagens nem na memória pessoal. A Plataforma reconstrói a sessão para a conversa, executa a solicitação e restaura a sessão global original. O arquivo `SERMAX-Windows/sermax_core.py` não foi alterado.

Anexos de imagem com OCR concluído entram no contexto como texto reconhecido, identificado como OCR e sujeito a erros. Quando o motor ou os idiomas não estão disponíveis, o MAX recebe essa limitação por metadados. O sistema não faz análise visual. A extração textual permanece limitada pelo orçamento de prompt existente no núcleo; o sistema não afirma ter lido o documento completo quando transmite somente trechos.


A proteção de instruções usa duas mensagens separadas: a instrução de segurança permanece no papel `system`; o JSON com os trechos extraídos entra no papel `user`. Assim, o texto dos arquivos não recebe o mesmo nível de autoridade da instrução de proteção.


## OCR local de anexos

O OCR é executado no computador que hospeda a Plataforma. Não há envio das imagens ou páginas a serviços externos. JPEG e PNG passam pelo Tesseract local. Em PDFs, o pypdf extrai primeiro o texto nativo; páginas sem texto são renderizadas pelo PDFium via pypdfium2 e encaminhadas ao Tesseract.

Limites: 8 segundos por imagem/página; até cinco páginas digitalizadas por PDF; renderização a 150 DPI, limitada a 3.000 pixels no maior lado; imagens de OCR reduzidas a no máximo 9 milhões de pixels. O limite original de 20 milhões de pixels para validação do arquivo permanece.

Dependências Python: pytesseract e pypdfium2. O executável Tesseract e os dados de idioma são componentes locais separados. O idioma padrão é por+eng. No Windows, instale o Tesseract e os arquivos de idioma português (por) e inglês (eng). O caminho do executável pode ser informado por SERMAX_TESSERACT_CMD; sem essa configuração, a Plataforma procura tesseract no PATH.

A ausência do executável, do pacote Python, dos dados de idioma ou do renderizador não bloqueia o upload. O SQLite registra extraction_method e extraction_status, e a interface mostra o estado. PDFs com texto nativo continuam legíveis sem OCR. Em documentos mistos, o texto nativo e o OCR são combinados, identificando as páginas reconhecidas.

O OCR não é prova de fidelidade. O MAX recebe a indicação de que o trecho veio de OCR e que pode conter erros. O conteúdo continua sendo dado não confiável, sem autoridade para alterar instruções do sistema. O contexto segue limitado a 2.600 caracteres agregados e 650 por arquivo.

A execução automatizada testa a integração com o renderizador PDF e simula a resposta do Tesseract. Ela não comprova a instalação do executável nem a qualidade do reconhecimento. A homologação com Tesseract real, pacote por+eng e imagens de referência continua pendente.

Licenças para a futura distribuição: Tesseract está sob Apache-2.0. pypdfium2 declara Apache-2.0/BSD-3-Clause e PDFium usa licença BSD-style, com licenças de dependências que devem acompanhar distribuições binárias. Antes de empacotar a Plataforma, revisar e incluir os avisos correspondentes.

Referências técnicas:
- Tesseract, instalação e idiomas: https://tesseract-ocr.github.io/tessdoc/Installation
- pypdfium2, instalação e licenças: https://pypdfium2.readthedocs.io/en/stable/readme.html


O painel Motores também informa se o Tesseract local está disponível e se os dados de idioma português (por) e inglês (eng) estão instalados. A consulta executa somente Tesseract --list-langs, com timeout de 2 segundos. Ela não inicia OCR nem processa anexos.


## Homologação local isolada

Depois de obter esta branch e instalar as dependências de backend no ambiente Python ativo, execute no PowerShell, a partir da raiz do repositório:

```powershell
python SERMAX-Platform/tools/run_homologation.py
```

O launcher usa o código do núcleo presente no repositório, mas define SERMAX_ROOT e SERMAX_PLATFORM_DATA para uma pasta temporária. A memória SERMAX, a memória neural e o banco SQLite da Plataforma ficam nessa pasta e são apagados quando o servidor encerra. Nenhum arquivo de memória é copiado de C:\\SERMAX. O worker OpenJarvis é copiado para a pasta temporária; o executável Python do ambiente OpenJarvis é preservado pela variável SERMAX_JARVIS_PYTHON, se configurada. O caminho do Tesseract também é preservado pela variável SERMAX_TESSERACT_CMD.

O modo de homologação bloqueia as funções de execução de comandos e planos. Consultas locais de leitura continuam disponíveis. Abra http://127.0.0.1:8765, verifique os cartões Motores, envie uma imagem e um PDF digitalizado de teste e encerre com Ctrl+C. Não use comandos operacionais neste modo.

O launcher não instala dependências nem modelos. Se os módulos Python estiverem ausentes, instale SERMAX-Platform/backend/requirements.txt no ambiente Python ativo. Para OpenJarvis, configure SERMAX_JARVIS_PYTHON com o caminho do python.exe do ambiente já instalado. Para Tesseract fora do PATH, configure SERMAX_TESSERACT_CMD.
