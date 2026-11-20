# Gate de recuperação na inicialização do SERMAX

**Data:** 20/11/2026  
**Branch:** sermax-launcher-recovery-gate-20261120  
**Base:** PR #21, commit 0bdbc0915848c938aec64815b2912b4be0cfd259

## Alteração no fluxo de inicialização

O sermax_launcher.py agora consulta o estado do atualizador antes de abrir o Terminal original. O gate usa handles para abrir a unidade, a pasta SERMAX e a estrutura privada _update.

A integração não altera SERMAX_terminal/sermax_terminal.py, o rosto ASCII, as cores, os comandos ou o layout do Terminal.

## Comportamento

- Instalações de desenvolvimento fora de uma pasta SERMAX na raiz de unidade: fluxo legado preservado.
- Instalações antigas sem _update: fluxo legado preservado.
- Estrutura _update presente e validada, sem transações pendentes: inicialização liberada.
- Preparação interrompida antes de INSTALL_STARTED: aviso ao operador; inicialização liberada; staging, backup e journal preservados.
- Instalação interrompida depois de INSTALL_STARTED: inicialização normal bloqueada; transação e último evento apresentados.
- ACL, estrutura, namespace ou journal inválido: inicialização bloqueada por segurança.

## Limites de segurança

- A inspeção é somente leitura.
- Nenhum rollback automático é executado.
- Nenhum staging, backup ou journal é removido.
- O rollback continua sendo uma operação separada, com manifesto autenticado e decisão explícita.
- Se a inspeção não conseguir validar a área existente, o launcher não abre o Terminal.
- O gate só se aplica ao caminho de instalação local X:\SERMAX. Execuções em outras pastas não são tratadas como instalação gerenciada.

## Empacotamento

O SERMAX.spec declara os módulos do gate e suas dependências Windows como hidden imports, incluindo win32api e win32security, para que a inspeção também exista no executável congelado.

## Testes

- Teste unitário do gate sem área _update.
- Rejeição de _update reparse ou não diretório.
- Delegação ao avaliador com fechamento do layout.
- Falha fechada quando a validação do layout falha.
- Teste do launcher que confirma que o Terminal não abre com instalação interrompida.
- Testes de empacotamento verificam os módulos e hidden imports.

## Estado

Implementação em branch isolada e PR em rascunho. CI e build congelado ainda precisam passar. A homologação no Windows 11 do mantenedor permanece pendente. Sem merge, sem release e sem alteração em C:\SERMAX.
