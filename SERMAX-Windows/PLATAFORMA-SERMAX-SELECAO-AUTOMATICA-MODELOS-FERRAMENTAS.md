# PLATAFORMA SERMAX: SELEÇÃO AUTOMÁTICA DE MODELOS E FERRAMENTAS

**Estado:** especificação conceitual e operacional  
**Escopo:** planejamento da Plataforma SERMAX  
**Implementação:** não autorizada por este documento  
**Branch de referência:** `sermax-windows-integration-20261029`

## 1. Objetivo

Definir como MAX selecionará modelos, motores e ferramentas para atender cada solicitação, preservando a escolha manual do usuário.

A seleção será híbrida:
- MAX identifica a natureza da tarefa e recomenda a combinação adequada.
- O usuário mantém controle para escolher manualmente um modelo ou ferramenta.
- A interface apresenta a escolha de forma discreta e informa o recurso em uso.
- MAX não troca silenciosamente uma escolha manual durante uma execução.

Esta especificação não autoriza alteração no núcleo atual, no Terminal, nos adaptadores, nos arquivos de memória ou na instalação existente.

## 2. Princípios obrigatórios

1. **Intenção antes do modelo:** classificar a tarefa antes de selecionar o motor.
2. **Capacidade comprovada:** selecionar somente modelos e ferramentas registrados e disponíveis.
3. **Compatibilidade:** considerar formato de entrada, saída, contexto, visão, áudio, ferramentas e requisitos de execução.
4. **Custo computacional:** considerar RAM, CPU, GPU, VRAM, latência e consumo estimado quando esses dados existirem.
5. **Privacidade:** priorizar processamento local para dados que não devam sair do equipamento, conforme política definida.
6. **Permissões:** a seleção de uma ferramenta nunca concede autorização para executar uma ação.
7. **Fallback controlado:** trocar de motor somente diante de falha identificada e dentro das regras desta especificação.
8. **Transparência:** registrar e informar qual modelo e ferramenta atenderam a solicitação.
9. **Controle manual:** respeitar a escolha explícita do usuário até o fim da tarefa, salvo indisponibilidade ou incompatibilidade, situações que exigem explicação e decisão do usuário.
10. **Preservação:** os motores atuais OpenJarvis e Ollama permanecem protegidos e integrados por adaptadores.

## 3. Classificação da solicitação

MAX deverá classificar cada solicitação em uma ou mais categorias:

| Categoria | Exemplos | Capacidades necessárias |
|---|---|---|
| Conversação | perguntas gerais, explicações | linguagem |
| Raciocínio | planejamento, análise, problemas complexos | raciocínio e contexto |
| Pesquisa | consulta de fontes externas | ferramenta de pesquisa e síntese |
| Arquivos | leitura, extração e análise de documentos | parser compatível com o formato |
| Imagens | interpretação de imagens | visão |
| Áudio | transcrição, fala e voz | áudio/STT/TTS conforme a tarefa |
| Código | leitura, escrita e depuração | código e ambiente autorizado |
| Dados | cálculos, tabelas e análise | execução controlada e análise |
| Ações | operações no sistema ou serviços | ferramenta específica e política de aprovação |

A classificação pode conter múltiplas categorias. Exemplo: analisar uma planilha enviada e pesquisar dados externos exige arquivos, dados e pesquisa.

## 4. Registro de capacidades

Cada modelo ou ferramenta deverá possuir um registro com, no mínimo:

- identificador e nome;
- tipo: modelo, motor local, serviço remoto ou ferramenta;
- estado: disponível, indisponível, degradado ou desativado;
- capacidades suportadas;
- formatos de entrada e saída;
- limite de contexto, quando conhecido;
- requisitos de hardware;
- localização de processamento: local ou remoto;
- custo conhecido ou classificação de custo;
- tempo limite;
- versão e origem;
- permissões exigidas;
- critérios de saúde e última verificação.

MAX não deverá inferir que um recurso está disponível só porque sua configuração existe. A disponibilidade depende de verificação de saúde ou de uma resposta válida recente, respeitando o tempo de validade do estado.

## 5. Fluxo de decisão

