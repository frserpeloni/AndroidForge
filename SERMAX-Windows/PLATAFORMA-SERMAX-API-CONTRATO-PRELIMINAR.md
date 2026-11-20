# SERMAX Platform API, contrato preliminar

**Estado:** proposta para revisão. Não implementada.
**Branch de referência:** `sermax-windows-integration-20261029`.
**Dependência:** `PLATAFORMA-SERMAX-ARQUITETURA-GUI.md`.
**Objetivo:** definir a fronteira entre a interface gráfica, o serviço central e o núcleo SERMAX existente.

> Este documento descreve contratos propostos. Nenhuma rota abaixo deve ser considerada existente até implementação e testes.

## 1. Princípios

1. O núcleo SERMAX existente permanece como motor de inteligência. A API atua como camada de serviço, não como substituta do núcleo.
2. Um usuário autenticado acessa o mesmo cérebro MAX por Windows, Android e navegador.
3. Toda operação recebe identidade de usuário, sessão e, quando aplicável, projeto.
4. Conversas e arquivos de projetos diferentes permanecem isolados.
5. Leitura autorizada é automática. Alterações exigem confirmação conforme a matriz de permissões. Ações críticas exigem autorização específica.
6. A interface recebe estados funcionais simples, sem expor detalhes internos, credenciais ou logs técnicos.
7. O contrato deve permitir evolução por versão e compatibilidade retroativa controlada.

## 2. Convenções HTTP

- Prefixo proposto: `/api/v1`.
- JSON UTF-8 em requisições e respostas.
- Datas em UTC no formato ISO 8601.
- IDs opacos, estáveis e não sequenciais.
- Paginação por cursor para listas extensas.
- Erros seguem envelope comum.
- Requisições mutáveis aceitam chave de idempotência quando houver risco de repetição.
- Concorrência otimista por `version` ou `ETag`.
- Limites de tamanho para anexos, mensagens e payloads devem ser definidos antes da implementação.

### Envelope de erro proposto

```json
{
  "error": {
    "code": "permission_required",
    "message": "Esta ação exige confirmação.",
    "request_id": "req_opaque",
    "details": {}
  }
}
```

Códigos previstos: `unauthenticated`, `forbidden`, `not_found`, `conflict`, `validation_error`, `permission_required`, `rate_limited`, `service_unavailable`, `internal_error`.

## 3. Recursos e rotas propostas

### 3.1 Autenticação e dispositivos

| Método | Rota | Finalidade |
|---|---|---|
| POST | `/auth/login` | Iniciar sessão |
| POST | `/auth/logout` | Revogar sessão atual |
| POST | `/auth/refresh` | Renovar sessão |
| POST | `/auth/recovery/request` | Solicitar recuperação |
| POST | `/auth/recovery/complete` | Concluir recuperação |
| POST | `/auth/2fa/enroll` | Iniciar cadastro de segundo fator |
| POST | `/auth/2fa/verify` | Validar segundo fator |
| GET | `/devices` | Listar dispositivos autorizados |
| DELETE | `/devices/{device_id}` | Revogar dispositivo, com confirmação |

Regras:
- Senhas nunca são retornadas pela API nem registradas em logs.
- Segredos de autenticação são armazenados com hash apropriado ou mecanismo de derivação resistente a ataques.
- Tokens de sessão devem ter expiração, rotação e revogação.
- Cookies de navegador, se adotados, devem usar atributos Secure, HttpOnly e SameSite adequados.
- Recuperação de conta não deve permitir enumeração de usuários.
- 2FA é opcional, mas a arquitetura deve suportá-lo.

### 3.2 Projetos

| Método | Rota | Finalidade |
|---|---|---|
| GET | `/projects` | Listar projetos do usuário |
| POST | `/projects` | Criar projeto |
| GET | `/projects/{project_id}` | Consultar projeto |
| PATCH | `/projects/{project_id}` | Editar metadados, confirmação |
| DELETE | `/projects/{project_id}` | Solicitar exclusão, nível crítico |

Projeto contém metadados, instruções, estado, versão e referências aos seus arquivos e conversas. Exclusão deve começar como operação de arquivamento ou solicitação confirmada, com política de retenção definida; não apagar arquivos de imediato.

### 3.3 Conversas e mensagens

| Método | Rota | Finalidade |
|---|---|---|
| GET | `/projects/{project_id}/conversations` | Listar conversas do projeto |
| POST | `/projects/{project_id}/conversations` | Abrir conversa |
| GET | `/conversations/{conversation_id}` | Consultar conversa |
| PATCH | `/conversations/{conversation_id}` | Renomear ou atualizar estado |
| GET | `/conversations/{conversation_id}/messages` | Listar mensagens paginadas |
| POST | `/conversations/{conversation_id}/messages` | Enviar mensagem ao MAX |

