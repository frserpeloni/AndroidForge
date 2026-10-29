# SERMAX Windows — status de integração

**Status: em integração; não é uma versão instalável nem um release.**

## Objetivo da integração
A referência de trabalho é o backup fornecido pelo mantenedor. A versão de destino planejada é SERMAX v1.8.2, partindo da base v1.8.1. A interface terminal verde/preta com rosto ASCII, memória persistente e comandos existentes devem ser preservados.

## Resultado de CI confirmado em 29/10/2026
- Workflow run: `40957286990`.
- Commit validado: `c71f2bb25d7fb376f6307b352100b2e2353fecc0`.
- Checagem de fontes obrigatórias: aprovada.
- Checagem de sintaxe: aprovada.
- Testes unitários disponíveis: aprovados.
- Compilação PyInstaller: aprovada.
- Verificação de `dist/SERMAX.exe`: aprovada.
- Artefato de teste gerado: `SERMAX-Windows-CI-34` (8.662.412 bytes; retenção indicada até 12/11/2026).

Esses resultados comprovam que a árvore atual compila no runner Windows do GitHub. Não comprovam a execução correta no computador do mantenedor, nem a integração real com Ollama, voz ou memória persistente após reinicialização.

## O que existe nesta ramificação
Há documentação, um fluxo de CI e módulos de integração. A presença desses arquivos não significa que o projeto original esteja integralmente importado. O arquivo atual `SERMAX_terminal/sermax_terminal.py` é explicitamente um terminal de contingência e não a interface visual original.

## Bloqueios atuais
- O núcleo e os módulos desta ramificação ainda precisam ser comparados com os arquivos oficiais do backup.
- A interface original `SERMAX_terminal/sermax_terminal.py`, com rosto ASCII verde e layout DOS, ainda precisa ser restaurada a partir da fonte original e conferida.
- A especificação de compilação e os recursos precisam ser comparados com a cópia original antes de considerar o executável fiel ao projeto.
- É necessário testar no Windows do mantenedor a persistência da memória fora da pasta temporária do PyInstaller, a inicialização, comandos, voz e conexão com Ollama.
- O artefato de CI é temporário e **não deve ser instalado sobre** `C:\SERMAX`.

## Critérios obrigatórios antes de publicar
1. Importar e comparar os fontes oficiais do backup, sem substituir a interface por outra.
2. Excluir memória pessoal, histórico, backups locais, modelos de IA, gravações de voz e outros dados privados do repositório público.
3. Confirmar sintaxe e testes automatizados em Windows.
4. Compilar o executável usando a especificação oficial revisada.
5. Verificar que a memória é gravada fora da pasta temporária do PyInstaller e continua existindo após reiniciar.
6. Testar comandos e interface no Windows real com Ollama; testes de CI não comprovam por si só a integração com o modelo local.
7. Só então preparar um release versionado e instruções de atualização com backup/rollback.

**Não instale nem distribua esta ramificação como uma versão final.** A instalação existente em `C:\SERMAX` não deve ser alterada até que um pacote de atualização validado esteja disponível.
