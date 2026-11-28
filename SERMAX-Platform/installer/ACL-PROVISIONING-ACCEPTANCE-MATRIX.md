# Matriz de provisionamento e aceitação de ACLs do SERMAX Installer Broker

Data: 2026-11-16  
Branch de referência: `sermax-platform-prototype-20261115`  
Status: especificação documental. Não implementada. Não autoriza serviço, broker, ACL, privilégio, IPC ou instalação.

## 1. Objetivo e limite

Definir como avaliar a proteção do namespace usado por um futuro instalador machine-wide do SERMAX no Windows. O objetivo é impedir que usuários padrão alterem diretórios, arquivos, staging, journal, backups, configuração do serviço ou binário do broker.

Esta matriz não é uma SDDL pronta. Os caminhos abaixo são uma proposta de organização para avaliação. O destino definitivo, as versões de Windows suportadas, os sistemas de arquivos e os SID reais ainda precisam ser definidos antes de aprovar ACLs.

A instalação existente em `C:\SERMAX`, suas memórias, configurações e backups ficam fora deste escopo. Esta especificação não autoriza migrar, modificar ou provisionar esses dados.

## 2. Modelo de implantação considerado

Modelo machine-wide, com diretórios de programa sob Program Files e estado privado do instalador sob ProgramData.

| Finalidade | Caminho lógico proposto | Observação |
|---|---|---|
| Aplicação | `%ProgramFiles%\SERMAX` | Raiz de programa protegida |
| Binário do serviço | `%ProgramFiles%\SERMAX\Broker\SermaxInstallerBroker.exe` | Separado do payload atualizável |
| Configuração do serviço | Registro do Service Control Manager e configuração protegida | Sem configuração gravável pelo usuário padrão |
| Estado privado do broker | `%ProgramData%\SERMAX\Installer` | Não guardar memória pessoal, histórico ou dados do usuário |
| Entrada/staging | `%ProgramData%\SERMAX\Installer\Staging` | Snapshot sob propriedade do broker |
| Journal | `%ProgramData%\SERMAX\Installer\Journal` | Estado de transação e recuperação |
| Backups | `%ProgramData%\SERMAX\Installer\Backups` | Backups de arquivos de programa, sem dados pessoais |
| Pipe local | `\\.\pipe\SERMAX.InstallerBroker.v1` | IPC local, sem acesso remoto |

Os nomes são identificadores de projeto, não caminhos aprovados para produção. A implantação deve resolver variáveis de ambiente e volume, canonicalizar a raiz por handles e registrar os caminhos efetivos.

## 3. Princípios de segurança

1. Proprietário administrativo confiável para diretórios e arquivos protegidos. O serviço não deve ser proprietário dos objetos que precisa proteger contra alteração de DACL.
2. Herança desabilitada nas raízes privadas quando a herança do ancestral não entregar exatamente o conjunto de direitos aprovado. ACEs explícitas e auditáveis.
3. Usuários padrão não recebem `WRITE_DAC`, `WRITE_OWNER`, `DELETE`, `FILE_DELETE_CHILD`, `FILE_ADD_FILE` ou `FILE_ADD_SUBDIRECTORY` nos objetos protegidos ou nos ancestrais que controlam o namespace.
4. O SID próprio do serviço recebe somente os direitos estritamente necessários. Testar `SERVICE_SID_TYPE_RESTRICTED` com o token real. Uma ACE no SID do serviço, isoladamente, não prova que o token restrito terá acesso.
5. O processo do broker não executa código, scripts, plugins ou binários graváveis por usuários padrão.
6. A GUI não envia caminhos arbitrários, comandos de shell ou destinos livres. Envia operações tipadas e dados do pacote por IPC autenticado.
7. O broker copia o pacote para staging privado, valida o snapshot e instala os mesmos bytes. Não volta a ler arquivos da origem controlada pelo cliente durante a transação.
8. O broker não recebe acesso a memórias, bancos SQLite, histórico, documentos, credenciais, modelos, ambientes Python ou backups pessoais do SERMAX.
9. Qualquer ACL inesperada, proprietário inesperado, reparse point não permitido ou identidade não reconhecida interrompe a operação em modo fechado.
10. Administrador local, SYSTEM, kernel comprometido e adulteração offline ficam fora da proteção prometida. Registrar explicitamente essas exclusões.

## 4. Matriz de diretórios e objetos

