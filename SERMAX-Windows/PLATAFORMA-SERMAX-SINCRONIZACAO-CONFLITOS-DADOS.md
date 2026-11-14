# PLATAFORMA SERMAX
## Especificação de sincronização de dados e resolução de conflitos

**Estado:** especificação de planejamento. Não implementada.  
**Branch:** `sermax-windows-integration-20261029`  
**Revisão:** 14/11/2026  
**Dependências:** contrato preliminar da API, operação local da primeira versão, recuperação de falhas, permissões e auditoria, identidade e autenticação.

## 1. Objetivo

Definir como conversas, projetos, mensagens, arquivos e memórias autorizadas serão disponibilizados de forma consistente entre Windows, Android e navegador, mantendo um único cérebro MAX central.

A sincronização não cria instâncias independentes do SERMAX em cada dispositivo. Os clientes consultam e atualizam o serviço central, respeitando identidade, sessão, escopo e permissões.

Este documento é planejamento técnico. Não implementa sincronização, não cria banco, não migra dados e não autoriza acesso remoto.

## 2. Escopo por fase

### Primeira versão local

A primeira versão continua restrita a um usuário e ao computador host:
- Um armazenamento experimental central no host.
- Interface local conectada ao serviço local.
- Persistência de conversas e estados experimentais.
- Sem sincronização entre dispositivos.
- Sem acesso remoto ou publicação na rede.
- Sem migração automática das memórias e históricos atuais.

### Fase multi-dispositivo

Após validação da primeira versão e autorização específica:
- Windows, Android e navegador passam a acessar o mesmo serviço central.
- O servidor central mantém a versão oficial dos dados.
- Clientes recebem alterações autorizadas e enviam mudanças identificadas.
- Sessões e dispositivos revogáveis controlam o acesso.
- A sincronização respeita projetos, permissões e escopos de memória.

A fase multi-dispositivo depende da aprovação da hospedagem e do acesso remoto. Não está incluída na primeira entrega local.

## 3. Fonte oficial dos dados

O serviço central é a fonte oficial de estado compartilhado.

Regras:
1. O cliente não declara uma alteração como sincronizada antes da confirmação do servidor.
2. O servidor valida identidade, sessão, permissão, versão e escopo.
3. O servidor atribui a versão confirmada e a sequência de sincronização.
4. O cliente mantém uma cópia local identificada como cache, nunca como autoridade concorrente.
5. Dados locais pendentes são preservados até confirmação ou resolução explícita.
6. Nenhum cliente pode sobrescrever silenciosamente uma versão mais recente.
7. Perda de conexão não autoriza repetição cega de operações.

O núcleo MAX permanece no host central. Os clientes enviam solicitações ao mesmo serviço e recebem respostas associadas às conversas correspondentes.

## 4. Categorias de dados

| Entidade | Regra de sincronização |
|---|---|
| Projetos | Metadados versionados, alterações concorrentes exigem comparação |
| Conversas | Metadados versionados; mensagens preservadas por sequência |
| Mensagens | Append-only após confirmação, sem edição silenciosa |
| Respostas do MAX | Vinculadas à execução e à mensagem de origem |
| Arquivos | Metadados e conteúdo por referência autorizada, com hash |
| Memória global | Fora da primeira versão; futura sincronização sujeita a política própria |
| Memória de projeto | Escopo restrito ao projeto e sujeita a aprovação |
| Preferências de interface | Preferências por usuário ou dispositivo, conforme definição futura |
| Aprovações | Estado central, vinculado à sessão e à ação |
| Execuções | Estado central e protocolo de recuperação, sem duplicação |

A memória pessoal atual, o histórico original do Terminal e a memória neural do Pestinha não serão importados ou sincronizados por esta especificação.

## 5. Identificadores, versões e sequência

Cada entidade sincronizável deverá possuir:
- ID opaco e estável, não sequencial.
- Escopo de proprietário e, quando aplicável, projeto.
- Número de versão inteiro crescente atribuído pelo servidor.
- Data de criação e atualização em UTC.
- Estado de exclusão lógica, quando aplicável.
- Identificador de origem da alteração.
- Identificador de requisição para idempotência.

Mensagens confirmadas recebem sequência estável dentro da conversa. A ordenação visual usa a sequência do servidor, não o relógio local do dispositivo.

O servidor mantém cursor de alterações por fluxo de sincronização. O cursor é opaco ao cliente e não deve ser calculado ou incrementado manualmente pelo dispositivo.

## 6. Protocolo de sincronização

Fluxo proposto:

1. O cliente autentica e obtém o escopo de dados autorizado.
2. O cliente envia seu último cursor confirmado.
3. O servidor retorna alterações posteriores ao cursor, paginadas.
4. O cliente aplica cada alteração de forma transacional.
5. O cliente confirma o cursor somente após persistir todas as alterações da página.
6. O cliente envia alterações locais pendentes com IDs idempotentes e versões esperadas.
7. O servidor valida autorização e versão.
8. O servidor confirma, rejeita ou sinaliza conflito.
9. O cliente mantém pendências rejeitadas até resolução.
10. O ciclo recomeça sem perder o último cursor confirmado.

