# Plataforma SERMAX, especificação de interface gráfica

**Estado:** especificação documental inicial. Não implementada.
**Ordem de referência:** ORDEM-SERMAX-PLATAFORMA-002.
**Branch:** sermax-windows-integration-20261029.
**Princípio de interface:** baixa densidade visual. A conversa com MAX é o foco.

## 1. Objetivo

Evoluir o SERMAX para uma plataforma gráfica responsiva, mantendo o núcleo existente como cérebro central. A interface gráfica será a entrada padrão. O Terminal original permanece preservado como ambiente administrativo e técnico avançado, acessível pelo comando reservado `/sermax terminal`.

Esta especificação não autoriza reescrita do núcleo, substituição do Terminal, instalação sobre `C:\\SERMAX`, alteração de dados pessoais ou implementação do SERMAX Drive Connect.

## 2. Diretriz visual obrigatória

As duas imagens fornecidas por Fabiano em 14/11/2026 são referências visuais da plataforma. A segunda imagem orienta a tela inicial. A primeira orienta a conversa, mas seus painéis laterais não devem ser reproduzidos integralmente.

Regras:
- Fundo escuro grafite ou azul profundo, com verde neon reservado a ações e estados importantes.
- Mascote e identidade SERMAX preservados, sem ocupar área excessiva.
- Menu lateral compacto, com ícones e rótulos curtos.
- Uma área principal por vez.
- Campo de mensagem como elemento de maior prioridade.
- Poucos atalhos, com rótulos objetivos.
- Sem painel permanente de atividade, fontes, permissões ou métricas.
- Sem cartões redundantes, indicadores decorativos, gráficos ou notificações contínuas.
- Informações contextuais aparecem sob demanda, em menus, detalhes ou painéis temporários.
- A interface informa quando MAX está usando uma ferramenta, sem expor detalhes técnicos desnecessários.
- Seletores manuais de modelo e projeto ficam discretos e não competem com o campo de mensagem.

## 3. Navegação

Menu principal:
1. Início
2. Conversas
3. Projetos
4. Arquivos
5. Ferramentas
6. Memória
7. Integrações
8. Configurações

A opção Ajuda pode ficar dentro de Configurações ou no menu de perfil, para evitar ampliar a navegação principal.

## 4. Tela inicial

Conteúdo padrão:
- Mascote SERMAX e saudação curta do MAX.
- Campo central para enviar mensagem.
- Ação de anexar arquivo.
- Seletor discreto do projeto atual.
- Seletor manual de modelo, recolhido ou discreto.
- Três atalhos: Pesquisar, Analisar arquivos e Automatizar.
- Indicador simples de estado do serviço.

Não exibir por padrão:
- Histórico detalhado de atividade.
- Painel de fontes.
- Painel de permissões.
- Painel de modelo ativo com detalhes técnicos.
- Estatísticas, gráficos ou múltiplos cartões.

## 5. Conversas

A conversa ocupa a área central. Elementos:
- Mensagens do usuário e do MAX.
- Campo de entrada fixo na parte inferior.
- Anexos associados à mensagem.
- Referências e fontes junto à resposta correspondente.
- Indicador compacto de ferramenta em uso.
- Controles de modelo e projeto em área secundária.

Histórico e lista de conversas ficam na seção Conversas, não como uma segunda coluna obrigatória na tela inicial.

## 6. Seleção de modelos e ferramentas

Comportamento híbrido já definido:
- MAX seleciona automaticamente modelo e ferramentas adequados à solicitação.
- Fabiano mantém a opção de selecionar manualmente.
- A interface informa a seleção automática quando ela for relevante e mostra a ferramenta ativa durante a execução.
- Ollama e modelos locais existentes devem ser preservados.
- Integrações externas dependem de análise de disponibilidade, privacidade e custo.
- A seleção manual não deve exigir navegar por telas técnicas complexas.

## 7. Projetos, arquivos e memória

Projetos agrupam conversas, arquivos e instruções próprias. O contexto de um projeto não deve contaminar outro projeto.

Memória:
- Memória geral e memória por projeto permanecem separadas.
- Gravação automática seletiva para informações comuns e relevantes.
- Confirmação explícita para informações importantes.
- O usuário mantém controle sobre consulta, correção e remoção, com proteção contra exclusões acidentais.

Arquivos:
- Exibir arquivos do projeto atual e permitir anexos à conversa.
- Mostrar referências junto às respostas que usarem documentos.
- Acesso ao Google Drive somente após autorização e implementação própria aprovada. O Drive Connect continua fora do escopo de implementação desta etapa.

## 8. Arquitetura lógica proposta

