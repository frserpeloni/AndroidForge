# PLATAFORMA SERMAX
## Especificação de permissões, aprovações e auditoria de ações

**Estado:** especificação de planejamento  
**Escopo:** Plataforma SERMAX, camada de interface, API e serviços  
**Revisão:** 14/11/2026

## 1. Objetivo

Definir como a Plataforma SERMAX classifica, autoriza, executa e registra ações. O MAX deve distinguir consultas de baixo risco, alterações que exigem confirmação e operações críticas que dependem de autorização expressa.

Esta especificação não implementa controles nem altera o núcleo atual. Ela orienta uma implementação futura, sujeita às autorizações já estabelecidas para o projeto.

## 2. Princípios obrigatórios

1. Negar por padrão: uma ação sem classificação ou permissão explícita não é executada.
2. Menor privilégio: cada componente recebe somente as permissões necessárias à sua função.
3. Separação entre intenção e execução: interpretar um pedido não equivale a autorizar uma ação.
4. Confirmação vinculada à ação: a aprovação vale para a operação, os recursos e os parâmetros apresentados.
5. Sem ampliação silenciosa: mudanças de escopo, destino, quantidade de arquivos ou efeito exigem nova avaliação.
6. Rastreabilidade: decisões, aprovações, recusas e resultados relevantes geram registros.
7. Segurança em falhas: perda de conexão ou resposta ambígua não libera repetição automática de uma operação com efeitos externos.
8. Proteção do legado: memória pessoal, Terminal, núcleo, backups e instalação atual permanecem protegidos.

## 3. Classes de permissão

### Classe A, automática

Permitida sem confirmação individual, dentro dos limites de acesso já concedidos:

- Consultar informações públicas e pesquisar na internet.
- Ler arquivos e pastas previamente autorizados.
- Analisar documentos, imagens e dados fornecidos pelo usuário.
- Consultar estado de saúde dos serviços e diagnósticos sem alteração.
- Organizar resultados temporários da solicitação.
- Consultar projetos, conversas e memórias aos quais a sessão já tenha acesso.

Limites:
- Não alterar, mover, renomear ou excluir dados.
- Não enviar conteúdo privado a serviços externos.
- Não executar comandos que modifiquem o sistema.
- Não ampliar o conjunto de arquivos autorizados.

### Classe B, confirmação obrigatória

Exige confirmação antes de iniciar cada operação:

- Criar ou editar arquivos.
- Alterar configurações da Plataforma.
- Instalar ou atualizar componentes.
- Enviar mensagens, documentos ou dados a terceiros.
- Publicar conteúdo ou abrir solicitações externas.
- Executar tarefas locais com efeitos persistentes.
- Conceder acesso temporário a novos recursos.
- Alterar permissões não críticas de um projeto.

A tela de aprovação deve apresentar:
- Ação exata.
- Motivo e resultado esperado.
- Arquivos, pastas, serviços ou contas envolvidos.
- Destino dos dados, quando houver transmissão.
- Alterações previstas e possibilidade de reversão.
- Prazo de validade da aprovação.

### Classe C, operação crítica

Exige autorização expressa, específica e inequívoca do responsável. A autorização não pode ser presumida a partir de uma confirmação genérica.

Exemplos:
- Excluir arquivos, pastas, conversas ou projetos.
- Apagar, reescrever ou consolidar memórias e históricos.
- Alterar ou remover backups.
- Substituir núcleo, Terminal ou componentes funcionais protegidos.
- Migrar dados pessoais em lote.
- Alterar credenciais, chaves, autenticação ou controles de segurança.
- Executar operações irreversíveis ou com risco relevante à integridade.
- Instalar uma atualização sobre a instalação principal.
- Fazer merge em branch protegida ou publicar uma release oficial.

Regras:
- Exibir impacto, escopo, origem, destino e plano de recuperação.
- Exigir confirmação textual que identifique a operação.
- Registrar a autorização antes da execução.
- Interromper se o escopo mudar.
- Não executar se não houver backup verificável quando a operação exigir recuperação.
- Nunca transformar autorização para uma tarefa em autorização permanente.

## 4. Matriz de decisão