Rotas já propostas no contrato preliminar:
- `GET /sync/changes?cursor={cursor}`
- `POST /sync/ack`

Essas rotas são conceituais e ainda não existem como implementação confirmada. O contrato final deverá incluir paginação, tamanho máximo, versão do protocolo e tratamento de cursor expirado.

## 7. Controle de concorrência

Adotar controle otimista por versão, conforme o contrato preliminar da API.

Toda alteração mutável deve informar a versão que o cliente leu:
- Se a versão esperada coincidir com a versão atual, o servidor valida e grava a nova versão.
- Se a versão esperada for antiga, o servidor retorna conflito com metadados suficientes para comparação.
- O servidor nunca substitui a versão atual sem sinalizar conflito.
- O cliente não deve repetir automaticamente uma alteração rejeitada com versão atualizada sem reapresentar o conteúdo e avaliar o impacto.

Para HTTP, o contrato poderá usar campo `version` ou cabeçalho `ETag/If-Match`. A escolha final deve ser uniforme em todos os recursos.

## 8. Regras específicas de conflito

### 8.1 Mensagens

- Mensagens do usuário confirmadas são imutáveis.
- Reenvio com o mesmo ID de cliente retorna o registro original.
- Se dois dispositivos enviarem mensagens diferentes, ambas são registradas com sequência atribuída pelo servidor.
- A interface apresenta a ordem confirmada pelo servidor.
- Uma mensagem sem confirmação permanece pendente no dispositivo de origem.
- A mesma mensagem não é enviada novamente com novo ID automaticamente após timeout.

### 8.2 Respostas e execuções MAX

- Cada execução possui ID próprio e referência à mensagem de entrada.
- O servidor mantém uma única execução para a chave idempotente recebida.
- Se a conexão cair, o cliente consulta o estado da execução.
- Estado incerto segue o documento de recuperação de falhas.
- O cliente não cria uma segunda execução automaticamente para substituir uma execução de resultado incerto.
- Uma resposta final persistida é reutilizada por todos os dispositivos autorizados.

### 8.3 Metadados de projetos e conversas

Exemplos: nome, descrição, instruções e estado.

- Se um dispositivo editar a versão 4 e outro já tiver gravado a versão 5, a alteração baseada na versão 4 será recusada como conflito.
- A interface apresenta a versão atual do servidor e a proposta local.
- O usuário escolhe manter a versão atual, reaplicar a proposta sobre a versão atual ou cancelar.
- A reaplicação gera uma nova alteração baseada na versão mais recente e passa novamente pela política de permissões.
- Alterações em instruções de projeto exigem confirmação conforme a matriz de permissões.

### 8.4 Arquivos

- Arquivos são identificados por ID, hash, tamanho e metadados.
- Upload concluído não é sobrescrito por outro conteúdo com o mesmo nome.
- Nome igual não significa arquivo igual.
- Arquivo novo recebe novo ID.
- Substituição de conteúdo é operação explícita, versionada e sujeita a confirmação.
- Exclusão usa tombstone e segue Classe C.
- O cliente valida hash após transferência, quando suportado.

### 8.5 Memória

- Memória global e memória de projeto permanecem separadas.
- Nenhum conflito autoriza combinar ou apagar entradas automaticamente.
- Alterações e exclusões de memória seguem a política de permissões.
- A memória atual do SERMAX não será sincronizada ou migrada nesta fase.
- A memória neural do Pestinha permanece separada.

## 9. Exclusão lógica e tombstones

Exclusões sincronizadas devem ser representadas por tombstones, não por remoção física imediata.

Cada tombstone contém:
- ID da entidade.
- Tipo da entidade.
- Versão final.
- Data e hora da exclusão.
- Identidade e solicitação autorizadora.
- Escopo de visibilidade.

Regras:
- Exclusão exige Classe C.
- Clientes recebem tombstone e removem a entidade da visualização normal.
- O conteúdo original segue política de retenção e backup separada.
- Tombstone não significa que o backup foi apagado.
- Retenção e compactação de tombstones exigem definição antes da implementação.
- Nenhum cliente decide sozinho que um tombstone expirou.

## 10. Dispositivos offline

Durante desconexão:
- O cliente informa estado offline.
- Rascunhos locais podem permanecer no dispositivo, identificados como não sincronizados.
- O cliente não apresenta alterações pendentes como confirmadas.
- Ações que exigem aprovação central ficam indisponíveis.
- Não executar ferramentas, ações externas ou alterações críticas sem conexão e autorização do servidor.
- O cache local deve limitar dados sensíveis e respeitar a política de armazenamento do dispositivo.
- A limpeza de cache não deve apagar conteúdo central.

Ao reconectar:
1. Revalidar sessão.
2. Consultar estado de revogação do dispositivo.
3. Obter cursor válido.
4. Receber alterações do servidor.
5. Comparar alterações locais pendentes com as versões centrais.
6. Resolver conflitos.
7. Enviar pendências autorizadas e idempotentes.
8. Confirmar sincronização somente após resposta do servidor.

Se a sessão expirou ou o dispositivo foi revogado, bloquear sincronização até nova autenticação autorizada.

