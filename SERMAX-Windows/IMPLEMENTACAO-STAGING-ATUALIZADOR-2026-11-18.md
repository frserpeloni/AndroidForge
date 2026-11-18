# Implementação inicial de staging do atualizador SERMAX

Data: 18/11/2026  
Branch: `sermax-installer-staging-20261118`  
Base: `sermax-windows-integration-20261029`

## Escopo implementado

Foi adicionado `sermax_update_staging.py`, com a função `stage_verified_release`.

O fluxo:
1. Exige diretório pai de staging já existente e rejeita link simbólico, reparse point ou objeto que não seja diretório.
2. Revalida o ZIP integralmente contra o manifesto previamente autenticado.
3. Reserva diretório exclusivo com nome aleatório.
4. Cria arquivos com modo exclusivo, sem sobrescrever destinos existentes.
5. Recalcula tamanho e SHA-256 durante a escrita e sincroniza cada arquivo.
6. Preserva o staging parcial em caso de falha, para inspeção.
7. Não escreve em `C:\SERMAX`, não executa scripts, não faz backup, não instala e não confirma release.

Foi adicionada a suíte `tests/test_sermax_update_staging.py` para extração exata, pacote inválido, pai reparse/link, pai inválido e ausência de alteração na instalação simulada.

## Limites de segurança

- O diretório pai precisa ser provisionado pelo instalador com ACL restrita. O módulo não cria nem endurece ACLs.
- A criação exclusiva e a rejeição de reparse points reduzem riscos, mas não constituem proteção completa contra um processo concorrente com a mesma identidade e permissão de escrita no diretório pai.
- A operação não é uma transação de instalação. Não substitui arquivos ativos.
- O manifesto precisa ter sido autenticado antes da chamada. A allowlist de chaves públicas de produção continua pendente.
- Testes ainda dependem da execução do CI Windows. Nenhum resultado de CI é antecipado neste documento.

## Próximas etapas

1. Executar a suíte em Windows CI e corrigir falhas observadas.
2. Implementar provisionamento/verificação de ACL e raiz de staging.
3. Implementar inventário por handles e backup verificável.
4. Implementar journal durável, troca controlada e rollback.
5. Injetar falhas em cada transição e testar recuperação após reinicialização.
6. Homologar em VM Windows limpa antes de qualquer release instalável.

## Arquivos desta etapa

- `SERMAX-Windows/sermax_update_staging.py`
- `SERMAX-Windows/tests/test_sermax_update_staging.py`
- `SERMAX-Windows/IMPLEMENTACAO-STAGING-ATUALIZADOR-2026-11-18.md`
