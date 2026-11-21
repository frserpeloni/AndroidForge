# ADR-001: parada controlada local da SERMAX Platform

- Estado: implementado na branch de trabalho, validação automatizada Windows em andamento
- Data: 2026-11-20
- Escopo: launcher local da SERMAX Platform no Windows
- Branch de trabalho: `sermax-platform-windows-autostart-20261120`

## Contexto

O launcher já solicita encerramento gracioso do Uvicorn quando recebe SIGINT ou SIGTERM e aguarda a thread do servidor. Ainda não existe um comando local `--stop`.

A API HTTP não deve ganhar uma rota de desligamento sem autenticação. O encerramento também não deve depender de localizar e matar um PID, pois o PID pode ser reutilizado ou pertencer a outro processo.

## Decisão proposta

Implementar o controle de parada no Windows por um objeto Event nomeado do kernel, sem endpoint HTTP.

1. O launcher cria um evento de parada com nome no namespace da sessão local: `Local\\SERMAX.Platform.Stop.<identificador-do-usuário>`.
2. O identificador é derivado do SID do usuário Windows atual, nunca do nome de exibição ou de variáveis de ambiente não verificadas.
3. O evento é criado com DACL explícita, concedendo acesso somente ao SID do usuário atual. A ACL não deve herdar permissões amplas.
4. O launcher mantém uma thread de espera para o evento. Ao receber o sinal, chama o mesmo caminho de encerramento gracioso já usado por SIGINT/SIGTERM, define `server.should_exit` e aguarda o worker dentro do timeout configurado.
5. O comando `--stop` abre o evento existente com permissão mínima para sinalização e chama `SetEvent`. Não enumera processos, não envia sinais por PID e não mata processos.
6. Se o evento não existir, o comando informa que não há instância controlável. Se a abertura ou sinalização falhar, retorna erro explícito. Não deve interpretar falha de acesso como instância parada.
7. O objeto é criado depois da aquisição do lock de instância e fechado no `finally` do ciclo de vida do launcher.
8. A implementação é Windows-only nesta etapa. Não introduzir fallback POSIX por PID.
9. O canal não é HTTP, não abre portas, não altera firewall e não habilita acesso remoto.

## Autenticação e limites

A autorização de sinalização é feita pelo controle de acesso do kernel sobre o objeto nomeado. A DACL deve conceder direitos somente ao SID atual. O nome inclui um identificador derivado do SID para separar usuários. O namespace `Local\\` limita o objeto à sessão Windows.

Um processo executado pelo mesmo usuário é considerado parte do mesmo limite de confiança e terá acesso ao comando de parada. Este mecanismo não protege contra malware executado sob a mesma conta. Usuários Windows distintos não devem conseguir abrir ou sinalizar o evento.

O comando não aceita nome de evento arbitrário, PID, caminho de processo ou destino fornecido pelo usuário. O nome é calculado internamente a partir da identidade Windows atual.

## Requisitos de implementação

- Usar APIs Win32 documentadas por meio de `ctypes`, sem adicionar dependência de terceiros.
- Converter o SID atual de forma nativa e validar erros das APIs Win32.
- Construir e aplicar uma DACL protegida, com ACE explícita para o SID atual.
- Verificar `ERROR_ALREADY_EXISTS` na criação. Nunca assumir propriedade de um evento preexistente.
- Fechar handles e liberar descritores de segurança em todos os caminhos.
- Evitar vazamento de handles entre processos.
- Aguardar o evento sem bloquear o thread principal do servidor.
- Preservar os timeouts e códigos de saída já definidos pelo launcher.
- Não registrar SID completo, tokens ou dados de autenticação em logs.

## Testes obrigatórios

1. Criação do evento com DACL explícita e sem herança ampla.
2. Evento novo não sinalizado no início.
3. Cliente da mesma identidade abre e sinaliza o evento.
4. Launcher recebe o sinal e solicita shutdown gracioso.
5. Ausência do evento retorna estado distinto de erro de permissão.
6. Falhas Win32 em criação, abertura, sinalização e espera geram erro controlado.
7. Handle e memória do descritor de segurança são liberados em sucesso e exceção.
8. Evento preexistente não é aceito como propriedade do launcher.
9. CLI `--stop` conflita com `--status` e operações de autostart.
10. Nenhum teste deve encerrar processos reais por PID.

## Fora do escopo

- Rota HTTP de desligamento.
- Acesso remoto, firewall, túnel ou autenticação de clientes Android.
- Encerramento forçado de processos.
- Alteração da instalação `C:\\SERMAX`, Terminal original, memória pessoal, configurações ou backups.
- Merge, release ou instalação.

## Implementação registrada

- `backend/windows_stop.py` obtém o SID do token primário do processo, deriva um identificador não reversível para o nome do evento e cria o objeto no namespace `Local\\`.
- A DACL protegida concede `SYNCHRONIZE` e `EVENT_MODIFY_STATE` ao SID atual. O descritor de segurança é liberado após a criação.
- O launcher mantém um monitor com espera temporizada, recebe o sinal e solicita `server.should_exit`. O encerramento aguarda o worker e respeita o timeout.
- `--stop` abre o evento da mesma conta e sessão e chama `SetEvent`. Códigos: 0 solicitação enviada, 8 evento ausente, 9 falha de controle.
- Evento preexistente com DACL restrita pode fazer `CreateEventW` retornar `ERROR_ACCESS_DENIED` em vez de `ERROR_ALREADY_EXISTS`. Ambos os caminhos agora recusam assumir a propriedade do objeto.
- Testes incluem política SDDL, sinalização real entre handles da mesma conta, colisão de nome, evento ausente, CLI e monitoramento do encerramento.
- A validação entre duas contas Windows distintas e a homologação no PC do usuário permanecem pendentes.
## Critérios de aceite

A implementação só será considerada pronta após os testes automatizados no runner Windows, validação de que o launcher recebe o evento e encerra o Uvicorn dentro do timeout, revisão da DACL efetiva e CI completo da branch. O teste automatizado com uma única conta não comprova isolamento entre duas contas Windows; essa validação deve permanecer registrada como pendência até existir ambiente dedicado com duas identidades.
