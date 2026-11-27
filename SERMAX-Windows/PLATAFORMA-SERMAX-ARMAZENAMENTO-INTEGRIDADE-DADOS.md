# PLATAFORMA SERMAX
## Especificação de armazenamento, integridade e ciclo de vida dos dados

**Estado:** planejamento técnico. Não implementado.  
**Branch:** `sermax-windows-integration-20261029`  
**Revisão:** 14/11/2026  
**Dependências:** contrato preliminar da API, operação local da primeira versão, recuperação de falhas, sincronização e conflitos, permissões e auditoria.

## 1. Objetivo

Definir os requisitos para armazenamento experimental da Plataforma SERMAX, integridade transacional, versionamento de esquema, retenção e recuperação de dados.

O armazenamento da plataforma será separado dos arquivos atuais do SERMAX. Esta especificação não cria banco, não migra dados e não altera arquivos existentes.

## 2. Separação obrigatória

A plataforma deverá manter seus dados em armazenamento próprio, separado de:
- Núcleo SERMAX atual.
- `memoria_sermax.json`.
- Histórico do Terminal.
- Memória neural do Pestinha.
- Configurações e credenciais dos motores existentes.
- Backups históricos e instaladores oficiais.

Nenhum componente da plataforma terá permissão de escrita nesses arquivos durante a primeira versão.

O diretório proposto `SERMAX-Platform/` ainda não está autorizado para criação. A estrutura descrita neste documento é conceitual.

## 3. Decisão de banco por fase

### Protótipo local

SQLite permanece candidato para o protótipo local de usuário único, não uma decisão final. Antes da adoção, será necessário testar:
- Acesso simultâneo entre API, supervisor e rotinas de backup.
- Transações de recebimento e conclusão de mensagens.
- Bloqueio e timeout de escrita.
- Recuperação após encerramento forçado.
- Integridade após reinício do Windows.
- Cópia consistente do banco com WAL, se habilitado.
- Restauração em diretório isolado.

### Expansão multi-dispositivo

Antes de habilitar múltiplos clientes remotos, reavaliar a topologia. PostgreSQL ou solução equivalente deverá ser comparada quando houver concorrência de processos, acesso remoto, múltiplas sessões ou necessidade de operação contínua.

Não migrar de SQLite para outro banco sem plano de exportação, reconciliação, backup e rollback testado.

## 4. Entidades lógicas

O modelo inicial deverá considerar as entidades já definidas no contrato preliminar:

| Entidade | Conteúdo lógico | Proteção |
|---|---|---|
| User | Identidade e estado da conta | Dados de autenticação restritos |
| Device | Cliente autorizado e revogação | Acesso controlado |
| Session | Validade e revogação da sessão | Segredos nunca expostos |
| Project | Nome, instruções, estado e versão | Isolamento por proprietário |
| Conversation | Projeto, título, estado e versão | Isolamento por proprietário |
| Message | Autor, conteúdo, sequência e IDs do cliente | Imutabilidade após confirmação |
| Attachment | Hash, tamanho, tipo e escopo | Conteúdo fora da pasta pública |
| MemoryEntry | Conteúdo, origem, escopo e aprovação | Escrita sujeita à política |
| Run | Estado e timestamps de execução | Idempotência e recuperação |
| ToolInvocation | Ferramenta e resultado resumido | Parâmetros permitidos |
| PermissionApproval | Ação, alvo, decisão e validade | Uso único e auditável |
| SyncChange | Entidade, versão, operação e cursor | Sequência central |

A estrutura física, nomes de tabelas e tipos SQL serão definidos após escolha do banco. Esta especificação não fixa um esquema executável.

## 5. Regras de integridade

- IDs internos devem ser únicos e não sequenciais quando expostos por API.
- Chaves estrangeiras devem impedir referências a entidades inexistentes.
- Recursos de projeto devem validar o proprietário e o projeto associado.
- Mensagens confirmadas devem manter sequência estável por conversa.
- IDs de cliente e chaves de idempotência devem ter restrições de unicidade no escopo correto.
- Alterações de entidades versionadas devem validar a versão esperada.
- Aprovações consumidas não podem ser reutilizadas.
- Arquivos devem ter hash e tamanho conferidos.
- Estados de execução devem respeitar transições válidas.
- Cursor de sincronização só avança após aplicação confirmada.
- Exclusões sincronizáveis usam tombstones e trilha de auditoria.
- Integridade referencial não autoriza exclusão em cascata de dados protegidos.

## 6. Transações críticas

### Recebimento de mensagem

Mensagem, solicitação e chave idempotente devem ser gravadas na mesma transação. A API confirma recebimento somente após commit.

### Conclusão de execução

Resposta final, estado `completed` e vínculo com a solicitação devem ser persistidos na mesma transação. A interface só recebe confirmação final após commit.

### Aprovação

Decisão, consumo da aprovação e registro de auditoria devem ser persistidos de forma consistente antes de iniciar a ação autorizada.

### Sincronização

Aplicação de uma página de alterações e atualização do cursor local devem ser transacionais no cliente. O servidor não deve confirmar cursor antes da validação correspondente.

### Migração de esquema

Cada migração deve possuir número, descrição, pré-condições e registro de aplicação. Quando uma migração falhar, manter o esquema anterior ou interromper a inicialização sem aceitar gravações.

## 7. Versionamento e compatibilidade

- Esquema de banco possui versão independente da versão da aplicação.
- Migrações são ordenadas e registradas.
- Mudanças destrutivas de esquema ficam bloqueadas até existir exportação e rollback comprovados.
- A aplicação deve recusar versão de banco incompatível em vez de tentar adaptar silenciosamente.
- Atualizações devem validar pré-condições antes de alterar esquema.
- Backup pré-migração é obrigatório quando houver risco de perda ou transformação de dados.
- Não remover colunas ou registros antigos na mesma entrega em que uma nova estrutura é introduzida, salvo plano de compatibilidade aprovado.