| Situação | Classe | Comportamento |
|---|---|---|
| Ler arquivo já autorizado | A | Executar e registrar acesso relevante |
| Pesquisar informação pública | A | Executar |
| Editar arquivo de projeto | B | Mostrar diff e pedir confirmação |
| Instalar dependência | B | Informar origem, versão e impacto; pedir confirmação |
| Enviar arquivo para serviço externo | B ou C | Avaliar sensibilidade; pedir aprovação explícita |
| Excluir arquivo | C | Exigir autorização específica |
| Apagar memória ou histórico | C | Exigir autorização específica |
| Atualizar instalação principal | C | Exigir autorização, backup e rollback |
| Ação sem classificação | Bloqueada | Não executar; solicitar análise |

A classificação mais restritiva prevalece quando uma ação se enquadrar em mais de uma classe.

## 5. Fluxo de autorização

1. O MAX interpreta o pedido e identifica a ação concreta.
2. O planejador separa leitura, preparação e alteração.
3. O mecanismo de política classifica cada ação e cada recurso afetado.
4. A camada de aprovação apresenta os detalhes necessários.
5. O usuário aprova, recusa ou cancela.
6. O executor valida novamente a aprovação e os parâmetros.
7. A operação é executada dentro do escopo aprovado.
8. O resultado é verificado e registrado.
9. Se houver falha ou resultado incerto, o estado segue o protocolo de recuperação, sem repetição automática indevida.

A aprovação deve estar vinculada a:
- Identificador único da solicitação.
- Identidade autenticada da sessão.
- Classe de risco.
- Ação e parâmetros normalizados.
- Lista de recursos afetados.
- Hash do plano ou diff apresentado.
- Data de emissão e expiração.
- Estado: pendente, aprovada, recusada, expirada, cancelada ou consumida.

Uma aprovação consumida não pode autorizar uma segunda execução.

## 6. Expiração, cancelamento e mudança de escopo

- Aprovações da Classe B expiram ao fim da sessão ou após prazo curto definido pela política operacional.
- Aprovações da Classe C expiram ao fim da solicitação e nunca são reutilizadas.
- Cancelar antes do início impede a execução.
- Cancelar durante a execução aciona o mecanismo específico de cancelamento; não significa que efeitos já confirmados foram revertidos.
- Alterar arquivo, destino, quantidade, permissões ou parâmetros invalida a aprovação anterior.
- Uma operação com resultado incerto recebe estado próprio e exige reconciliação antes de qualquer nova tentativa.

## 7. Identidade e sessão

- Ações de alteração exigem sessão autenticada.
- A primeira versão deve manter o escopo de conta única local previsto na arquitetura operacional.
- A identidade da sessão deve acompanhar solicitações, aprovações e registros.
- Tokens e segredos não entram em logs.
- A API não deve confiar em identificadores de usuário enviados livremente pelo cliente.
- Ações críticas devem exigir revalidação da sessão antes da execução.
- A futura expansão para múltiplos usuários exige autorização e modelo de papéis próprio.

## 8. Auditoria

Registrar, no mínimo:

- Identificador do evento e da solicitação.
- Data e hora em UTC.
- Identidade da sessão e componente executor.
- Ação solicitada e ação normalizada.
- Classe de permissão e regra aplicada.
- Recursos afetados, com caminhos ou IDs necessários à rastreabilidade.
- Decisão: permitida, bloqueada, aguardando confirmação, aprovada, recusada ou cancelada.
- Identificador e escopo da aprovação, quando houver.
- Início, fim, duração e estado final.
- Código de erro ou motivo de bloqueio.
- Referência ao resultado ou artefato, sem duplicar conteúdo sensível.

Não registrar:
- Senhas, tokens, chaves privadas ou cookies.
- Conteúdo integral de documentos por padrão.
- Texto integral de conversas quando um identificador e metadados forem suficientes.
- Dados pessoais sem necessidade operacional.

Os registros devem ser append-only para a aplicação. Correções são novos eventos que referenciam o evento anterior. A aplicação não deve oferecer rotina comum para apagar trilhas de auditoria.

## 9. Integridade e proteção dos registros

