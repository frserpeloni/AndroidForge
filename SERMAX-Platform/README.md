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
python -m unittest -v test_api.py test_tasks_api.py test_memory_api.py test_core_session_contract.py test_real_core_import.py
```

O GitHub Actions executa testes da API em Python 3.12 e 3.14, verifica a sintaxe JavaScript, executa testes de interação com DOM simulado e roda uma bateria adicional em `windows-latest` com Python 3.12 e Node 22. O teste de persistência fecha e reabre o cliente da aplicação usando o mesmo arquivo SQLite temporário, verificando projetos, conversas e mensagens. Isso valida o comportamento do banco após reabertura no ambiente de CI. Não substitui teste visual em navegador real, execução no computador do usuário, integração com o núcleo real ou validação de instalação.

## Proteções

A implementação está em branch e diretório separados. Não altera a branch `main`, núcleo, Terminal original, arquivos de memória ou backups. Drive Connect permanece fora do escopo.
