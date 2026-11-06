> **HISTÓRICO SUPERADO:** esta proposta de duas equipes foi substituída pela diretriz de equipe única coordenada pelo MAX. Consulte `ARQUITETURA-EQUIPE-UNICA-MAX.md`. O conteúdo abaixo foi preservado como histórico de decisões e não deve orientar novas implementações.

# SERMAX: arquitetura de duas equipes coordenadas pelo MAX

**Estado:** decisão arquitetural aprovada pelo mantenedor; especificação e plano de implementação.  
**Branch de trabalho:** `sermax-windows-integration-20261029`.  
**Proteções:** `main`, instalação `C:\\SERMAX`, interface original e memórias existentes permanecem fora do escopo de escrita desta etapa.

## 1. Decisão estrutural

O SERMAX terá duas estruturas distintas:

1. **SERMAX DEVELOPMENT TEAM:** equipe de engenharia que trabalha no código-fonte do SERMAX, no ambiente de desenvolvimento e em branch autorizada.
2. **SERMAX INTELLIGENCE TEAM:** equipe interna do produto SERMAX, que atende o usuário e executa tarefas autorizadas durante o funcionamento normal.

O MAX é o coordenador geral e o ponto de entrada. Cada equipe terá supervisor, fila, estado, ferramentas, permissões e registros próprios. Uma equipe não recebe permissões da outra por herança.

A existência de agentes na Intelligence Team não comprova autonomia de desenvolvimento. A Development Team só será considerada autônoma após demonstrar o ciclo completo de inspeção, edição de código, execução de testes, avaliação independente, correção e registro de progresso.

## 2. Fronteiras e permissões

| Área | Development Team | Intelligence Team |
|---|---|---|
| Objetivo | Evoluir o código-fonte do SERMAX | Atender o usuário e executar tarefas solicitadas |
| Ambiente | Workspace/worktree isolado | Runtime instalado do SERMAX |
| Git | Branch de desenvolvimento autorizada | Sem escrita no repositório por padrão |
| Arquivos | Fontes, testes e docs do workspace | Arquivos explicitamente autorizados pelo usuário |
| Testes | Testes do produto e CI | Testes de tarefas do usuário, dentro do escopo |
| Memória | Registro técnico próprio | Memória pessoal SERMAX existente e contexto operacional segregado |
| Deploy/merge | Exige aprovação humana | Sem permissão |
| C:\\SERMAX | Sem acesso de escrita | Preservação; alterações só por fluxo de atualização aprovado |
| Credenciais/segredos | Negado por padrão | Negado por padrão |

Ações como merge, release, publicação, instalação, exclusão, alteração da memória pessoal, acesso a credenciais e mudanças fora do workspace exigem aprovação explícita.

## 3. SERMAX DEVELOPMENT TEAM

### Papéis

- **Development Supervisor:** recebe objetivos técnicos, mantém fila e estados, aplica limites e coordena os agentes.
- **Researcher:** consulta documentação, dependências, APIs, licenças e histórico técnico.
- **Architect:** define desenho, contratos, riscos e critérios de aceitação.
- **Programmer:** edita fontes e testes somente no workspace autorizado.
- **Test Engineer:** executa testes permitidos, coleta logs e reproduz falhas.
- **Reviewer:** avalia diff, segurança, regressões e critérios de aceitação sem depender da autodeclaração do programador.
- **Integrator:** prepara commits e atualiza PR na branch autorizada, sem fazer merge.

### Ciclo exigido

1. Observar estado do repositório e da CI.
2. Registrar problema ou objetivo com evidências.
3. Criar plano pequeno, arquivos-alvo, critérios de aceitação e rollback.
4. Confirmar branch, HEAD e permissões antes de escrever.
5. Alterar código em workspace isolado.
6. Executar testes unitários, integração, análise estática e build aplicáveis.
7. Avaliar resultados por verificador separado.
8. Corrigir falhas dentro de limite de tentativas.
9. Reexecutar a suíte relevante.
10. Registrar diff, hashes, logs, commit, resultados e pendências.
11. Solicitar aprovação humana para operações protegidas.

