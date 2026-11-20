# Avaliação de recuperação na inicialização SERMAX

**Data:** 20/11/2026  
**Branch:** `sermax-startup-recovery-assessment-20261120`  
**Base:** PR #20, commit `5e9739b950e2a24667a092ab08c51245b63b27e2`

## Objetivo

Inspecionar o journal persistente antes da inicialização normal e classificar transações incompletas. Esta etapa não executa rollback e não apaga staging, backup ou journal.

## Política implementada

| Situação do journal | Ação da avaliação | Inicialização normal |
|---|---|---|
| `COMMITTED` ou `ROLLED_BACK` | Terminal | Liberada |
| `INSTALL_STARTED` presente, sem evento terminal | Bloquear e solicitar decisão explícita | Bloqueada |
| Preparação interrompida antes de `INSTALL_STARTED` | Solicitar revisão, sem rollback | Liberada |
| Diretório de transação vazio | Sinalizar revisão, sem limpeza automática | Liberada |
| Journal inválido, cadeia quebrada ou namespace inseguro | Falhar fechado | Bloqueada |

A instalação ativa só começa depois da persistência de `INSTALL_STARTED`. Portanto, transações sem esse evento não são classificadas como rollback executável por esta camada.

## Contrato do módulo

Arquivo: `sermax_update_recovery.py`

Função: `inspect_startup_recovery_by_handle(journal_parent_handle)`

A função:
- chama a varredura validada do journal por handles;
- informa `startup_allowed` e a ação indicada;
- identifica transações que exigem decisão do operador;
- indica se o rollback existente aceita aquela fase da transação;
- informa explicitamente `automatic_rollback_performed: false`;
- não grava eventos, não abre manifestos, não altera arquivos e não executa rollback.

A varredura do journal agora informa se `INSTALL_STARTED` aparece na cadeia validada e se o rollback é suportado para a transação não terminal.

## Limites

- Este módulo ainda não está ligado ao launcher nem à abertura do Terminal. É uma camada de avaliação testável, não uma integração concluída com o fluxo de inicialização.
- O rollback continua exigindo manifesto autenticado e handles das áreas privadas, por chamada separada.
- Nenhum rollback é executado sem decisão explícita.
- Transações de preparação interrompida e diretórios vazios ficam preservados para revisão. Não há limpeza automática.
- Journal inválido bloqueia a avaliação. Não há tentativa de reparar ou reescrever a cadeia.
- A CI não comprova o comportamento no Windows 11 instalado em `C:\\SERMAX`.

## Testes adicionados

- Estado terminal libera a inicialização.
- Instalação interrompida bloqueia a inicialização e não executa rollback.
- Preparação interrompida antes de `INSTALL_STARTED` permite iniciar SERMAX e exige revisão.
- Transação vazia é sinalizada sem limpeza.
- Journal corrompido e resumo inconsistente falham fechados.
- Teste nativo Windows verifica que a avaliação não altera os hashes dos eventos do journal.

## Estado de entrega

Implementação isolada em branch e PR em rascunho, aguardando CI e revisão. Sem merge, sem release e sem escrita em `C:\\SERMAX`.


## Evidência CI, 20/11/2026

- Run `44787796107`, commit `985e42fdf1fcf9091b7298f7a4014bc02be8ca3e`.
- Runner Windows, Python 3.14.
- A compilação dos módulos passou.
- Os testes de journal e avaliação de inicialização passaram.
- O teste nativo Windows `test_assessment_reads_persistent_journal_without_mutating_it` passou e confirmou que a cadeia de hashes permanece inalterada durante a inspeção.
- Todas as etapas do workflow `SERMAX Update Staging Validation` concluíram com sucesso.
- Run: https://github.com/frserpeloni/AndroidForge/actions/runs/44787796107.

A execução comprova o comportamento no runner Windows. Não comprova integração ao launcher nem homologação na instalação local do Windows 11.
