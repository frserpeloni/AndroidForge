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
- O núcleo mantém variáveis globais de sessão e memória persistente. A API reconstrói a sessão temporária a partir das mensagens da conversa selecionada, substitui `core.sessao` durante a chamada e restaura a sessão original em `finally`. `CHAT_LOCK` serializa chamadas ao núcleo. O teste `test_chat_reconstructs_only_the_requested_conversation_history` verifica que o contexto de uma conversa não recebe mensagens de outra. A memória persistente `historico` do núcleo continua compartilhada entre conversas e deve ser tratada como memória pessoal global do usuário. A integração permanece local e single-user; não há isolamento entre identidades de usuários.
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


## Acesso por Android e outros dispositivos da rede local

**Estado atual: bloqueado por segurança, sem implementação de acesso remoto.**

- O launcher inicia a API em `127.0.0.1:8765`.
- O middleware da API aceita somente clientes com endereço IP de loopback e cabeçalhos Host/Origin locais.
- O CORS permite somente `http://127.0.0.1:8765` e `http://localhost:8765`.
- A interface usa URLs relativas, então ela acompanha a origem do navegador, mas isso não remove as restrições do servidor.
- Não há autenticação, pareamento de dispositivos, gestão de sessões de usuário ou TLS configurado para acesso pela rede.

Consequência: a Plataforma atual atende o navegador no próprio PC. Um celular Android ou outro computador não consegue acessar o serviço pela rede local. Isso ainda não atende ao requisito de clientes em vários dispositivos ligados a um cérebro central.

Não alterar o bind para `0.0.0.0`, não remover o middleware e não liberar portas no firewall como solução improvisada. A etapa de acesso entre dispositivos exige desenho e implementação próprios de autenticação/pareamento, credenciais revogáveis, transporte protegido, política de origem, limites de sessão, firewall e testes de acesso autorizado e negado. Até concluir esses controles, manter a API restrita ao loopback.

## Proposta técnica: acesso seguro por dispositivos da rede local

**Estado: desenho proposto. Nenhuma porta de rede foi aberta e nenhuma autenticação remota foi implementada.**

### Objetivo e limite de confiança

O computador Windows permanece como único servidor e único processo proprietário do núcleo MAX, da memória e do banco da Plataforma. Navegadores e Android funcionam como clientes. Um cliente nunca recebe acesso direto ao sistema de arquivos, ao SQLite ou ao processo Ollama.

A primeira versão de rede deve atender somente à LAN privada configurada pelo operador. Não deve publicar a API na internet nem criar encaminhamento automático de portas.

### Fluxo de ativação proposto

1. O servidor inicia fechado para clientes de rede, mantendo o acesso local atual.
2. O operador abre a função de pareamento no próprio PC.
3. A Plataforma gera um código aleatório de uso único, com validade curta e limite de tentativas. O código é exibido localmente como QR e texto.
4. O Android informa o código e solicita pareamento.
5. O PC exige aprovação explícita do operador, identifica o dispositivo e emite uma credencial individual.
6. A credencial fica vinculada ao dispositivo, armazenada no servidor somente em formato protegido por hash, com data de emissão, último uso e estado de revogação.
7. O operador consulta os dispositivos autorizados e revoga cada credencial individualmente.

O código de pareamento não é uma senha permanente e não concede acesso antes da aprovação local.

### Transporte e fronteira de rede

- HTTPS obrigatório para todo acesso pela LAN.
- Certificado do servidor emitido por uma autoridade local controlada pelo PC, com procedimento explícito de confiança no dispositivo cliente. Não aceitar certificado inválido silenciosamente.
- Bind restrito às interfaces privadas selecionadas pelo operador. Nunca usar exposição indiscriminada em todas as interfaces como padrão.
- Firewall do Windows limitado ao perfil privado e à porta configurada. Não criar regra para perfil público.
- Rejeitar conexões fora da sub-rede autorizada, além da autenticação. A sub-rede é uma barreira complementar, não substitui credenciais.
- Manter CORS com lista explícita de origens HTTPS autorizadas. Validar Host, Origin e proteção CSRF nos endpoints que alteram dados.
- Não permitir acesso remoto a endpoints administrativos, diagnóstico sensível ou operações locais sem política específica.

### Identidade, sessão e autorização

- Credencial aleatória independente por dispositivo, com escopo mínimo e revogação imediata.
- Tokens nunca aparecem em logs, URLs, mensagens de erro ou telemetria.
- Sessões curtas, renovação controlada e proteção contra repetição de requisições.
- Limites de tentativas de pareamento e autenticação, tamanho de requisições e conexões simultâneas.
- Toda requisição remota é associada a um dispositivo autorizado.
- A primeira versão continua single-user: pareamento identifica dispositivos do mesmo proprietário, não cria contas independentes nem promete isolamento multiusuário.
- Memória persistente global do núcleo permanece compartilhada entre conversas. Não declarar isolamento entre pessoas enquanto essa arquitetura não for alterada e testada.

