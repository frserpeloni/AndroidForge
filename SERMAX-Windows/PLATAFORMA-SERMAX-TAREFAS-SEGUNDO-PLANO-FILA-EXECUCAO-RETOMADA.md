# Sistema de tarefas em segundo plano do MAX

**Projeto:** SERMAX  
**Documento:** Especificação técnica e operacional  
**Estado:** Planejamento documental, não implementado  
**Branch de referência:** `sermax-windows-integration-20261029`

## 1. Objetivo

Definir o comportamento de tarefas que continuam em execução ou aguardam processamento enquanto o usuário navega pela Plataforma SERMAX. O sistema deve permitir acompanhar tarefas, compreender seu estado, cancelar operações com segurança e retomar trabalho após interrupções sem duplicar efeitos.

Este documento não autoriza implementação, execução no computador do usuário, alteração do núcleo, criação de serviços ou mudança de dados existentes.

## 2. Princípios

1. Toda tarefa recebe identificador único e estado persistente.
2. A interface nunca deve indicar conclusão antes da confirmação do executor.
3. Uma tarefa não pode ser executada simultaneamente por dois trabalhadores.
4. Repetição de solicitação deve ser controlada por chave de idempotência.
5. Cancelamento depende do tipo e do ponto de execução.
6. Resultado incerto não deve provocar repetição automática.
7. Prioridade não pode quebrar dependências nem regras de autorização.
8. Operações críticas exigem aprovação vinculada à ação específica.
9. O núcleo SERMAX deve permanecer serializado até comprovação de isolamento de contexto.
10. Logs e histórico de tarefas não substituem a memória do usuário.
11. O sistema deve funcionar inicialmente em processo local, com limites de concorrência conservadores.
12. Falha de uma tarefa não deve derrubar a fila inteira.

## 3. Categorias de tarefa

- **Interativa:** resposta aguardada pelo usuário, prioridade de latência.
- **Pesquisa:** coleta e análise de fontes autorizadas.
- **Processamento:** análise de arquivos e dados autorizados.
- **Manutenção:** verificações operacionais e diagnósticos somente leitura.
- **Agendada:** execução iniciada por horário ou condição previamente configurada.
- **Ação externa:** envio, publicação ou operação em serviço externo, sempre sujeita a autorização.
- **Crítica:** operação que altera ou exclui dados, configurações, memória, backups ou componentes funcionais.

A categoria não concede permissão. A política de permissões e aprovações continua sendo a autoridade para decidir se a tarefa pode avançar.

## 4. Modelo de estados

Estados persistentes propostos:

- `created`: tarefa registrada.
- `queued`: aguardando recurso.
- `waiting_approval`: aguardando autorização.
- `ready`: aprovada e apta a executar.
- `running`: execução iniciada.
- `cancellation_requested`: pedido de cancelamento recebido.
- `cancelled`: cancelamento confirmado.
- `succeeded`: execução concluída com resultado confirmado.
- `failed`: falha confirmada.
- `retry_wait`: aguardando nova tentativa autorizada pela política.
- `unknown_outcome`: execução iniciada, mas sem confirmação conclusiva.
- `blocked`: impedida por dependência, permissão ou pré-condição.
- `expired`: tarefa perdeu validade antes de iniciar.

Toda transição deve ser validada pelo gerenciador. Transições inválidas devem ser rejeitadas e registradas.

## 5. Registro da tarefa

Cada registro deve conter:

- ID imutável;
- tipo e categoria;
- descrição curta apresentada ao usuário;
- origem da solicitação;
- projeto e conversa associados, quando aplicável;
- prioridade;
- estado atual;
- data de criação, início, atualização e conclusão;
- dependências;
- chave de idempotência;
- executor e versão do adaptador;
- política de autorização aplicada;
- aprovação associada, quando exigida;
- prazo e limite de execução;
- tentativas realizadas;
- resultado resumido ou referência ao resultado;
- código de erro sanitizado;
- indicação de cancelabilidade;
- versão do esquema do registro.

Não duplicar conteúdo privado desnecessariamente no registro. Anexos e resultados extensos devem ser referenciados por identificadores internos protegidos.

## 6. Fila e prioridades

A primeira versão deve adotar fila persistente FIFO por padrão, com prioridades limitadas e explícitas.

Ordem conceitual:
1. tarefas interativas prontas;
2. tarefas aprovadas com prazo operacional;
3. pesquisas e processamentos comuns;
4. tarefas de manutenção;
5. tarefas agendadas sem urgência.

