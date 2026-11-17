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

## Candidatos que exigem investigação adicional

- `SERMAX-Windows/sermax.py` é um ponto de entrada CLI separado do launcher/Terminal. Não retirar sem comprovar ausência de uso externo.
- `SERMAX-Windows/SERMAX_terminal/sermax_terminal.py` importa módulos de integração e voz. Preservar até auditoria de chamadas e do empacotamento.
- `sermax_voz.py` percorre recursivamente diretórios de instalação e Downloads para localizar Whisper/modelo. Há oportunidade de otimização, mas mudanças exigem teste de descoberta e compatibilidade.
- Os módulos Windows de handle, ACL, Authz e área privada possuem dependências cruzadas e testes nativos. Não consolidar nem remover por semelhança nominal.
- O protótipo Android está em árvore separada. Não há evidência suficiente para classificá-lo como obsoleto.
- A PR da Plataforma divergiu do HEAD Windows atual em 28 commits. A branch desta operação incorporou os arquivos novos da Plataforma, preservando os módulos Windows mais recentes. Alterações compartilhadas da PR da Plataforma exigem integração seletiva.

## Garbage

Nenhum arquivo foi movido nesta etapa. A pasta `garbage/` foi criada com regras de preservação. Candidatos só serão movidos após análise de imports, referências dinâmicas, entrypoints, PyInstaller, workflows e testes.

## Validação

Nenhum teste é declarado aprovado por esta auditoria inicial. Resultados de CI serão registrados com commit, run ID, job, contagem e artefatos quando disponíveis.

## Entrega

Esta documentação é registro parcial da operação. Não representa conclusão da auditoria geral, pacote instalável ou release.
