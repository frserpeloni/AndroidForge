# SERMAX Platform, recuperação de falhas e retomada segura

**Estado:** especificação técnica documental. Não implementada.
**Ordem:** ORDEM-SERMAX-PLATAFORMA-002.
**Branch:** `sermax-windows-integration-20261029`.
**Escopo:** recuperação do serviço experimental, fila e solicitações após encerramento normal, falha ou reinicialização do Windows.
**Dependências:** operação local da primeira versão e integração controlada com o núcleo existente.

## 1. Objetivo

Definir como a Plataforma SERMAX preservará o estado das conversas e tratará solicitações em andamento quando ocorrer falha do serviço, encerramento forçado, queda de energia ou reinicialização do computador.

O protocolo prioriza integridade e prevenção de duplicidade. Não promete retomar uma inferência interrompida dentro do modelo. Uma execução só será retomada automaticamente quando houver prova de que ainda não foi iniciada; execuções iniciadas e sem resultado confirmado serão classificadas como estado incerto e exigirão tratamento seguro.

Este documento não autoriza implementação, criação de diretórios, alterações no núcleo, instalação ou execução de testes.

## 2. Princípios de recuperação

1. Persistir o recebimento antes de confirmar a solicitação à interface.
2. Manter estados explícitos e transições auditáveis.
3. Nunca presumir que uma execução terminou porque o processo do serviço caiu.
4. Nunca reenviar automaticamente uma solicitação cujo início no núcleo não esteja comprovadamente ausente.
5. Nunca apresentar resposta parcial como resposta concluída.
6. Preservar mensagens do usuário mesmo quando o núcleo falhar.
7. Não alterar memória pessoal, histórico do Terminal ou arquivos originais.
8. Não remover registros de execução incerta durante recuperação automática.

## 3. Registro persistente mínimo

Cada solicitação deverá possuir registro próprio no banco experimental:

| Campo | Finalidade |
|---|---|
| request_id | Chave única de idempotência |
| session_id | Sessão que originou a solicitação |
| conversation_id | Conversa associada |
| message_id | Mensagem do usuário preservada |
| state | Estado atual |
| created_at | Recebimento |
| queued_at | Entrada na fila |
| execution_started_at | Início confirmado pelo adaptador |
| execution_finished_at | Fim confirmado |
| response_id | Resposta vinculada, se concluída |
| attempt_number | Número de tentativa autorizada |
| worker_instance_id | Instância do serviço que assumiu a execução |
| lease_expires_at | Expiração da posse temporária da execução |
| error_code | Código técnico, se houver |

O registro não deve conter credenciais, tokens ou cópias desnecessárias de memória pessoal. O texto da mensagem e da resposta ficará na tabela própria de mensagens, com vínculo por identificador.

## 4. Máquina de estados para recuperação

Estados persistentes:

- `received`: solicitação gravada, ainda não validada.
- `validated`: entrada validada, ainda fora da fila.
- `queued`: aguardando execução.
- `claimed`: worker reservou a solicitação, mas ainda não confirmou chamada ao núcleo.
- `running`: chamada ao núcleo iniciada.
- `completed`: resposta final persistida.
- `failed`: falha confirmada.
- `cancel_requested`: cancelamento solicitado.
- `cancelled`: executor confirmou encerramento.
- `interrupted`: serviço ou executor encerrou sem resultado final confirmado.
- `unknown_outcome`: não há prova suficiente para afirmar se o núcleo processou a solicitação.
- `rejected`: solicitação recusada por limite ou validação.

Transições principais:

```text
received -> validated -> queued -> claimed -> running -> completed
                                      |          |
                                      |          +-> failed
                                      |          +-> cancel_requested
                                      |          +-> interrupted
                                      |
                                      +-> queued, se a reserva expirou
                                          e a chamada ao núcleo não começou

interrupted -> unknown_outcome
unknown_outcome -> completed, se resultado original for recuperado
unknown_outcome -> failed, se falha for comprovada
unknown_outcome -> aguardando decisão do usuário, se resultado permanecer incerto
```

A transição de `claimed` para `queued` só será permitida quando o registro provar que o adaptador ainda não iniciou a chamada ao núcleo. Se a fronteira entre gravação e chamada não permitir essa prova, a solicitação será classificada como `unknown_outcome`.

## 5. Escrita transacional

As operações que alteram estado e fila deverão ocorrer em transações do banco experimental.

### Recebimento