1. Receber a solicitação e os anexos autorizados.
2. Identificar intenção, categorias, complexidade e requisitos de modalidade.
3. Verificar se o usuário fixou manualmente modelo ou ferramenta.
4. Consultar o registro de capacidades e o estado de saúde.
5. Aplicar as políticas de privacidade e permissão.
6. Eliminar candidatos incompatíveis.
7. Classificar os candidatos restantes por adequação, qualidade esperada, latência e custo computacional.
8. Selecionar o candidato de maior prioridade dentro dos limites configurados.
9. Executar por meio do adaptador correspondente.
10. Avaliar o resultado técnico, sem confundir resposta válida com resposta factualmente correta.
11. Acionar fallback somente se as condições permitirem.
12. Registrar a decisão e apresentar um indicador compacto ao usuário.

## 6. Prioridades de seleção automática

A ordem de decisão será:

1. Compatibilidade obrigatória com a tarefa.
2. Restrições de privacidade e localização dos dados.
3. Permissões e limites de segurança.
4. Disponibilidade e saúde do recurso.
5. Adequação de capacidade e qualidade esperada.
6. Viabilidade no hardware disponível.
7. Latência.
8. Custo financeiro ou computacional.

A qualidade não será estimada por um único número sem evidência. Quando não houver benchmark comparável, MAX deverá usar perfis qualitativos documentados e evitar alegações de superioridade.

## 7. Perfis de execução

Os perfis são critérios de decisão, não nomes fixos de modelos.

- **Rápido:** tarefas simples, baixa latência e baixo consumo.
- **Equilibrado:** uso geral, com relação adequada entre qualidade e recursos.
- **Raciocínio:** tarefas com múltiplas etapas, planejamento ou análise complexa.
- **Local e privado:** processamento no equipamento ou servidor controlado pelo usuário.
- **Multimodal:** tarefas com imagem, áudio ou outros formatos além de texto.
- **Pesquisa assistida:** tarefas que exigem fontes externas e referências.
- **Código controlado:** análise ou execução de código em ambiente isolado e autorizado.

MAX escolhe o perfil conforme a tarefa. O usuário poderá fixar um modelo ou perfil manualmente quando a interface oferecer essa opção.

## 8. Política de escolha manual

Quando o usuário selecionar um modelo:
- a seleção fica fixa para a tarefa ou conversa, conforme o escopo escolhido na interface;
- MAX não substitui o modelo silenciosamente;
- se faltar capacidade necessária, MAX explica a incompatibilidade;
- se o modelo ficar indisponível, MAX informa a falha e solicita autorização para trocar, exceto se o usuário tiver ativado previamente uma regra explícita de fallback;
- a escolha manual não altera permissões de ferramentas.

Quando o usuário selecionar uma ferramenta:
- a ferramenta escolhida fica vinculada à tarefa;
- MAX verifica disponibilidade, compatibilidade e permissão;
- operações que exigem confirmação continuam exigindo confirmação.

## 9. Fallback e recuperação

Fallback automático só será permitido quando:
- a execução falhar antes de produzir efeito externo ou persistente;
- a falha for classificada como transitória ou indisponibilidade;
- o próximo candidato for compatível e estiver dentro das mesmas restrições de privacidade;
- a política da tarefa permitir fallback automático.

Fallback não será automático quando:
- a execução tiver resultado incerto;
- houver possibilidade de repetição de uma ação externa;
- a troca exigir envio de dados a outro provedor;
- a escolha manual estiver fixa sem fallback autorizado;
- a falha envolver integridade, autenticação, permissão ou segurança.

Em resultado incerto, a tarefa deverá assumir estado equivalente a `unknown_outcome`, registrar o ocorrido e aguardar reconciliação. Não repetir automaticamente uma operação cujo efeito não foi confirmado.

## 10. Ferramentas e permissões

A seleção de ferramenta é separada da autorização de uso.

- **Classe A, automática:** consulta, pesquisa e leitura de fontes autorizadas.
- **Classe B, confirmação:** edição, instalação, alteração de configuração e envio externo.
- **Classe C, autorização expressa:** exclusão, alteração de memória ou histórico, backups, integridade e operações críticas.

A interface deverá mostrar a ferramenta selecionada e o tipo de aprovação necessário. MAX não deverá contornar uma recusa, uma permissão negada ou um pedido de confirmação.

## 11. Interface do usuário

