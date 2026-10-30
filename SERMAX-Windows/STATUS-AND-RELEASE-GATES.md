# SERMAX Windows, status de integração

**Status: integração em andamento. O artefato gerado é de teste, não é release nem instalador validado.**

## Referência e integridade
- Referência de trabalho do projeto: `SERMAX_CONSOLIDACAO_TECNICA_CANDIDATA_28-10-2026`.
- Commit atual da integração Windows: `4ec2927d7728ff050da514ed1d07c8a74a4488fd`.
- Backup de referência informado: `SERMAX bkp 28 10 26.zip`.
- A interface original foi restaurada em `SERMAX_terminal/sermax_terminal.py`, usando a fonte preservada. A verificação automatizada confirmou os marcadores do rosto ASCII, cores verdes, funções de renderização e comandos `/vozdiag`, `/reiniciar` e `/repetir`.

## Validação automatizada em 30/10/2026
- Workflow run: `41057411248`, conclusão `success`.
- Workflow run duplicado: `41057404849`, conclusão `success`.
- Commit validado: `4ec2927d7728ff050da514ed1d07c8a74a4488fd`.
- Verificação dos arquivos obrigatórios: aprovada.
- Verificação da interface e dos comandos originais: aprovada.
- Compilação sintática dos arquivos Python: aprovada.
- Testes unitários existentes: aprovados.
- Compilação PyInstaller: aprovada.
- Verificação da saída `dist/SERMAX.exe`: aprovada.
- Artefato de teste: `SERMAX-Windows-CI-44`, executável de 8.865.683 bytes. Cabeçalho PE válido verificado após baixar o ZIP.
- O artefato tem retenção limitada no GitHub Actions. Não o tratar como pacote de instalação.

Esses resultados confirmam a restauração da interface no repositório e a compilação no runner Windows do GitHub. Não comprovam execução funcional no computador do mantenedor nem integração real com Ollama, voz, memória persistente ou atualização segura da instalação.

## O que ainda precisa ser validado
1. Comparar o núcleo e todos os módulos da ramificação com os arquivos oficiais do backup de referência.
2. Conferir a especificação PyInstaller e os recursos incluídos no executável contra a instalação aprovada.
3. Testar no Windows do mantenedor a inicialização, o rosto e o layout reais, os comandos existentes e o comportamento com Ollama indisponível e disponível.
4. Confirmar que `memoria_sermax.json` é gravada em `C:\\SERMAX`, permanece após fechar e reabrir o programa e nunca é substituída durante atualização.
5. Testar voz com os arquivos locais reais do Whisper e o modelo de voz, sem baixar nem substituir recursos existentes.
6. Preparar e testar um atualizador com backup e rollback, preservando memória, interface, ferramentas e backups anteriores.
7. Registrar cada teste como APROVADO, FALHOU ou NÃO EXECUTADO. Não inferir aprovação de testes que dependem do computador do mantenedor.

## Proteção da instalação existente
- Não instalar o artefato de CI diretamente sobre `C:\\SERMAX`.
- Não declarar a versão v1.8.2 concluída.
- Não mesclar nem publicar como release até que a comparação com o backup e os testes funcionais sejam concluídos.
- Não incluir `memoria_sermax.json`, históricos pessoais, gravações de voz ou outros dados privados no repositório.
