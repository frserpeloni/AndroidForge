# Auditoria técnica do instalador e inicialização SERMAX
Data: 2026-11-15
Branch: sermax-platform-prototype-20261115
Base revisada: 81d6746e8714a8168d6eea3d9a696d4694a9137e

## Resultado executivo

O CI do commit-base concluiu com sucesso nos cinco jobs: frontend-check, frontend-interaction, backend-tests Python 3.12, backend-tests Python 3.14 e windows-validation.

O instalador segue como protótipo de desenvolvimento. Esta auditoria identifica bloqueios que impedem classificar o motor como seguro para distribuição ou montar um pacote oficial.

## Achados do motor de instalação

### P0. Reparse points do Windows e junctions não estão cobertos
O motor verifica `Path.is_symlink()` nos componentes de origem e destino. Essa checagem não demonstra proteção contra todas as classes de reparse points do Windows, incluindo junctions. O uso de `resolve()` pode atravessar esses pontos antes de validar a localização efetiva. A documentação atual já limita a garantia a links simbólicos, mas a proteção precisa ser ampliada antes da distribuição.

Ação necessária:
- Identificar junctions e reparse points em todos os componentes do caminho no Windows.
- Rejeitar destinos que atravessem esses pontos.
- Testar junctions reais em runner Windows com permissões adequadas.
- Verificar também a raiz da instalação, pasta de backup, marcador e diretórios pais.

### P0. Janela TOCTOU entre validação e operações de arquivo
A validação de caminhos ocorre antes de operações posteriores de criação, cópia e substituição. Um processo concorrente pode trocar um diretório por link ou reparse point entre a checagem e a operação. As verificações atuais não são resistentes a esse tipo de corrida.

Ação necessária:
- Reduzir operações baseadas em caminhos re-resolvidos.
- Revalidar componentes imediatamente antes de cada operação sensível.
- Quando suportado, usar operações relativas a handles e flags que impeçam seguir links/reparse points.
- Documentar a garantia residual quando não houver primitiva segura equivalente no Windows.

### P1. Marcador de instalação precisa de tratamento explícito de links e reparse points
`.sermax-install.json` é lido antes da instalação para preservar o conteúdo anterior. O código verifica `is_file()`, que segue links. Um marcador redirecionado pode fazer o instalador ler um arquivo fora da pasta esperada. O replace posterior substitui a entrada do caminho, mas não elimina o risco da leitura inicial e de corridas.

Ação necessária:
- Rejeitar marcador existente que seja link, junction ou reparse point.
- Validar o tipo do marcador e o diretório raiz antes da leitura.
- Adicionar testes para marcador redirecionado e marcador substituído durante a operação.

### P1. Pasta de backup e raiz da instalação exigem validação reforçada
O código rejeita `.sermax-backups` quando `is_symlink()` retorna verdadeiro e verifica symlinks nos diretórios de destino. Não cobre todas as classes de reparse points e não elimina TOCTOU. A raiz da instalação também é resolvida antes da operação, o que exige validar a cadeia original e a cadeia resolvida.

Ação necessária:
- Validar raiz, pais, backup root, diretórios de destino e temporários.
- Confirmar que os backups são gravados dentro da raiz autorizada.
- Cobrir colisões e substituições de diretórios durante a execução.

### P1. Pré-validação e instalação são duas passagens separadas
A GUI executa `preflight()`, solicita confirmação e depois chama `install_package()`, que carrega e valida o pacote novamente. O destino e o pacote podem mudar entre as duas passagens. A segunda validação ajuda a integridade do pacote, mas não vincula a confirmação do usuário a um snapshot imutável do pacote/destino.

Ação necessária:
- Criar um plano de instalação validado e imutável, com identidade do pacote, hashes, versão, destino e estado detectado.
- Revalidar esse plano no início da execução e abortar se houver divergência.
- Não tratar a confirmação da GUI como autorização para conteúdo que mudou após a confirmação.

### P2. Semântica de preservação precisa ser fechada
`preserve_paths` é declarativo. O motor impede que os destinos do manifesto sobrescrevam caminhos protegidos, mas não faz backup completo de bancos, memórias, configurações ou dados. O backup atual cobre somente arquivos de programa listados que já existam no destino. A documentação informa essa limitação corretamente.

Ação necessária:
- Definir política de backup completo separada da lista de arquivos do pacote.
- Exigir autorização e validação específica antes de qualquer migração de dados.
- Manter memórias, banco, credenciais e backups fora do manifesto de programa.

## Cobertura de testes observada

Os testes existentes cobrem:
- Integridade SHA-256 e tamanho.
- Path traversal.
- Nomes reservados do Windows.
- Conflitos de destino case-insensitive e parent-child.
- Preservação de alguns caminhos de dados.
- Backup de arquivo substituído.
- Rollback após falha em substituição e após falha posterior ao marcador.
- Falha no rollback com preservação do backup e nota de recuperação.
- Symlink aninhado no construtor, com skip quando o ambiente não permite criar symlink.