### Critérios obrigatórios de aceite

1. Cliente não pareado recebe negação e não acessa dados.
2. Código expirado, reutilizado ou incorreto é recusado.
3. Aprovação no PC habilita somente o dispositivo solicitado.
4. Revogação bloqueia imediatamente novas requisições desse dispositivo.
5. Origem web não autorizada e requisição CSRF são recusadas.
6. Certificado ausente, inválido ou incompatível impede conexão segura.
7. Perfil público do Windows não recebe regra de entrada.
8. Limites de tentativas, payload e conexões são testados.
9. Acesso local em 127.0.0.1 continua funcionando sem pareamento.
10. Testes positivos e negativos rodam no Windows CI e em navegador Android real antes de declarar compatibilidade.

### Sequência de implementação após aprovação do desenho

1. Implementar serviço de identidade de dispositivo e armazenamento de credenciais revogáveis, sem abrir a rede.
2. Implementar fluxo de pareamento local e testes unitários.
3. Implementar autenticação por requisição, proteção CSRF, política de origem e limites.
4. Implementar HTTPS e gestão do certificado local.
5. Adicionar configuração explícita de interface privada e regra de firewall restrita.
6. Executar testes de segurança automatizados no Windows.
7. Homologar pareamento, conexão, revogação e reconexão em Android físico.
8. Somente então habilitar a opção de acesso LAN na interface.

**Bloqueio de segurança:** não alterar o bind atual, middleware, CORS ou firewall antes de concluir os critérios de aceite e aprovar a sequência. Esta seção documenta uma proposta, não uma implementação nem uma autorização para expor a API.



## Validação CI #723, 22/11/2026

