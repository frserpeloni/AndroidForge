# Retomada técnica SERMAX unificado

Data: 10/11/2026  
Branch-base preservada: `sermax-windows-integration-20261029`  
Branch desta retomada: `sermax-unified-runtime-20261110`

## Decisão de produto

SERMAX é a única identidade, interface e ponto de entrada. OpenJarvis e Pestinha são subsistemas internos, invisíveis como produtos separados. O usuário não seleciona agente, motor, Jarvis ou Pestinha por comando. O núcleo decide automaticamente quais capacidades internas acionar em cada solicitação.

A integração não é uma chamada alternativa de chat. É um ciclo de coordenação no núcleo SERMAX.

## História e decisões preservadas

- Base técnica de continuidade: `SERMAX_CONSOLIDACAO_TECNICA_CANDIDATA_28-10-2026`.
- Branch de desenvolvimento preservada: `sermax-windows-integration-20261029`.
- `main` permanece intacta até validação e autorização.
- Terminal original verde/preto, rosto ASCII, fluxo de conversa, voz e atalhos existentes devem ser preservados.
- `C:\SERMAX`, `memoria_sermax.json`, configurações, histórico e modelos locais não podem ser sobrescritos durante desenvolvimento ou atualização.
- SERMAX Core mantém identidade, contexto, memória pessoal, planejamento, segurança e coordenação.
- OpenJarvis fornece agentes, orquestração, ReAct, skills e capacidades de execução que serão adaptadas às permissões SERMAX.
- Pestinha fornece subsistema neural comportamental, atenção, estado, adaptação e aprendizagem que existirem comprovadamente no código upstream. Não é modelo de linguagem nem executor de ações.
- Agentes da equipe de desenvolvimento são instrumentos do ambiente de engenharia, não agentes embutidos no produto SERMAX.

## Diagnóstico da implementação existente

### OpenJarvis
O adaptador atual executa worker separado em Python 3.13 e chama SDK com agente `simple`, `tools=[]` e `context=False`. Isso valida uma ponte de transporte, mas não incorpora o orquestrador, ReAct, operative, skills, ferramentas, memória operacional ou avaliação do OpenJarvis.

### Pestinha
O adaptador atual cria `LIFBrain`, envia cinco eventos sintéticos (`idle`, `attention`, `processing`, `completed`, `error`), executa 80 passos e traduz alguns motores em estados visuais. O estado neural fica separado em `memoria_neural_pestinha.json`. Isso é uma integração neural limitada ao estado visual, não a incorporação dos mecanismos amplos de percepção, atenção, condicionamento, memória episódica e aprendizagem.

### Núcleo
`sermax_core.py` ainda oferece seleção manual `/motor` e chamada explícita `/jarvis`. Isso contraria a experiência final aprovada. Esses comandos são legado provisório e não devem definir a arquitetura final.

### Launcher e interface
O launcher resolve a raiz persistente e executa o terminal empacotado. A interface original deve permanecer como casca do produto, sem mostrar subsistemas internos como opções de motor.

## Arquitetura-alvo

Implementar um supervisor interno no núcleo SERMAX com ciclo:

1. Interpretar intenção, contexto e objetivo.
2. Classificar tarefa, risco, recursos e necessidade de planejamento.
3. Selecionar modelo/agente/skills OpenJarvis automaticamente, com base em capacidades reais e allowlist.
4. Consultar Pestinha com estímulos internos tipados para sinais de atenção, estado, prioridade e adaptação.
5. Planejar com o agente adequado e converter chamadas de ferramentas em propostas estruturadas.
6. Validar toda proposta no executor seguro SERMAX.
7. Executar somente ações autorizadas, em escopo e com limites.
8. Avaliar resultado, aplicar timeout, retry limitado e fallback.
9. Produzir uma única resposta com identidade SERMAX.
10. Registrar telemetria técnica mínima e atualizar estado neural separado conforme política de aprendizagem.

