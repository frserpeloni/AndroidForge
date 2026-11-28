# Operação Limpeza Geral SERMAX, registro técnico

Data de início: 17/11/2026
Prazo autorizado: 12 horas corridas a partir do início efetivo
Branch de trabalho: `sermax-cleanup-20261117`
Commit-base: `3bee76de0b4224453c3ce02f8f74cc76ef240351`
Primeiro commit de consolidação: `67ecd698528ad6bbc421dfdf91c4ef920343a973`

## Escopo e integridade

A auditoria abrange SERMAX-Windows, SERMAX-Platform, workflows SERMAX, protótipo Android e seus testes, scripts e dependências. A branch de trabalho parte do HEAD atual da integração Windows. Os arquivos da Plataforma SERMAX e seu workflow foram incorporados como diretório isolado, sem substituir versões mais recentes dos módulos compartilhados do Windows. A PR da Plataforma permanece independente.

Não foram alterados `main`, `C:\\SERMAX`, memórias pessoais, histórico local ou backups. Não houve exclusão definitiva.

## Inventário inicial

- O snapshot da branch de trabalho contém 206 arquivos rastreados.
- A árvore inclui SERMAX-Windows, SERMAX-Platform, protótipo Android, workflows, scripts e documentação.
- SERMAX-Windows contém núcleo, Terminal original, launcher, memória/histórico, adaptadores Jarvis/Pestinha, executor, atualização e testes.
- SERMAX-Platform contém frontend, API local, launcher, testes, instalador e gerador de pacotes.
- A Plataforma é protótipo local. Não possui autenticação, acesso remoto, streaming, anexos nem tarefas em segundo plano, conforme seu README.
- O instalador da Plataforma possui testes de regressão TOCTOU marcados como expectedFailure na validação anterior. Isso não comprova segurança de instalação.
- O atualizador Windows ainda não possui fluxo transacional completo validado.

## Achado confirmado

1. `SERMAX-Windows/sermax_tarefas.py` importava `re` sem qualquer referência no restante do módulo. O import foi retirado em alteração localizada. Nenhuma função ou contrato foi alterado.
2. `SERMAX-Windows/SERMAX_terminal/sermax_voz.py` repetia buscas recursivas por `whisper-cli.exe` e `ggml-tiny.bin` em chamadas sucessivas. Foi adicionado cache positivo por caminho, com revalidação `is_file()`, prioridade mantida para os caminhos padrão e nova busca quando o arquivo em cache desaparece. Foram adicionados três testes para reutilização, prioridade de instalação nova e invalidação do cache.
3. O módulo `SERMAX-Windows/sermax_windows_handle_enum.py` e seu teste foram transferidos para `garbage/SERMAX-Windows/`. A implementação antiga usa enumeração `FILE_ID_BOTH_DIR_INFO` e FileId de 64 bits. A implementação ativa `sermax_windows_directory_enum.py` usa `FILE_ID_EXTD_DIR_INFO` e FileId de 128 bits, integrada a `sermax_windows_directory_handle.py`. A busca dos imports dos módulos de produção não identificou consumidor do módulo antigo; o único import encontrado estava no teste correspondente, que também foi preservado em garbage. Registro completo em `garbage/INDEX.md`.

## Candidatos que exigem investigação adicional

- `SERMAX-Windows/sermax.py` é um ponto de entrada CLI separado do launcher/Terminal. Não retirar sem comprovar ausência de uso externo.
- `SERMAX-Windows/SERMAX_terminal/sermax_terminal.py` importa módulos de integração e voz. Preservar até auditoria de chamadas e do empacotamento.
- `sermax_voz.py` percorre recursivamente diretórios de instalação e Downloads para localizar Whisper/modelo. Há oportunidade de otimização, mas mudanças exigem teste de descoberta e compatibilidade.
- Os módulos Windows de handle, ACL, Authz e área privada possuem dependências cruzadas e testes nativos. Não consolidar nem remover por semelhança nominal.
- O protótipo Android está em árvore separada. Não há evidência suficiente para classificá-lo como obsoleto.
- A PR da Plataforma divergiu do HEAD Windows atual em 28 commits. A branch desta operação incorporou os arquivos novos da Plataforma, preservando os módulos Windows mais recentes. Alterações compartilhadas da PR da Plataforma exigem integração seletiva.

## Garbage

Dois arquivos foram movidos para preservação em `garbage/`: o módulo antigo de enumeração e seu teste correspondente. Os blobs originais foram preservados e registrados em `garbage/INDEX.md`. Nenhum arquivo foi excluído definitivamente. A pasta não é incluída no empacotamento SERMAX.

## Validação

- PR #6, execução inicial de Plataforma run `44106817817`: sucesso nos cinco jobs, incluindo backend Python 3.12/3.14, frontend, testes de interação e validação Windows. Esse run antecede as otimizações recentes.
- PR #6, Plataforma run `44107016190`: jobs Linux de frontend, backend Python 3.12 e 3.14 concluídos com sucesso; validação Windows ainda em execução no último registro.
- Windows run `44107030850`: validação do commit com cache e novo teste ainda em execução no último registro.
- Nenhum resultado de teste local ou físico em `C:\\SERMAX` é alegado.
- A quantidade final de testes e o resultado dos novos testes de voz serão registrados após conclusão do Windows CI.

## Entrega

Esta documentação é registro parcial da operação. Não representa conclusão da auditoria geral, pacote instalável ou release.

## Atualização final de validação, 17/11/2026