## 11. Cursor, paginação e recuperação

- Cursor confirmado é salvo após aplicação transacional da página.
- Se o cliente falhar antes de salvar o cursor, poderá solicitar a mesma página novamente.
- Aplicação repetida deve ser idempotente por ID de alteração e versão.
- Se o cursor expirar, o servidor informa que é necessário reconciliar o estado.
- Reconciliação completa não deve apagar dados locais pendentes.
- Se o banco central apresentar inconsistência, interromper sincronização e preservar dados para diagnóstico.
- A retomada de execuções segue a máquina de estados do documento de recuperação, não o protocolo de sincronização.

## 12. Segurança e isolamento

- Toda consulta é filtrada pela identidade autenticada e pelas permissões no servidor.
- IDs opacos não substituem autorização.
- Um cliente não escolhe livremente o usuário, projeto ou escopo da requisição.
- Respostas de sincronização não incluem conteúdo de outro projeto.
- Dispositivo revogado não recebe novas alterações.
- Tráfego remoto exige HTTPS e canal privado aprovado.
- Tokens não são gravados no cache de sincronização.
- Logs registram IDs, versões, cursores e decisões, sem duplicar conteúdo sensível.
- A trilha de auditoria segue a política append-only.
- Limites de tamanho, frequência e paginação devem prevenir abuso e consumo excessivo de recursos.

## 13. Estados visíveis na interface

A interface deverá distinguir:
- **Sincronizado:** servidor confirmou a versão.
- **Pendente:** alteração existe no dispositivo, sem confirmação central.
- **Enviando:** transmissão em andamento.
- **Conflito:** servidor recusou a versão antiga.
- **Offline:** serviço central indisponível.
- **Sessão expirada:** autenticação necessária.
- **Dispositivo revogado:** acesso bloqueado.
- **Falha de sincronização:** operação não confirmada, com opção segura de tentar novamente após consulta de estado.

Não usar um único indicador verde para representar estados distintos.

## 14. Auditoria

Registrar:
- Início e fim de ciclo de sincronização.
- Identificador do dispositivo e da sessão.
- Cursor inicial e final.
- Entidades e versões alteradas.
- Confirmações, rejeições e conflitos.
- Tombstones recebidos e aplicados.
- Revogação ou expiração de sessão.
- Falhas de integridade e reconciliação.
- IDs idempotentes relevantes.

Não registrar tokens, conteúdo integral de mensagens, arquivos ou memórias por padrão.

## 15. Testes de aceitação planejados

1. Cliente sem sessão não recebe alterações.
2. Cliente de projeto A não recebe dados do projeto B.
3. Cursor válido retorna somente alterações posteriores.
4. Cursor só é confirmado após aplicação transacional.
5. Página repetida não duplica entidades.
6. Reenvio idempotente não duplica mensagem.
7. Mensagens simultâneas recebem sequência central estável.
8. Resposta MAX aparece em todos os clientes autorizados.
9. Execução incerta não é reenviada automaticamente.
10. Edição baseada em versão antiga gera conflito.
11. Conflito não sobrescreve versão atual.
12. Reaplicação exige nova versão esperada.
13. Arquivos de mesmo nome não são confundidos.
14. Hash de arquivo é validado após transferência.
15. Exclusão gera tombstone e respeita Classe C.
16. Dispositivo revogado não sincroniza.
17. Sessão expirada exige autenticação.
18. Rascunho offline permanece marcado como pendente.
19. Reconexão não duplica operações.
20. Cursor expirado aciona reconciliação sem apagar pendências.
21. Falha durante aplicação de página não avança cursor.
22. Memória global e de projeto permanecem isoladas.
23. Memória atual e memória neural do Pestinha não são alteradas.
24. Falha no banco central interrompe sincronização com segurança.
25. Logs não contêm tokens ou conteúdo sensível desnecessário.

Nenhum desses testes foi executado. São critérios para validação futura.

## 16. Decisões pendentes

- Definir quais dados terão cache local em cada tipo de dispositivo.
- Definir prazo de retenção e tamanho máximo do cache.
- Escolher mecanismo de eventos em tempo real, como SSE ou consulta periódica, conforme infraestrutura validada.
- Definir duração e política de expiração dos cursores.
- Definir limites de paginação e tamanho de anexos.
- Definir política de retenção dos tombstones.
- Definir backup e restauração do banco central.
- Definir se projetos poderão ser disponibilizados seletivamente por dispositivo.
- Definir estratégia de sincronização de preferências por dispositivo versus preferências globais.
- Validar comportamento em rede instável antes de liberar clientes móveis.

## 17. Critério de liberação

A sincronização multi-dispositivo só poderá ser habilitada após:
- Primeira versão local validada.
- Autenticação e revogação de sessões testadas.
- Hospedagem e acesso remoto aprovados.
- Testes de concorrência, idempotência, isolamento e recuperação executados.
- Backup e restauração comprovados.
- Aprovação expressa da fase multi-dispositivo.

Este documento não autoriza implementação, migração, exposição de rede, sincronização real, alteração do núcleo, Terminal, memórias ou backups.
