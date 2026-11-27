# Contrato de segurança da área privada _update

Status: especificação técnica. Não implementado. Não autoriza criação de diretórios, alteração de ACL ou escrita na instalação.
Data: 2026-11-13
Branch-alvo: sermax-windows-integration-20261029

## 1. Objetivo

Definir como o futuro atualizador poderá manter staging, backups, journal e logs em `_update`, sem transformar essa pasta em destino permitido para arquivos de release e sem enfraquecer a proteção de dados pessoais.

Este contrato complementa `ARQUITETURA-ATUALIZADOR-TRANSACIONAL.md`. Não substitui os gates de assinatura, inventário por handles, backup verificável, journal durável, rollback e homologação Windows.

## 2. Regra de separação

Há dois domínios distintos:

1. **Domínio de release:** arquivos listados no manifesto assinado. O manifesto nunca poderá escrever em `_update`, nem em qualquer descendente.
2. **Domínio interno do atualizador:** diretórios e arquivos de transação criados pelo próprio atualizador, por APIs internas específicas, após validação da raiz e das permissões.

A proteção atual de `_update` no inventário geral permanece ativa. Não remover `_update` de `PROTECTED_DIRECTORY_SEGMENTS` para facilitar a implementação. Não criar uma exceção genérica em `is_protected_path()`, `classify_inventory()` ou `build_inventory_plan()`.

A futura exceção deverá existir somente na camada privada de armazenamento do atualizador, que não aceita caminhos vindos do manifesto ou do usuário sem validação estrita.

## 3. Estrutura reservada

Estrutura lógica proposta:

- `_update/staging/<transaction_id>/`
- `_update/backups/<transaction_id>/`
- `_update/journal/<transaction_id>.json`
- `_update/logs/update.log`
- `_update/locks/active.lock`

Regras:

- Cada identificador de transação deve ser gerado internamente, ter formato limitado e ser validado antes de compor qualquer nome.
- Nenhum caminho absoluto será aceito por APIs internas. A resolução deve ocorrer componente a componente, a partir de handle confiável.
- Os nomes reservados acima não são destinos de manifesto.
- Não criar nem remover diretórios durante preflight.
- Não reutilizar diretório de transação existente sem validar integralmente sua identidade, estado e vínculo ao journal.
- Diretórios de transações concluídas não serão removidos na mesma execução que confirma a atualização.

## 4. Estabelecimento da raiz confiável

Antes de qualquer operação de escrita:

1. Abrir a raiz do volume e a raiz SERMAX por handles, usando os validadores existentes.
2. Confirmar Windows x64, volume esperado, identidade do diretório e ausência de reparse point ou DeletePending.
3. Enumerar o diretório SERMAX por handle e localizar `_update`.
4. Se `_update` existir, abrir relativamente ao handle pai e comparar FileId de 128 bits, volume, tipo, atributos e estado.
5. Se não existir, a criação futura deverá ocorrer relativamente ao handle pai, com semântica de criação exclusiva. A API de criação relativa ainda precisa ser implementada e testada.
6. Reabrir e validar o objeto criado. Não confiar no nome retornado nem em uma verificação anterior por caminho.
7. Manter os handles ancestrais abertos durante as operações dependentes deles.

Falhar fechado se a raiz for reparse point, junction, symlink, objeto especial, volume divergente, identidade divergente ou estado DeletePending.

A implementação atual de inventário por handles não cria um snapshot transacional. O atualizador deverá revalidar identidade e metadados imediatamente antes de cada operação de escrita e não poderá interpretar o inventário como bloqueio contra alterações posteriores.

## 5. ACL e controle de acesso

A ACL de `_update` deverá ser explícita, restritiva e validada por handle.

Política a implementar e testar:

- Identificar o SID do usuário que executa a instalação.
- Restringir leitura, criação, alteração e exclusão dos dados da transação ao SID autorizado e às identidades de sistema estritamente necessárias.
- Não conceder acesso amplo a `Everyone`, `Users` ou `Authenticated Users`.
- Não presumir que a ACL atual da raiz SERMAX é segura por herança.
- Proteger a DACL da área privada contra alterações por usuários não autorizados.
- Preservar proprietário e ACEs preexistentes quando houver alteração autorizada.
- Verificar DACL presente e não nula, proprietário, herança, ACEs explícitas e herdadas, permissões efetivas relevantes e capacidade de criação/remoção.
- Não considerar a simples presença de uma ACE de negação como prova de isolamento.
- Não alterar a ACL da raiz SERMAX para obter acesso à pasta privada.
- Não exigir elevação administrativa se a instalação tiver permissões suficientes.
- Se não for possível estabelecer ou comprovar a política, abortar sem gravar.

