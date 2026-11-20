# SERMAX Platform, integração controlada com o núcleo existente

**Estado:** especificação técnica documental. Não implementada.
**Ordem:** ORDEM-SERMAX-PLATAFORMA-002.
**Branch:** `sermax-windows-integration-20261029`.
**Escopo:** contrato entre o serviço da Plataforma SERMAX e o núcleo atual.
**Dependências:** arquitetura GUI, contrato preliminar da API, especificação operacional da interface e operação local da primeira versão.

## 1. Objetivo e limite

Definir uma fronteira controlada entre a futura interface gráfica e o núcleo SERMAX existente. A plataforma deverá encaminhar solicitações ao núcleo sem reescrever, substituir ou assumir propriedade sobre seus componentes internos.

Esta especificação não autoriza código, criação de diretórios, alterações no núcleo, instalação ou execução de testes.

## 2. Fatos técnicos considerados

A documentação e a auditoria anteriores registram:

- O núcleo Windows existente está em `SERMAX-Windows/`.
- O roteamento atual tenta OpenJarvis primeiro e mantém Ollama como fallback.
- OpenJarvis é executado em processo Python isolado, enquanto o núcleo SERMAX usa Python 3.14.
- O worker OpenJarvis auditado está configurado para o agente `orchestrator`, com allowlist `calculator` e `think` e limite de quatro turnos. A seleção do agente não é dinâmica pelo MAX.
- Ollama é acessado pelo endpoint local `http://127.0.0.1:11434/api/chat`.
- A auditoria identificou estado global de sessão e histórico no núcleo. O isolamento entre chamadas concorrentes não está comprovado.
- O Terminal original e a memória pessoal existente devem permanecer preservados.
- A memória neural do Pestinha tem armazenamento separado.

Esses pontos descrevem o estado auditado. A implementação futura deverá conferir novamente os arquivos e suas assinaturas antes de integrar.

## 3. Princípio de integração

A plataforma conversa com um adaptador. O adaptador conversa com o núcleo. A interface nunca importa módulos internos do núcleo diretamente.

Fluxo lógico:

```text
Interface gráfica
      |
      v
API da Plataforma
      |
      v
Gerenciador de solicitações
      |
      v
Fila serializada
      |
      v
Adaptador do núcleo
      |
      v
Núcleo SERMAX existente
      |
      +----> OpenJarvis, conforme roteamento atual
      |
      +----> Ollama, conforme fallback atual
```

O adaptador será a única fronteira autorizada para chamadas da plataforma ao núcleo. Não haverá segunda instância concorrente do núcleo na primeira versão.

## 4. Responsabilidades por camada

| Camada | Responsabilidade | Fora de sua responsabilidade |
|---|---|---|
| Interface | Capturar mensagem, mostrar estado e apresentar resposta | Escolher caminhos internos ou acessar memória |
| API | Validar entrada, sessão e autorização | Executar lógica do modelo diretamente |
| Gerenciador | Criar ID, controlar estado, fila, timeout e cancelamento | Alterar arquivos originais |
| Adaptador | Traduzir contrato da plataforma para a chamada real do núcleo | Reimplementar roteamento ou memória |
| Núcleo | Processar solicitação conforme comportamento existente | Gerenciar estado visual da plataforma |
| Persistência experimental | Registrar conversas e estados próprios | Substituir histórico ou memória original |

## 5. Contrato mínimo do adaptador

O contrato é conceitual. Os nomes abaixo não afirmam que funções equivalentes já existam no núcleo.

### Entrada

Cada chamada deverá receber:

- `request_id`: identificador único e não reutilizável.
- `session_id`: identificador da sessão da plataforma.
- `conversation_id`: conversa à qual a mensagem pertence.
- `message`: texto validado da solicitação.
- `created_at`: horário de criação registrado pelo serviço.
- `model_preference`: preferência manual opcional, quando suportada e autorizada.
- `tool_policy`: política de ferramentas definida pelo serviço, sem conceder acesso adicional ao núcleo.

A plataforma não enviará caminhos arbitrários de arquivos, comandos de sistema, tokens ou conteúdo de memória pessoal como parâmetros implícitos.

### Saída

O adaptador deverá devolver um resultado estruturado:

- `request_id`
- `status`
- `response_text`, quando houver
- `backend_used`, quando identificável pelo núcleo
- `started_at`
- `finished_at`
- `error_code`, em caso de falha
- `error_summary`, sem segredos ou dados sensíveis