A tela inicial permanece limpa. O seletor manual fica discreto, sem ocupar o centro da experiência.

Na conversa, apresentar:
- nome do modelo ou perfil ativo;
- ferramenta em uso quando houver;
- indicador compacto de processamento local ou remoto;
- estado de fallback, quando ocorrer;
- aviso de incompatibilidade ou indisponibilidade;
- controle manual acessível sem abrir painéis técnicos extensos.

Detalhes técnicos, custos e histórico de roteamento ficam sob demanda. Não exibir uma lista extensa de modelos na tela inicial.

## 12. Registro de decisão e auditoria

Para cada execução, registrar:
- identificador da tarefa;
- data e hora;
- categorias detectadas;
- modelo/perfil selecionado;
- ferramenta(s) acionada(s);
- motivo resumido da seleção;
- origem local/remota;
- estado de saúde observado;
- latência e consumo, quando mensuráveis;
- fallback e motivo, se houver;
- aprovações exigidas e resultado;
- estado final ou resultado incerto.

Não registrar conteúdo sensível integral por padrão. O histórico técnico deverá respeitar as políticas de retenção e as permissões de memória e auditoria.

## 13. Limites da primeira versão

A primeira versão da Plataforma deverá manter o roteamento simples e previsível:
- usar os adaptadores já existentes, sem reescrever o núcleo;
- serializar chamadas ao núcleo enquanto o isolamento de sessão não estiver comprovado;
- preservar o fluxo atual OpenJarvis primeiro e Ollama como fallback, até uma migração formal testada;
- não executar ferramentas arbitrárias;
- não habilitar troca automática para serviços remotos sem política explícita;
- não incluir Drive Connect;
- não prometer seleção dinâmica de agentes de desenvolvimento;
- não alterar o Terminal nem os arquivos de memória.

A evolução para roteamento multi-modelo só ocorrerá depois de inventário real dos motores instalados, medições de hardware e testes de compatibilidade.

## 14. Testes de aceitação planejados

1. Solicitação simples seleciona perfil compatível.
2. Tarefa complexa prioriza capacidade de raciocínio adequada.
3. Tarefa com imagem elimina modelos sem visão.
4. Tarefa com áudio exige capacidade correspondente.
5. Modelo indisponível é identificado antes da execução, quando possível.
6. Estado de saúde expirado provoca nova verificação.
7. Escolha manual é respeitada.
8. Incompatibilidade de escolha manual é explicada.
9. Fallback não viola a política de privacidade.
10. Fallback não ocorre após resultado incerto.
11. Ferramenta Classe B solicita confirmação.
12. Ferramenta Classe C exige autorização expressa.
13. Recusa de permissão bloqueia a execução.
14. Interface mostra modelo e ferramenta ativos.
15. Registro permite reconstruir a decisão sem armazenar conteúdo sensível desnecessário.
16. Falha de um adaptador não corrompe o estado da conversa.
17. Chamadas concorrentes ao núcleo permanecem serializadas.
18. Reinício não repete operações com resultado incerto.

**Estado dos testes:** planejados. Nenhum teste foi executado por esta especificação.

## 15. Dependências para uma futura implementação

Antes de implementar, será necessário:
- inventariar os modelos e ferramentas efetivamente instalados;
- confirmar versões e endpoints dos adaptadores existentes;
- medir RAM, CPU, GPU, VRAM e latência no equipamento real;
- definir limites de custo e privacidade;
- estabelecer como o usuário fixa modelo, perfil e escopo da escolha;
- definir telemetria mínima e retenção;
- implementar testes automatizados e testes no equipamento real;
- obter autorização expressa para criar o diretório e os arquivos de implementação da Plataforma.

## 16. Fora do escopo e bloqueios

Este documento não:
- cria código executável;
- altera o núcleo SERMAX;
- altera o Terminal;
- modifica memórias, históricos ou backups;
- instala modelos ou ferramentas;
- ativa serviços remotos;
- executa agentes;
- autoriza merge da PR;
- autoriza implementação do Drive Connect.

**Conclusão operacional:** a seleção híbrida está especificada em nível conceitual e de operação. A próxima atividade segura é consolidar o inventário real de modelos, motores e ferramentas já presentes no repositório e nos adaptadores, sem instalar, executar ou alterar componentes.
