# SERMAX Windows — status de integração

**Status: em integração; não é uma versão instalável nem um release.**

## Objetivo da integração
A referência de trabalho é o backup fornecido pelo mantenedor. A versão de destino planejada é SERMAX v1.8.2, partindo da base v1.8.1. A interface terminal verde/preta com rosto ASCII, memória persistente e comandos existentes devem ser preservados.

## O que existe nesta ramificação
Há documentação, um fluxo inicial de CI e alguns módulos auxiliares. A presença desses arquivos não significa que o projeto original esteja integralmente importado. Alguns arquivos nesta pasta são módulos auxiliares de integração e ainda precisam ser comparados com o backup oficial antes de qualquer release.

## Bloqueios atuais
- O núcleo original `sermax_core.py` do backup ainda não foi incorporado nesta pasta.
- A interface original `SERMAX_terminal/sermax_terminal.py` ainda não foi incorporada nesta pasta.
- A especificação original `SERMAX.spec` e os recursos necessários ao executável ainda não foram integrados.
- A execução do workflow no Windows falhou na etapa de build porque a estrutura de projeto exigida para produzir o executável ainda está incompleta.
- Não há artefato `SERMAX.exe` novo produzido por este workflow.

## Critérios obrigatórios antes de publicar
1. Importar e comparar os fontes oficiais do backup, sem substituir a interface por outra.
2. Excluir memória pessoal, histórico, backups locais, modelos de IA, gravações de voz e outros dados privados do repositório público.
3. Confirmar sintaxe e testes automatizados em Windows.
4. Compilar o executável usando a especificação oficial revisada.
5. Verificar que a memória é gravada fora da pasta temporária do PyInstaller e continua existindo após reiniciar.
6. Testar comandos e interface no Windows real com Ollama; testes de CI não comprovam por si só a integração com o modelo local.
7. Só então preparar um release versionado e instruções de atualização com backup/rollback.

**Não instale nem distribua esta ramificação como uma versão final.** A instalação existente em `C:\SERMAX` não deve ser alterada por este trabalho até que um pacote de atualização validado esteja disponível.