### Correção do comando de planejamento
- `sermax_core.py` agora extrai o objetivo do texto original, em vez da versão normalizada usada para reconhecer o comando.
- Preserva capitalização, acentos e espaços internos do objetivo.
- Testes adicionados em `tests/test_sermax_core.py` para `/PLANO` com espaços iniciais e para o alias `/planejar`.

### Validação Windows, commit de código `1a4bee6ffb8aeb5ed415783297e4040350b4bc83`
- GitHub Actions run `44107822948`: conclusão `success`.
- Compilação de fontes: sucesso.
- Suíte SERMAX/Pestinha/OpenJarvis: sucesso.
- Build `SERMAX.exe` com Python 3.14: sucesso.
- Smoke test do executável congelado e Terminal original: sucesso.
- Publicação do artefato técnico: sucesso.
- Run: https://github.com/frserpeloni/AndroidForge/actions/runs/44107822948

Artefato:
- Nome: `SERMAX-Windows-executable`.
- ID: `14338958338`.
- Tamanho: 22.836.007 bytes.
- SHA-256: `7c2e7ca694660b96261553e0e9dfb88f2fc8e0c4a66964908347daba43ccc9a3`.
- Expira em 01/12/2026.
- É executável experimental de CI. Não é ZIP instalável, instalador ou release. Não instalar sobre `C:\\SERMAX`.

### Validação da Plataforma
- Run `44107837810`: sucesso em frontend, testes de interação, backend Python 3.12/3.14 e validação Windows.
- Run: https://github.com/frserpeloni/AndroidForge/actions/runs/44107837810

### Resultado e limites
- O cache de voz foi validado pela suíte automatizada; não foi executado benchmark de tempo no computador do usuário. O ganho verificado é a eliminação de buscas recursivas repetidas enquanto os caminhos encontrados continuam válidos.
- O teste de planejamento confirma preservação do texto original.
- Nenhum teste físico foi executado em `C:\\SERMAX`.
- O instalador da Plataforma não foi liberado. Os testes TOCTOU conhecidos continuam marcados como expectedFailure.
- O atualizador Windows transacional não foi concluído nem homologado.
- Nenhum pacote ZIP instalável foi produzido.
- A PR #6 permanece aberta, em rascunho e sem merge. A branch `main` não foi alterada.


## Encerramento da operação de limpeza, 17/11/2026

### Disposição final dos candidatos

A revisão final dos candidatos listados acima não encontrou evidência suficiente para excluir ou mover outros componentes. A decisão para cada item é:

| Item | Disposição | Fundamentação |
|---|---|---|
| `SERMAX-Windows/sermax.py` | PRESERVADO | É uma CLI funcional independente, com entrada interativa, streaming de resposta e diagnóstico. Não há prova de que nenhum usuário ou script externo dependa dela. |
| `SERMAX-Windows/SERMAX_terminal/sermax_terminal.py` | PRESERVADO | É o Terminal original. Contém a interface verde, rosto ASCII, painel, conversa, histórico, comandos, voz e reinício. É componente ativo e protegido pelo escopo da operação. |
| `SERMAX-Windows/SERMAX_terminal/sermax_voz.py` | PRESERVADO, com otimização já aplicada | A descoberta de Whisper e modelo é funcional e integrada ao Terminal. A alteração aprovada limita-se ao cache positivo com revalidação e testes. Não há base para remover a busca de compatibilidade. |
| Módulos Windows de handle, ACL, Authz e área privada | PRESERVADOS | O relatório registra dependências cruzadas e testes nativos. A inspeção disponível não sustenta remoção ou consolidação segura. |
| Protótipo Android | PRESERVADO | Está isolado em sua árvore e não há evidência de obsolescência ou substituição formal. |
| SERMAX-Platform | PRESERVADA | A Plataforma permanece em diretório isolado. Seus componentes são protótipo em desenvolvimento, não arquivos obsoletos. |
| Instalador e atualizador | PRESERVADOS, BLOQUEADOS PARA DISTRIBUIÇÃO | A revisão estática confirma riscos TOCTOU, ausência de broker/raiz protegida, assinatura de pacote, transação global e rollback garantido. Não corrigir esses riscos por exclusão ou improviso. |

### Resultado da limpeza

- Correções localizadas aprovadas e registradas: concluídas.
- Componente legado de enumeração sem consumidor de produção identificado: movido para `garbage/`, com blobs preservados e índice de recuperação.
- Demais candidatos: classificados como preservados, pois há uso ativo, dependência, proteção explícita ou falta de evidência para remoção.
- Nenhuma exclusão definitiva foi realizada.
- Nenhum arquivo de `C:\\SERMAX`, memória, histórico local ou backup foi alterado.
- `main` permanece fora da operação.
- A PR #6 permanece em rascunho, sem merge.

### Limites que não fazem parte da limpeza de código

A limpeza de código fica encerrada com a disposição acima. Isso não equivale à homologação do instalador ou à liberação de atualização. Permanecem bloqueados: implementação do broker e raiz protegida, prova de ACLs/identidade, assinatura e autenticidade dos pacotes, journal/transação, recuperação/rollback, testes adversariais em Windows real e validação física em `C:\\SERMAX`. Esses itens exigem projeto e validação próprios; não serão marcados como concluídos por esta operação.

### Critério de encerramento

Não há, na evidência revisada desta operação, outro arquivo cuja exclusão ou transferência para `garbage/` seja tecnicamente justificada. A limpeza está encerrada sem remoções especulativas. A PR #6 continua aguardando revisão e decisão de merge do responsável pelo projeto.
