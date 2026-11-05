# Arquitetura SERMAX unificado: incorporação Jarvis + Pestinha

**Objetivo aprovado pelo mantenedor:** o usuário interage exclusivamente com SERMAX. As tecnologias incorporadas de OpenJarvis e Pestinha são capacidades internas, coordenadas automaticamente pelo núcleo. Não deve existir dependência de comandos como `/jarvis`, `/pestinha` ou `/motor` para obter essas capacidades.

**Estado:** especificação de arquitetura. Não representa integração concluída nem altera o comportamento executável atual.

## 1. Princípio de integração

SERMAX é o produto, a identidade conversacional, o supervisor e o ponto único de entrada. Jarvis e Pestinha deixam de ser apresentados como assistentes ou motores escolhidos pelo usuário.

A separação em processos internos continua permitida quando exigida por compatibilidade de Python, isolamento de dependências ou estabilidade. Separação de processo não significa separação de produto: o núcleo deve coordenar os serviços sem intervenção manual do usuário.

## 2. Capacidades a incorporar

### OpenJarvis

O inventário de capacidades deve cobrir, com base no código upstream fixado e em suas licenças:

- interface unificada para modelos e provedores;
- seleção automática de modelo/provedor por tarefa, com política SERMAX;
- agentes e fluxo de execução;
- ferramentas e chamadas estruturadas, integradas ao executor seguro SERMAX;
- contexto e recuperação de informação;
- memória e estado de agente, subordinados à arquitetura de memória SERMAX;
- avaliação, observabilidade e métricas, quando disponíveis no upstream;
- tratamento de falhas, timeout, fallback e cancelamento.

Não considerar uma capacidade incorporada enquanto existir somente uma chamada ao método `ask()` com agente simples, sem ferramentas e sem contexto.

### Pestinha

O inventário deve examinar os módulos upstream, não somente a classe `LIFBrain`:

- dinâmica neural LIF e estado interno;
- estímulos e processamento temporal;
- mecanismos de atenção, motivação e seleção de ação presentes no código;
- memória/estado neural e persistência;
- interfaces de percepção e ação, quando existirem;
- aprendizagem, adaptação e mecanismos de feedback presentes no projeto.

Cada capacidade deve receber uma decisão documentada: incorporar, adaptar, substituir por implementação SERMAX equivalente ou rejeitar por incompatibilidade, risco ou ausência de utilidade. Não atribuir ao Pestinha capacidades que o código upstream não implementa.

## 3. Núcleo unificado SERMAX

O núcleo deve coordenar um ciclo automático:

1. interpretar a solicitação e recuperar contexto autorizado;
2. classificar objetivo, risco, recursos necessários e necessidade de planejamento;
3. selecionar internamente modelo, agente e ferramentas adequados;
4. consultar os componentes neurais para sinais de atenção, estado, prioridade e adaptação, sem tratar saídas neurais como comandos confiáveis;
5. planejar a execução e validar permissões;
6. executar ferramentas por interfaces controladas do SERMAX;
7. avaliar resultado, detectar falhas e decidir entre concluir, tentar novamente dentro de limites ou pedir aprovação;
8. produzir uma única resposta SERMAX;
9. registrar métricas e atualizar estados de aprendizagem autorizados.

O fluxo não deve exigir que o usuário escolha Jarvis, Pestinha, agente ou motor.

## 4. Memória e aprendizagem

Manter domínios separados:

- `memoria_sermax.json`: memória pessoal já existente, preservada byte a byte durante a migração e protegida contra sobrescrita acidental;
- estado neural Pestinha: arquivo próprio, versionado e validado;
- memória/contexto operacional de agentes: armazenamento próprio, com política de retenção e acesso definida pelo SERMAX;
- logs técnicos: sem credenciais, conteúdo pessoal desnecessário ou segredos.

O componente neural não recebe acesso irrestrito à memória pessoal. O núcleo entrega estímulos e sinais mínimos necessários. Qualquer aprendizagem baseada em conversas exige política explícita, filtragem, rastreabilidade e mecanismo de correção/esquecimento.

