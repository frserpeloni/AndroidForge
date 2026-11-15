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

- `index.html`, interface gráfica.
- `styles.css`, identidade visual responsiva.
- `app.js`, navegação e comunicação HTTP com a API.
- `backend/server.py`, API FastAPI, persistência SQLite e adaptador de chamada ao núcleo.
- `backend/run_local.bat`, inicializador Windows.
- `backend/test_api.py`, testes básicos da API.

## Integração com o núcleo

O backend tenta carregar o núcleo existente de `SERMAX-Windows/sermax_core.py` sob demanda. A chamada é serializada por bloqueio global porque o núcleo atual mantém sessão e histórico globais. Isso evita concorrência, mas ainda não oferece isolamento de conversas.

O núcleo existente mantém suas regras atuais de memória e roteamento OpenJarvis/Ollama. A Plataforma grava seu próprio histórico em `%USERPROFILE%\\.sermax-platform\\platform.sqlite3`. Não altere nem copie manualmente os arquivos de memória do núcleo.

## Limitações conhecidas

- A primeira versão é local e de usuário único.
- Não há autenticação nem acesso remoto.
- Não há streaming de tokens.
- Projetos, anexos e tarefas em segundo plano ainda não estão conectados.
- Se dependências do núcleo estiverem ausentes, a API retorna erro explícito e não inventa resposta.
- Compatibilidade real com o ambiente Python do computador precisa ser testada.
- Não é hospedagem pública nem instalador validado.

## Testes

No diretório `backend`:

```powershell
python -m pip install -r requirements.txt
python -m unittest -v test_api.py
```

Validação automatizada: GitHub Actions executou os testes com sucesso em Python 3.12 e 3.14 no commit `15842233ce8a8a19f3e724445fd9402adfa40180`. Isso valida os testes da API em Linux. A execução no Windows do usuário e a integração com o núcleo real continuam pendentes.

## Proteções

A implementação está em branch e diretório separados. Não altera a branch `main`, núcleo, Terminal original, arquivos de memória ou backups. Drive Connect permanece fora do escopo.