Legenda: **A** = Administradores; **S** = SYSTEM; **B** = SID exclusivo do serviço; **U** = usuário interativo; **U2** = segundo usuário padrão. Os nomes representam identidades a resolver no sistema real. Não são ACEs finais.

| Objeto | Proprietário esperado | A / S | B, serviço | U / U2 | Regra e evidência exigida |
|---|---|---|---|---|---|
| Raiz do volume, por exemplo `C:\` | Conforme política Windows do volume | Conforme política do SO | Sem concessão nova | Sem direitos de escrita sobre ancestrais usados | Inspecionar owner, DACL e ACEs herdadas. Não reescrever ACL da raiz do volume. |
| `%ProgramFiles%` | Conforme política Windows | Conforme política do SO | Sem concessão ampla | Leitura/execução conforme política | Inspecionar a cadeia. Não modificar ACL global de Program Files. |
| `%ProgramFiles%\SERMAX` | A ou identidade administrativa aprovada | Controle total | Modificar somente se o broker precisar substituir payload; direitos limitados ao escopo de instalação | Leitura/execução; sem criação, exclusão ou alteração de ACL | Raiz dedicada. Sem gravação por U/U2. Validar todos os ancestrais. |
| `%ProgramFiles%\SERMAX\Broker` | A | Controle total | Leitura/execução; sem escrita, exclusão ou alteração de ACL | Sem acesso de escrita; leitura conforme política | Binário e dependências do serviço não podem ser substituídos pelo próprio broker nem por usuário padrão. |
| Configuração do serviço no SCM | A / S conforme modelo SCM | Controle administrativo | Leitura do próprio estado operacional necessário | Sem alteração de configuração, conta, binPath, start type ou DACL | Consultar DACL do objeto de serviço e testar tentativas de reconfiguração por U/U2. |
| `%ProgramData%` | Conforme política Windows | Conforme política do SO | Sem concessão nova na raiz global | Conforme política do SO | Inspecionar somente. Não alterar ACL global de ProgramData. |
| `%ProgramData%\SERMAX` | A | Controle total | Travessia/leitura somente se indispensável | Sem escrita em subárvore privada | Diretório dedicado. Não misturar com dados pessoais ou pastas de usuário. |
| `%ProgramData%\SERMAX\Installer` | A | Controle total | Modificar somente subpastas de transação necessárias | Sem listar, ler ou escrever, salvo requisito de suporte aprovado | Herança controlada; validar acesso efetivo. |
| `...\Staging` | A | Controle total | Criar, ler, renomear e excluir objetos de staging; sem WRITE_DAC/WRITE_OWNER | Sem acesso | Snapshot criado pelo broker. Cliente não escolhe nome final nem reabre staging. |
| `...\Journal` | A | Controle total | Criar, ler e atualizar journal; sem WRITE_DAC/WRITE_OWNER | Sem acesso | Journal autenticado/integridade protegida; retenção e recuperação têm testes próprios. |
| `...\Backups` | A | Controle total | Criar e ler backups; excluir somente segundo política de retenção aprovada | Sem acesso | Não incluir memória, histórico, credenciais ou dados pessoais. Testar restauração. |
| Marcador de instalação | A | Controle total | Atualizar somente por operação autorizada | Leitura, se necessário | Não tratar marcador como prova de integridade do conjunto instalado. |
| Logs do broker | A | Leitura e administração | Acrescentar logs em diretório privado | Sem leitura por padrão, salvo decisão explícita de suporte | Não registrar segredos, tokens, conteúdo pessoal ou payload integral. |
| Pipe `SERMAX.InstallerBroker.v1` | Objeto efêmero do broker | Controle do serviço | Acesso do próprio processo | Conexão somente para usuário local autorizado; direitos mínimos para protocolo duplex | DACL criada no runtime, identidade do cliente verificada por impersonation; rejeitar clientes remotos. |
| Arquivo temporário de intake | A | Controle total | Criar, validar e remover | Sem acesso após envio | Não confiar em caminho fornecido pelo cliente. Copiar bytes pelo canal autenticado. |

### 4.1 Direitos que exigem revisão individual

Para cada diretório e arquivo, registrar os direitos abaixo em separado. Não resumir tudo como “Modify” ou “Full Control”.

- Leitura: `FILE_READ_DATA`, `FILE_READ_ATTRIBUTES`, `FILE_READ_EA`.
- Escrita: `FILE_WRITE_DATA`, `FILE_APPEND_DATA`, `FILE_WRITE_ATTRIBUTES`, `FILE_WRITE_EA`.
- Criação de filhos: `FILE_ADD_FILE`, `FILE_ADD_SUBDIRECTORY`.
- Remoção e rename: `DELETE`, `FILE_DELETE_CHILD`.
- Segurança: `READ_CONTROL`, `WRITE_DAC`, `WRITE_OWNER`.
- Execução/travessia: `FILE_EXECUTE`, `FILE_TRAVERSE`.
- Herança: flags de herança e propagação, com ACEs herdadas identificadas.

A concessão de `DELETE` em um filho e `FILE_DELETE_CHILD` no pai tem efeitos diferentes. Testar ambos no objeto e no diretório pai.

## 5. Serviço e identidade

Identidade candidata: `NT SERVICE\SermaxInstallerBroker`, com SID exclusivo do serviço. Alvo de teste: `SERVICE_SID_TYPE_RESTRICTED`.

Requisitos:

- Conta virtual exclusiva, sem senha administrada pela aplicação.
- Processo separado da GUI e sem carregar extensões controladas pelo usuário.
- Sem privilégios opcionais por padrão.
- Negar rede de saída enquanto não houver requisito aprovado.
- Não usar LocalSystem como padrão.
- LocalService somente como alternativa documentada, com SID exclusivo e isolamento comprovado.
- NetworkService não é necessário no escopo local atual.
- Capturar token real: usuário, grupos habilitados/restritos, privilégios, SID de logon, integridade e tipo de token.
- Verificar DACL do objeto de serviço, configuração, binário, diretórios e dependências.
- Confirmar que reinício do serviço e do Windows não amplia direitos nem reutiliza estado de autorização.

## 6. IPC e autorização do cliente

Pipe proposto: `\\.\pipe\SERMAX.InstallerBroker.v1`.

Controles mínimos:

1. Criar pipe local com rejeição explícita de clientes remotos.
2. DACL concedida ao usuário local autorizado, sem abrir a todos os usuários autenticados por conveniência.
3. Verificar o token do cliente e obter o SID real por impersonation.
4. Autorizar cada operação por identidade e tipo de ação. Conexão ao pipe não equivale a autorização para instalar.
5. Protocolo com versão, tamanho máximo, timeout, nonce/identificador de requisição e resposta correlacionada.
6. Allowlist fechada de operações. Nenhuma operação genérica de executar comando, copiar para caminho livre, apagar diretório ou editar ACL.
7. Limitar frequência e tamanho de payload. Rejeitar mensagens truncadas, duplicadas, fora de ordem e malformadas.
8. Não confiar em nome de processo, PID isolado, nome de usuário textual ou caminho da GUI como prova de identidade.
9. Registrar SID autenticado, operação, resultado e identificador de transação, sem registrar conteúdo sensível.
10. Testar conexão por U, U2, administrador, serviço e cliente remoto. O remoto deve falhar.

A DACL exata do pipe depende do modelo de usuário autorizado e dos direitos exigidos pelo protocolo duplex. Não publicar SDDL até que esses requisitos e o mecanismo de impersonation estejam definidos.

## 7. Processo de provisionamento administrativo proposto

O provisionamento deve ocorrer em etapa elevada, separada do processo normal da GUI:

1. Resolver e registrar volume, sistema de arquivos, build do Windows e caminhos canônicos.
2. Inspecionar todos os ancestrais desde a raiz do volume. Confirmar que U/U2 não conseguem substituir ou renomear componentes da cadeia.
3. Criar somente as raízes dedicadas SERMAX. Não alterar ACL global de `C:\`, Program Files ou ProgramData.
4. Definir proprietário administrativo, desabilitar herança onde necessário e aplicar ACEs explícitas revisadas.
5. Criar diretórios de programa e estado privado com ACLs distintas.
6. Instalar binário e dependências do broker a partir de pacote autenticado e sob diretório administrativo protegido.
7. Registrar serviço com identidade virtual dedicada, SID de serviço e configuração mínima.
8. Definir DACL do objeto de serviço e política do pipe.
9. Ler novamente owner, DACL, ACEs herdadas e acesso efetivo após o provisionamento.
10. Executar testes positivos e negativos com tokens reais U, U2, B, A e S.
11. Gravar relatório de provisionamento com Windows build, filesystem, volume, SIDs, SDDL efetiva, hashes dos binários e resultados.
12. Se qualquer verificação divergir do esperado, interromper e reverter somente os objetos recém-provisionados, sem tocar em instalações ou dados preexistentes.

## 8. Matriz de testes de aceitação

| ID | Identidade | Operação | Resultado esperado |
|---|---|---|---|
| ACL-001 | U | Criar arquivo em cada ancestral protegido | Negado |
| ACL-002 | U | Criar subdiretório em cada ancestral protegido | Negado |
| ACL-003 | U | Renomear ou excluir raiz, staging, journal, backup ou binário | Negado |
| ACL-004 | U | Inserir symlink, junction ou outro reparse point | Negado |
| ACL-005 | U | Alterar DACL ou proprietário | Negado |
| ACL-006 | U | Abrir staging, journal e backups | Negado |
| ACL-007 | U | Alterar configuração ou binário do serviço | Negado |
| ACL-008 | U2 | Repetir ACL-001 a ACL-007 | Negado |
| ACL-009 | B | Ler/escrever apenas nos diretórios explicitamente concedidos | Permitido no escopo; negado fora dele |
| ACL-010 | B | Alterar DACL, proprietário ou binário do próprio serviço | Negado |
| ACL-011 | B | Acessar memória, SQLite, histórico, credenciais e backups pessoais | Negado |
| ACL-012 | U | Enviar operação não prevista ou caminho arbitrário pelo pipe | Rejeitado |
| ACL-013 | U | Conectar ao pipe com identidade não autorizada | Negado |
| ACL-014 | Cliente remoto | Conectar ao pipe | Negado |
| ACL-015 | U | Substituir pacote de origem durante intake | Bytes instalados devem corresponder ao snapshot privado validado |
| ACL-016 | U | Correr para substituir staging, journal, backup ou marcador | Sem alteração do objeto privado; transação interrompida se a integridade divergir |
| ACL-017 | U | Alterar diretório ancestral enquanto o broker opera | Sem troca de namespace; falha fechada se a proteção não se mantiver |
| ACL-018 | B | Reiniciar serviço e retomar transação incompleta | Recuperação conforme journal, sem ampliar privilégios |
| ACL-019 | A | Executar provisionamento aprovado | Permitido e auditado |
| ACL-020 | S | Operações do sistema necessárias | Conforme política documentada, sem acesso adicional por conveniência |

Executar testes com dois usuários padrão distintos, em todas as versões de Windows e sistemas de arquivos suportados. Registrar cada tentativa, chamada, identidade efetiva e resultado. Um teste manual isolado não substitui automação repetível.

## 9. Critérios de bloqueio

A distribuição fica bloqueada se ocorrer qualquer condição:

- Usuário padrão consegue gravar, renomear, excluir ou alterar ACL em qualquer ancestral relevante.
- Owner, DACL, ACE herdada ou acesso efetivo diverge da especificação aprovada.
- SID restrito do serviço não consegue executar operações necessárias ou recebe acesso excessivo.
- Serviço executa código de diretório gravável por usuário padrão.
- Pipe aceita cliente remoto ou não autentica o SID real do chamador.
- GUI consegue pedir caminho, comando ou operação arbitrária.
- Pacote é validado em uma origem e instalado a partir de outra leitura não vinculada ao snapshot privado.
- Journal, backup ou staging não estão protegidos contra substituição.
- Relatório não registra build do Windows, filesystem, volume, SID, owner, SDDL e resultado.
- Recuperação após crash, rollback, integridade de pacote ou health gate não passou nos testes próprios.

## 10. Evidências que devem acompanhar a aprovação

- Matriz de caminhos efetivos e cadeia completa de ancestrais.
- SDDL final de cada objeto, com ACEs herdadas e explícitas separadas.
- Owner e acesso efetivo para U, U2, B, A e S.
- Captura do token real do serviço, incluindo SIDs restritos e privilégios.
- DACL e configuração do objeto SCM.
- DACL do pipe e resultados de impersonation/autorização.
- Hashes e origem dos binários instalados.
- Logs dos testes positivos, negativos, adversariais e de recuperação.
- Build do Windows, filesystem, volume e versão do pacote testado.
- Aprovação explícita da arquitetura e do escopo de implantação.

## 11. Decisão atual

A raiz protegida machine-wide com broker de identidade exclusiva continua sendo a direção principal de avaliação. Esta matriz transforma essa direção em critérios verificáveis, mas não fecha os gates.

Nenhuma SDDL final foi aprovada. Nenhum caminho foi provisionado. Nenhum serviço, broker, pipe, ACL, privilégio, teste ou instalador foi implementado nesta etapa. O protótipo atual permanece sem autorização de distribuição para instalação de produção.
