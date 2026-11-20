# PLATAFORMA SERMAX: INVENTÁRIO TÉCNICO DE MODELOS, MOTORES E FERRAMENTAS

**Estado:** auditoria estática do código da branch  
**Data da consulta:** 14/11/2026  
**Branch:** `sermax-windows-integration-20261029`  
**Repositório:** `frserpeloni/AndroidForge`  
**Execução no computador do usuário:** não realizada  
**Testes nesta auditoria:** não executados

## 1. Objetivo e limites

Registrar o que o código versionado comprova sobre modelos, motores, adaptadores e ferramentas disponíveis para o SERMAX.

Esta é uma leitura estática dos arquivos na branch indicada. Ela não comprova que Ollama, OpenJarvis, Qwen, Pestinha ou qualquer dependência estejam instalados e funcionando no computador do usuário. Também não comprova quais modelos estão baixados no Ollama.

Nenhum arquivo funcional foi alterado. Nenhum pacote foi instalado. Nenhum modelo foi iniciado. Nenhum agente foi executado.

## 2. Resumo executivo

O código atual apresenta um fluxo de linguagem com dois caminhos locais:
1. OpenJarvis é tentado primeiro, usando o engine `ollama` e o identificador de modelo configurado como `sermax`.
2. Se o caminho OpenJarvis falhar, o núcleo chama diretamente a API local do Ollama em `127.0.0.1:11434/api/chat`, também com o identificador `sermax`.

O código não comprova a existência de vários modelos de linguagem instalados nem um roteador geral entre provedores. O agente `simple` ou `orchestrator` é selecionado por regras de texto e ambos usam o mesmo engine Ollama através do OpenJarvis.

O Pestinha é uma integração neural auxiliar para estados visuais e métricas. Seu adaptador declara expressamente que saídas neurais não executam ações nem ferramentas. Não é um modelo de linguagem de conversação.

## 3. Modelos e motores encontrados

### 3.1 Ollama

**Estado no código:** integração configurada.

Evidências:
- Endpoint: `http://127.0.0.1:11434/api/chat`.
- Identificador enviado no campo `model`: `sermax`.
- Opções: `num_ctx=2048` e `num_predict=256`.
- `keep_alive=10m`.
- Requisição de conversa direta usa streaming.
- Timeout da chamada direta: 300 segundos.

O arquivo de identidade do núcleo contém a frase de que Qwen é o modelo de linguagem utilizado pelo SERMAX. Entretanto, o código consultado não comprova qual tag de modelo Ollama está associada ao nome `sermax`, nem a versão ou quantização instalada.

**Conclusão:** Ollama está configurado como backend local e fallback. A identidade exata do modelo carregado depende da configuração real do Ollama no computador.

### 3.2 OpenJarvis

**Estado no código:** adaptador e worker presentes.

O adaptador:
- inicia um processo Python separado;
- procura o ambiente em `.venv-jarvis/Scripts/python.exe`, salvo configuração por variável de ambiente;
- procura `sermax_jarvis_worker.py`;
- usa timeout padrão de 180 segundos;
- valida resposta JSON e resposta textual não vazia.

O worker:
- configura o engine como `ollama`;
- recebe o identificador de modelo informado pelo núcleo;
- aceita somente os agentes `simple` e `orchestrator`;
- desativa integrações MCP e armazenamento de ferramentas na configuração apresentada;
- limita ferramentas do agente `orchestrator` a `calculator` e `think`;
- não habilita ferramentas para o agente `simple`.

**Conclusão:** OpenJarvis é uma camada de orquestração sobre o engine Ollama nesta implementação. Não há evidência neste fluxo de que seja um segundo provedor de inferência independente.

### 3.3 Agentes OpenJarvis

O núcleo escolhe o agente por regras textuais:
- `simple` para diálogo direto;
- `orchestrator` quando a mensagem excede 180 caracteres ou contém gatilhos de planejamento, pesquisa, código, análise, testes, execução e termos semelhantes.

Essa seleção não é um classificador semântico independente nem prova avaliação de qualidade. É uma função determinística baseada em tamanho e palavras-chave.

### 3.4 Pestinha

**Estado no código:** adaptador opcional.

Funções encontradas:
- recebe eventos como `idle`, `attention`, `processing`, `completed` e `error`;
- recebe estímulos sensoriais validados;
- coleta métricas de pools, eficácia e atividade motora;
- registra feedback explícito limitado a -1 ou +1;
- salva estado neural em arquivo separado.

O adaptador não autoriza a rede neural a executar comandos, ferramentas ou alterar permissões. Sua finalidade atual é auxiliar estados e sinais visuais.