Nenhuma saída do modelo ou da rede neural executa diretamente ações do Windows. O executor SERMAX é a única fronteira de execução.

## Domínios de estado separados

- Memória pessoal existente: `memoria_sermax.json`, preservada byte a byte em migrações.
- Estado neural: `memoria_neural_pestinha.json`, com versão, validação, backup e recuperação.
- Estado operacional dos agentes: armazenamento próprio, sem acesso irrestrito à memória pessoal.
- Logs e traces: técnicos, redigidos e sem segredos ou conteúdo pessoal desnecessário.

## Ordem de implementação

### Fase 1, inventário upstream e contratos
Fixar commits upstream e inventariar APIs, dependências, licenças, agentes, tools, skills, memória, traces, avaliação e mecanismos neurais. Produzir matriz de capacidade, destino, permissões e teste de aceite. Não implementar por suposição.

### Fase 2, contratos internos SERMAX
Definir interfaces tipadas para intenção, plano, chamada de ferramenta, resultado, estado neural, erro, cancelamento e telemetria. Separar planejamento de execução.

### Fase 3, supervisor automático
Implementar classificador/roteador interno e orquestração OpenJarvis. Integrar primeiro `orchestrator`, `native_react`, `operative` e skills aprovadas. Nenhum comando de seleção na interface. O modo Ollama atual permanece como backend/fallback, não como produto concorrente.

### Fase 4, Pestinha comportamental
Ampliar o contrato neural além de estados visuais. Avaliar atenção, habituação, adaptação, condicionamento, memória episódica e feedback documentados no commit fixado. Começar com estímulos sintéticos tipados; excluir sensores de teclado, mouse, janelas e rotina do computador.

### Fase 5, segurança e avaliação
Adicionar testes de roteamento, ferramentas, injeção de prompt, isolamento de memória, falha de cada subsistema, timeouts, cancelamento, consumo de CPU/RAM e degradação graciosa. O verificador deve ser independente do componente que implementou a mudança.

### Fase 6, empacotamento e validação
Resolver compatibilidade Python 3.14/3.13, empacotamento do worker, dependências, licenças e obrigações GPL-3.0-or-later do Pestinha. Testar CI, depois Windows real, preservando a instalação e oferecendo rollback.

## Critérios de aceite da integração real

- Uma pergunta comum chega ao núcleo SERMAX e o supervisor seleciona capacidades automaticamente, sem comandos especiais.
- Tarefas que exigem planejamento usam agente adequado e ciclo multi-etapas.
- Chamadas de ferramentas chegam ao executor SERMAX como propostas estruturadas, passam por validação e respeitam permissões.
- Falha de OpenJarvis ou Pestinha não derruba o terminal nem corrompe estado; Ollama mantém fallback conversacional.
- Pestinha altera sinais internos úteis além de decoração visual, com comportamento mensurável e repetível.
- Memória pessoal, neural e operacional permanecem isoladas.
- Logs e testes identificam exatamente quais componentes foram chamados e por quê.
- Build, testes e smoke test estão ligados ao commit exato.
- Validação no Windows do mantenedor concluída antes de release estável.

## Limites e proibições

- Não criar comandos `/jarvis`, `/pestinha` ou `/motor` como requisito de integração.
- Não tratar `ask()` do agente `simple` como integração completa.
- Não tratar um rótulo LIF/estado visual como aprendizagem neural ampla.
- Não habilitar shell livre, MCP, skills arbitrárias, sensores de rotina ou acesso geral a arquivos.
- Não sobrescrever arquivos funcionais com implementações improvisadas.
- Não alterar `main`, a instalação ativa ou dados pessoais sem autorização.
- Não publicar release antes de testes, licenças e rollback.

## Estado desta retomada

Esta branch registra o contrato arquitetural e a ordem correta de engenharia. Nenhuma capacidade nova é declarada implementada por este documento. A próxima alteração de código deve decorrer do inventário upstream e de testes de contrato, não de roteamento superficial entre dois chats.