### Estados persistentes da tarefa

`queued`, `inspecting`, `diagnosed`, `planned`, `awaiting_approval`, `implementing`, `testing`, `reviewing`, `completed`, `blocked`, `failed`.

Cada transição registra horário, agente, entrada, saída, evidências e motivo. O supervisor deve retomar tarefas interrompidas sem repetir alterações já aplicadas.

### Critérios de autonomia demonstrável

A equipe só será chamada autônoma quando um teste de aceitação comprovar que ela:
- recebe uma tarefa técnica sem instruções humanas por etapa;
- inspeciona o repositório e apresenta evidências;
- modifica código e/ou testes em branch/workspace permitido;
- executa os testes reais e identifica falhas;
- corrige ao menos uma falha reproduzível ou justifica tecnicamente o bloqueio;
- executa novamente os testes e compara resultados;
- produz diff e registro persistente;
- bloqueia tentativas de alterar `main`, `C:\\SERMAX`, memórias ou arquivos fora do escopo.

Até esse teste passar, o estado deve ser descrito como **automação de engenharia em desenvolvimento**, nunca autonomia concluída.

## 4. SERMAX INTELLIGENCE TEAM

### Papéis

- **Intelligence Supervisor:** classifica a solicitação e escolhe capacidades internas.
- **Assistant:** mantém a conversa e entrega a resposta unificada SERMAX.
- **Researcher:** pesquisa fontes e documentação quando há ferramenta e autorização.
- **Analyst:** analisa dados, arquivos e problemas.
- **Programmer:** auxilia o usuário com código e tarefas de programação no escopo permitido.
- **Task Planner:** divide solicitações em etapas.
- **Task Executor:** executa ferramentas com parâmetros validados e permissões.
- **Verifier:** confere resultados e comunica limitações.

A equipe funciona durante o uso normal do produto. Não altera o código-fonte do SERMAX como parte de suas tarefas rotineiras.

## 5. MAX e coordenação entre equipes

MAX coordena as duas estruturas por um **control plane** comum, com dois supervisores independentes:

- solicitação de uso do produto segue para Intelligence Team;
- tarefa de engenharia do próprio SERMAX segue para Development Team;
- tarefa híbrida é dividida em entregas com fronteiras explícitas;
- a Intelligence Team não recebe acesso automático ao workspace de desenvolvimento;
- a Development Team não recebe memória pessoal nem dados privados do usuário.

O control plane compartilha somente contratos, catálogo de capacidades, política de segurança, telemetria técnica mínima e estado de disponibilidade. Filas, contextos e memórias de cada equipe permanecem separados.

## 6. Jarvis e Pestinha

### OpenJarvis / Jarvis

**Possível papel na Intelligence Team:** motor/agente para raciocínio e execução de tarefas, desde que o SERMAX integre agentes, ferramentas e contexto de forma segura.

**Possível papel na Development Team:** componente de orquestração ou agente de programação somente se a integração demonstrar leitura do repositório, edição em workspace isolado, execução de testes e retorno de diffs/resultados. O SDK atual configurado como `simple`, `tools=[]` e `context=False` não comprova essas capacidades.

A compatibilidade atual exige worker Python 3.13 separado do núcleo Python 3.14. Não habilitar ferramentas de shell, escrita irrestrita, navegador, MCP ou skills sem revisão individual, isolamento e testes.

### Pestinha

Pestinha é uma rede comportamental LIF para o pet de tela. Pode contribuir com estado, atenção, sinais comportamentais e adaptação limitada.

**Intelligence Team:** sinais internos de estado/atenção e comportamento visual, subordinados ao supervisor.  
**Development Team:** no máximo, sinais auxiliares de estado ou prioridade do agente, após avaliação. Não atribuir a ele programação, raciocínio de código ou execução de testes.

A rede não decide permissões nem executa ações. Saídas neurais são dados não confiáveis. Sensores do computador, rotina, teclado, mouse, leitura de janelas, autostart e assets não são habilitados por esta arquitetura.

## 7. Reaproveitamento sem duplicação

Criar uma camada compartilhada de contratos, não duas implementações das mesmas ferramentas:

- **Capability Registry:** declara capacidades, versão, disponibilidade, equipe permitida e permissões.
- **Policy Engine:** valida escopo, risco, diretórios, ferramentas, limites e aprovações.
- **Model/Agent Gateway:** interface comum para modelos e agentes, com adaptadores por runtime.
- **Tool Contracts:** schemas e validadores comuns; cada equipe recebe uma allowlist própria.
- **Evidence Store:** formato comum para logs técnicos, hashes, resultados e citações, com namespaces separados.
- **Task State Schema:** formato de estado reutilizável, mas filas e registros independentes.

Ferramentas de leitura e análise podem compartilhar implementação. Ferramentas de escrita devem ter adaptadores e raízes de diretório distintas: workspace de desenvolvimento para Development Team, caminhos autorizados do usuário para Intelligence Team. Nenhum agente acessa a outra raiz por padrão.

## 8. Estado dos componentes atuais

| Componente | Estado verificado | Destino |
|---|---|---|
| `sermax_core.py` / MAX | Núcleo conversacional; ainda sem dois supervisores | Control plane e entrada única |
| `sermax_planejador.py` | Planeja tarefas curtas; não altera código | Reaproveitar como planejador, com contratos separados por equipe |
| `sermax_executor.py` | Ações locais restritas de sistema, memória e cálculo | Reaproveitar políticas e validadores; ampliar por ferramentas específicas |
| `sermax_tarefas.py` | Consultas sequenciais limitadas; sem fila persistente de engenharia | Reaproveitar execução sequencial no runtime |
| `sermax_jarvis_adapter.py` / worker | Processo separado; SDK em agente `simple`, sem ferramentas/contexto próprios | Gateway de agente; avaliar agentes distintos por equipe |
| `sermax_pestinha_adapter.py` | Eventos fechados e estados visuais; sem autonomia de código | Subsistema comportamental da Intelligence Team |
| Testes atuais | Testes parciais de núcleo, adaptadores e integração simulada | Reaproveitar e ampliar com testes de aceitação das duas equipes |
| GitHub PR #2 | Branch de integração aberta em draft; sem merge | Base de trabalho, após verificar HEAD a cada escrita |

## 9. Trabalho necessário

### Prioridade 1: proteger e organizar

- manter `main` intacta;
- manter `C:\\SERMAX` intocada;
- preservar interface original, `memoria_sermax.json`, memória neural e backups;
- definir inventário e hashes de arquivos protegidos;
- registrar contratos, permissões e separação de dados.

### Prioridade 2: Intelligence Team

- implementar supervisor de inteligência e roteamento automático;
- retirar a dependência de seleção manual de motor para o fluxo normal;
- definir papéis e ferramentas com allowlists;
- manter Jarvis como adaptador isolado até validar SDK real;
- manter Pestinha como subsistema comportamental, sem autoridade de execução.

### Prioridade 3: Development Team

- criar workspace isolado e fila persistente;
- implementar observador Git/CI e diagnóstico baseado em evidências;
- implementar programador com edição restrita e diff obrigatório;
- implementar executor de testes com allowlist, timeout e limites;
- implementar revisor independente e registro de progresso;
- criar testes de aceitação que demonstrem modificação real, testes, correção e registro.

### Prioridade 4: integração e validação

- ligar os dois supervisores ao MAX pelo control plane;
- testar roteamento correto de tarefas;
- testar isolamento entre equipes, diretórios e memórias;
- testar falhas, retomada e limites de recursos;
- executar CI no commit exato e validação Windows real;
- manter PR em draft até todos os gates aplicáveis passarem.

## 10. Gates de liberação e comunicação

Não declarar equipe autônoma, agente integrado, teste aprovado ou versão concluída sem evidência verificável.

Relatórios devem separar:
- especificado;
- implementado no código;
- integrado ao fluxo;
- testado automaticamente;
- validado no Windows real;
- pendente ou bloqueado.

Nenhuma alteração nesta arquitetura autoriza merge, release, instalação ou modificação da memória pessoal. A interface original e os arquivos protegidos permanecem preservados.