A saída não deverá declarar ferramenta ou modelo como utilizado sem confirmação do núcleo ou do adaptador.

## 6. Ciclo de vida da solicitação

Estados previstos:

1. `received`: API recebeu a mensagem.
2. `validated`: entrada e sessão foram validadas.
3. `queued`: solicitação entrou na fila.
4. `running`: adaptador iniciou a chamada ao núcleo.
5. `completed`: resposta foi recebida e persistida.
6. `failed`: chamada terminou com erro.
7. `cancel_requested`: cancelamento solicitado pelo usuário.
8. `cancelled`: cancelamento confirmado pelo executor.
9. `timed_out`: limite de tempo atingido e execução encerrada ou isolada com segurança.

Transições inválidas serão rejeitadas. Uma solicitação terminal não retornará a `queued` ou `running`. Uma repetição de envio com o mesmo `request_id` retornará o estado já registrado, sem iniciar outra chamada.

## 7. Concorrência e fila

Até existir prova de isolamento de contexto no núcleo:

- Uma chamada ao núcleo por vez.
- Fila FIFO na primeira versão.
- Cada item mantém sessão e conversa associadas.
- O adaptador não troca o contexto de uma chamada em andamento.
- O serviço não executa duas chamadas em threads ou processos concorrentes contra o mesmo estado global.
- Limite máximo da fila será configurado e documentado antes da implementação.
- Ao atingir o limite, a API rejeitará novas solicitações com estado explícito, sem descartá-las silenciosamente.
- A fila não será tratada como mecanismo de persistência. Os estados serão registrados no armazenamento experimental.

A fila FIFO é uma decisão de segurança inicial, não uma garantia de desempenho. Testes de isolamento poderão fundamentar revisão futura.

## 8. Isolamento de sessões e conversas

A primeira versão será de usuário único, mas ainda deverá separar os identificadores de sessão e conversa.

Regras:

- A API determina a sessão autenticada. Não confia em permissões informadas pelo cliente.
- Cada solicitação fica vinculada a uma sessão e conversa.
- A interface não escolhe diretamente variáveis globais do núcleo.
- Enquanto a chamada estiver em execução, nenhuma outra solicitação poderá sobrescrever o contexto compartilhado.
- Se o núcleo atual não oferecer contexto isolado por conversa, a plataforma deverá manter a serialização e documentar a limitação.
- Não misturar histórico experimental da plataforma com histórico original do Terminal.
- Não gravar automaticamente mensagens da plataforma na memória pessoal do SERMAX.

## 9. Memória e persistência

A primeira integração não fará migração nem escrita na memória pessoal existente.

Separação obrigatória:

| Dado | Destino inicial |
|---|---|
| Conversas da nova interface | Banco experimental da plataforma |
| Estado da fila e execução | Banco experimental da plataforma |
| Preferências da interface | Configuração experimental |
| Memória pessoal existente | Mantida no local atual, sem escrita pela plataforma |
| Histórico do Terminal | Mantido no mecanismo atual |
| Memória neural Pestinha | Arquivo e mecanismo próprios |

Uma futura integração de memória exige contrato próprio, política de consentimento, auditoria de origem e autorização específica.

## 10. Seleção de modelo e ferramentas

A seleção híbrida definida para a Plataforma SERMAX deverá respeitar a capacidade real do núcleo:

- MAX escolhe automaticamente modelo ou ferramenta quando o roteador existente oferecer essa capacidade.
- O usuário mantém seleção manual nas opções efetivamente suportadas.
- A interface mostra o motor confirmado para a execução.
- A plataforma não simula seleção dinâmica de agentes que ainda não existe.
- A seleção fixa do worker OpenJarvis permanece identificada como fixa até implementação e validação de um roteador dinâmico.
- A preferência manual não poderá contornar allowlists, limites ou permissões do núcleo.
- Fallback para Ollama só será informado quando ocorrer de fato.

A evolução do roteador será tratada em especificação separada. Esta integração não altera a ordem OpenJarvis/Ollama existente.

## 11. Timeout, cancelamento e falhas

O serviço deverá definir timeout de fila e timeout de execução como limites distintos.