1. Validar tamanho e formato da mensagem.
2. Gerar `request_id` no serviço.
3. Gravar mensagem e solicitação na mesma transação.
4. Confirmar a transação.
5. Só então informar à interface que a mensagem foi recebida.

Se a gravação falhar, a API não confirmará recebimento.

### Reserva

1. Selecionar a próxima solicitação elegível.
2. Marcar como `claimed`.
3. Registrar `worker_instance_id` e prazo de lease.
4. Confirmar a transação.
5. Verificar novamente a posse antes de chamar o adaptador.

### Início da execução

O adaptador deverá registrar o início antes de encaminhar a chamada ao núcleo, quando tecnicamente possível. Se não houver operação atômica entre registro e chamada externa, a janela de incerteza será documentada e tratada como `unknown_outcome` após queda do processo.

### Conclusão

1. Receber resposta do núcleo.
2. Gravar resposta e estado `completed` na mesma transação.
3. Confirmar a transação.
4. Só então enviar a resposta à interface.

Se a resposta chegar, mas a gravação falhar, o serviço deverá tentar preservar o resultado em mecanismo temporário seguro ou classificar o caso como incerto. Não deverá executar novamente o núcleo por padrão.

## 6. Recuperação na inicialização

Ao iniciar, o supervisor deverá:

1. Confirmar que não existe outra instância ativa.
2. Verificar versão e integridade do banco experimental.
3. Adquirir uma nova identificação de instância.
4. Ler solicitações não terminais.
5. Verificar leases e estado do worker anterior.
6. Classificar cada registro conforme as regras desta especificação.
7. Recolocar na fila somente solicitações comprovadamente não iniciadas.
8. Bloquear reenvio automático de solicitações com resultado incerto.
9. Exibir um resumo de recuperação sem expor conteúdo privado em logs.
10. Liberar a interface para novas mensagens após concluir a reconciliação.

Se a integridade do banco não puder ser confirmada, o serviço deverá iniciar em modo de proteção, sem aceitar gravações, preservando os arquivos para diagnóstico e recuperação.

## 7. Matriz de recuperação

| Situação encontrada | Ação automática | Reenvio ao núcleo |
|---|---|---|
| `received` persistido | Validar e encaminhar à fila | Sim, após validação |
| `validated` sem reserva | Inserir na fila | Sim |
| `queued` | Manter na fila | Sim |
| `claimed` com lease expirado e prova de que não iniciou | Retornar à fila | Sim |
| `running` sem resultado | Marcar `unknown_outcome` | Não |
| `completed` com resposta persistida | Exibir resposta existente | Não |
| `failed` confirmado | Exibir falha | Não, salvo nova solicitação autorizada |
| `cancel_requested` sem confirmação | Consultar executor; manter bloqueio | Não |
| `cancelled` confirmado | Encerrar registro | Não |
| Banco corrompido ou inconsistente | Bloquear escrita e preservar cópia | Não |

## 8. Idempotência e duplicidade

A chave `request_id` deverá ter restrição de unicidade no banco.

Regras:

- Reenvio HTTP com o mesmo identificador retorna o registro existente.
- Duplo clique na interface não cria duas solicitações.
- Atualização da página não reenvia mensagem já confirmada.
- Reinício do serviço não cria novo identificador para solicitação antiga.
- Uma resposta final só poderá ser vinculada uma vez ao mesmo `request_id`.
- Uma tentativa adicional exige novo registro de tentativa e decisão explícita conforme a classificação anterior.
- O sistema não tratará idempotência da API como prova de idempotência do modelo ou do núcleo.

## 9. Execução incerta e decisão do usuário

Uma solicitação em `unknown_outcome` poderá ter sido processada pelo núcleo antes da falha. Reenviá-la poderá gerar resposta duplicada, gasto adicional de recursos ou efeito repetido em ferramenta.

A interface deverá informar:

- Que a execução foi interrompida.
- Que não foi possível confirmar o resultado.
- Se existe resposta recuperada.
- Que reenviar iniciará uma nova execução.

Ações disponíveis conceitualmente:

1. Consultar novamente o estado, sem executar o núcleo.
2. Marcar como encerrada sem resposta, mantendo o histórico.
3. Enviar novamente como nova solicitação, após confirmação explícita.

Não haverá botão de repetição automática para estado incerto.

## 10. Cancelamento e reinicialização

Se houver cancelamento solicitado antes do início da execução, a solicitação poderá ser marcada como `cancelled` sem chamar o núcleo.

Se a execução já começou:

- O serviço solicitará cancelamento ao executor, se houver mecanismo confiável.
- A fila permanecerá bloqueada enquanto o executor ainda puder estar processando.
- Se o processo cair antes da confirmação, a solicitação será `unknown_outcome`.
- A reinicialização não interpretará ausência de processo como prova de que nenhum efeito ocorreu.

## 11. Integridade, backup e restauração

Antes de migrações do banco experimental:

- Criar backup consistente.
- Registrar versão do esquema, data, tamanho e SHA-256.
- Preservar o arquivo original do backup.
- Validar restauração em diretório separado.
- Comparar contagens de solicitações, mensagens e respostas.
- Verificar vínculos entre mensagens e solicitações.
- Não restaurar banco experimental sobre diretórios originais do SERMAX.

Se a recuperação exigir intervenção manual, preservar banco, WAL e logs relacionados antes de qualquer tentativa de reparo. Não executar reparo destrutivo automático.

## 12. Limites de execução e recursos

A recuperação deverá respeitar:

- Uma única instância ativa do supervisor.
- Uma única chamada ao núcleo por vez, até prova de isolamento.
- Limite configurado de fila.
- Limites separados para espera, execução e lease.
- Política de backoff para falhas transitórias do serviço, sem repetir inferência incerta.
- Proteção contra ciclo infinito de reinicialização.
- Verificação de espaço livre antes de operações de escrita relevantes.

Valores numéricos de timeout, lease, backoff e capacidade da fila continuam pendentes de medição e teste. Não fixar números arbitrários nesta especificação.

## 13. Observabilidade da recuperação

Registrar:

- Instância anterior e atual.
- Horário de início da recuperação.
- Quantidade de solicitações por estado.
- Solicitações recolocadas na fila e justificativa.
- Solicitações classificadas como incertas.
- Falhas de integridade e backup.
- Tempo total de reconciliação.

Não registrar conteúdo integral de mensagens, respostas, arquivos ou segredos.

## 14. Plano de validação futuro

Todos os testes abaixo estão planejados e **não foram executados**.

| ID | Cenário | Critério de aceite |
|---|---|---|
| REC-01 | Queda após recebimento persistido | Mensagem aparece após reinício |
| REC-02 | Queda antes da reserva | Solicitação entra na fila uma vez |
| REC-03 | Queda após reserva, antes do início | Recolocação segura, sem duplicidade |
| REC-04 | Queda durante chamada ao núcleo | Estado incerto, sem reenvio automático |
| REC-05 | Queda após resposta, antes da persistência | Resultado tratado como incerto, sem nova chamada automática |
| REC-06 | Queda após persistência da resposta | Resposta reaparece sem nova execução |
| REC-07 | Duplo clique | Uma solicitação persistida |
| REC-08 | Reenvio do mesmo request_id | Registro original retornado |
| REC-09 | Lease expirado | Somente tarefa comprovadamente não iniciada é liberada |
| REC-10 | Cancelamento durante execução | Fila bloqueada até confirmação ou classificação incerta |
| REC-11 | Banco inconsistente | Serviço entra em modo de proteção |
| REC-12 | Restauração de backup | Contagens e vínculos conferidos |
| REC-13 | Reinício do Windows | Reconciliação concluída antes de aceitar novas gravações |
| REC-14 | Duas instâncias do supervisor | Segunda instância impedida |
| REC-15 | Falta de espaço | Nenhuma conclusão é confirmada sem persistência |

## 15. Dependências e decisões pendentes

Antes da implementação:

1. Confirmar tecnologia e configuração do banco experimental.
2. Definir mecanismo de lock/lease compatível com o banco escolhido.
3. Determinar se o núcleo oferece correlação de execução e consulta de resultado.
4. Determinar se o adaptador consegue confirmar o instante de início da chamada.
5. Definir timeouts, lease, backoff e limite de fila após medição.
6. Definir mecanismo de cópia consistente e restauração.
7. Validar o comportamento de encerramento do processo do núcleo.
8. Obter autorização expressa para criar `SERMAX-Platform/` e implementar o protótipo isolado.

## 16. Estado e limites

Este documento registra o protocolo proposto. Não cria código, banco, serviço, supervisor ou instalador. Não executa agentes nem testes. Não altera núcleo, Terminal, memórias, histórico, backups, instalação local, workflows ou branch `main`.

A PR #2 permanece em rascunho. Nenhum merge está autorizado por este documento. Drive Connect permanece fora do escopo e sem implementação.