Lacunas:
- Junctions e reparse points no Windows.
- Corridas TOCTOU.
- Marcador de instalação como symlink/junction.
- Raiz de instalação e diretório de backup redirecionados.
- Falhas durante criação e escrita do backup.
- Colisões de nomes em volume Windows real.
- Interrupção abrupta do processo e recuperação no próximo início.
- Testes de snapshot entre confirmação e execução.

## Inventário de inicialização

### Inicializador atual do SERMAX Windows
`SERMAX-Windows/sermax_launcher.py` inicia o Terminal original com `runpy.run_path()`. Define `SERMAX_ROOT`, ajusta `sys.path` e muda o diretório de trabalho. Não inicia a Plataforma.

### Spec atual do executável
`SERMAX-Windows/SERMAX.spec` empacota o launcher do Terminal, configura `console=True` e inclui arquivos de Terminal, worker Jarvis e dados/dependências Pestinha. Portanto, esse spec não atende ao requisito da nova Plataforma como interface principal.

### Inicializador da Plataforma
`SERMAX-Platform/backend/run_local.bat` cria ambiente virtual, instala dependências via pip e executa `server.py`. O README orienta abrir o navegador manualmente em `http://127.0.0.1:8765`.

Não existe ainda supervisor integrado que:
- Inicie o backend e aguarde health check.
- Abra a interface automaticamente.
- Monitore queda do serviço e encerre processos filhos corretamente.
- Inicie o Terminal original em janela independente por comando administrativo autenticado.
- Mantenha logs de inicialização e recuperação.

### Decisão técnica recomendada
Implementar um novo launcher dentro de `SERMAX-Platform/`, sem alterar `SERMAX-Windows/sermax_launcher.py` nem `SERMAX-Windows/SERMAX.spec` nesta etapa. O novo launcher deve ser projetado para o executável SERMAX abrir a Plataforma, manter o serviço local em loopback, verificar health check e permitir encerramento limpo. O acesso ao Terminal deve ser tratado em etapa própria, com autenticação no backend, sem expor comando administrativo no JavaScript.

## Composição do pacote

O construtor inclui somente os arquivos informados explicitamente por `--map`. Isso é uma proteção contra inclusão acidental de dados, mas exige uma lista oficial revisada. Ainda não há pacote completo com Plataforma, launcher, núcleo, Terminal e dependências. Não gerar pacote oficial até concluir a matriz de arquivos, licenças, dependências e testes de instalação/atualização.

## Limites e preservação

Esta auditoria não alterou núcleo, Terminal, memórias, bancos, backups, branch principal ou PR base. Drive Connect permanece fora de implementação. A PR #5 continua sem merge.

## Próxima sequência

1. Implementar e testar proteção contra junctions/reparse points em Windows.
2. Tratar marcador, raiz e backup com validação reforçada.
3. Projetar mitigação TOCTOU e registrar limites residuais.
4. Criar testes de falha de backup, interrupção e recuperação.
5. Desenvolver launcher novo isolado para a Plataforma.
6. Fechar inventário e matriz oficial de arquivos e dependências.
7. Somente então montar pacote de teste completo e executar instalação inicial e atualização em ambiente Windows descartável.


## Aditivo de revalidação, 2026-11-15

Após a auditoria-base, a implementação recebeu os seguintes controles e testes na mesma branch isolada:

- Detecção de reparse points do Windows por atributos de arquivo, além de symlinks, em componentes existentes de origem e destino.
- Verificações aplicadas à raiz do pacote, manifesto, arquivos de origem, raiz de instalação, marcador, pasta de backup e caminhos de destino.
- Revalidação de contenção lexical e componentes reparse antes de operações críticas de backup, staging, substituição e gravação do marcador.
- Testes Windows de rejeição de junction no construtor de pacotes.
- Teste multiprocesso do lock de instalação, incluindo bloqueio concorrente e liberação após saída do processo.
- Documentação específica das garantias e limitações em `installer/SECURITY_NOTES.md`.

Os itens P0 relativos à detecção de junctions/reparse points e à revalidação antes de operações críticas foram parcialmente tratados por essas mudanças. A proteção TOCTOU permanece incompleta: as operações ainda usam caminhos convencionais do Python, sem uma cadeia de operações relativa a handles Windows. Portanto, não classificar como proteção contra processo local hostil concorrente.

A proteção do marcador, da raiz e dos diretórios de backup foi ampliada com verificações de reparse points. Ainda faltam testes específicos de troca concorrente do marcador, falha real de gravação de backup, interrupção abrupta e recuperação após reinicialização. A pré-validação continua sendo uma passagem separada da instalação e ainda não existe plano imutável vinculado à confirmação da GUI.

O CI dos commits `54f52e4`, `af4a349` e `4fb6793` concluiu com sucesso nos cinco jobs. O commit `60fa336` adicionou testes para metadados de lock preexistentes e rejeição de lock como symlink; no momento deste aditivo, o job Windows ainda estava em execução. Não antecipar o resultado desse fluxo.

A matriz oficial de arquivos, dependências e licenças continua pendente. Nenhum pacote oficial ou instalador distribuível foi gerado.
