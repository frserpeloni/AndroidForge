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


## Atualização de auditoria, 01/11/2026
- Commit verificado: `2fde2fcac29643f3612b44913988fc9e0509742e`.
- GitHub Actions run `41311712672`, execução `102`, conclusão `success`. Passaram todas as etapas listadas no job: verificação de fontes, marcadores do terminal, sintaxe, testes unitários, build PyInstaller, verificação do executável e upload.
- Artefato de CI: `SERMAX-Windows-CI-102`, ID `13085925800`, ZIP de 8.668.103 bytes, SHA-256 `bd992876a83b413cca174cff76f31c55b41d7fb57311fe7116cd0b982eff2d0d`, retenção até 15/11/2026. Artefato de teste, não instalador.
- A revisão estática encontrou uma divergência de configuração a validar antes da liberação: `sermax_core.py` define `MODELO = "sermax"`, enquanto o painel do terminal exibe `QWEN 2.5 1.5B` e o comando `/modelo` responde `qwen2.5:1.5b`. O alias `sermax` pode ser intencional no Ollama, mas isso não foi comprovado nesta auditoria. Confirmar o modelo/alias real no Windows do mantenedor e alinhar a informação exibida sem alterar a configuração até confirmar a referência.
- O launcher resolve a pasta persistente a partir de `sys.executable` e carrega a interface a partir de `sys._MEIPASS`; os testes automatizados verificam essa separação. Ainda falta executar o EXE no Windows real e confirmar memória, voz, Ollama, reinício e atualização/rollback.


## Atualização de auditoria, 01/11/2026, CI 104
- O commit `2461c69f2b1f90ec4c88ddc7a7b807344840c131` recebeu a execução `41316219916`, run `104`, conclusão `success`.
- Todas as etapas do job `test-and-build` concluíram com sucesso: fontes obrigatórias, marcadores de interface/comandos, sintaxe, suíte de testes, build PyInstaller, verificação do executável e upload.
- Artefato `SERMAX-Windows-CI-104`, ID `13087577168`, ZIP de 8.669.163 bytes, digest SHA-256 `e9f2aab6231d56d1cff663478f72c947000eb641e5b1f078141c7ce0f5220172`. Expira em 15/11/2026. É um executável de CI, não instalador nem atualizador.
- Run: https://github.com/frserpeloni/AndroidForge/actions/runs/41316219916
- Revisão adicional do histórico persistente confirmou que `registrar()` recusa gravação quando o JSON existente está corrompido ou não possui a estrutura `{"comandos": [...]}`; os testes dedicados comparam os bytes originais antes e depois da tentativa de gravação.
- A revisão do núcleo confirma que a memória persistente é resolvida por `SERMAX_ROOT` quando definida, ou pela pasta do executável quando empacotado. A CI verifica o build, mas não executa o EXE nem prova a persistência no Windows do mantenedor.
- A divergência entre `MODELO = "sermax"` e o texto de interface `QWEN 2.5 1.5B` permanece como verificação funcional pendente. Não alterar o modelo até confirmar o alias e o comportamento no Ollama instalado.


## Atualização de integração Jarvis, 05/11/2026

- O OpenJarvis agora também está ligado ao fluxo principal de respostas do SERMAX, por seleção explícita do motor.
- Comandos: `/motor status`, `/motor jarvis` e `/motor ollama`. A seleção vale para a sessão atual. O padrão permanece Ollama nativo para preservar a inicialização existente em computadores sem Python 3.13.
- Ao selecionar Jarvis, o SERMAX envia identidade, memórias recuperadas e contexto recente como prompt. O SDK OpenJarvis continua com `tools=[]` e `context=False`; não ganha acesso à memória ou ferramentas por conta própria.
- Pestinha permanece ligado ao ciclo de solicitações por eventos fechados e saída limitada aos estados visuais permitidos. A persistência neural continua em `memoria_neural_pestinha.json`.
- Adicionados testes para a seleção do motor e o encaminhamento de identidade/memória/contexto ao Jarvis.
- Commits desta etapa: `5462aec4c551ada5d564acb2f571c4714a23dfac`, `952f284dd42ce3acb60736dbb99ccd76faabfc2d`, `548842bd0286f4c972a19ea0e6d1aa563ff9b3e2`.
- **Validação pendente:** os novos testes ainda precisam executar na CI Windows. A integração real com Ollama no computador do mantenedor, instalação do ambiente Python 3.13, teste de resposta Jarvis com modelo local e persistência neural após reinício continuam não executados.
- Não há release nem instalador aprovado. A revisão GPL-3.0-or-later, a correção final do empacotamento Pestinha e o atualizador com backup/rollback continuam como gates de distribuição.


## Revisão de arquitetura e fontes upstream, 05/11/2026

