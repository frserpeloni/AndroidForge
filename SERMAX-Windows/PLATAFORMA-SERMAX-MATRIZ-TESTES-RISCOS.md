# SERMAX Platform, matriz de validação e riscos da primeira versão

**Estado:** plano de testes e riscos. Não executado.
**Branch:** `sermax-windows-integration-20261029`.
**Escopo:** primeira versão experimental da plataforma gráfica, em diretório separado.
**Documentos-base:** arquitetura GUI, contrato API, hospedagem/acesso remoto e plano de migração.

## 1. Regra de evidência

Cada teste deve registrar:
- Identificador e objetivo.
- Ambiente, sistema operacional e versões.
- Commit testado.
- Pré-condições.
- Passos executados.
- Resultado esperado e observado.
- Log ou evidência verificável.
- Estado: aprovado, reprovado, bloqueado ou não executado.

Não marcar teste como aprovado por inspeção documental. Teste não executado permanece explicitamente pendente.

## 2. Matriz funcional

| ID | Área | Cenário | Critério de aprovação |
|---|---|---|---|
| UI-01 | Interface | Abrir tela inicial em desktop | Campo de conversa é o foco; sem painéis permanentes excessivos |
| UI-02 | Interface | Abrir em viewport móvel | Menu compacto e conversa sem sobreposição |
| UI-03 | Interface | Abrir conversa | Mensagens e campo de envio visíveis; controles secundários discretos |
| UI-04 | Interface | Ferramenta em execução | MAX mostra estado curto e compreensível |
| API-01 | API | Inicializar serviço | Health check responde sem expor segredos |
| API-02 | Conversa | Enviar mensagem | Mensagem persiste e chega ao adaptador do núcleo |
| API-03 | Conversa | Reenviar mesmo ID de cliente | Não duplica a mensagem |
| API-04 | Conversa | Núcleo indisponível | Erro controlado, sem perda silenciosa da mensagem |
| CORE-01 | Integração | Uma sessão com Ollama | Resposta ou falha controlada registrada |
| CORE-02 | Integração | Fallback do motor | Comportamento compatível com roteamento existente |
| CORE-03 | Concorrência | Duas conversas simultâneas | Contextos não se misturam; se não suportado, segunda execução fica em fila |
| DATA-01 | Dados | Iniciar e encerrar plataforma | JSONs originais permanecem byte a byte idênticos |
| DATA-02 | Dados | Reiniciar serviço | Conversas experimentais persistem |
| DATA-03 | Dados | Exportar e restaurar banco experimental | Contagens e hashes conferidos |
| SEC-01 | Segurança | Acessar recurso com usuário não autorizado | Acesso negado |
| SEC-02 | Segurança | Enviar caminho inválido em upload | Requisição recusada; sem escrita fora da área autorizada |
| SEC-03 | Segurança | Verificar logs | Nenhuma senha, token ou conteúdo privado integral |
| SEC-04 | Segurança | Serviço em primeira versão | Bind local; nenhuma porta pública ou regra de roteador |
| REG-01 | Regressão | Executar testes atuais do SERMAX | Testes existentes continuam aprovados |
| REG-02 | Regressão | Abrir Terminal original | Visual, comandos e fluxo preservados |
| PKG-01 | Pacote | Gerar pacote experimental separado | Inicia e encerra conforme instruções |
| PKG-02 | Pacote | Remover protótipo | Não remove nem altera instalação original |

## 3. Verificações de integridade obrigatórias

Antes de iniciar qualquer implementação:
1. Registrar SHA-256 dos arquivos protegidos.
2. Registrar commit base da branch.
3. Confirmar diretório de dados experimental separado.
4. Confirmar que nenhum segredo será versionado.

Após cada ciclo:
1. Recalcular hashes dos JSONs protegidos.
2. Comparar hash e tamanho dos arquivos do Terminal.
3. Executar testes de regressão.
4. Verificar diff da branch.
5. Conferir que `main` não recebeu commits.
6. Gerar manifesto do pacote experimental.

Arquivos protegidos incluem, no mínimo, núcleo, Terminal, memórias JSON, histórico, adaptadores existentes, configurações e backups. A lista definitiva depende da reconciliação da base original de 28/10.

## 4. Registro de riscos

| ID | Risco | Impacto | Mitigação / condição de saída |
|---|---|---|---|
| R-01 | Estado global do núcleo compartilhado | Mistura de contexto entre conversas | Adaptador serializado inicialmente; testes de isolamento antes de paralelismo |
| R-02 | Hardware host insuficiente | Lentidão ou indisponibilidade | Medir CPU, RAM, disco e consumo sob carga real |
| R-03 | Perda ou corrupção de memória | Perda de dados pessoais | Não migrar origem; cópia, hash, backup e restauração testada |
| R-04 | Exposição da API | Acesso indevido | Bind local na primeira versão; VPN antes de acesso remoto |
| R-05 | Sessão sem isolamento | Acesso entre usuários | Primeira versão de conta única local; testes de autorização antes de multiusuário |
| R-06 | Sincronização sobrescreve dados | Perda de alterações | Versionamento e conflitos explícitos |
| R-07 | Atualização quebra instalação | Indisponibilidade | Pacote separado, rollback e validação antes de substituir inicialização |
| R-08 | Dependência de serviço externo | Custo ou indisponibilidade | Núcleo local preservado; custos e termos documentados |
| R-09 | Interface visual excessiva | Experiência ruim | Critérios UI-01 a UI-04 e aprovação visual |
| R-10 | Referência original de 28/10 ausente | Inventário incompleto | Reconciliar candidata e ZIP antes de migração de dados |
| R-11 | Agentes não acionados | Trabalho automatizado não validado | Executar workflow manualmente quando a operação estiver disponível e revisar patch/testes |
| R-12 | Testes CI confundidos com testes físicos | Falsa garantia | Separar CI, teste de integração e validação no PC do usuário |

## 5. Critérios de bloqueio

Bloquear a promoção para versão utilizável se:
- Qualquer hash de arquivo protegido mudar sem autorização.
- Testes atuais do núcleo falharem.
- Terminal original deixar de iniciar.
- Contextos de conversas se misturarem.
- Houver acesso indevido entre escopos.
- Backup não puder ser restaurado.
- Serviço abrir portas externas sem aprovação.
- Pacote exigir substituir arquivos atuais.
- Não houver evidência reproduzível dos testes.

## 6. Estado real nesta data

- Documentação de arquitetura, API, hospedagem e migração registrada na branch.
- Matriz de testes e riscos especificada neste documento.
- Nenhum código da plataforma gráfica implementado.
- Nenhum teste desta matriz executado.
- Workflow da equipe existe e usa `workflow_dispatch`; a conexão GitHub desta sessão não expõe operação de dispatch.
- Não foram alterados núcleo, Terminal, JSONs, backups, instalação local, workflow ou `main`.

## 7. Próximos passos

1. Obter os arquivos oficiais de 28/10 para reconciliação, caso estejam disponíveis.
2. Medir hardware do computador host.
3. Decidir escopo de conta única local e topologia inicial.
4. Obter autorização expressa para iniciar criação do diretório `SERMAX-Platform/` e testes.
5. Acionar workflow dos agentes por `workflow_dispatch` quando houver ferramenta autorizada para isso.
6. Revisar qualquer patch dos agentes antes de aceitar e executar regressão.

## 8. Limites

Este documento não implementa nem executa testes. Não altera workflows ou arquivos de produção. A primeira versão segue experimental e isolada até aprovação formal.