Regras:
- tarefas críticas não ganham prioridade para contornar aprovação;
- dependências precisam estar concluídas antes da tarefa dependente;
- prioridade não permite ultrapassar uma tarefa já em execução no núcleo serializado;
- evitar starvation com envelhecimento controlado da prioridade;
- limites de fila devem impedir consumo ilimitado de memória e armazenamento;
- ao atingir limite, rejeitar ou pausar novas tarefas com mensagem clara.

Os valores numéricos de concorrência e tamanho de fila devem ser definidos após inventário e benchmark autorizados. Não presumir capacidade do computador.

## 7. Execução e isolamento

O gerenciador de tarefas deve ser separado da interface e da camada de API.

Fluxo conceitual:
1. validar solicitação e identidade;
2. classificar tarefa e recursos necessários;
3. verificar permissões e aprovações;
4. validar dependências;
5. persistir a tarefa;
6. inserir na fila;
7. reservar o recurso executor;
8. iniciar execução com identificador de correlação;
9. registrar progresso e eventos;
10. persistir resultado final;
11. liberar recurso e atualizar dependências.

Até que o núcleo demonstre isolamento de sessão e histórico, chamadas ao núcleo devem usar exclusão mútua e execução serializada. Não compartilhar variáveis globais de conversa entre tarefas concorrentes.

A interface, API e trabalhadores não devem acessar diretamente arquivos internos do núcleo fora dos adaptadores definidos.

## 8. Progresso e acompanhamento

O progresso deve ser apresentado em etapas verificáveis, não em percentuais inventados.

Exemplos:
- aguardando na fila;
- aguardando autorização;
- preparando recursos;
- consultando motor;
- processando resultado;
- salvando resultado;
- concluída.

Percentual só deve aparecer quando o executor fornecer medida confiável. Caso contrário, mostrar etapa atual e horário da última atualização.

O usuário deve conseguir abrir detalhes da tarefa e consultar:
- estado;
- descrição;
- início e duração;
- dependências;
- recurso em uso;
- progresso confirmado;
- resultado ou erro;
- histórico de transições.

## 9. Cancelamento

O cancelamento deve ser cooperativo e depender do executor.

- Antes do início: remover da fila e marcar `cancelled`.
- Aguardando aprovação: encerrar a solicitação e invalidar a aprovação pendente.
- Durante execução cancelável: solicitar interrupção e aguardar confirmação.
- Durante operação não cancelável: informar que o pedido foi recebido, mas que a etapa atual precisa terminar.
- Após efeito externo iniciado: não presumir que cancelar localmente desfaz o efeito.
- Com resultado incerto: marcar `unknown_outcome` e impedir reenvio automático.

O botão de cancelar deve indicar o resultado real do pedido, não assumir cancelamento imediato.

## 10. Retentativas e idempotência

Retentativas só são permitidas quando:
- o erro é classificado como transitório;
- a tarefa é segura para repetição;
- o limite de tentativas não foi atingido;
- a chave de idempotência é preservada;
- a política de autorização continua válida.

Não repetir automaticamente:
- envio externo com confirmação ausente;
- gravação cuja conclusão seja incerta;
- migração de dados;
- exclusão ou alteração crítica;
- chamada ao núcleo que possa duplicar efeitos ou contexto.

Cada tentativa deve ter número, início, fim e resultado próprios. A política deve aplicar espera progressiva e limite máximo, sem loops.

## 11. Retomada após reinício ou falha

Na inicialização, o gerenciador deve reconciliar tarefas persistidas:

- `created`, `queued` e `ready`: validar novamente dependências e autorização antes de agendar.
- `waiting_approval`: manter pendente até expiração ou decisão.
- `running`: classificar como `unknown_outcome`, salvo se o executor provar que não iniciou efeito.
- `cancellation_requested`: consultar executor e confirmar estado; não assumir cancelamento.
- estados terminais: preservar sem reexecução.
- `retry_wait`: reavaliar política, validade e idempotência.

A retomada nunca deve duplicar uma execução cujo resultado anterior seja desconhecido. A reconciliação deve ser transacional e auditável.

## 12. Dependências entre tarefas

Tarefas podem depender de resultados anteriores. O grafo de dependências deve:
- rejeitar ciclos;
- identificar dependências falhas ou canceladas;
- bloquear tarefas descendentes quando necessário;
- permitir retomada somente após resolver a dependência;
- registrar a razão do bloqueio.

Não iniciar tarefa dependente com base em resultado parcial não confirmado, salvo se o contrato declarar explicitamente esse comportamento.

## 13. Limites e proteção do equipamento

A primeira versão deve privilegiar baixo consumo e execução serializada do núcleo.