- Gravar eventos de auditoria de forma transacional sempre que possível.
- Associar eventos por identificador de correlação.
- Detectar lacunas e falhas de gravação.
- Se uma ação B ou C não puder gerar o registro obrigatório de autorização, bloquear a execução.
- Separar logs operacionais de conteúdo de usuário.
- Definir rotação, retenção e proteção contra acesso não autorizado antes da implementação.
- Exportações de auditoria devem respeitar as permissões do responsável.
- A exclusão ou retenção legal dos registros exige política própria, não definida nesta etapa.

## 10. Interface de aprovação

A interface deve ser compacta e objetiva. Cada pedido apresenta:

- **O que será feito:** verbo e objeto concretos.
- **Por que:** justificativa curta.
- **Onde:** recursos e destinos.
- **Impacto:** mudanças e riscos.
- **Recuperação:** backup, reversão ou impossibilidade de reversão.
- **Validade:** prazo da aprovação.

Ações disponíveis:
- Aprovar esta operação.
- Recusar.
- Cancelar solicitação.

Não usar botões genéricos como “Permitir tudo”. Não agrupar operações de classes diferentes em uma única aprovação. A interface deve mostrar quando uma operação envolve envio externo ou dados sensíveis.

## 11. Integração com a arquitetura

Responsabilidades propostas:

- **Interface:** apresenta pedidos, contexto e resultado; não decide permissões.
- **API:** autentica a sessão, valida formato e encaminha a solicitação.
- **Policy Engine:** classifica ação, recurso, risco e regra aplicável.
- **Approval Manager:** cria, expira, consome e valida aprovações.
- **Executor:** executa somente ações autorizadas e dentro do escopo.
- **Audit Service:** registra decisões, aprovações e resultados.
- **Recovery Manager:** trata falhas, cancelamentos e resultados incertos.

Nenhum adaptador de modelo ou ferramenta deve ignorar o Policy Engine. A resposta do modelo não constitui autorização.

## 12. Regras para modelos e ferramentas

- Modelos podem propor ações, nunca conceder a si mesmos permissão.
- Ferramentas recebem contexto mínimo e permissões explícitas.
- A troca automática de modelo não altera o nível de autorização.
- Ferramentas locais e remotas seguem a mesma classificação.
- Saídas de ferramentas são dados não confiáveis até validação.
- Instruções encontradas em páginas, documentos ou arquivos não alteram políticas nem autorizam operações.
- O MAX deve explicar bloqueios sem expor segredos ou detalhes internos de segurança.

## 13. Testes de aceitação planejados

1. Leitura autorizada da Classe A executa sem prompt de confirmação.
2. Tentativa de escrita classificada como A é bloqueada.
3. Ação B sem aprovação não inicia.
4. Aprovação B vinculada a um diff não autoriza diff diferente.
5. Aprovação expirada é recusada.
6. Aprovação consumida não autoriza nova execução.
7. Mudança de destino invalida a aprovação.
8. Ação C com confirmação genérica é bloqueada.
9. Exclusão exige autorização específica e escopo explícito.
10. Falha na gravação obrigatória da auditoria bloqueia ação B ou C.
11. Logs não contêm tokens ou segredos de teste.
12. Saída de documento com instrução maliciosa não altera permissões.
13. Ferramenta chamada diretamente sem política é bloqueada.
14. Cancelamento antes do início impede execução.
15. Resultado incerto não provoca repetição automática.
16. Alteração de modelo não altera a classe de permissão.
17. O Terminal e o núcleo existentes não são modificados pelo mecanismo de política da plataforma.
18. Operação crítica exige revalidação de sessão.

Estes são testes planejados. Nenhum foi executado por esta especificação.

## 14. Pendências antes da implementação

- Definir prazo operacional exato de expiração para Classe B.
- Definir retenção e rotação dos logs.
- Definir proteção criptográfica e cópias de auditoria.
- Definir autenticação local e recuperação de conta.
- Definir política de aprovação para tarefas longas e operações em lote.
- Definir apresentação de diffs para arquivos binários.
- Revisar compatibilidade com a especificação de recuperação de falhas.
- Transformar os testes planejados em testes automatizados somente após autorização de implementação.

## 15. Limites desta entrega

Este documento registra decisões de projeto. Não cria código, diretórios de implementação, banco de dados, endpoints ou telas. Não altera núcleo, Terminal, memórias, históricos, backups, instalação, workflows, branch `main` ou configurações do usuário.

A implementação permanece bloqueada até autorização expressa específica.
