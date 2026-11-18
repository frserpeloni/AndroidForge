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