O módulo atual `sermax_windows_root.py` contém abertura de diretório para ACL e uma rotina de negação de criação para SID específico. Isso não equivale a uma política completa de isolamento de `_update`. Não reutilizar essas funções como prova de segurança sem auditoria de seus efeitos e testes em Windows.

## 6. Reparse points, hardlinks e identidade

Em cada componente de caminho:

- Abrir sem seguir reparse point.
- Rejeitar reparse points, junctions, symlinks e objetos especiais.
- Vincular o handle aberto ao FileId de 128 bits observado na enumeração.
- Confirmar mesmo volume e tipo esperado.
- Rejeitar arquivos com mais de um hardlink quando a operação exigir identidade exclusiva.
- Validar metadados antes e depois da leitura ou escrita.
- Fechar handles em todos os caminhos de erro.
- Não converter falha de validação em fallback para APIs baseadas somente em caminho.

A detecção de reparse point precisa ocorrer no próprio objeto aberto, não somente no nome enumerado.

## 7. Concorrência e lock

O lock deve ser criado exclusivamente dentro da área privada, por operação atômica equivalente a CREATE_NEW e relativa ao handle validado.

- Um segundo atualizador deve falhar sem alterar o estado da primeira transação.
- Não remover lock de outra instância.
- Registrar PID, identidade do processo, identificador da transação e versão do protocolo, sem dados pessoais.
- O conteúdo do lock não substitui a exclusividade do handle.
- Manter o handle exclusivo durante toda a transação.
- Após reinício, lock abandonado não autoriza apagar ou sobrescrever journal. Primeiro executar recuperação e validação de estado.
- Não permitir dois journals ativos para a mesma raiz.

## 8. Journal durável

O journal deve ser gravado por escrita em arquivo temporário exclusivo, flush dos dados e metadados aplicáveis, seguido de substituição controlada no mesmo diretório e volume.

Cada transição deverá registrar:

- versão do protocolo;
- ID da transação;
- estado anterior e novo estado;
- sequência monotônica;
- timestamp UTC;
- versão de origem e destino;
- caminhos relativos;
- ação planejada e resultado;
- tamanho, SHA-256 e FileId aplicáveis;
- códigos de erro do sistema.

Não registrar conteúdo de memória, prompts, tokens, credenciais, áudio ou dados pessoais.

Uma transição só será considerada persistida após a operação de flush apropriada retornar sucesso. A implementação deverá documentar as garantias reais do Windows e do sistema de arquivos, sem prometer durabilidade que não tenha sido testada.

JSON inválido, sequência regressiva, transição impossível, hash divergente, FileId divergente ou estado desconhecido deverá levar a `RECOVERY_REQUIRED`. Nunca reconstruir ou descartar journal ambíguo por inferência.

## 9. Backup e staging

### Backup

- Copiar somente arquivos classificados como managed e explicitamente listados no plano autenticado.
- Criar cada destino de backup de forma exclusiva e relativa ao handle do diretório de backup.
- Ler origem e gravar cópia por handles.
- Calcular SHA-256 da origem e da cópia, comparar tamanhos e hashes e validar identidade.
- Não copiar arquivos protegidos, desconhecidos, memórias, configurações ou diretórios inteiros.
- Preservar atributos necessários ao rollback e documentar quais metadados não são preservados.
- Não iniciar instalação enquanto todo o backup exigido não estiver validado.

### Staging de ZIP

- Ler a tabela central e validar todas as entradas antes de gravar qualquer arquivo.
- Rejeitar caminho absoluto, UNC, letra de unidade, traversal, separadores ambíguos, nomes reservados do Windows, componentes terminados em ponto/espaço e caminhos fora da raiz.
- Rejeitar entradas duplicadas, colisões case-insensitive, colisões após normalização Unicode e conflitos arquivo/diretório.
- Rejeitar symlinks, reparse metadata, hardlinks e tipos especiais.
- Exigir correspondência exata entre o conjunto de arquivos do ZIP e o manifesto assinado.
- Impor limites de quantidade, tamanho individual, tamanho total descompactado, razão de compressão e profundidade.
- Detectar ZIP bombs e arquivos truncados.
- Validar tamanho e SHA-256 de cada conteúdo descompactado.
- Não usar extração direta por nome de caminho. A escrita deverá ocorrer por handles relativos já validados.
- Não executar scripts, instaladores ou comandos contidos no pacote.

