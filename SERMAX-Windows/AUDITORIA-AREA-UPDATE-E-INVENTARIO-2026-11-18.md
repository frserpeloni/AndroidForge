# Auditoria técnica da próxima etapa do atualizador SERMAX

Data: 18/11/2026
Branch: `sermax-installer-staging-20261118`
Base: `sermax-windows-integration-20261029`

## Evidências revisadas

Foram lidos nesta branch:
- `sermax_update_staging.py`
- `sermax_update_inventory.py`
- `sermax_windows_handle_inventory.py`
- `sermax_windows_root.py`
- `sermax_windows_directory_handle.py`
- `sermax_windows_handle_io.py`
- testes de staging, raiz Windows e inventário por handles.

O CI Windows do commit anterior concluiu com sucesso no run `44344129592`: integração SERMAX, build do executável, smoke test do Terminal original e publicação do artefato técnico. O run de staging `44344230649` confirmou compilação e cinco testes específicos de staging. Essas execuções não homologam o atualizador transacional nem uma instalação física.

## Achados que bloqueiam o uso de _update

1. `_update` consta em `PROTECTED_DIRECTORY_SEGMENTS`. O inventário por handles registra esse diretório como `protected` e não o percorre. Isso protege seu conteúdo, mas não valida a área privada.
2. `open_managed_directory` e `open_managed_directory_for_private_area` aceitam exclusivamente o componente `SERMAX`. Não existe ainda abertura dedicada e validada de `_update` relativamente ao handle SERMAX.
3. `deny_child_creation_for_sid` acrescenta uma ACE de negação para um SID informado. Não inspeciona nem prova, por si só, que a DACL completa da área privada exclui escrita por todos os demais principals não confiáveis.
4. `query_handle_metadata` já expõe `number_of_links`, mas o inventário por handles não registra esse valor nos resultados. O contrato do inventário ainda não oferece uma decisão auditável sobre hardlinks.
5. O inventário por handles valida FileId, atributos, tamanho e estabilidade da enumeração. Não é snapshot atômico. A classificação atual de arquivos comuns é sempre `unknown`.
6. O staging atual recebe um caminho de diretório pai. Ele rejeita links/reparse points por inspeção de caminho, mas não está ligado a um handle privado validado nem a uma ACL comprovada.
7. A allowlist oficial de chaves públicas de release continua vazia. Não existe autenticação de release de produção disponível.

## Contrato exigido antes de permitir escrita em _update

A próxima implementação deve falhar fechada e cumprir todos estes pontos:

- Abrir a raiz do volume e SERMAX por handles, preservando os handles pais durante toda a operação.
- Enumerar o filho `_update` sob o handle SERMAX, rejeitar ausência, duplicidade, reparse point, objeto não diretório, delete-pending e divergência de volume.
- Vincular o handle de _update ao FileId enumerado e revalidar a identidade.
- Consultar metadados de segurança pelo handle. Não inferir segurança a partir do nome, caminho ou da existência de uma ACE isolada.
- Validar proprietário, DACL presente e não nula, ACEs explícitas e herdadas, grupos/principals efetivos e direitos de criação, escrita, exclusão, alteração de ACL e tomada de propriedade.
- Definir explicitamente quais identidades podem gravar. A identidade do processo instalador deve ser a única identidade operacional autorizada durante a fase de staging; a política para administradores e SYSTEM precisa estar documentada e testada.
- Verificar hardlinks e identidade do volume. Rejeitar estados que não tenham política explícita.
- Manter handles abertos durante validação e uso. Revalidar ACL e identidade imediatamente antes de qualquer escrita.
- Testar concorrência, substituição de diretório, junctions, symlinks, hardlinks, ACL herdada e tentativas de escrita por outra conta Windows.
- Nunca permitir que entradas do manifesto de release escrevam em `_update`.

## Próxima sequência autorizada

1. Definir e testar o leitor de segurança por handle, sem alterar ACL.
2. Implementar abertura e validação de _update por handle, somente leitura.
3. Estender o inventário para expor metadados necessários, incluindo número de links, sem ler arquivos protegidos.
4. Definir allowlist gerenciada e classificação determinística, mantendo `unknown` como bloqueio.
5. Só depois projetar provisionamento ACL e staging vinculado a handle.
6. Implementar backup em sandbox, journal durável, recuperação e rollback em sandbox.
7. Homologar em VM Windows 11 com contas distintas antes de considerar release.

## Restrições preservadas

Nenhuma escrita foi feita em `C:\SERMAX`. Nenhum arquivo foi substituído ou removido. Não houve alteração em `main`, merge de PR, criação de chave de produção, backup da instalação, instalação ou rollback. O staging parcial de qualquer falha deve ser preservado até revisão.


