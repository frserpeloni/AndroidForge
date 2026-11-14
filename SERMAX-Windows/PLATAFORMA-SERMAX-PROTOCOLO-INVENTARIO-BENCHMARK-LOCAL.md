# PLATAFORMA SERMAX: PROTOCOLO DE INVENTÁRIO OPERACIONAL E BENCHMARK LOCAL

**Estado:** procedimento proposto, ainda não executado  
**Branch:** `sermax-windows-integration-20261029`  
**Ambiente-alvo:** Windows 11 do host SERMAX  
**Permissão atual:** documentação e planejamento  
**Execução no equipamento:** depende de autorização e acesso ao host

## 1. Objetivo

Definir uma coleta controlada para identificar os recursos realmente disponíveis no computador que hospeda o SERMAX. O resultado servirá de base para a futura seleção automática de modelos e ferramentas.

O protocolo separa:
1. inventário somente leitura;
2. verificações de disponibilidade;
3. benchmark de inferência;
4. análise dos resultados.

As etapas não devem ser misturadas. Uma falha de coleta não autoriza instalação, atualização ou correção automática.

## 2. Regras de segurança

- Não instalar, atualizar ou remover pacotes.
- Não baixar modelos.
- Não alterar variáveis de ambiente.
- Não editar configurações do Ollama, OpenJarvis ou SERMAX.
- Não iniciar serviços que estejam desligados sem autorização.
- Não executar testes de carga prolongados.
- Não alterar memória, histórico, Terminal ou backups.
- Não copiar conteúdo de conversas ou arquivos pessoais para o relatório.
- Registrar comando, horário, código de saída e mensagem de erro.
- Armazenar o relatório em diretório de diagnóstico separado, após autorização para gravação.
- Se o host não estiver acessível, registrar a etapa como não executada.

## 3. Etapa A: identificação do sistema

Coletar:
- versão e edição do Windows;
- arquitetura do sistema;
- nome e modelo do processador;
- quantidade de núcleos lógicos;
- RAM total e disponível;
- unidades de armazenamento, capacidade total e espaço livre;
- adaptadores gráficos identificados e memória de vídeo reportada.

Fontes possíveis no Windows:
- `Get-ComputerInfo`;
- `Get-CimInstance Win32_Processor`;
- `Get-CimInstance Win32_OperatingSystem`;
- `Get-CimInstance Win32_PhysicalMemory`;
- `Get-CimInstance Win32_VideoController`;
- `Get-Volume`.

Os comandos acima são referências para uma futura coleta. Não foram executados neste documento.

## 4. Etapa B: inventário Ollama

Verificações propostas:
1. Consultar a versão do executável `ollama`.
2. Consultar a lista local de modelos com `ollama list`.
3. Consultar detalhes do modelo `sermax`, se ele estiver listado, com `ollama show sermax`.
4. Verificar se o endpoint local responde, sem iniciar ou modificar o serviço.
5. Registrar nome, família, parâmetros, quantização e tamanho quando o próprio Ollama fornecer esses dados.

Regras:
- Se o comando não existir, registrar Ollama como não localizado no PATH.
- Se o serviço não responder, registrar indisponibilidade; não iniciar automaticamente.
- Se `sermax` não estiver listado, não presumir qual modelo ele representa.
- Não baixar ou substituir modelos para resolver ausência.
- Não publicar o conteúdo integral de arquivos de configuração que possam conter dados privados.

## 5. Etapa C: inventário OpenJarvis

Verificações propostas:
- existência do ambiente `.venv-jarvis`;
- existência do interpretador Python configurado;
- existência de `sermax_jarvis_worker.py`;
- versão do Python do ambiente;
- versão do pacote OpenJarvis, se consultável sem importações com efeitos colaterais;
- disponibilidade das dependências declaradas pelo projeto;
- existência e estado do adaptador.

Não executar o worker nesta etapa. A execução de uma inferência de teste pertence à etapa de benchmark e requer autorização específica.

## 6. Etapa D: inventário Pestinha

Verificações propostas:
- existência dos arquivos do componente;
- versão do Python usado pelo ambiente;
- disponibilidade da dependência NumPy;
- disponibilidade do módulo neural;
- existência da memória neural separada.

Não carregar, treinar, alterar ou salvar o estado neural durante o inventário. A leitura da existência dos arquivos não autoriza abrir ou modificar seus conteúdos.

