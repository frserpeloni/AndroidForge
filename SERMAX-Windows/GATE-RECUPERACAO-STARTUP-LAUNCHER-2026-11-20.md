# Gate de recuperação na inicialização do SERMAX

**Data:** 20/11/2026  
**Branch:** sermax-launcher-recovery-gate-20261120  
**Base:** PR #21, commit 0bdbc0915848c938aec64815b2912b4be0cfd259

## Alteração no fluxo de inicialização

O sermax_launcher.py consulta o estado do atualizador antes de abrir o Terminal original. O gate usa handles para abrir a unidade, a pasta SERMAX e a estrutura privada _update.

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
- O gate só se aplica ao caminho de instalação local X:\\SERMAX. Execuções em outras pastas não são tratadas como instalação gerenciada.

## Empacotamento

O SERMAX.spec declara os módulos do gate e suas dependências Windows como hidden imports, incluindo win32api e win32security, para que a inspeção também exista no executável congelado.

## Testes

- Teste unitário do gate sem área _update.
- Rejeição de _update reparse ou não diretório.
- Delegação ao avaliador com fechamento do layout.
- Falha fechada quando a validação do layout falha.
- Teste do launcher que confirma que o Terminal não abre com instalação interrompida.
- Testes de empacotamento verificam os módulos e hidden imports.

## Evidência de CI, 20/11/2026

- Workflow SERMAX Update Staging Validation, run 44788421076: todas as etapas passaram.
- Workflow SERMAX Update Staging Validation, run 44788607573: todas as etapas passaram após a atualização dos filtros de CI.
- Workflow SERMAX Windows CI, run 44788948615: concluído com sucesso.
- A execução 44788948615 aprovou compilação das fontes, testes de integração SERMAX, build de SERMAX.exe com Python 3.14, smoke test do executável congelado e Terminal original, e publicação do artefato.
- Execução completa: https://github.com/frserpeloni/AndroidForge/actions/runs/44788948615.

## Artefato produzido

- Nome: SERMAX-Windows-executable.
- Arquivo ZIP: 23.044.238 bytes.
- Conteúdo: exclusivamente SERMAX.exe.
- Formato do executável: PE32+, Windows x86-64.
- SHA-256 do ZIP: 128c57bf02e4c89db237586cc5bbe75580b0fb45e096fc9f2d726887435316ed.
- SHA-256 do SERMAX.exe: 325a21caf370b4841476fbe37bece9b7eb327d3e7b523a2c4a583ffc80784577.

**Este artefato não é um instalador/atualizador instalável.** Não contém pacote de atualização, manifesto assinado, chave pública de produção ou procedimento de instalação. O sucesso do CI não comprova instalação na máquina Windows 11 do mantenedor e não autoriza alteração em C:\\SERMAX.

## Estado e próximos passos

Implementação em branch isolada e PR em rascunho. CI e build congelado aprovados no runner Windows do GitHub. Homologação na instalação Windows 11 do mantenedor permanece pendente. O próximo passo é homologação controlada sem sobrescrever a instalação ativa, seguida da implementação e validação separada do instalador/atualizador de produção. Sem merge, sem release e sem alteração em C:\\SERMAX.