Mensagem de entrada proposta:

```json
{
  "client_message_id": "msg_client_opaque",
  "content": "Texto enviado ao MAX",
  "attachment_ids": [],
  "model_preference": "auto",
  "tool_preferences": "auto",
  "expected_conversation_version": 12
}
```

- `model_preference=auto` mantém a seleção automática do MAX.
- Uma escolha manual deve ser validada contra os modelos habilitados.
- Preferências de ferramenta não autorizam ferramentas indisponíveis ou proibidas.
- O serviço valida acesso à conversa e ao projeto antes de chamar o núcleo.
- Repetições com o mesmo `client_message_id` não devem duplicar mensagens.

### 3.4 Estado de geração e ferramentas

| Método | Rota | Finalidade |
|---|---|---|
| GET | `/runs/{run_id}` | Consultar estado de uma resposta |
| GET | `/runs/{run_id}/events` | Receber eventos, via SSE ou mecanismo equivalente |
| POST | `/runs/{run_id}/cancel` | Solicitar cancelamento |

Estados propostos: `queued`, `running`, `waiting_approval`, `completed`, `failed`, `cancelled`.

Eventos de interface:
- `response.started`
- `tool.started`
- `tool.completed`
- `approval.required`
- `response.delta`
- `response.completed`
- `response.failed`

A interface mostra uma indicação curta, por exemplo “MAX está pesquisando” ou “MAX está analisando um arquivo”. Não exibe stack traces, prompts internos ou credenciais.

### 3.5 Arquivos e anexos

| Método | Rota | Finalidade |
|---|---|---|
| POST | `/uploads` | Iniciar envio autorizado |
| POST | `/uploads/{upload_id}/complete` | Finalizar envio e validar arquivo |
| GET | `/files` | Listar arquivos acessíveis |
| GET | `/files/{file_id}` | Consultar metadados |
| GET | `/files/{file_id}/content` | Baixar conteúdo autorizado |
| DELETE | `/files/{file_id}` | Solicitar exclusão, nível crítico |

O serviço deve validar extensão, MIME real, tamanho, nome, armazenamento, permissões e varredura de segurança conforme os recursos disponíveis. Arquivos não devem ser executados automaticamente. O caminho físico nunca é exposto ao cliente.

### 3.6 Memória

| Método | Rota | Finalidade |
|---|---|---|
| GET | `/memory` | Consultar memória autorizada |
| POST | `/memory/entries` | Propor ou registrar entrada |
| PATCH | `/memory/entries/{entry_id}` | Corrigir entrada, confirmação |
| DELETE | `/memory/entries/{entry_id}` | Remover entrada, nível crítico |

Cada entrada tem escopo `global` ou `project`, origem, estado de aprovação, versão e data. O serviço deve manter separação entre memória pessoal e memória neural do Pestinha. A migração do JSON atual exige inventário, backup e mapeamento explícito, sem sobrescrever os arquivos originais.

### 3.7 Aprovações

| Método | Rota | Finalidade |
|---|---|---|
| GET | `/approvals/pending` | Listar confirmações pendentes |
| POST | `/approvals/{approval_id}/decision` | Aprovar ou rejeitar ação |

A aprovação deve estar vinculada ao usuário, sessão, ação, alvo, escopo, resumo dos efeitos e prazo de validade. Aprovação de uma ação não autoriza ações futuras semelhantes automaticamente, quando o risco ou alvo mudar.

### 3.8 Sincronização

| Método | Rota | Finalidade |
|---|---|---|
| GET | `/sync/changes?cursor={cursor}` | Buscar alterações desde o cursor |
| POST | `/sync/ack` | Confirmar cursor aplicado |

Cada alteração tem entidade, ID, versão, operação, data e escopo. Exclusões são representadas por tombstones até expirar a política de retenção. Conflitos de edição não são resolvidos por “última gravação vence” sem regra explícita.

## 4. Modelo de dados lógico

Entidades mínimas:
- `User`: conta e estado.
- `Device`: dispositivo registrado e revogável.
- `Session`: sessão autenticada, expiração e revogação.
- `Project`: nome, instruções, versão e estado.
- `Conversation`: projeto, título, estado e versão.
- `Message`: autor, conteúdo, sequência, data e IDs do cliente.
- `Attachment`: metadados, hash, tamanho, localização interna e escopo.
- `MemoryEntry`: conteúdo, escopo, origem, aprovação e versão.
- `Run`: execução de resposta do MAX, estado e timestamps.
- `ToolInvocation`: ferramenta, parâmetros permitidos, estado e resultado resumido.
- `PermissionApproval`: solicitação, alvo, decisão, usuário e validade.
- `SyncChange`: sequência, entidade, versão e cursor.

