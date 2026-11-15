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
- `backend/run_local.bat`, inicializador Windows.
- `backend/test_api.py`, testes da API e dos projetos persistentes.

## Integração com o núcleo

O backend tenta carregar o núcleo existente de `SERMAX-Windows/sermax_core.py` sob demanda. A chamada é serializada por bloqueio global porque o núcleo atual mantém sessão e histórico globais. Antes de cada chamada, o backend reconstrói temporariamente a sessão com o histórico da conversa selecionada e as instruções do projeto, quando houver. Ao final, restaura a sessão global original. Isso separa o contexto transitório das conversas nesta integração, mas não isola a memória persistente geral do núcleo, que continua compartilhada.

O núcleo existente mantém suas regras atuais de memória e roteamento OpenJarvis/Ollama. A Plataforma grava seu próprio histórico em `%USERPROFILE%\\.sermax-platform\\platform.sqlite3`. Não altere nem copie manualmente os arquivos de memória do núcleo.

## Limitações conhecidas

- A primeira versão é local e de usuário único.
- Não há autenticação nem acesso remoto.
- Não há streaming de tokens.
- Projetos persistentes estão disponíveis localmente, com criação, edição, arquivamento, detalhes e associação de conversas. O painel do projeto lista as conversas vinculadas e permite reabri-las. Anexos e tarefas em segundo plano seguem pendentes.
- Se dependências do núcleo estiverem ausentes, a API retorna erro explícito e não inventa resposta.
- Compatibilidade real com o ambiente Python do computador precisa ser testada.
- Não é hospedagem pública nem instalador validado.

## Projetos

Os projetos ficam na tabela `projects` do banco local. Cada registro contém nome, descrição, instruções, estado de arquivamento e datas. Conversas guardam uma referência opcional ao projeto. Arquivar não apaga o projeto nem suas conversas. Não há operação de exclusão nesta versão.

Endpoints locais: `GET/POST /api/projects`, `GET/PUT /api/projects/{id}`, `POST /api/projects/{id}/archive` e `GET /api/projects/{id}/conversations`.

As instruções do projeto entram como contexto de sistema em cada solicitação vinculada. A API reconstrói temporariamente a sessão do núcleo com o histórico daquela conversa e restaura a sessão global anterior ao final da chamada. O bloqueio global impede chamadas simultâneas durante essa troca. A memória persistente geral do núcleo continua compartilhada, conforme o comportamento original do SERMAX. Conversas de projetos arquivados preservam o vínculo e as instruções ao serem retomadas.

## Testes

No diretório `backend`:

```powershell
python -m pip install -r requirements.txt
python -m unittest -v test_api.py
```

Validação automatizada: GitHub Actions executou os 11 testes da API com sucesso em Python 3.12 e 3.14 no commit `d7dc788c456830b8793173912e650ac8edc73d6c` (execução `43716401255`). Isso valida os testes automatizados em Linux. A execução no Windows do usuário, a integração com o núcleo real e a persistência após reinício continuam pendentes.

## Proteções

A implementação está em branch e diretório separados. Não altera a branch `main`, núcleo, Terminal original, arquivos de memória ou backups. Drive Connect permanece fora do escopo.
