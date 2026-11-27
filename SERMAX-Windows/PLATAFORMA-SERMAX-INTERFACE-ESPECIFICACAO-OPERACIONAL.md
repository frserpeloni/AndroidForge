# SERMAX Platform, especificação operacional da interface

**Estado:** especificação documental. Não implementada.
**Ordem:** ORDEM-SERMAX-PLATAFORMA-002.
**Branch:** `sermax-windows-integration-20261029`.
**Dependências:** arquitetura GUI, contrato preliminar da API e matriz de testes/riscos.
**Objetivo:** transformar as diretrizes visuais em comportamento verificável para a primeira interface gráfica.

## 1. Princípios de interação

1. A conversa com MAX é a atividade principal.
2. Cada tela apresenta uma tarefa principal e mantém ações secundárias recolhidas.
3. A interface não exibe painéis técnicos permanentes.
4. O usuário identifica com clareza o que está selecionado, o que está em execução e o que exige aprovação.
5. Ações críticas nunca ficam junto de ações comuns sem confirmação.
6. O estado visual não substitui a validação feita pelo serviço.
7. A interface deve permanecer utilizável com teclado, mouse, toque e leitores de tela.

## 2. Estrutura global

### 2.1 Cabeçalho compacto

Elementos:
- Identidade SERMAX em tamanho reduzido.
- Nome da área atual.
- Indicador simples de conexão com o serviço central.
- Menu de perfil e configurações.

O cabeçalho não deve exibir CPU, RAM, temperatura, nome do modelo interno, logs ou métricas por padrão.

Estados do serviço:
- **Conectado:** serviço central acessível.
- **Reconectando:** tentativa de restabelecer comunicação.
- **Offline:** serviço central indisponível.
- **Local:** motor local disponível no próprio computador, quando detectado e validado.

Não indicar “MAX online” com base apenas no carregamento da interface. O estado depende de resposta válida do endpoint de saúde do serviço.

### 2.2 Navegação principal

Menu compacto com:
- Início
- Conversas
- Projetos
- Arquivos
- Ferramentas
- Memória
- Integrações
- Configurações

No desktop, o menu pode ficar recolhido por padrão, exibindo ícones com rótulos acessíveis. No celular, abre como painel temporário e fecha após a seleção. A tela de conversa não deve manter uma segunda coluna aberta por padrão.

### 2.3 Área de conteúdo

- Uma área de conteúdo principal.
- Largura de leitura controlada para mensagens longas.
- Rolagem independente somente quando necessária.
- Campo de mensagem fixo na parte inferior da conversa.
- Painéis contextuais temporários, com fechamento explícito e retorno ao ponto anterior.

## 3. Tela Início

Ordem visual:
1. Mascote SERMAX discreto.
2. Saudação curta de MAX.
3. Campo de mensagem em destaque.
4. Seletor de projeto atual, discreto.
5. Seletor de modelo, inicialmente em **Automático**.
6. Até três atalhos: Pesquisar, Analisar arquivos e Automatizar.

Comportamento:
- Enter envia a mensagem.
- Shift+Enter insere nova linha.
- Botão de envio fica desabilitado enquanto não houver conteúdo válido ou envio em andamento.
- Anexar abre o seletor de arquivos do dispositivo.
- Seleção de projeto mostra o projeto atual e permite trocar sem sair da tela.
- Seleção de modelo oferece Automático e modelos habilitados. Não listar modelos indisponíveis como selecionáveis.
- A escolha manual permanece ativa até o usuário retornar a Automático ou definir outra preferência, com escopo claramente indicado.

A tela inicial não deve apresentar histórico completo, estatísticas, fontes, permissões, atividade técnica ou cartões de recomendação.

## 4. Tela Conversa

### 4.1 Mensagens

Cada mensagem apresenta:
- Autor.
- Conteúdo.
- Horário discreto, quando útil.
- Anexos e referências associados.
- Ações contextuais, como copiar ou selecionar texto.

Ações de edição, exclusão ou alteração de histórico não devem aparecer como controles primários. Se forem incluídas posteriormente, seguem o nível de permissão correspondente.

