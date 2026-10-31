# SERMAX Windows, status de integração

**Status: integração em andamento. O artefato gerado é de teste, não é release nem instalador validado.**

## Atualização de 30/10/2026, CI 90
- Run `41085611109` concluído com `success` no branch `sermax-windows-integration-20261029`, commit `e1d3f7498df6f44df5ec198f4364e7829e962169`.
- As etapas de fontes obrigatórias, marcadores da interface original, sintaxe, testes automatizados, compilação PyInstaller, verificação do executável e upload do artefato passaram.
- Isso valida a compilação automatizada no runner Windows. Não valida a execução real do SERMAX.exe, Ollama, voz, persistência após reinício ou atualização segura no computador do mantenedor.
- Run: https://github.com/frserpeloni/AndroidForge/actions/runs/41085611109

## Atualização de 30/10/2026, CI 88
- Run `41081941583` concluído com `success` no branch `sermax-windows-integration-20261029`, commit `8d171c99e2d5a8c52fd90cdc90c15da553271672`.
- Foram aprovadas as etapas de verificação das fontes, marcadores da interface original, sintaxe Python, testes automatizados, compilação PyInstaller, verificação do executável e upload do artefato.
- Artefato `SERMAX-Windows-CI-88`, ID `12989792029`, tamanho ZIP de 8.667.380 bytes, SHA-256 `1150f89d5a518546258d3332c26e424c6c77173090a94cb9edcbb8197b6047e0`. Retenção até 13/11/2026.
- A CI não executa o `.exe` gerado e não valida a integração real com Ollama, voz, memória após reinício ou atualização segura.
- Run: https://github.com/frserpeloni/AndroidForge/actions/runs/41081941583

## Atualização de 30/10/2026, CI 84
- Run `41078209745` concluído com `success` no branch `sermax-windows-integration-20261029`, commit `f57bfa84fe681a70b57bda13f16512b8ab8782af`.
- Foram aprovados 23 testes automatizados: 9 testes de núcleo/memória e 14 testes de integração/empacotamento, incluindo validação de WAV, fallback quando faltam os recursos do Whisper, caminhos do launcher e preservação da memória.
- Também passaram a verificação de fontes obrigatórias, marcadores da interface original, sintaxe Python, compilação PyInstaller, verificação do executável e upload do artefato.
- Artefato `SERMAX-Windows-CI-84`, ID `12987663118`, tamanho ZIP de 8.666.192 bytes, SHA-256 do ZIP `2ef1340b568a65c316e7bb6d6b0856ad17f7affdb661d52f403de1c11111ce47`. Retenção até 13/11/2026. É artefato de CI, não instalador aprovado.
- Run: https://github.com/frserpeloni/AndroidForge/actions/runs/41078209745

## Referência e integridade
- Referência de trabalho do projeto: `SERMAX_CONSOLIDACAO_TECNICA_CANDIDATA_28-10-2026`.
- Commit de restauração da interface original: `4ec2927d7728ff050da514ed1d07c8a74a4488fd`.
- Commit da branch na referência anterior deste registro: `8d171c99e2d5a8c52fd90cdc90c15da553271672`. Commit atual do registro: `e1d3f7498df6f44df5ec198f4364e7829e962169`.
- Backup de referência informado: `SERMAX bkp 28 10 26.zip`.
- A interface original foi restaurada em `SERMAX_terminal/sermax_terminal.py`, usando a fonte preservada. A verificação automatizada confirmou os marcadores do rosto ASCII, cores verdes, funções de renderização e comandos `/vozdiag`, `/reiniciar` e `/repetir`.

## Validação automatizada anterior em 30/10/2026
- Workflow run `41059175794`, conclusão `success`, commit `f3a386917e982e377b487bb9beec5d7af06bc15e`.
- O run 49 executou 10 testes unitários e de integração, todos aprovados.
- Runs anteriores `41057411248` e `41057404849` também concluíram com `success` no commit de restauração da interface.
- Artefato de teste do run 49: `SERMAX-Windows-CI-49`, ID `12977713565`, ZIP de 8.667.355 bytes. Não é pacote de instalação validado.

Esses resultados confirmam a validação automatizada e a compilação no runner Windows do GitHub. Não comprovam execução funcional no computador do mantenedor nem integração real com Ollama, voz, memória persistente ou atualização segura da instalação.

## Auditoria de continuidade, 30/10/2026
- A árvore atual de `SERMAX-Windows` não contém instalador nem atualizador/rollback dedicado. A CI gera somente `SERMAX.exe`; não gera um pacote seguro de atualização para `C:\\SERMAX`.
- A comparação completa com `SERMAX_CONSOLIDACAO_TECNICA_CANDIDATA_28-10-2026` e com `SERMAX bkp 28 10 26.zip` continua NÃO EXECUTADA: esses arquivos de referência não estão disponíveis na árvore da branch nem foram localizados na busca de arquivos disponível nesta sessão. Não substituir essa comparação por suposição.
- Próxima tarefa técnica: localizar e obter a referência oficial, inventariar e comparar os módulos antes de alterar o núcleo; em paralelo, desenhar testes e implementação do atualizador com backup, preservação da memória/interface/ferramentas e rollback. Não publicar nem instalar o executável de CI enquanto esses gates estiverem abertos.

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
