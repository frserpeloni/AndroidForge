# Auditoria de continuidade SERMAX Windows, 07/11/2026

## Escopo

Auditoria feita diretamente na branch `sermax-windows-integration-20261029`, sem alterar `main`, sem instalar arquivos no computador do mantenedor e sem declarar testes não executados.

## Estado Git verificado

- Branch de trabalho: `sermax-windows-integration-20261029`.
- HEAD consultado: `60119ebf7a92762cbd629caee7c9f6d87d60cdfe`.
- `main`: `eb9f55d0d18099a1d6bfde4df63144515ed15412`.
- Merge base: `9c99d8fd26ca6e5176630adf6d06c81303f6ba15`.
- Comparação: branch com 220 commits exclusivos e 2 commits exclusivos de main.
- PR #2 permanece aberta e em rascunho, sem merge.

## Divergência de histórico e workflow

Os dois commits exclusivos de `main` são:

1. `95463343cc2b3597d081c837f9f06bd0bb213bd9`, criação de `.github/workflows/sermax-dev-agents.yml`.
2. `eb9f55d0d18099a1d6bfde4df63144515ed15412`, troca do modelo Groq para `openai/gpt-oss-20b`.

A branch também criou esse workflow de forma independente. Por isso o Git registra divergência no mesmo caminho, embora a branch já contenha o modelo `openai/gpt-oss-20b` introduzido em main.

Diferenças intencionais preservadas na branch:
- Gatilho `push` restrito à branch de desenvolvimento e ao próprio arquivo de workflow.
- Entrada `task` opcional com tarefa padrão de aceitação.
- `GROQ_MAX_TOKENS=2048`.
- Modelo `GROQ_MODEL=openai/gpt-oss-20b`.

A versão de main exige a entrada `task` e não define `GROQ_MAX_TOKENS`. Não substituir a versão da branch pela versão de main. A resolução da divergência deve preservar os ajustes acima e ser feita em branch/merge controlado, nunca por sobrescrita cega.

## CI

A consulta de execuções associadas ao HEAD `60119ebf7a92762cbd629caee7c9f6d87d60cdfe` retornou lista vazia. Portanto, não há CI nova comprovada para o HEAD atual.

Os resultados históricos descritos em `STATUS-AND-RELEASE-GATES.md` são de commits anteriores e não aprovam este HEAD. Também permanece necessária execução de CI Windows para a sequência atual.

## Revisão estática do núcleo

Arquivos lidos na branch:
- `SERMAX-Windows/sermax_core.py`
- `SERMAX-Windows/sermax_groq_backend.py`
- `SERMAX-Windows/sermax_dev_team.py`
- `SERMAX-Windows/sermax_github_agent_runner.py`
- `SERMAX-Windows/tests/test_sermax_core.py`

Observações confirmadas no código:
- O núcleo usa `MODELO = "sermax"` para a API Ollama. O alias local precisa ser confirmado no Ollama do mantenedor.
- O motor padrão é Ollama. Jarvis é selecionado por `SERMAX_MOTOR` ou pelos comandos de sessão `/motor`.
- A memória pessoal fica em `memoria_sermax.json`; o estado neural Pestinha usa arquivo separado `memoria_neural_pestinha.json`.
- A gravação da memória pessoal usa arquivo temporário, `fsync` e `os.replace`. Há testes para falha de substituição e preservação do arquivo anterior.
- A equipe de desenvolvimento usa uma fila SQLite sequencial e quatro papéis. O executor valida propostas, aplica alterações e executa testes antes do parecer final.
- O runner do GitHub limita os arquivos de contexto e restringe as propostas a Python e Markdown. O workflow concede `contents: write` à automação, portanto a revisão do diff e do commit produzido continua obrigatória.

Esta leitura é estática. Não equivale a execução de testes nem validação de Ollama, Jarvis ou Pestinha em ambiente real.

## Próximas ações técnicas

1. Resolver a divergência de histórico preservando integralmente a configuração atual do workflow da branch.
2. Acionar CI atualizada e registrar os resultados por commit.
3. Auditar o contrato de resposta/erro entre o motor Jarvis e o motor Ollama, com testes de fallback e sessão.
4. Confirmar o alias `sermax` no Ollama Windows e a exibição do modelo no terminal.
5. Só depois avançar para atualizador, backup e rollback. Não instalar artefato de CI sobre `C:\\SERMAX`.

## Gates ainda abertos

- CI do HEAD atual: NÃO EXECUTADA / NÃO COMPROVADA.
- Execução do SERMAX.exe no Windows físico: NÃO EXECUTADA.
- Ollama real e alias local: NÃO VALIDADO.
- Jarvis com ambiente Python 3.13 real: NÃO VALIDADO.
- Persistência neural após reinício: NÃO VALIDADA no computador do mantenedor.
- Atualizador e rollback: NÃO IMPLEMENTADOS/VALIDADOS como fluxo de release.
- Revisão de licença GPL-3.0-or-later e ativos Pestinha: PENDENTE.

Nenhuma versão final ou instalador foi declarado nesta auditoria.
