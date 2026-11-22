# Estado da integração local

## Implementado nesta etapa

- Conexões SQLite fechadas em todas as operações, com commit e rollback explícitos.
- Migração compatível do histórico antigo para incluir estado da mensagem (`pending`, `complete`, `error`).
- Mensagens do usuário preservadas com estado de erro quando o núcleo falha.
- Lista de conversas recentes carregada pela interface e reabertura de conversas persistidas.
- Testes adicionais para gravação, reabertura e falha do núcleo.

- API FastAPI separada da interface.
- Bind previsto exclusivamente em `127.0.0.1:8765`.
- Health check.
- Endpoint de catálogo de modelos sem declarar motores disponíveis.
- Persistência SQLite isolada em `~/.sermax-platform/platform.sqlite3`.
- Histórico de conversas próprio da Plataforma.
- Adaptador de chamada ao núcleo existente por importação tardia.
- Bloqueio global para serializar chamadas ao núcleo compartilhado.
- Proteção de origem local e validação de entrada.
- Inicializador Windows e testes unitários básicos.

## Limites e riscos ainda abertos

- O backend é executado no GitHub Actions em Python 3.12, 3.14 e Windows. Isso não equivale à execução no computador do usuário.
- Dependências e compatibilidade com Python 3.14 precisam ser verificadas.
- O smoke test passou a importar o núcleo real no CI, sem iniciar modelo e com a memória redirecionada para diretório temporário. A execução de uma conversa com OpenJarvis/Ollama real continua pendente.
- O núcleo mantém sessão e histórico globais. A serialização evita concorrência, mas não separa contexto por conversa. Portanto, a primeira integração deve ser tratada como uso local de usuário único.
- O núcleo existente também grava memória segundo suas regras atuais. A interface não oferece edição ou exclusão dessa memória.
- A autenticação de usuário e acesso remoto estão fora desta etapa. A API não deve ser exposta à rede.
- O gerenciador de tarefas persistentes em SQLite foi implementado na branch de prontidão, com API, interface e testes. Não há execução automática/em segundo plano, streaming de tokens, anexos, sincronização Android nem publicação pública.

## Validação necessária

1. Instalar dependências em ambiente isolado.
2. Rodar os testes unitários.
3. Verificar health check.
4. Confirmar falha clara quando o núcleo não estiver disponível.
5. Confirmar importação do núcleo sem alterar seus arquivos.
6. Enviar mensagem de teste autorizada e conferir resposta real do motor local.
7. Reiniciar serviço e conferir persistência SQLite.
8. Confirmar que o serviço permanece limitado a loopback.

Os testes automatizados da API foram executados com sucesso no GitHub Actions em Python 3.12 e 3.14, no commit `15842233ce8a8a19f3e724445fd9402adfa40180`. A validação em Linux não substitui os testes no Windows nem comprova a integração com o núcleo real. Permanecem pendentes os itens 4 a 8 da lista acima no ambiente de destino, além da validação de dependências do núcleo.

## Validação adicional em 22/11/2026

No GitHub Actions, execução [#21](https://github.com/frserpeloni/AndroidForge/actions/runs/45031088484), commit `e60978f385d5f858f0ea9e1735870483f8febb6b`:

- Os cinco jobs do workflow SERMAX Platform CI terminaram com sucesso.
- O job `windows-validation` executou em `windows-latest`.
- Os três testes de `backend/test_instance_lock.py` passaram no Windows, incluindo tentativa de aquisição por processo independente.
- Os mesmos três testes passaram em Linux nos jobs Python 3.12 e 3.14.
- Os testes de API, integração de streaming com o núcleo real sob dependências simuladas, importação do núcleo, launcher, interface e instalador passaram nos jobs correspondentes.
- Esta execução comprova os testes automatizados nesses runners. Não comprova ainda uma conversa real com Ollama/OpenJarvis no computador de destino, nem a instalação e operação contínua no Windows do usuário.

A branch isolada permanece sem merge. O servidor central `backend/server.py` não foi alterado nesta etapa.


## Validação de isolamento de conversas em 22/11/2026

Execução [#23](https://github.com/frserpeloni/AndroidForge/actions/runs/45032874969), commit `be695223477dbf59212e32392a1d5399a6cc5b8e`:

- Os cinco jobs do workflow passaram: Python 3.12, Python 3.14, Windows, verificação JavaScript e testes de interação da interface.
- O novo teste `test_chat_reconstructs_only_the_requested_conversation_history` passou no runner Windows e nos dois ambientes Python Linux. Ele prepara duas conversas com históricos diferentes e verifica que o núcleo recebe somente o histórico da conversa solicitada.
- A validação Windows também executou os testes de streaming e persistência da API.
- A execução comprova o isolamento do contexto reconstruído nos testes automatizados. Não comprova a operação com Ollama/OpenJarvis real no computador de destino.

A execução [#24](https://github.com/frserpeloni/AndroidForge/actions/runs/45032879598), commit `4aaa02be6b87089c17e6c0c38ef3f65e338e43e9`, repetiu os cinco jobs e todos passaram.

O workflow foi ajustado para disparar em pull requests cujo branch-base é `sermax-platform-windows-autostart-20261120`. A branch de desenvolvimento permanece isolada e o PR #27 continua sem merge.