## 10. Recuperação e retenção

- Toda operação de substituição deve ter intenção persistida no journal antes de modificar o destino.
- O backup anterior permanece disponível até a confirmação do health check.
- Recuperação deve validar journal, lock, backup, FileId e hashes antes de qualquer restauração.
- Rollback deve seguir ordem inversa e verificar cada arquivo restaurado.
- Se backup estiver ausente, corrompido ou inconsistente, bloquear novas atualizações e preservar todos os dados restantes.
- Nunca limpar automaticamente uma transação em `RECOVERY_REQUIRED`.
- A política de retenção de backups só será definida depois de testes de restauração e de uma operação separada de limpeza, com confirmação explícita.

## 11. Testes obrigatórios antes de habilitar a área

### Testes unitários simulados

1. `_update` ausente, regular, reparse, junction, especial e DeletePending.
2. FileId e volume divergentes entre enumeração e abertura.
3. Hardlink inesperado.
4. ACL ausente, nula, permissiva, herdada e modificada durante a operação.
5. SID do usuário diferente do proprietário.
6. Criação concorrente de lock.
7. Lock abandonado com journal válido, inválido e incompleto.
8. Falha em cada etapa de escrita, flush e rename do journal.
9. IDs de transação inválidos, duplicados ou com traversal.
10. ZIP com entradas duplicadas, Unicode ambíguo, colisões, traversal, symlink, ZIP bomb e hash incorreto.
11. Interrupção simulada em cada transição do journal.
12. Backup incompleto, truncado, com hash divergente ou metadados inconsistentes.
13. Reexecução idempotente de recuperação.
14. Tentativa de manifesto com destino em `_update` e em qualquer descendente.

### Testes Windows reais, em ambiente descartável

1. Windows x64 e NTFS.
2. Duas contas Windows distintas, com permissões diferentes.
3. Usuário padrão sem elevação administrativa.
4. Reparse points e junctions criados no ambiente de teste.
5. Hardlinks e arquivos abertos concorrentemente.
6. Encerramento forçado do processo em cada etapa de backup, staging, journal e rollback.
7. Reinício da VM durante a transação.
8. Verificação byte a byte do backup e do rollback.
9. Verificação de que nenhum arquivo fora do sandbox foi alterado.

Mocks não substituem os testes nativos de ACL, handles, rename, flush e recuperação após reinício.

## 12. Gaps de implementação confirmados

Na revisão da branch atual:

- `sermax_windows_root.py` abre e valida raízes e diretórios e contém funções parciais de ACL.
- `sermax_windows_directory_handle.py` abre filhos relativamente ao handle pai e confere identidade.
- `sermax_windows_handle_inventory.py` enumera e calcula hashes por handles, mas não oferece snapshot transacional.
- `sermax_update_manifest.py` valida manifesto assinado, mas não instala.
- `sermax_update_signature.py` verifica Ed25519, mas a allowlist de produção permanece vazia.
- `sermax_update_inventory_contract.py` produz plano somente de leitura.
- Não foi identificada API completa para criação relativa de diretórios/arquivos na área privada, lock exclusivo, escrita durável de journal, staging seguro de ZIP, backup por handles ou rollback.

## 13. Ordem de implementação

1. Especificar e testar primitivas nativas de criação relativa e abertura exclusiva.
2. Implementar inspeção e validação de ACL sem mutação.
3. Implementar provisionamento restrito de `_update`, com rollback de ACL em caso de erro.
4. Implementar lock exclusivo e journal durável isolados em diretório temporário de teste.
5. Implementar leitor/validador ZIP sem extração.
6. Implementar staging por handles em sandbox.
7. Implementar backup por handles em sandbox e verificação de hashes.
8. Implementar máquina de estados e injeção de falhas.
9. Implementar rollback em sandbox e comprovar restauração byte a byte.
10. Somente após todos os gates, planejar integração com a raiz real da instalação.

## 14. Restrições de liberação

- Nenhuma instalação em `C:\\SERMAX`.
- Nenhuma alteração de ACL na instalação do usuário.
- Nenhum merge da PR #2.
- Nenhuma alteração em `main`.
- Nenhuma chave privada no repositório.
- Nenhuma chave pública de produção fictícia.
- Nenhum artefato experimental tratado como instalador.
- Nenhuma alegação de homologação Windows sem evidência dos testes descritos.

Status final deste documento: contrato de segurança proposto, implementação pendente.