**Conclusão:** Pestinha não deve entrar na lista de modelos de linguagem. Deve constar em uma categoria separada de componente neural auxiliar.

## 4. Ferramentas locais identificadas

| Componente | Função comprovada no código | Limite observado |
|---|---|---|
| `ferramenta_windows.py` | Informações do Windows, arquitetura, processador, RAM e disco; consultas locais de leitura | Não é um executor geral |
| `sermax_executor.py` | Ações `sistema`, `memoria` e `calcular` | Sem shell, rede externa ou escrita de arquivos |
| `sermax_tarefas.py` | Execução sequencial de até cinco consultas/cálculos explícitos | Interrompe diante de falha ou resultado incerto |
| `sermax_planejador.py` | Solicita plano estruturado ao Ollama e valida etapas | Planeja; não executa as ações do plano |
| OpenJarvis `calculator` | Ferramenta disponível ao agente `orchestrator` | Restrita à configuração do worker |
| OpenJarvis `think` | Ferramenta disponível ao agente `orchestrator` | Restrita à configuração do worker |

Não foi encontrada, nesses arquivos, uma ferramenta geral de navegação web, leitura multimodal, acesso ao Google Drive ou execução irrestrita de código.

## 5. Diagnóstico de roteamento atual

O núcleo mantém um diagnóstico com backend, agente e fallback. O fluxo observado é:

1. O núcleo tenta OpenJarvis.
2. Se OpenJarvis responder, registra backend `openjarvis` e o agente escolhido.
3. Se OpenJarvis lançar exceção, registra a falha e chama Ollama diretamente.
4. Se Ollama falhar, a chamada retorna erro de conexão.
5. A resposta do Ollama registra métricas de duração e contagem de tokens quando o servidor as fornece.

O fallback atual é uma troca de caminho de execução dentro do ecossistema Ollama. Não equivale a uma política de fallback entre provedores distintos.

## 6. Lacunas para a seleção híbrida futura

O inventário estático não encontrou comprovação de:
- catálogo dinâmico de modelos instalados;
- identificação confiável de modelo, versão e quantização;
- verificação de saúde por modelo;
- benchmarks comparáveis de qualidade e latência;
- medição integrada de GPU e VRAM;
- roteamento entre múltiplos provedores;
- capacidades multimodais registradas;
- política geral de privacidade por provedor;
- seleção dinâmica de ferramentas por catálogo de capacidades;
- controle de modelo manual pela futura interface gráfica.

Esses itens são lacunas de evidência ou de implementação. Não significam que o computador não possua determinado recurso.

## 7. Implicações para a Plataforma

1. A primeira versão deve preservar o fluxo OpenJarvis para Ollama já existente.
2. O identificador `sermax` deve ser tratado como configuração, não como prova da identidade do modelo instalado.
3. MAX não deve apresentar `simple` e `orchestrator` como modelos diferentes. São agentes/perfis do OpenJarvis.
4. Pestinha deve aparecer como componente auxiliar, fora do seletor de modelos de linguagem.
5. As ferramentas locais devem ser registradas com suas restrições reais.
6. A futura seleção automática deve começar com o catálogo comprovado e crescer somente após testes.
7. A seleção manual não deve ser exibida como funcional antes de existir mecanismo implementado e validado.

## 8. Próxima verificação necessária

Para fechar o inventário operacional, ainda será necessário consultar o computador que hospeda o SERMAX, mediante autorização e execução controlada, para obter:
- saída de `ollama list`;
- versão do Ollama;
- associação do identificador `sermax` ao modelo real;
- estado do ambiente Python OpenJarvis;
- dependências instaladas;
- disponibilidade e versão do Pestinha;
- CPU, RAM, GPU, VRAM e espaço em disco;
- tempos reais de inicialização e resposta.

Esta verificação não foi executada nesta auditoria porque o ambiente local do usuário não está conectado a esta sessão.

## 9. Estado e proteção

- Auditoria estática concluída para os arquivos listados.
- Nenhum teste foi executado.
- Nenhum agente foi executado.
- Nenhum modelo foi iniciado.
- Nenhuma alteração no núcleo, Terminal, memória, histórico ou backup.
- Nenhuma instalação ou alteração no computador do usuário.
- Nenhuma implementação da Plataforma autorizada por este documento.

**Resultado:** o código comprova atualmente um fluxo local OpenJarvis sobre Ollama, com fallback direto para Ollama, agentes `simple` e `orchestrator`, ferramentas locais restritas e Pestinha como componente neural auxiliar. O inventário de modelos efetivamente instalados continua pendente de verificação no equipamento.
