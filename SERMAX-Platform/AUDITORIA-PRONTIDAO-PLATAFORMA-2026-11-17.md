# Auditoria de prontidao da Plataforma SERMAX
Data: 2026-11-17
Branch de trabalho: `sermax-platform-readiness-20261117`
Base: `sermax-cleanup-20261117`
Estado: auditoria inicial; desenvolvimento funcional autorizado por Fabiano em 2026-11-17.

## 1. Preservacao e estrategia de branches

- A branch de trabalho foi criada a partir de `sermax-cleanup-20261117`.
- A branch `sermax-cleanup-20261117` esta 18 commits a frente de `sermax-windows-integration-20261029`, sem commits atras.
- A branch antiga `sermax-platform-prototype-20261115` diverge da branch de limpeza: 261 commits a frente e 46 atras em relacao a `sermax-cleanup-20261117`.
- Nao foi feito merge, rebase ou force push.
- PR #5 e PR #6 permanecem sem merge.
- `main`, `C:\SERMAX`, memoria pessoal, historico local e backups nao foram alterados.

A continuidade sera feita na nova branch para evitar incorporar os 46 commits ausentes por um merge amplo e sem revisao. A branch antiga sera mantida como referencia historica ate a revisao das diferencas.

## 2. Evidencia da validacao automatizada existente

No commit de codigo `cadcd1fc3fc6e7c7798f2f851759a2dc576e2e7f`:

- Windows CI, run `44108333243`: sucesso. O job `validate-and-build` concluiu compilacao, testes configurados, build do executavel e smoke test do Terminal original.
- Platform CI, run `44108334492`: sucesso. Foram concluidos os jobs `windows-validation`, `frontend-interaction`, `frontend-check`, `backend-tests (3.12)` e `backend-tests (3.14)`.
- O Platform CI cobre API com FakeCore, testes de interface com DOM simulado, launcher e testes do prototipo do instalador.
- O CI nao comprova conversa com Ollama real, worker OpenJarvis real, navegador real, instalacao no computador do usuario ou atualizacao segura.

## 3. Estado confirmado por componente

| Componente | Estado observado | Lacuna |
|---|---|---|
| Interface de conversa | Implementada | Sem streaming; erros exibidos como mensagem simples |
| Historico SQLite | Implementado | Sem exportacao, busca ou gestao avancada |
| Projetos | CRUD basico, arquivamento e associacao implementados | Sem permissao por projeto; memoria geral continua compartilhada |
| Contexto de conversa | Sessao temporaria reconstruida e sessao global restaurada | Validacao ainda usa FakeCore |
| API FastAPI | Implementada, loopback, verificacao de Host, Origin e IP | Sem autenticacao local por token; nao expor em rede |
| Tela Tarefas | Placeholder | Sem fila persistente ou execucao |
| Tela Memoria | Placeholder protegido | Sem consulta controlada da memoria |
| Seletor de modelo | Opcoes visiveis na interface | Alteracao nao altera o roteamento; mostra somente aviso |
| Anexos | Botao informativo | Nenhum upload ou leitura implementado |
| Launcher | Script Python de desenvolvimento | Nao integrado ao SERMAX.exe |
| Instalador/atualizador | Prototipo e documentacao | Bloqueado por riscos de seguranca, assinatura, transacao e rollback |
| Integracao com nucleo real | Adaptador tardio implementado | Nao homologado com o ambiente real e motores locais |

## 4. Achados tecnicos da leitura do codigo

### 4.1 Integracao do nucleo
O backend importa `sermax_core.py` sob demanda. Durante a chamada, substitui `core.sessao` pelo contexto reconstruido da conversa e restaura a sessao anterior no bloco `finally`. O bloqueio global serializa as chamadas.

Os testes atuais usam FakeCore. Portanto, ainda nao existe evidencia automatizada de que o nucleo real importe no ambiente de execucao da Plataforma e responda por OpenJarvis/Ollama.

A memoria persistente geral do SERMAX continua compartilhada e segue as regras do nucleo. Esse comportamento esta documentado e nao sera alterado sem decisao expressa.

### 4.2 Interface
O seletor apresenta “Automatico”, “Ollama local” e “OpenJarvis”, mas o evento de mudanca informa que o roteamento permanece automatico. Nenhum valor e enviado a API. A interface sugere uma selecao manual que ainda nao existe.

As telas Tarefas e Memoria exibem estados de espera. Nao ha operacoes funcionais ligadas a elas.