## 5. Ferramentas e autonomia

As ferramentas Jarvis devem ser adaptadas ao executor SERMAX. Não importar execução arbitrária de shell, acesso irrestrito a arquivos ou navegação sem política de permissões.

Classificar ações por risco:
- leitura e cálculo local: execução automática dentro de escopo permitido;
- escrita em workspace temporário: permitida com limites, diff e rollback;
- alteração da instalação ativa, exclusão, credenciais, compras, publicação, merge ou ações externas: aprovação explícita.

Saídas de modelo e da rede neural são dados não confiáveis. Toda ação passa por validação determinística do executor.

## 6. Compatibilidade e implantação

- SERMAX Core e Pestinha permanecem no ambiente Python 3.14, se a compatibilidade upstream for confirmada.
- OpenJarvis permanece em worker Python 3.13 enquanto o upstream exigir `<3.14`; o worker é serviço interno invisível ao usuário.
- O launcher inicia e supervisiona os serviços necessários, verifica saúde e aplica fallback.
- O Terminal original, rosto ASCII, cores, voz, atalhos existentes e caminho `C:\\SERMAX` devem ser preservados.
- Atualização deve manter memória, configuração, modelos e arquivos do usuário, com backup e rollback.

## 7. Etapas de engenharia e critérios de aceite

### Etapa A: inventário upstream completo
- fixar commits e dependências;
- mapear módulos, APIs, capacidades, dados e permissões;
- registrar licença por componente;
- produzir matriz capacidade x destino SERMAX.

Aceite: nenhuma afirmação de integração sem arquivo/API upstream identificado.

### Etapa B: camada interna de capacidades
- definir contratos internos independentes da interface;
- substituir seleção manual de motor por roteamento automático;
- unificar agentes, ferramentas e contexto sob o supervisor SERMAX;
- definir ciclo neural útil além da expressão visual.

Aceite: perguntas comuns e tarefas suportadas passam pelo mesmo ponto de entrada, sem comandos de seleção.

### Etapa C: aprendizagem e memória
- separar estado neural, memória pessoal e memória operacional;
- implementar validação, migração, backup e recuperação;
- testar isolamento de dados e persistência.

Aceite: nenhum componente sobrescreve ou lê dados fora de sua permissão.

### Etapa D: segurança e avaliação
- testes de permissões e injeção de prompt;
- limites de tempo, tentativas, CPU e RAM;
- avaliação de qualidade por tarefa;
- fallback quando Jarvis, Ollama ou Pestinha falharem.

Aceite: falhas isoladas não derrubam o Terminal nem corrompem memórias.

### Etapa E: empacotamento e validação
- build Windows reproduzível;
- teste do executável no computador do mantenedor;
- revisão GPL-3.0-or-later do Pestinha e demais licenças;
- atualizador com backup e rollback.

Aceite: só declarar versão estável após todos os gates. Builds semanais incompletos devem ser marcados como experimentais e não instalados quando houver risco aos dados.

## 8. Estado real na data desta especificação

- OpenJarvis: adaptador de resposta e worker isolado existentes; não equivale à incorporação de todas as capacidades do projeto.
- Pestinha: adaptador LIF existente, conectado a eventos limitados do ciclo e estados visuais; não equivale à incorporação de toda a arquitetura neural ou de aprendizagem.
- Roteamento: existe seleção manual `/motor`; isso é provisório e contraria a experiência final pretendida.
- Agentes com ferramentas, memória operacional unificada e roteamento automático: não comprovados como integrados.
- Aprendizagem neural ampla e feedback adaptativo: não comprovados como integrados.
- Testes contra modelos reais, desempenho no Windows do mantenedor, revisão de licenças e atualizador: pendentes.

## 9. Regra de comunicação

Relatórios devem separar: implementado, integrado ao fluxo principal, testado automaticamente, validado no Windows real e pendente. Nunca descrever um adaptador ou uma prova de conceito como incorporação completa.