## 8. Arquivos e anexos

- Conteúdo binário fica fora da pasta pública da interface.
- Metadados registram ID, hash, tamanho, MIME detectado, nome original sanitizado, escopo e estado de validação.
- Nome do arquivo não é identificador.
- Caminho físico não é exposto pela API.
- Arquivos não são executados automaticamente.
- Upload incompleto não aparece como anexo confirmado.
- Transferência interrompida mantém estado pendente ou falho, sem declarar sucesso.
- Hash é conferido após gravação e após restauração.
- Limites de tamanho, extensões permitidas, inspeção de conteúdo e retenção precisam ser definidos antes de habilitar upload.

Upload permanece fora da primeira entrega mínima até validação específica.

## 9. Retenção e exclusão

As políticas de retenção ainda não estão definidas. Antes da implementação, definir por categoria:
- Conversas e mensagens.
- Projetos.
- Arquivos e anexos.
- Memórias.
- Logs operacionais.
- Auditoria.
- Execuções e resultados temporários.
- Tombstones de sincronização.
- Backups.

Regras obrigatórias:
- Não apagar conteúdo por limpeza automática sem política aprovada.
- Não confundir arquivamento, exclusão lógica e exclusão física.
- Exclusão de conversas, projetos, arquivos ou memórias segue Classe C.
- Backups não são apagados automaticamente junto com a entidade original.
- Retenção legal ou exigência de privacidade requer procedimento específico.
- A interface deve informar o efeito da exclusão e se existem cópias de backup.

## 10. Backup e restauração

Antes de qualquer liberação:
1. Definir diretório e política de backup.
2. Produzir backup consistente com o banco em uso.
3. Gerar manifesto de arquivos, tamanhos e SHA-256.
4. Proteger backup contra leitura não autorizada.
5. Restaurar em diretório isolado.
6. Conferir integridade do banco e hashes dos anexos.
7. Verificar contagem de entidades e vínculos.
8. Executar testes de leitura e exportação.
9. Registrar evidências e limitações.
10. Manter a origem intacta até aprovação.

Backup criado não é backup validado. Só declarar restauração comprovada após executar o procedimento completo.

A frequência, retenção e eventual criptografia devem ser definidas com base no host aprovado e na capacidade real de armazenamento.

## 11. Falhas de armazenamento

| Condição | Comportamento exigido |
|---|---|
| Disco sem espaço | Bloquear novas gravações inseguras e preservar estado |
| Banco bloqueado | Aplicar timeout e retornar erro controlado |
| Banco corrompido | Suspender escrita e preservar cópia para diagnóstico |
| Migração falha | Interromper inicialização ou reverter transação |
| Hash divergente | Marcar arquivo inválido e bloquear uso |
| Backup incompleto | Não marcar como válido |
| Restauração divergente | Não substituir a origem |
| Versão incompatível | Bloquear inicialização com diagnóstico |
| Falha de auditoria obrigatória | Bloquear ação B ou C |

A aplicação não deve reparar automaticamente arquivos originais do SERMAX.

## 12. Observabilidade sem exposição de conteúdo

Registrar:
- Versão do esquema.
- Duração e resultado de transações relevantes.
- Erros de integridade.
- Estado de backup e restauração.
- Quantidade de registros processados.
- IDs de correlação.
- Espaço livre e limites operacionais.

Não registrar conteúdo integral de conversas, documentos, memórias, senhas, tokens ou chaves privadas por padrão.

## 13. Testes de aceitação planejados

1. Banco experimental inicia em diretório separado.
2. Arquivos originais do SERMAX permanecem byte a byte inalterados.
3. Chaves estrangeiras impedem referências inválidas.
4. IDs únicos impedem duplicidade.
5. Recebimento de mensagem é transacional.
6. Reenvio idempotente não duplica mensagem.
7. Conclusão de execução persiste resposta e estado juntos.
8. Aprovação consumida não é reutilizada.
9. Versão antiga gera conflito.
10. Migração aplicada registra versão.
11. Migração com falha não deixa banco parcialmente utilizável.
12. Banco incompatível bloqueia inicialização.
13. Anexo tem hash conferido.
14. Upload incompleto não é exibido como concluído.
15. Backup consistente pode ser restaurado em diretório isolado.
16. Hashes e contagens são conferidos após restauração.
17. Falta de espaço bloqueia gravação insegura.
18. Corrupção suspende escrita e preserva evidência.
19. Tombstone não apaga backup automaticamente.
20. Logs não contêm conteúdo sensível desnecessário.
21. Exportação preserva vínculos entre projetos, conversas e mensagens.
22. Restauração não altera os dados originais do SERMAX.

Nenhum teste foi executado. A lista define critérios futuros.

## 14. Decisões pendentes

- Banco definitivo para cada fase.
- Diretório físico e permissões do armazenamento.
- Política de backup e criptografia.
- Retenção por categoria de dado.
- Limites de anexos e quota.
- Política de exportação e portabilidade.
- Estratégia de migração de esquema.
- Estratégia de monitoramento de espaço em disco.
- Política de restauração após falha de hardware.
- Requisitos de privacidade para logs e auditoria.

## 15. Critério de liberação

O armazenamento só será liberado quando a escolha tecnológica estiver justificada, os testes de integridade e recuperação forem executados, o backup tiver restauração comprovada e os dados experimentais estiverem isolados dos arquivos originais.

Este documento não autoriza criação de diretórios, banco, migrações, upload, sincronização, implementação, instalação ou alteração do núcleo, Terminal, memórias e backups existentes.
