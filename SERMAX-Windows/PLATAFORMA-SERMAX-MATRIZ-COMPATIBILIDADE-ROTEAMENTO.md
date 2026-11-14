# PLATAFORMA SERMAX: MATRIZ DE COMPATIBILIDADE DE TAREFAS, MODELOS E FERRAMENTAS

**Estado:** análise estática e matriz preliminar  
**Branch:** `sermax-windows-integration-20261029`  
**Base:** código versionado e documentos de arquitetura da Plataforma  
**Execução no equipamento:** não realizada  
**Testes:** não executados  
**Implementação:** não autorizada por este documento

## 1. Objetivo

Relacionar as tarefas previstas para a Plataforma SERMAX com os recursos comprovados no código atual, indicar lacunas e definir o comportamento seguro da primeira versão.

Esta matriz separa três situações:
- **Disponível no código:** existe integração ou função identificável no repositório.
- **Parcial:** existe recurso relacionado, mas não cobre a capacidade completa.
- **Pendente:** não há implementação comprovada ou falta validação operacional.

A existência de um arquivo ou configuração não comprova que o recurso esteja instalado ou funcionando no computador.

## 2. Matriz de compatibilidade

| Tipo de tarefa | Recurso atual identificado | Situação | Regra para a primeira versão |
|---|---|---|---|
| Conversação textual | OpenJarvis sobre engine Ollama, com fallback direto para Ollama | Disponível no código, operação não validada no equipamento | Preservar fluxo atual e serializar chamadas ao núcleo |
| Perguntas simples | Agente OpenJarvis `simple` | Parcial, seleção por regras textuais | Manter regra existente, sem apresentar como modelo separado |
| Planejamento e tarefas complexas | Agente `orchestrator`, ferramentas `calculator` e `think` | Parcial, seleção por palavras-chave e tamanho | Não ampliar ferramentas sem revisão e testes |
| Cálculos locais | Executor local e ferramenta calculator do OpenJarvis | Disponível com limites distintos | Preferir cálculo local determinístico quando a expressão for reconhecida |
| Consulta de memória | Leitura de `memoria_sermax.json` pelo núcleo | Disponível no código | Respeitar proteção e regras existentes de memória |
| Diagnóstico Windows | `ferramenta_windows.py` | Disponível no código | Consultas de leitura, sem alteração do sistema |
| Leitura de arquivos comuns | Não foi comprovado um catálogo geral de parsers integrado ao núcleo | Pendente | Não prometer suporte universal a PDF, DOCX, XLSX ou outros formatos |
| Análise de imagens | Não foi comprovado adaptador de visão no fluxo auditado | Pendente | Não selecionar modelo de visão até inventário e teste |
| Áudio e voz | Não foi comprovado pipeline STT/TTS integrado ao núcleo auditado | Pendente | Manter fora do roteamento funcional da primeira versão |
| Pesquisa na web | Não foi comprovada ferramenta web geral no conjunto auditado | Pendente | Não indicar pesquisa externa como recurso já integrado |
| Código e depuração | Supervisor externo de desenvolvimento e componentes locais de execução restrita | Parcial | Não confundir agente de desenvolvimento com recurso disponível ao usuário final |
| Execução de ações Windows | Executor com ações `sistema`, `memoria` e `calcular` | Disponível com escopo restrito | Proibir shell genérico e escrita arbitrária |
| Execução de planos | `sermax_tarefas.py`, até cinco tarefas sequenciais | Disponível com escopo restrito | Interromper diante de falha ou resultado incerto |
| Integração Pestinha | Adaptador neural para contexto, métricas e estados visuais | Parcial, componente auxiliar | Não listar como modelo de linguagem nem permitir ações |
| Google Drive | Projeto SERMAX Drive Connect em planejamento | Pendente e bloqueado | Não implementar nem conectar nesta fase |
| Sincronização entre dispositivos | Especificação documental, sem serviço implementado comprovado | Pendente | Não prometer sincronização funcional |
| Acesso remoto | Arquitetura documentada, sem serviço operacional validado | Pendente | Não expor portas nem habilitar acesso remoto nesta fase |

## 3. Matriz de seleção para o roteador futuro

A tabela abaixo define o comportamento pretendido. Não descreve uma funcionalidade já implementada.

| Solicitação detectada | Seleção automática pretendida | Verificação obrigatória | Fallback permitido |
|---|---|---|---|
| Texto simples | Perfil leve compatível | Saúde do backend e contexto | OpenJarvis para Ollama conforme fluxo existente |
| Raciocínio complexo | Perfil de raciocínio disponível | Capacidade, contexto e recursos do host | Somente dentro da política de privacidade |
| Cálculo reconhecido | Calculadora determinística | Validação da expressão | Sem necessidade de modelo quando o cálculo local resolver |
| Consulta do sistema | Ferramenta Windows de leitura | Ação dentro da lista permitida | Sem fallback para comando de sistema genérico |
| Memória | Leitura autorizada do núcleo | Escopo e integridade do arquivo | Sem cópia ou alteração automática |
| Arquivo | Parser específico do formato | Tipo, tamanho, integridade e permissões | Não enviar a serviço remoto sem política e autorização |
| Imagem | Modelo com visão | Formato, resolução e disponibilidade | Informar incompatibilidade se não houver modelo validado |
| Áudio | Pipeline de áudio compatível | Codec, duração e privacidade | Informar indisponibilidade |
| Pesquisa externa | Ferramenta de pesquisa autorizada | Conectividade e fontes | Não substituir por resposta inventada |
| Ação externa | Ferramenta específica | Classe de permissão e aprovação | Nunca repetir quando o resultado for incerto |