- Timeout de fila: encerra a espera antes de iniciar o núcleo, se a política assim determinar.
- Timeout de execução: solicita interrupção controlada.
- Cancelamento: só será apresentado como concluído após confirmação de encerramento.
- Se a chamada não aceitar interrupção segura, o serviço marcará cancelamento pendente e não iniciará outra chamada até confirmar que o executor anterior terminou ou foi isolado.
- Falha do OpenJarvis deverá seguir o fallback já implementado no núcleo. O adaptador não criará um fallback paralelo.
- Falha do Ollama deverá retornar erro claro.
- Falha de persistência impedirá a confirmação de conclusão ao cliente até que o estado esteja consistente.
- Exceções não deverão expor tokens, caminhos privados, variáveis de ambiente ou conteúdo integral de arquivos.

## 12. Observabilidade e auditoria

Registrar eventos técnicos mínimos:

- ID da solicitação.
- ID da sessão e conversa, com identificadores não sensíveis.
- Horário de entrada, início e término.
- Mudanças de estado.
- Backend confirmado.
- Duração da fila e da execução.
- Código de falha.
- Resultado do cancelamento.

Não registrar por padrão:

- Senhas, tokens ou chaves de API.
- Conteúdo integral de mensagens.
- Conteúdo de arquivos anexados.
- Memória pessoal.
- Variáveis de ambiente completas.

A configuração de retenção dos logs será definida antes da implementação.

## 13. Segurança da fronteira

- O adaptador não aceitará caminho de arquivo arbitrário vindo da interface.
- Não haverá execução de comandos de shell por meio do contrato de conversa.
- A API validará tamanho e tipo dos campos.
- A origem local e a sessão serão verificadas em cada operação.
- CORS ficará restrito à origem da interface.
- Operações de edição, instalação ou envio externo exigirão confirmação.
- Exclusão, alteração de memória, backup e integridade exigirão autorização expressa específica.
- O adaptador não terá permissão para sobrescrever o núcleo, Terminal, memória ou backups originais.

## 14. Plano de validação futuro

Os testes abaixo são critérios planejados. Nenhum foi executado por este documento.

| ID | Cenário | Critério de aceite |
|---|---|---|
| INT-01 | Mensagem simples | Uma resposta retorna vinculada ao ID correto |
| INT-02 | Duas mensagens simultâneas | Execução serializada, sem mistura de contexto |
| INT-03 | Mesmo request_id reenviado | Nenhuma segunda execução |
| INT-04 | Sessões distintas | Contextos não são cruzados |
| INT-05 | Fila cheia | Nova solicitação recebe rejeição explícita |
| INT-06 | Núcleo indisponível | Erro controlado, dados da conversa preservados |
| INT-07 | OpenJarvis falha | Fallback existente ocorre uma vez, se aplicável |
| INT-08 | Ollama indisponível | Erro identificado sem falso sucesso |
| INT-09 | Timeout | Estado final corresponde ao encerramento real |
| INT-10 | Cancelamento | Nenhuma nova chamada inicia antes da liberação do executor |
| INT-11 | Falha de persistência | Serviço não confirma conclusão inconsistente |
| INT-12 | Memória original | Hash e conteúdo permanecem inalterados |
| INT-13 | Terminal original | Inicialização e operação não são afetadas |
| INT-14 | Logs | Nenhum segredo ou conteúdo integral é gravado |
| INT-15 | Reinício do serviço | Solicitações incompletas são recuperadas sem duplicação |

## 15. Dependências e bloqueios

Antes de implementar:

1. Conferir novamente as assinaturas reais de entrada e saída do núcleo.
2. Identificar os pontos exatos de mutação do estado global de sessão e histórico.
3. Confirmar se há mecanismo confiável de cancelamento.
4. Confirmar como o núcleo informa backend e ferramenta efetivamente usados.
5. Definir limite da fila, timeouts e retenção de logs.
6. Medir o computador host conforme a especificação operacional.
7. Receber e reconciliar a candidata oficial e o backup de 28/10, se ainda disponíveis.
8. Obter autorização expressa para criar `SERMAX-Platform/` e iniciar implementação isolada.

## 16. Estado e limites

Este documento registra decisões e critérios para a futura integração. Não cria código, diretórios, banco, API, serviço ou executável. Não executa os agentes do workflow. Não altera o núcleo, Terminal, memória, histórico, backups, instalação local, workflows ou branch `main`.

A PR #2 permanece em rascunho e não deve ser mesclada sem autorização. Drive Connect permanece fora deste escopo e sem implementação.