### 4.3 Inicializacao e dependencias
`backend/run_local.bat` executa `pip install -r requirements.txt` em toda inicializacao. As dependencias estao declaradas por faixas de versao, sem lockfile. Isso permite alteracao de versoes resolvidas entre inicializacoes e exige acesso ao indice de pacotes.

O launcher Python da Plataforma nao esta integrado ao executavel principal.

### 4.4 Instalacao e atualizacao
Os documentos de auditoria existentes registram risco TOCTOU, ausencia de assinatura/autenticidade comprovada, ausencia de transacao global e rollback garantido, alem de lacunas de preservacao e recuperacao. Nenhum instalador sera liberado nesta etapa.

## 5. Plano de execucao

### Fase A, homologacao da integracao
1. Criar teste de importacao controlada do nucleo real, sem chamada a modelo e sem gravacao de memoria.
2. Verificar dependencias reais do nucleo em Windows.
3. Criar teste de contrato do adaptador para confirmar restauracao de sessao em sucesso e excecao.
4. Executar CI em Windows e registrar exatamente quais verificacoes foram aprovadas.
5. Preparar procedimento de teste local que nao toque na instalacao `C:\SERMAX`.

### Fase B, funcionalidades de trabalho
1. Implementar tarefas persistentes com estados, datas, prioridade e historico.
2. Ligar a tela Tarefas a API e SQLite.
3. Projetar consulta de memoria com leitura controlada, sem editar ou apagar arquivos de memoria.
4. Tornar o estado do nucleo e dos motores explicito na interface.

### Fase C, conversa
1. Implementar streaming com cancelamento seguro e persistencia de estado.
2. Projetar anexos com allowlist de formatos, limite de tamanho, armazenamento isolado e validacao de conteudo.
3. Testar retomada de conversa e falha durante streaming.

### Fase D, modelos e ferramentas
1. Definir contrato real de selecao manual e automatica.
2. Implementar override sem quebrar a selecao automatica atual.
3. Exibir disponibilidade verificada, nunca presumida, dos motores.

### Fase E, distribuicao
1. Fixar dependencias e gerar inventario/SBOM.
2. Fechar avisos e obrigacoes das licencas de terceiros.
3. Concluir instalador/atualizador com protecao baseada em handles, plano imutavel, assinatura, journal e rollback validado.
4. Integrar launcher sem substituir o Terminal original.

### Fase F, homologacao Windows
Executar instalacao limpa e atualizacao em ambiente Windows descartavel, testes de interrupcao, recuperacao, preservacao de dados, inicializacao, encerramento e reinicio. Somente depois avaliar pacote candidato.

## 6. Criterios de conclusao

A Plataforma so sera declarada pronta para uso quando:
- a integracao com o nucleo real for validada;
- as telas anunciadas tiverem funcionalidades reais ou forem explicitamente removidas/identificadas como indisponiveis;
- os fluxos de conversa, historico, projetos e tarefas passarem por testes;
- o comportamento de memoria estiver documentado e comprovado;
- o launcher iniciar e encerrar corretamente;
- instalador e atualizador passarem por testes de seguranca e recuperacao no Windows;
- nenhuma alteracao comprometer o Terminal original, memoria pessoal, historico ou backups.


## 7. Atualização de execução, 2026-11-17

Após a auditoria inicial, a branch recebeu a primeira entrega funcional da Fase B:

- Criada tabela SQLite `tasks`, com migração aditiva e estados `pending`, `in_progress`, `completed` e `cancelled`.
- API para criar, listar, consultar e editar tarefas, atualizar estado, filtrar por estado e ordenar por prioridade/prazo.
- Validação de título, descrição, prioridade e data ISO 8601.
- Tela Tarefas conectada à API, com formulário, prioridade, prazo, filtro e atualização de estado.
- Não há exclusão física, execução de comandos ou execução em segundo plano.
- Testes adicionados para criação, ordenação, edição, conclusão, filtros, data inválida, campos nulos e persistência após reabertura do SQLite.
- Teste de interface adicionado para criação e atualização do estado.

A execução CI `44131386495` foi iniciada para validar a versão com tarefas e os testes atualizados. Até a conclusão dos jobs, esta entrega permanece aguardando validação automatizada. A execução anterior `44130892314` aprovou os testes de importação do núcleo real e restauração de sessão na versão anterior à entrega de tarefas e ao caso de sessão originalmente nula.

Nenhum teste físico no computador do usuário foi realizado nesta auditoria. Nenhum arquivo de `C:\SERMAX` foi acessado ou alterado.