### 4.2 Campo de mensagem

Elementos:
- Área de texto expansível.
- Anexar.
- Seletor compacto de projeto, quando a conversa permitir troca.
- Seletor de modelo.
- Enviar ou cancelar geração, conforme o estado.

O campo permanece acessível durante a rolagem. Em telas pequenas, não deve cobrir a última mensagem nem o teclado virtual.

### 4.3 Estados de execução

| Estado interno | Texto curto na interface | Comportamento |
|---|---|---|
| queued | Na fila | Indica que a solicitação aguarda processamento |
| running | MAX está respondendo | Exibe resposta progressiva quando disponível |
| waiting_approval | Aguardando sua confirmação | Mostra resumo da ação e opções aprovar ou rejeitar |
| completed | Concluído | Libera novo envio |
| failed | Não foi possível concluir | Preserva a mensagem e oferece detalhes úteis e nova tentativa |
| cancelled | Cancelado | Mantém o conteúdo já recebido |

A interface não deve simular progresso nem afirmar que uma ferramenta foi executada antes de receber confirmação do serviço.

### 4.4 Ferramentas

Quando uma ferramenta estiver ativa, exibir uma linha compacta com:
- Nome amigável da atividade.
- Estado: iniciada, concluída ou falhou.
- Resultado resumido, quando disponível.

Detalhes técnicos ficam recolhidos. Credenciais, prompts internos, stack traces e parâmetros sensíveis nunca aparecem na interface comum.

### 4.5 Erros e recuperação

- Falha de rede: manter o texto digitado e informar que o envio não foi confirmado.
- Timeout: consultar o estado do mesmo identificador de execução antes de oferecer reenvio.
- Erro do motor: preservar a mensagem e informar indisponibilidade do motor.
- Resposta parcial: preservar o conteúdo recebido e identificar que a execução falhou antes da conclusão.
- Reenvio: usar identificador idempotente para evitar mensagens duplicadas.

## 5. Projetos

Lista simples com nome, descrição curta e data de atividade. Ações:
- Abrir projeto.
- Criar projeto.
- Renomear, com confirmação.
- Arquivar, com confirmação e política de retenção definida.

Dentro do projeto:
- Conversas do projeto.
- Arquivos associados.
- Instruções do projeto.
- Memória do projeto.

O contexto do projeto deve ser claramente indicado na conversa. Trocar de projeto não move nem copia automaticamente conversas, arquivos ou memória.

## 6. Arquivos

A primeira versão deve distinguir:
- Arquivos anexados à conversa.
- Arquivos pertencentes ao projeto.
- Arquivos importados para a área experimental da plataforma.

Cada item mostra nome, tipo, tamanho e origem. O serviço valida conteúdo e autorização. A interface não executa arquivos nem expõe caminhos físicos.

Integração com Google Drive permanece indisponível nesta etapa. A seção Integrações deve mostrar o estado “não configurado” sem sugerir que há acesso ativo.

## 7. Ferramentas

Apresentar ferramentas habilitadas e seu estado. A seleção automática é o padrão. A seleção manual mostra somente ferramentas disponíveis e autorizadas.

Cada ferramenta deve ter:
- Nome amigável.
- Descrição objetiva.
- Estado de disponibilidade.
- Indicação de que exige confirmação, quando aplicável.

Não permitir que a interface conceda permissões que o serviço não reconhece. A seleção manual não contorna políticas de segurança.

## 8. Memória

Separar visualmente:
- Memória geral do usuário.
- Memória do projeto atual.

Cada registro deve indicar escopo, origem e estado. Consulta é leitura. Edição exige confirmação. Remoção segue nível crítico e confirmação específica.

A interface não deve misturar memória conversacional com memória neural do Pestinha. A migração dos arquivos existentes fica fora do escopo desta especificação.

## 9. Aprovações

Uma solicitação de aprovação deve informar:
- Ação solicitada.
- Arquivo, recurso ou destino afetado.
- Motivo.
- Efeitos esperados.
- Se há alteração irreversível.
- Prazo de validade da solicitação.