## 7. Etapa E: benchmark controlado

O benchmark só deverá ocorrer depois do inventário e de autorização expressa para executar inferências de teste.

### Preparação
- selecionar um modelo já instalado;
- confirmar que há espaço e RAM disponíveis;
- fechar tarefas pesadas não essenciais, se o usuário autorizar;
- definir duração e limite de tentativas;
- usar prompts sintéticos, sem dados pessoais;
- não alterar o modelo, sua quantização ou configuração;
- medir uma execução por vez.

### Cargas de teste propostas
1. Resposta curta em português.
2. Resumo de um texto sintético com tamanho fixo.
3. Raciocínio com múltiplas etapas e resposta limitada.
4. Repetição do mesmo prompt para medir variação.
5. Teste de contexto maior somente se a memória disponível permitir.

### Métricas
- tempo de carregamento;
- tempo até o primeiro token, quando mensurável;
- duração total;
- tokens de entrada e saída, quando fornecidos;
- tokens por segundo, quando calculável a partir de métricas confiáveis;
- RAM antes, durante e depois;
- uso de GPU e VRAM, se os sensores fornecerem dados confiáveis;
- erros, timeouts e encerramentos inesperados.

Não inferir qualidade factual a partir de velocidade. Avaliação de qualidade exige rubrica e conjunto de perguntas separados.

## 8. Etapa F: teste do fluxo OpenJarvis e fallback

Após autorização específica:
1. executar uma solicitação sintética pelo fluxo OpenJarvis;
2. registrar agente escolhido e backend reportado;
3. observar se o caminho conclui com resposta válida;
4. testar fallback somente em ambiente controlado, com método de falha que não danifique dados nem altere serviços;
5. verificar se o diagnóstico registra a causa;
6. não provocar indisponibilidade do Ollama em ambiente de uso real;
7. não repetir solicitações cujo resultado tenha ficado incerto.

O teste não deverá interromper uma sessão real do usuário.

## 9. Modelo de relatório

| Campo | Resultado |
|---|---|
| Data/hora e fuso | A preencher |
| Host e versão do Windows | A preencher |
| CPU | A preencher |
| RAM total/livre | A preencher |
| GPU/VRAM | A preencher |
| Disco livre | A preencher |
| Versão Ollama | A preencher |
| Modelos instalados | A preencher |
| Identidade do modelo `sermax` | A preencher |
| Versão Python OpenJarvis | A preencher |
| Estado OpenJarvis | A preencher |
| Estado Pestinha | A preencher |
| Benchmarks autorizados | A preencher |
| Erros e limitações | A preencher |
| Evidências anexas | A preencher |

Cada campo deverá usar um dos estados:
- confirmado;
- não localizado;
- indisponível;
- não consultado;
- não autorizado;
- inconclusivo.

Não preencher campos desconhecidos por estimativa.

## 10. Critérios para recomendar modelos

Uma recomendação só será emitida quando houver:
- modelo identificado sem ambiguidade;
- compatibilidade com a tarefa;
- benchmark concluído ou justificativa técnica clara;
- consumo de memória observado;
- estabilidade em mais de uma execução;
- limites de privacidade e custo respeitados.

A recomendação deverá indicar o escopo de validade: equipamento, versão, modelo e condições de teste.

## 11. Sequência operacional

1. Obter autorização para acessar o host e executar inventário somente leitura.
2. Realizar etapas A a D.
3. Entregar relatório do inventário.
4. Apresentar proposta de benchmark com cargas, duração e riscos.
5. Aguardar autorização para benchmark.
6. Executar etapa E.
7. Se autorizado, testar fluxo e fallback na etapa F.
8. Atualizar catálogo de capacidades com evidências.

O inventário não concede autorização automática para benchmark.

## 12. Situação atual

- Protocolo documentado.
- Nenhum comando foi executado no host.
- Nenhum modelo foi iniciado ou baixado.
- Nenhum benchmark foi executado.
- Nenhuma configuração foi alterada.
- Nenhum agente foi acionado.
- Nenhum arquivo funcional, memória, histórico, Terminal ou backup foi modificado.

**Resultado:** o procedimento está pronto para uma futura coleta controlada. A próxima dependência é acesso autorizado ao computador host para executar somente a etapa de inventário. O benchmark continuará separado e dependerá de autorização própria.
