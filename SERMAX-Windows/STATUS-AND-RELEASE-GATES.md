# SERMAX Windows, status de integração

**Status: integração em andamento. O artefato gerado é de teste, não é release nem instalador validado.**

## Atualização de 30/10/2026, CI 55
- Run `41060423045` concluído com `success` no branch `sermax-windows-integration-20261029`.
- Passaram as verificações de fontes, marcadores da interface original, sintaxe, testes unitários, compilação PyInstaller, verificação do executável e upload do artefato.
- Artefato `SERMAX-Windows-CI-55`, ID `12977819771`, tamanho ZIP de 8.667.631 bytes, SHA-256 do ZIP `8e1b2dd6e551dfa1f3bc5d9b28d039c5f0f19658b6f7a443bb6a17f07b30e12d`. Retenção de 14 dias. É artefato de CI, não instalador aprovado.
- Correção validada pelo CI: o diagnóstico `/integracao` prioriza `SERMAX_ROOT` ao localizar os arquivos de voz, evitando depender da pasta temporária do PyInstaller.
- Teste de regressão acrescentado para verificar o uso de `SERMAX_ROOT`. O CI concluiu com sucesso, mas a execução real do `.exe` e os testes de voz/memória no computador de destino continuam pendentes.
- Run: https://github.com/frserpeloni/AndroidForge/actions/runs/41060423045


## Referência e integridade
- Referência de trabalho do projeto: `SERMAX_CONSOLIDACAO_TECNICA_CANDIDATA_28-10-2026`.
- Commit atual da integração Windows: `4ec2927d7728ff050da514ed1d07c8a74a4488fd`.
- Backup de referência informado: `SERMAX bkp 28 10 26.zip`.
- A interface original foi restaurada em `SERMAX_terminal/sermax_terminal.py`, usando a fonte preservada. A verificação automatizada confirmou os marcadores do rosto ASCII, cores verdes, funções de renderização e comandos `/vozdiag`, `/reiniciar` e `/repetir`.

## Validação automatizada em 30/10/2026
- Workflow run mais recente: `41059175794`, conclusão `success`, commit `f3a386917e982e377b487bb9beec5d7af06bc15e`.
- O run 49 executou 10 testes unitários e de integração, todos aprovados.
- Também passaram verificação dos arquivos obrigatórios, marcadores da interface original, sintaxe Python, compilação PyInstaller, verificação do executável e envio do artefato.
- Runs anteriores `41057411248` e `41057404849` também concluíram com `success` no commit de restauração da interface `4ec2927d7728ff050da514ed1d07c8a74a4488fd`.
- Testes identificados no log: 6 testes de memória/núcleo e 4 testes de integração/empacotamento, total de 10 aprovados.
- Os testes cobrem arquivos necessários, referências no `SERMAX.spec`, configuração do caminho da memória e ausência de memória pessoal no repositório.
- Artefato de teste do run 49: `SERMAX-Windows-CI-49`, ID `12977713565`, ZIP de 8.667.355 bytes. Não é pacote de instalação validado.
- O artefato tem retenção limitada no GitHub Actions. Não o tratar como release.

Esses resultados confirmam a restauração da interface no repositório, a aprovação dos 10 testes automatizados e a compilação no runner Windows do GitHub. Não comprovam execução funcional no computador do mantenedor nem integração real com Ollama, voz, memória persistente ou atualização segura da instalação.

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