Controles:
- Aprovar esta ação.
- Rejeitar.
- Ver detalhes.

A aprovação deve ser específica para a ação, alvo e escopo apresentados. Não criar aprovação permanente implícita. Se o alvo ou os efeitos mudarem, solicitar nova aprovação.

## 10. Configurações

Organização proposta:
- Conta e sessão.
- Dispositivos autorizados.
- Aparência.
- Preferências de modelo.
- Privacidade e memória.
- Conexão com o serviço.
- Diagnóstico básico.
- Ajuda e versão.

Configurações avançadas e logs técnicos ficam recolhidos. Revogar dispositivos, apagar dados ou alterar configurações críticas exige confirmação compatível com o risco.

## 11. Responsividade

### Desktop
- Menu lateral compacto.
- Conteúdo central com largura máxima de leitura.
- Campo de mensagem fixo na base da conversa.
- Atalhos de teclado documentados.

### Tablet
- Menu recolhível.
- Uma coluna principal.
- Controles secundários em menus ou painéis temporários.

### Celular
- Navegação em painel temporário.
- Campo de mensagem adaptado ao teclado virtual.
- Botões com área de toque adequada.
- Sem tabelas largas ou painéis paralelos.
- Anexos e referências em blocos recolhíveis.

A interface deve ser testada em larguras estreitas e amplas, orientação retrato e paisagem. Os pontos de quebra exatos serão definidos na implementação e registrados nos testes visuais.

## 12. Acessibilidade e consistência

- Contraste suficiente entre texto, fundo e estados.
- Verde neon reservado a ação primária, foco ou estado positivo.
- Não comunicar estado somente por cor.
- Rótulos acessíveis em ícones e controles.
- Foco de teclado visível.
- Ordem de tabulação coerente.
- Mensagens de erro associadas ao controle correspondente.
- Respeitar preferência do sistema por redução de movimento.
- Não usar animações contínuas para indicar atividade.

## 13. Critérios de aceite operacional

| ID | Verificação | Resultado esperado |
|---|---|---|
| UX-01 | Abrir Início | Campo de mensagem é o foco visual |
| UX-02 | Abrir menu | Navegação não encobre permanentemente a conversa |
| UX-03 | Trocar projeto | Projeto ativo fica visível e contexto não é misturado |
| UX-04 | Trocar modelo | Automático e escolha manual funcionam sem painel técnico |
| UX-05 | Enviar mensagem | Texto permanece até confirmação de recebimento |
| UX-06 | Falha de rede | Texto não é perdido nem duplicado no reenvio |
| UX-07 | Ferramenta ativa | Estado curto aparece sem dados sensíveis |
| UX-08 | Aprovação | Ação, alvo e efeitos ficam claros antes da decisão |
| UX-09 | Celular | Campo e mensagens não ficam cobertos pelo teclado |
| UX-10 | Acessibilidade | Navegação básica funciona por teclado e leitor de tela |
| UX-11 | Offline | Interface distingue indisponibilidade central de motor local |
| UX-12 | Memória | Escopo geral e de projeto ficam separados |

## 14. Fora do escopo desta etapa

- Implementação de frontend ou backend.
- Alteração do núcleo SERMAX ou do Terminal.
- Migração de memória e histórico.
- Sincronização entre dispositivos.
- Autenticação real.
- Upload e processamento real de anexos.
- Execução de código arbitrário.
- Integração Google Drive.
- Publicação em nuvem ou abertura de portas.
- Instalação ou atualização sobre a pasta atual do SERMAX.

## 15. Estado e próximo passo

Esta especificação detalha o comportamento esperado da interface, mas não comprova implementação nem execução de testes. A próxima decisão técnica, antes de iniciar código, é fechar o ambiente da primeira versão: host local, conta única, armazenamento experimental separado e estratégia de acesso somente local. A criação do diretório `SERMAX-Platform/` e qualquer implementação continuam condicionadas à autorização expressa já prevista na ordem do projeto.

Nenhum arquivo funcional, memória, Terminal, backup, instalação local, workflow ou branch `main` foi alterado por esta especificação.