- Criado `ARQUITETURA-SERMAX-UNIFICADO-JARVIS-PESTINHA.md`, com o desenho final de coordenação automática sob identidade SERMAX.
- Consultados os repositórios oficiais OpenJarvis e Pestinha, incluindo README, manifesto de dependências, núcleo LIF e documentação de arquitetura, rede e privacidade.
- OpenJarvis documenta oito agentes, catálogo de skills e fluxos de avaliação/aprendizagem. A integração atual do SERMAX continua limitada ao agente `simple`, sem ferramentas e sem contexto próprio do SDK. Não declarar incorporação ampla.
- Pestinha documenta rede de 470 neurônios LIF, 15.939 sinapses, 30 canais sensoriais, 10 populações de interneurônios e 15 populações motoras, com habituação, plasticidade, condicionamento e memória episódica. O adaptador SERMAX atual utiliza somente eventos sintéticos e a interface LIF. Não declarar incorporação de toda a arquitetura.
- A rede Pestinha é um sistema comportamental para um pet de tela. Não é, por si só, um modelo geral de linguagem ou raciocínio humano. No SERMAX, deve atuar como subsistema comportamental/atencional, sob supervisão do núcleo.
- Sensores do computador, rotina, interface Qt, autostart e assets do Pestinha ficam fora da primeira integração. O código é GPL-3.0-or-later e assets têm licenças distintas; revisar antes de distribuição.
- README atualizado para documentar `/motor` como seleção manual provisória e registrar o objetivo de roteamento automático.
- Commits desta sequência: `4b8dc68efb72338ae25071e6f12e6b4b8ee86317`, `ee6768e738fa854805ab106a9c3032502a0badc9`, `b0546d5c636b48f4abf01679c46ee41966c9d554`, `90b98686e2c29b894b13f3f4b6abbffffdd096be`.
- Consulta de workflows para o commit `b0546d5c636b48f4abf01679c46ee41966c9d554` retornou lista vazia. Não há CI nova comprovada para esta sequência.
- A PR nº 2 permanece aberta e em rascunho. Nenhuma alteração foi feita em `main`.

### Próximas tarefas técnicas
1. Fixar e auditar os commits upstream exatos usados pelo instalador, comparando-os com os commits atualmente consultados.
2. Mapear os contratos públicos do OpenJarvis para orquestrador, ReAct, operative, skills, traces e avaliação. Selecionar primeiro o conjunto compatível com as permissões SERMAX.
3. Mapear os mecanismos internos Pestinha e separar o que é lógica neural reutilizável da infraestrutura de pet/sensores.
4. Desenhar e implementar o supervisor SERMAX com roteamento automático, estado auditável, limites e fallback. Manter os comandos manuais como compatibilidade temporária.
5. Criar testes de integração de ponta a ponta e disparar CI em commit atualizado.
6. Só depois iniciar testes com modelo Ollama real e validação no Windows do mantenedor.

**Não executado nesta revisão:** testes locais da nova sequência, CI dos commits recentes, execução com modelo real, teste físico Windows, medição de recursos, atualizador/rollback e revisão jurídica de licença.


## Atualização de auditoria, 07/11/2026, CI 254

- Commit validado: `8afa040ed944591e0742bbdef930b4e56cf4a341`.
- Workflow run `42396609888`, execução 254, conclusão `success`.
- Job `validate-and-build`: todas as etapas concluídas com sucesso.
- Foram aprovados 94 testes automatizados em Python 3.14.
- OpenJarvis foi instalado em ambiente isolado Python 3.13.
- PyInstaller gerou `SERMAX.exe` no runner Windows.
- Smoke test executou o binário congelado, confirmou a abertura do terminal original, encontrou o prompt de entrada e processou `/sair`.
- Artefato `SERMAX-Windows-executable`, ID `13582579833`, ZIP de 22.827.088 bytes, digest SHA-256 `659130e36a7c32db14eec789e47d387f152639ca1cd8f3a42839e717215084d3`. Expira em 21/11/2026. É artefato de CI, não instalador.
- A primeira tentativa do smoke test falhou por comparação literal do caractere acentuado `ê` sob a página de código do runner. A verificação foi ajustada para procurar o prefixo ASCII `Voc`, sem alterar o terminal. A execução 254 passou após a correção.
- Run: https://github.com/frserpeloni/AndroidForge/actions/runs/42396609888
- A PR nº 2 permanece aberta, em rascunho e sem merge. Nenhuma alteração foi feita em `main`.
- Permanecem NÃO EXECUTADOS: comparação integral com a candidata `SERMAX_CONSOLIDACAO_TECNICA_CANDIDATA_28-10-2026` e o backup `SERMAX bkp 28 10 26.zip`; testes físicos na instalação `C:\\SERMAX`; validação de Ollama, Jarvis com modelo local, voz e persistência após reinício; atualizador e rollback; revisão final das obrigações GPL e assets.
- Não declarar versão final nem instalar o artefato de CI na instalação existente com base somente nesta execução.