Restrições:
- Toda entidade de usuário inclui `user_id` como limite de isolamento.
- Recursos de projeto exigem validação de pertencimento antes de leitura ou escrita.
- Mensagens preservam ordem estável por conversa.
- Anexos herdam escopo explícito, sem depender somente do nome do arquivo.
- Logs técnicos guardam IDs de correlação e estado, não conteúdo privado integral.

## 5. Adaptador para o núcleo existente

O serviço não deve importar nem executar o núcleo diretamente dentro do processo web sem avaliação de concorrência e isolamento. Primeiro deve existir um adaptador com interface interna definida:
- `create_session_context(user_id, project_id, conversation_id)`
- `send_message(context, message, model_preference, tool_policy)`
- `get_run_status(run_id)`
- `cancel_run(run_id)`

Esses nomes são contratos conceituais, não funções já existentes. O adaptador deverá:
1. Criar contexto isolado por conversa.
2. Recuperar somente memórias autorizadas para aquele escopo.
3. Aplicar instruções do projeto sem permitir que substituam políticas de segurança.
4. Invocar o roteamento existente de forma serializada ou por worker, após teste de concorrência.
5. Persistir mensagens e eventos na camada de plataforma, sem mudar os JSON originais nesta fase.
6. Retornar status e referências de ferramentas ao cliente.

A implementação deve primeiro verificar que estado global do `sermax_core.py` pode ser compartilhado com segurança. O código auditado contém variáveis globais de sessão e histórico, portanto execução concorrente por múltiplos usuários/conversas não deve ser presumida segura.

## 6. Persistência e migração

- Não alterar os arquivos JSON atuais na primeira fase.
- Criar armazenamento de plataforma separado.
- Definir migrações de esquema numeradas e reversíveis quando possível.
- Fazer importação somente por cópia, com relatório de contagem, hash e erros.
- Manter fonte original em modo somente leitura durante validação.
- Validar exportação e restauração antes de qualquer troca de fonte de verdade.
- Não migrar memória neural Pestinha como se fosse memória conversacional.

A escolha entre SQLite e PostgreSQL depende da topologia de servidor, número de usuários simultâneos, necessidade de acesso remoto e operação de backup. SQLite é candidato para primeiro host local de usuário único; para múltiplos processos ou usuários concorrentes, testar PostgreSQL ou arquitetura equivalente antes de fechar decisão.

## 7. Segurança e abuso

- TLS em conexões remotas.
- Rate limit em login, recuperação, uploads e envio de mensagens.
- Limites de tamanho e tempo para chamadas ao núcleo e ferramentas.
- Proteção CSRF quando autenticação por cookie for adotada.
- CORS com origens explícitas.
- Validação de caminho e prevenção de path traversal.
- Proteção contra SSRF nas ferramentas que consultam URLs.
- Segredos fora do Git e fora de logs.
- Sandbox para execução de código e tarefas de desenvolvimento.
- Auditoria de decisões de aprovação.
- Backup criptografado e teste periódico de restauração antes de release.

## 8. Testes de aceitação da API

1. Usuário A não lê projetos, conversas, arquivos ou memória do usuário B.
2. Usuário não acessa projeto de outro usuário alterando IDs na URL.
3. Reenvio da mesma mensagem com mesmo ID de cliente não duplica conteúdo.
4. Mensagens concorrentes preservam ordenação ou retornam conflito explícito.
5. Sessão revogada perde acesso imediatamente ou dentro do prazo de revogação definido.
6. Aprovação expirada ou de outro usuário é rejeitada.
7. A ferramenta em execução gera evento e estado visível sem expor detalhes sensíveis.
8. Upload inválido, excessivo ou fora do escopo é recusado.
9. Sincronização não apaga alteração mais nova com versão antiga.
10. Exportação e restauração recuperam conversas, anexos e memória com hashes conferidos.
11. Falha do Ollama ou OpenJarvis retorna estado de erro controlado, preservando mensagens.
12. O modo offline não afirma que o cérebro central está disponível quando a rede caiu.

## 9. Decisões pendentes antes da implementação

- Host central: PC próprio, servidor dedicado ou nuvem.
- Acesso externo: VPN, túnel privado ou outra topologia.
- Banco inicial e estratégia de backup.
- Política de cadastro: conta única local ou múltiplas contas.
- Limites de anexos e retenção.
- Estratégia de execução concorrente do núcleo.
- Tecnologia de eventos em tempo real.
- Recuperação de conta sem provedor pago.
- Estratégia de atualização e rollback.

## 10. Limites de escopo

Este contrato não implementa endpoints, banco, autenticação, sincronização, cliente Android, interface ou Drive Connect. Não altera `sermax_core.py`, memória JSON, Terminal, workflows, segredos ou arquivos de instalação. A próxima etapa é revisão arquitetural e decisão de hospedagem antes de iniciar código.