Prever:
- limite configurável de trabalhadores;
- fila persistente limitada;
- timeout por categoria;
- cancelamento cooperativo;
- limite de tamanho de entrada e resultado;
- controle de espaço em disco;
- pausa de tarefas não urgentes em condição de pressão de recursos, se houver sinal confiável;
- encerramento gracioso;
- recuperação após encerramento inesperado.

Não fixar números de CPU, RAM ou concorrência antes de medir o equipamento com autorização específica.

## 14. Interface do usuário

A interface deve manter a tela principal limpa.

Exibir um indicador compacto de tarefas ativas. Ao abrir, apresentar lista com:
- nome curto;
- estado;
- etapa atual;
- horário;
- projeto relacionado;
- ação disponível, como abrir, cancelar ou consultar resultado.

Não criar painel permanente carregado de gráficos. Filtros e detalhes avançados ficam sob demanda.

Notificações devem ocorrer em eventos relevantes: conclusão, falha, pedido de aprovação, bloqueio ou resultado incerto. Não notificar a cada etapa rotineira.

## 15. Segurança e autorização

Toda tarefa deve herdar identidade, projeto, escopo de dados e política de autorização da solicitação que a originou.

- Classe automática: somente tarefas autorizadas de consulta e leitura.
- Classe de confirmação: edição, instalação, configuração ou envio externo.
- Classe crítica: exclusão, memória, histórico, backups, integridade e arquivos essenciais, com autorização expressa específica.

Aprovação deve identificar exatamente a tarefa, os recursos, o impacto e a versão do plano aprovado. Mudança material no escopo invalida a aprovação anterior.

O trabalhador deve validar a aprovação imediatamente antes da ação protegida, não somente ao enfileirar.

## 16. Observabilidade e auditoria

Registrar:
- criação e origem;
- mudanças de estado;
- posição e prioridade;
- início e fim;
- executor e recurso selecionado;
- aprovações;
- cancelamentos;
- tentativas;
- falhas e timeouts;
- retomadas;
- resultado incerto;
- intervenção manual.

Usar IDs de correlação. Não registrar credenciais, tokens ou conteúdo privado integral. Eventos de auditoria devem ser append-only sempre que tecnicamente viável.

## 17. Critérios de aceite e testes planejados

Os testes abaixo são requisitos futuros. **Nenhum foi executado por este documento.**

1. Persistir tarefa antes de colocá-la em execução.
2. Impedir duas execuções simultâneas da mesma tarefa.
3. Preservar FIFO quando prioridades forem iguais.
4. Respeitar dependências.
5. Rejeitar ciclos no grafo.
6. Bloquear tarefa sem aprovação exigida.
7. Invalidar aprovação quando o escopo mudar.
8. Serializar chamadas ao núcleo enquanto não houver isolamento comprovado.
9. Exibir progresso sem inventar percentuais.
10. Cancelar tarefa ainda não iniciada.
11. Confirmar cancelamento cooperativo de tarefa em execução.
12. Não afirmar cancelamento de operação externa já iniciada.
13. Marcar execução interrompida como `unknown_outcome`.
14. Não repetir automaticamente resultado incerto.
15. Aplicar limite de retentativas e espera progressiva.
16. Preservar chave de idempotência entre tentativas.
17. Retomar tarefas seguras após reinício.
18. Revalidar permissões e dependências na retomada.
19. Impedir starvation com política documentada.
20. Respeitar limites de fila e armazenamento.
21. Manter falha isolada sem interromper toda a fila.
22. Registrar transições e ações para auditoria.
23. Manter interface responsiva durante execução em segundo plano.
24. Encerrar trabalhadores de forma controlada.
25. Preservar núcleo, Terminal, memória, histórico e backups.

## 18. Dependências documentais

Esta especificação depende e complementa:
- contrato preliminar da API;
- operação local da primeira versão;
- integração controlada com o núcleo;
- recuperação de falhas e retomada;
- permissões, aprovações e auditoria;
- identidade, autenticação e sessões;
- sincronização e conflitos de dados;
- armazenamento e integridade;
- seleção automática de modelos e ferramentas;
- monitoramento, diagnóstico e saúde operacional;
- política de atualização, backup e rollback.

Em caso de conflito, prevalecem as regras mais restritivas de integridade, autorização e preservação.

## 19. Estado e autorização

**Estado:** especificação documental.  
**Código:** não implementado.  
**Testes:** planejados, não executados.  
**Execução no computador do usuário:** não realizada.  
**Alterações no núcleo, Terminal, memória ou backups:** nenhuma.  
**Autorização de implementação:** continua pendente de autorização expressa específica.
