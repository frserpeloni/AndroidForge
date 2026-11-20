# SERMAX Nível 2: Engenheiro de Software Autônomo

**Estado:** especificação técnica inicial. Não é implementação concluída nem autorização para release.
**Base de continuidade:** `SERMAX_CONSOLIDACAO_TECNICA_CANDIDATA_28-10-2026`.
**Branch de trabalho:** `sermax-windows-integration-20261029`.

## Objetivo

Dar ao SERMAX capacidade de atuar como engenheiro de software autônomo: inspecionar o próprio projeto, identificar problemas, propor soluções, escrever alterações isoladas, executar testes, analisar falhas, corrigir o código e apresentar evidências. O ciclo deve reduzir a necessidade de intervenção humana em tarefas técnicas rotineiras, sem comprometer a instalação funcional.

"Programador de alto nível" é uma meta de engenharia, não uma alegação de que o sistema já possui capacidade equivalente à de um especialista humano. Cada competência será implementada e validada separadamente.

## Auditoria inicial do código existente

A inspeção estática dos módulos atuais mostra:

- `sermax_planejador.py`: consulta o Ollama e gera planos curtos em JSON. As instruções proíbem execução, comandos de terminal, scripts, alterações de arquivos e instalações.
- `sermax_executor.py`: aceita somente três ações locais: diagnóstico do sistema, consulta à memória e cálculo. Não oferece shell nem escrita de arquivos.
- `sermax_tarefas.py`: executa sequencialmente até cinco consultas/cálculos permitidos e interrompe na primeira falha de verificação.
- `sermax_core.py`: integra esses módulos, mantém memória pessoal em `memoria_sermax.json) e chama o Ollama. A memória pessoal não deve ser usada como banco de aprendizado de programação.
- A CI atual verifica fontes, interface, sintaxe, testes unitários e build do executável. Isso não prova funcionamento completo no Windows do mantenedor.

Conclusão: há componentes úteis de planejamento e execução restrita, mas ainda não existe um ciclo autônomo de engenharia de software. O planejador atual explicitamente não executa alterações.

## Arquitetura proposta

### 1. Observador do projeto

Responsabilidades:
- mapear arquivos, módulos, dependências, testes e configurações;
- consultar estado do Git, branch, commits e diferenças;
- identificar falhas de CI, testes quebrados, dependências ausentes e documentação desatualizada;
- registrar evidências com caminho, linha, hash e origem.

Restrições:
- leitura por padrão;
- não alterar arquivos durante a fase de inspeção;
- não ler `memoria_sermax.json`, credenciais ou dados pessoais como material de treinamento.

### 2. Diagnóstico e definição de objetivos

Cada problema identificado vira um registro estruturado:
- identificador;
- sintoma observado;
- evidência reproduzível;
- impacto e prioridade;
- hipótese de causa;
- objetivo técnico mensurável;
- critério de aceitação;
- risco e permissões necessárias.

O agente deve separar fatos, hipóteses e sugestões. Não pode declarar uma causa como confirmada sem teste.

### 3. Planejador de engenharia

O planejador divide o objetivo em tarefas pequenas, ordenadas e verificáveis. Cada tarefa informa:
- arquivos que pretende ler ou alterar;
- justificativa;
- mudança esperada;
- testes necessários;
- risco;
- plano de reversão.

Antes de editar, verifica se os arquivos mudaram desde a inspeção. Se houver divergência, interrompe e reavalia.

### 4. Ambiente isolado de desenvolvimento

O agente trabalha em uma cópia de trabalho ou worktree vinculada à branch autorizada. Nunca programa diretamente sobre a instalação ativa `C:\SERMAX`.

Requisitos:
- preservar o backup original;
- não alterar a candidata de referência;
- registrar diff antes e depois;
- limitar caminhos graváveis ao workspace;
- bloquear caminhos fora do repositório;
- manter dependências e artefatos identificados;
- permitir descarte integral da tentativa sem afetar a instalação.

### 5. Executor de engenharia com permissões

Separar ferramentas por nível:

- **Leitura automática:** listar e ler fontes, pesquisar símbolos, consultar Git e resultados de CI.
- **Escrita isolada automática:** editar arquivos no workspace autorizado, criar testes e documentação, desde que o diff passe pelas políticas.
- **Execução automática restrita:** formatadores, análise estática, compilação e testes previamente permitidos, sem acesso irrestrito à rede ou ao sistema.
- **Aprovação humana:** instalar dependências não aprovadas, acessar dados sensíveis, alterar instalação ativa, modificar memória pessoal, publicar releases, mesclar PR, apagar dados, executar comandos privilegiados ou realizar ações externas irreversíveis.

Não implementar um executor genérico de shell como atalho para autonomia. Cada ferramenta deve ter contrato, parâmetros validados, diretórios permitidos, timeout e limites de recursos.

### 6. Verificador independente

O agente não deve aprovar o próprio trabalho por autodeclaração. Um verificador separado confere:
- testes unitários e de integração;
- análise estática e sintaxe;
- build;
- integridade dos arquivos protegidos;
- ausência de alterações fora do escopo;
- diff e critérios de aceitação;
- resultados de CI associados ao commit exato.

Falha, resultado inconclusivo ou ausência de evidência bloqueia a conclusão. O sistema deve informar o teste que falhou e preservar logs.

### 7. Aprendizado técnico separado

Manter um repositório técnico próprio, separado da memória pessoal e do histórico de conversa. Registrar:
- problemas encontrados;
- soluções testadas;
- soluções rejeitadas e motivo;
- resultados dos testes;
- dependências e versões;
- decisões arquiteturais;
- regressões conhecidas.

O agente pode atualizar esse registro após verificação. Não deve treinar ou alterar pesos de rede neural automaticamente nesta primeira etapa.

### 8. Ciclo autônomo

1. Observar o estado do projeto.
2. Detectar uma oportunidade ou falha.
3. Reunir evidências.
4. Definir objetivo e critérios de aceitação.
5. Planejar uma alteração pequena.
6. Verificar permissões e escopo.
7. Implementar em ambiente isolado.
8. Executar testes permitidos.
9. Analisar falhas e corrigir, com limite de tentativas.
10. Executar toda a suíte relevante novamente.
11. Solicitar revisão humana para operações protegidas.
12. Registrar resultado e preparar relatório.

O ciclo deve ter limites de tempo, tentativas, CPU, RAM, tamanho de diff e quantidade de arquivos alterados. Ao atingir um limite, parar e reportar.

## Fases de implementação

### Fase A: inventário e proteção
- inventário verificável do repositório e da candidata de referência;
- manifesto de arquivos protegidos e hashes;
- identificação de testes e comandos seguros;
- testes para impedir escrita fora do workspace.

### Fase B: supervisor de autonomia
- fila de eventos técnicos;
- classificação de eventos;
- criação de objetivos mensuráveis;
- máquina de estados: observado, diagnosticado, planejado, aguardando aprovação, executando, verificando, concluído ou bloqueado;
- trilha de auditoria.

### Fase C: programador isolado
- leitura e busca de código;
- edição controlada no workspace;
- criação e execução de testes;
- limite de tentativas;
- rollback do workspace;
- diff obrigatório.

### Fase D: verificação independente
- avaliador separado;
- execução de CI;
- comparação com baseline;
- bloqueio automático diante de regressões;
- relatório com evidências.

### Fase E: iniciativa contínua controlada
- monitoramento de CI e mudanças no repositório;
- detecção de pendências;
- priorização técnica;
- propostas e execução de tarefas seguras;
- relatório periódico de progresso.

## Critérios de aceite para considerar o Nível 2 funcional

- Detecta uma falha real a partir de um evento observável.
- Produz diagnóstico com evidências e distingue hipótese de fato.
- Cria plano com critérios de aceitação.
- Implementa correção somente no workspace autorizado.
- Cria ou ajusta testes relacionados.
- Executa testes e reage a falhas sem esconder resultados.
- Bloqueia alterações fora do escopo e ações que exigem aprovação.
- Preserva memória pessoal, terminal original e arquivos protegidos.
- Registra diff, hashes, logs e resultado reproduzível.
- Consegue parar com segurança e retomar sem perder o estado da tarefa.

## Limites operacionais

Autonomia para programar não significa autonomia irrestrita sobre o computador. O SERMAX não recebe permissão automática para apagar arquivos, alterar a instalação ativa, acessar credenciais, gastar dinheiro, publicar, mesclar ou executar comandos privilegiados. Essas operações exigem aprovação explícita.

## Estado atual e pendências

- Planejador existente: planejamento sem execução.
- Executor existente: consultas e cálculos locais restritos.
- Executor de tarefas existente: sequência limitada de consultas/cálculos.
- Supervisor autônomo: ainda não implementado.
- Ambiente isolado de edição: ainda não implementado.
- Verificador independente de alterações: ainda não implementado.
- Aprendizado técnico separado: ainda não implementado.
- CI: validações automatizadas existentes, sem equivalência a testes completos na máquina Windows do mantenedor.

Nenhuma versão é declarada concluída por este documento. Não mesclar a PR nem publicar release com base nesta especificação.