Execução [#723](https://github.com/frserpeloni/AndroidForge/actions/runs/45036208580), commit `4571a1416e198edfe221d72389b2905bb5a0b7fe`:

- Os cinco jobs terminaram com sucesso: backend Python 3.12, backend Python 3.14, frontend-check, frontend-interaction e windows-validation.
- O runner Windows concluiu os testes de backend, streaming, anexos, integração controlada com o núcleo, tarefas persistentes, memória somente leitura, diagnóstico de motores, importação do núcleo, restauração de sessão, interface, segurança do instalador, construtor de pacote, launcher, lock de instância, política de inicialização automática e sintaxe.
- Os jobs Python 3.12 e 3.14 também concluíram todos os testes previstos.
- O resultado comprova a suíte automatizada nos runners do GitHub Actions. Não comprova inferência real com Ollama/OpenJarvis no computador de destino, homologação Android pela LAN, instalação em `C:\\SERMAX` ou operação contínua no PC do usuário.
- O arquivo `SERMAX-Platform/backend/server.py` permanece byte a byte idêntico à branch-base, blob SHA `238d764b7a761baee421cc2d36e64be533fb6d5d`.
- PR #27 permanece aberta em Draft, sem merge. A branch `main` não foi alterada.

**Próximo bloqueio de arquitetura:** acesso LAN segue somente documentado. A API continua em loopback. Não abrir portas, alterar bind, CORS ou middleware sem aprovação específica do desenho e dos critérios de segurança. O workflow de agentes não foi executado por esta atualização documental; o resultado #723 corresponde ao CI da Plataforma.


## Validação CI #726 e #727, 22/11/2026

Execução [#726](https://github.com/frserpeloni/AndroidForge/actions/runs/45037048650), commit `7f28987ef5db6b8dd7dd7b3ec2f5d6b662045702`:
- Os cinco jobs terminaram com sucesso: backend Python 3.12, backend Python 3.14, frontend-check, frontend-interaction e windows-validation.
- O runner Windows concluiu a suíte de API, streaming, anexos, integração controlada com o núcleo, tarefas persistentes, memória, diagnóstico dos motores, importação do núcleo, restauração de sessão, interface, segurança do instalador, construtor de pacote, launcher, lock de instância, política de inicialização automática e sintaxe.

Execução [#727](https://github.com/frserpeloni/AndroidForge/actions/runs/45037117096), commit `30a3f7dfb6ff64d8e0654dac9fbc23f590b4ca9c`:
- Os mesmos cinco jobs terminaram com sucesso.
- O runner dos agentes recebeu uma instrução adicional que proíbe mudanças de bind, middleware, CORS, autenticação, pareamento, TLS, firewall e políticas de rede enquanto o acesso LAN não tiver aprovação específica.
- O teste CI comprova que a suíte da Plataforma continua passando após a inclusão dessa proteção. Não comprova execução efetiva da equipe de agentes.

A PR #27 continua aberta em Draft, sem merge. A branch `main` permanece intocada. O servidor central `backend/server.py` conserva o blob SHA `238d764b7a761baee421cc2d36e64be533fb6d5d`, idêntico à branch-base.

**Limites ainda pendentes:** a equipe de agentes não tem execução confirmada nesta etapa; o acesso Android/LAN permanece bloqueado; não há inferência real Ollama/OpenJarvis comprovada no PC de destino; não há instalador novo homologado.


## Execução da equipe de agentes #22 e auditoria da proposta, 22/11/2026

Workflow [SERMAX Platform Development Agents #22](https://github.com/frserpeloni/AndroidForge/actions/runs/45039518167), disparado no commit `aeab596f396c6ebf691731030cf1d0e215075798`:
- OpenJarvis foi instalado no runner Linux.
- Contrato Groq: 2 testes aprovados.
- Workspace isolado: 10 testes aprovados.
- A equipe executou os papéis Analista, Pesquisador, Programador e Testador.
- A tarefa terminou com status `completed`; o workflow terminou com sucesso.
- O commit gerado pelo agente foi `6b3e0b8f309cbf2d7193b9035ed64f00dd388191`.

**Ressalva de auditoria:** a proposta do Programador listava dois arquivos, mas a aplicação registrou somente `backend/instance_lock.py`. O Testador retornou PASS apesar dessa divergência. O commit inicial também truncava o arquivo de lock Windows antes de adquirir o bloqueio, operação que foi considerada insegura e corrigida na revisão. Portanto, o PASS do agente não foi aceito como prova suficiente da proposta completa.

## Correção auditada do lock e CI #731 a #733, 22/11/2026

Na branch isolada `sermax-platform-agent-scope-20261122`:
- O lock foi corrigido para não truncar o arquivo antes de adquirir a exclusividade Windows.
- A compatibilidade com entrada `str` foi mantida convertendo o argumento para `Path`.
- Foi acrescentado o teste `test_lock_accepts_string_data_directory` em `SERMAX-Platform/tests/test_instance_lock.py`.
- O arquivo `SERMAX-Platform/backend/server.py` permaneceu idêntico à branch-base, blob SHA `238d764b7a761baee421cc2d36e64be533fb6d5d`.

Execuções CI:
- [#731](https://github.com/frserpeloni/AndroidForge/actions/runs/45040434714), commit `2d5a98cbdf7d0fa9212b1c197eb41df6e69fb75c`, cinco jobs aprovados.
- [#732](https://github.com/frserpeloni/AndroidForge/actions/runs/45040438731), mesmo commit, cinco jobs aprovados.
- [#733](https://github.com/frserpeloni/AndroidForge/actions/runs/45040442593), commit `951f313b88d3c33ce33a543b9934bb5a8fbc908b`, cinco jobs aprovados.

No runner Windows do CI #733, os três testes de lock foram executados e passaram, incluindo exclusividade entre processos independentes. Os jobs de backend Python 3.12 e 3.14 e os dois jobs de frontend também passaram.

**Limites:** a validação Windows ocorreu em runner hospedado pelo GitHub, não no PC físico do usuário. Não comprova inferência real com Ollama/OpenJarvis no PC de destino, instalação em `C:\\SERMAX`, acesso Android pela LAN ou instalador pronto.

PR #27 permanece aberta em Draft, sem merge. A branch `main` não foi alterada. O acesso LAN continua bloqueado até aprovação específica do desenho de segurança.


## Revisão do contrato de aprovação de pareamento, 23/11/2026

- O parâmetro booleano `approved=True` foi removido de `complete_pairing()`. Ele permitia que o próprio chamador declarasse uma aprovação sem demonstrar sua origem.
- A função agora exige `approval_verifier`, um callback interno injetado pelo servidor. O callback recebe o identificador do dispositivo e o código de pareamento e precisa retornar exatamente `True`.
- A função rejeita ausência de verificador, booleanos e respostas diferentes de `True`. Exceções do verificador interrompem a emissão e mantêm o código sem consumo.
- Contrato de integração: o callback deverá consultar um estado de aprovação gerado exclusivamente pela UI administrativa local no PC central. O endpoint remoto nunca deverá aceitar callback, booleano, campo `approved` ou resultado de aprovação enviado pelo cliente.
- Os testes foram adaptados e incluem recusa sem callback, rejeição de booleano, aprovação negada, exceção do verificador e continuidade do código quando a aprovação falha.
- Commits desta correção: `fdab4edbb12f0a662ea7159810052d95da89976f` (módulo) e `b711b2f2808fc51403d9d110d52bc767739241a9` (testes).
- O workflow já contém o passo de testes de pareamento em Linux e Windows. A consulta disponível de execuções/status ainda não retornou execução associada a esse commit. Portanto, testes CI permanecem **não confirmados**.
- O callback ainda não está conectado a uma UI administrativa real. A fronteira de confiança depende dessa integração futura e de sua revisão. Esta alteração remove a aprovação booleana controlada pelo chamador, mas não habilita pareamento remoto.
- Nenhuma alteração em `server.py`, bind, middleware, CORS, TLS, firewall, Terminal, memória, `C:\\SERMAX`, backups ou `main`. PR #27 permanece em Draft e sem merge.