## Execução da etapa de inspeção por handle

Implementado na branch:
- `sermax_windows_security.py`: leitura somente de owner, group, DACL, ACEs, controle de herança, FileId, volume e número de links.
- `sermax_windows_update_area.py`: enumeração e abertura de `_update` relativa ao handle SERMAX, com validação de nome literal, tipo, reparse point, FileId, volume e leitura do descritor de segurança.
- Os handles permanecem abertos até encerramento explícito pela classe de inspeção.
- Nenhuma ACL é alterada. Nenhuma gravação é autorizada por esses módulos.

## Evidência de CI desta etapa

- Run push `44348206885`, commit `5ed4c044387b25c82f4928cf4bed3be3391aabfe`.
- Windows Server 2025, Python 3.14.10.
- Compilação dos módulos: sucesso.
- Staging: 5 testes aprovados.
- Leitor de segurança: 5 testes aprovados.
- Inspeção de `_update`: 7 testes aprovados.
- Total: 17 testes aprovados.
- Run: https://github.com/frserpeloni/AndroidForge/actions/runs/44348206885

Os testes do leitor de segurança e do inspetor de `_update` usam mocks para as APIs nativas. Portanto, esta execução valida contratos e tratamento de falhas, não comprova leitura de ACL real sob contas Windows distintas. A homologação nativa permanece pendente.

## Estado após esta etapa

A inspeção da área privada foi implementada em modo somente leitura. Ainda faltam:
1. Política explícita de autorização baseada no descritor completo, incluindo ACEs herdadas, grupos, proprietário e direitos efetivos.
2. Testes nativos com contas Windows distintas, incluindo usuário padrão, Administradores e SYSTEM.
3. Política formal de hardlinks e validação de identidade durante staging.
4. Provisionamento e validação de ACL, ainda sem implementação nesta etapa.
5. Backup verificável, journal durável, instalação transacional e rollback.
6. Chave pública oficial de release e homologação em VM Windows 11.

A PR permanece em rascunho, sem merge. A instalação ativa permanece intocada.


## Integração com a política ACL existente e validação nativa

A revisão do repositório identificou os componentes ACL/Authz que já faziam parte do SERMAX. O fluxo de inspeção foi ajustado para reutilizá-los:
- `sermax_windows_acl_inspection.py`: leitura do descritor pelo handle.
- `sermax_windows_private_area_acl_policy.py`: validação da DACL estrita, proprietário, trustees, identidade e diretório vazio.
- `sermax_windows_effective_access.py`: leitura do descritor binário e avaliação de direitos via Authz para o token real fornecido.
- `sermax_windows_update_area.py`: orquestra inspeção, validação de política e avaliação de direitos, mantendo o mesmo handle aberto.

O módulo `sermax_windows_security.py` foi marcado como protótipo independente preservado para comparação. Não é usado como autoridade no fluxo integrado.

### CI Windows atualizado

- Run push `44349316172`, commit `1d1f3ea129a778450426d006796a1fdd798951f9`.
- Windows Server 2025, Python 3.14.10, pywin32 instalado no job.
- Compilação dos módulos: sucesso.
- Staging: 5 testes.
- Leitor de segurança protótipo: 5 testes.
- Inspeção e política de `_update`: 10 testes.
- Inspeção ACL existente: 5 testes, incluindo leitura nativa de ACL real em diretório temporário.
- Política ACL: 15 testes.
- Integração nativa da política privada: 1 teste, incluindo criação de DACL temporária, leitura pelo mesmo handle e Authz para o token real do processo.
- Total: 41 testes aprovados.
- [Execução CI](https://github.com/frserpeloni/AndroidForge/actions/runs/44349316172).

A execução nativa comprova o fluxo no token do processo do runner e em diretórios temporários descartáveis. Não comprova o comportamento sob sessões separadas de usuário padrão, Administradores e SYSTEM, nem homologa a máquina local do mantenedor.

### Estado atualizado

A inspeção de `_update` e a validação da política existente estão integradas em modo somente leitura. A função de validação não cria nem altera ACL e não executa escrita.

Continuam pendentes:
1. Testes com identidades Windows distintas e política de acesso por conta.
2. Criação atômica de nova pasta privada com SECURITY_DESCRIPTOR explícito. A primitiva atual com descritor nulo segue proibida para produção.
3. Política de revalidação e bloqueio durante staging.
4. Backup verificável, journal durável, instalação transacional e rollback.
5. Chave pública oficial de release e homologação em VM Windows 11.

Nenhuma alteração em `C:\\SERMAX`, `main` ou backups foi realizada.