## 4. Requisitos de hardware e custo computacional

O código consultado não fornece medições atuais de CPU, RAM livre, GPU, VRAM ou latência no computador do usuário.

Antes de definir limites automáticos, será necessário coletar:
- CPU, arquitetura e número de núcleos;
- RAM instalada e disponível;
- GPU e VRAM, se houver;
- espaço livre em disco;
- versão do Windows;
- versão do Ollama;
- modelos locais e tamanhos instalados;
- tempo de carregamento e resposta por modelo;
- consumo de memória durante uma conversa representativa.

Não será definido um modelo recomendado por estimativa de hardware. A máquina deverá ser medida antes.

## 5. Regras de compatibilidade e exclusão

MAX deverá excluir um candidato quando:
- não suportar a modalidade exigida;
- exceder limites conhecidos de contexto ou memória;
- estiver indisponível ou com estado de saúde expirado;
- violar a política de privacidade da tarefa;
- exigir ferramenta ou permissão não concedida;
- não tiver versão ou origem identificável quando isso for requisito da política.

A ausência de informação deverá ser tratada como desconhecida, não como compatibilidade confirmada.

## 6. Comportamento com seleção manual

- O modelo escolhido manualmente permanece fixo no escopo definido pelo usuário.
- MAX informa incompatibilidade sem trocar silenciosamente o modelo.
- O usuário decide se aceita outra opção quando a escolha manual não atende à tarefa.
- A ferramenta manualmente selecionada não ganha permissão automática.
- A escolha manual e a escolha automática devem aparecer no registro de execução.

## 7. Riscos identificados

1. **Identificador de modelo ambíguo:** `sermax` não comprova tag, família, versão ou quantização do modelo instalado.
2. **Dois caminhos sobre o mesmo engine:** OpenJarvis e Ollama direto não representam dois provedores independentes.
3. **Seleção por palavras-chave:** a regra atual pode classificar incorretamente solicitações ambíguas.
4. **Concorrência de sessão:** o núcleo mantém estado global de sessão e histórico; não liberar concorrência antes de isolamento comprovado.
5. **Capacidade multimodal não comprovada:** não anunciar visão, áudio ou análise universal de arquivos.
6. **Ferramenta confundida com autorização:** roteamento nunca substitui aprovação.
7. **Hardware desconhecido:** não escolher modelo por requisitos presumidos.
8. **Fallback com efeito incerto:** não reenviar ações quando o resultado anterior não for conhecido.

## 8. Critérios de aceite para uma implementação futura

1. Cada categoria de tarefa possui capacidades e requisitos declarados.
2. O catálogo distingue modelos, agentes, motores e ferramentas.
3. O sistema verifica disponibilidade real antes de selecionar.
4. O identificador `sermax` é associado a uma referência de modelo verificável.
5. A escolha manual é respeitada e registrada.
6. Incompatibilidade é informada sem troca silenciosa.
7. Fallback respeita privacidade, permissões e estado da execução.
8. Ações restritas continuam protegidas por aprovação.
9. A interface mostra modelo, agente e ferramenta sem confundir suas funções.
10. Métricas de hardware e latência vêm de medições, não de estimativas.
11. Chamadas ao núcleo permanecem serializadas até comprovação de isolamento.
12. Falhas e resultados incertos não provocam repetição automática.

**Estado dos critérios:** definidos, não testados.

## 9. Próxima etapa documental

A próxima etapa é definir o **protocolo de inventário operacional e benchmark local**, com comandos de diagnóstico somente leitura, coleta de versões, identificação do modelo Ollama, medição de recursos e testes de latência controlados.

A execução desses comandos no computador do usuário dependerá de acesso autorizado ao equipamento. A especificação do protocolo não autoriza instalação, alteração de configurações ou execução de benchmarks que alterem dados.

## 10. Registro de integridade

- Matriz construída a partir da leitura estática dos arquivos da branch.
- Não foram executados testes ou benchmarks.
- Não houve execução de agentes.
- Não houve acesso ao computador do usuário.
- Não houve instalação ou inicialização de modelos.
- Núcleo, Terminal, memória, histórico e backups não foram alterados.
- Drive Connect permanece bloqueado para implementação.
- A implementação da Plataforma permanece sujeita à autorização específica.

**Resultado:** a matriz separa as capacidades comprovadas no código das funções ainda pendentes. A Plataforma deverá iniciar com o fluxo textual local existente e expandir o roteamento somente após inventário operacional, medições e testes.
