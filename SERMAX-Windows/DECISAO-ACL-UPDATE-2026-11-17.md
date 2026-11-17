# Decisão de arquitetura: ACL da área privada _update

Data: 2026-11-17
Estado: decisão técnica para implementação futura, sem autorização para alterar a instalação.

## Problema

O contrato de 2026-11-13 exige preservar proprietário e ACEs preexistentes quando houver alteração autorizada. A política estrita implementada em `sermax_windows_private_area_acl_policy.py` exige DACL protegida com exatamente três ACEs ACCESS_ALLOWED, uma para o proprietário esperado, SYSTEM e BUILTIN Administrators. As duas regras não definem o comportamento para uma pasta `_update` que já exista com ACL divergente.

## Decisão

1. Uma pasta `_update` preexistente é objeto de inspeção e validação, nunca de reparo automático.
2. Se proprietário, DACL, ACEs, volume, FileId, tipo, estado ou conteúdo divergirem da política aprovada, a operação aborta sem alterar ACL, conteúdo ou estrutura.
3. A regra de preservação de ACEs preexistentes não autoriza transformar uma ACL divergente em ACL aprovada. Ela permanece aplicável a qualquer fluxo futuro de reparo explicitamente autorizado, separado e com plano próprio de backup e rollback.
4. Uma pasta `_update` nova não possui ACEs preexistentes a preservar. Seu descritor de segurança deve ser estabelecido de forma atômica durante a criação, com a política explícita aprovada, antes de qualquer gravação ou abertura por outro fluxo.
5. A primitiva atual `create_private_directory_component()` passa descritor de segurança nulo para `NtCreateFile`. Portanto, ela ainda não comprova provisionamento ACL atômico e não deve ser tratada como pronta para criar a área privada de produção.
6. A validação da política deve ocorrer por handle retido, incluindo identidade de volume e FileId, DACL, proprietário, enumeração vazia e avaliação dos direitos efetivos exigidos. Qualquer falha fecha a operação.
7. Nenhuma destas regras autoriza alteração na instalação `C:\\SERMAX`, merge da PR #2 ou escrita em `main`.

## Consequências e gates

- Implementar primeiro a abertura/inspeção fail-closed de `_update` preexistente.
- Implementar separadamente criação com descritor de segurança explícito e atômico.
- Testar ambos os caminhos em diretórios temporários Windows x64.
- Testar usuário padrão e identidades de sistema relevantes.
- Não criar staging, backup, journal ou arquivos de transação até a ACL estar validada.
- Não declarar o atualizador pronto enquanto os testes nativos e de recuperação previstos no contrato estiverem pendentes.

## Escopo desta decisão

Este registro esclarece a política. Não altera código funcional, ACLs, arquivos da instalação, memória pessoal ou configurações locais.