- Núcleo atual SERMAX: cérebro central e compatibilidade com memória, roteamento e adaptadores existentes.
- Camada de serviço: API autenticada para conversas, projetos, arquivos, memória e execução de ferramentas.
- Interface web responsiva/PWA: cliente principal para Windows, Android e navegador.
- Cliente Android nativo: etapa posterior, conectado ao mesmo serviço central.
- Armazenamento: iniciar com solução local transacional e migração versionada; avaliar banco servidor quando concorrência e sincronização exigirem.
- Comunicação em tempo real: canal autenticado para estado de resposta e eventos de ferramenta.
- Acesso remoto: preferir VPN ou túnel privado; não expor painel administrativo nem portas de desenvolvimento diretamente à internet.

A tecnologia final, hospedagem e banco ainda dependem de decisão arquitetural documentada. Não presumir serviço de nuvem gratuito ou sem mensalidade.

## 9. Entidades e contratos mínimos da API

Entidades previstas:
- User, Device, Session
- Project, Conversation, Message, Attachment
- MemoryEntry
- ToolInvocation, ModelSelection
- PermissionApproval
- SyncCursor e ChangeVersion

Requisitos dos contratos:
- Identificadores estáveis.
- Datas em UTC.
- Versão de registro para sincronização e detecção de conflito.
- Paginação para conversas, mensagens e arquivos.
- Operações idempotentes quando houver repetição de envio.
- Autorização por usuário, dispositivo e projeto.
- Registro de ações sem gravar conteúdo sensível em logs.

## 10. Permissões

Nível automático:
- Consultas, pesquisas, leitura e análise de arquivos autorizados.

Nível com confirmação:
- Edição de arquivos, instalação, configuração e envio externo.

Nível crítico:
- Exclusão, alteração de histórico ou memória, backups, integridade e mudanças destrutivas. Exige autorização específica.

## 11. Sincronização e modo offline

- Um único cérebro MAX no servidor central.
- Conversas, projetos, memória e configurações sincronizados entre dispositivos autenticados.
- Identificação de versão e resolução explícita de conflitos, sem sobrescrever silenciosamente alterações.
- Offline: interface abre, permite consultar conteúdo local previamente armazenado e preparar rascunhos.
- Inferência local offline fica disponível no computador que hospeda o Ollama. Um dispositivo móvel desconectado não acessa o cérebro central.

## 12. Segurança

- Senhas armazenadas com hash apropriado para autenticação.
- Sessões revogáveis e protegidas.
- Recuperação de conta com fluxo seguro.
- 2FA opcional.
- Isolamento por usuário e projeto.
- Execução de tarefas de desenvolvimento em ambiente isolado.
- Segredos fora do repositório.
- Ações críticas exigem aprovação específica e trilha de auditoria.

## 13. Desenvolvimento e migração

A plataforma deve nascer em diretório novo e isolado, sem substituir o núcleo atual. Um adaptador chamará o núcleo SERMAX existente. O Terminal original permanece intacto.

Etapas:
1. Concluir inventário e reconciliação com a base oficial de 28/10, quando os arquivos forem disponibilizados.
2. Aprovar arquitetura de serviço, autenticação, armazenamento e hospedagem.
3. Definir contratos da API e migração versionada.
4. Implementar protótipo gráfico mínimo em diretório separado.
5. Validar conversas, anexos, projetos, memória, roteamento e permissões.
6. Empacotar e planejar atualização com backup e rollback comprovados.

## 14. Critérios de aceitação visual

- A tela inicial permite começar uma conversa sem navegar por painéis.
- O campo de mensagem é o elemento de maior destaque.
- A navegação principal permanece compacta.
- Os atalhos são limitados a três ações principais.
- Detalhes técnicos aparecem sob demanda.
- A tela de conversa não mantém colunas laterais cheias de informações.
- A identidade visual corresponde às referências enviadas por Fabiano.
- A interface funciona em larguras de desktop e celular sem sobreposição.

## 15. Estado e limites atuais

A auditoria anterior encontrou núcleo Windows e app Android básico, mas não encontrou backend de plataforma, autenticação central, banco de conversas/projetos ou sincronização multi-dispositivo. O app Android existente não foi comprovado como cliente conectado ao núcleo Windows.

O workflow de equipe no GitHub existe e define os papéis Analista, Pesquisador, Programador e Testador em sequência. O runner usa um backend Groq configurado por secret e exige testes para propostas de código. Esta especificação documental não foi submetida a uma execução do workflow de agentes; a conexão GitHub consultada nesta rodada não expõe ação de dispatch. Não declarar execução dos agentes nem testes desta especificação.

Nenhum código funcional, workflow, memória pessoal ou instalação local foi alterado por este documento.
