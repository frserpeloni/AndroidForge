# SERMAX Platform, operação local da primeira versão

**Estado:** especificação operacional documental. Não implementada.
**Ordem:** ORDEM-SERMAX-PLATAFORMA-002.
**Branch:** `sermax-windows-integration-20261029`.
**Dependências:** arquitetura GUI, contrato preliminar da API, plano de migração, matriz de testes/riscos e especificação operacional da interface.
**Objetivo:** definir a operação segura do primeiro protótipo local, isolado da instalação atual do SERMAX.

## 1. Decisão de escopo da primeira versão

A primeira versão será planejada como protótipo local de usuário único, executado no computador Windows que hospeda o núcleo. A interface será acessada inicialmente pelo próprio computador.

Esta decisão reduz a superfície de risco e evita antecipar autenticação multiusuário, sincronização remota e exposição de rede antes de validar o adaptador do núcleo.

A decisão não autoriza implementação nem instalação. O host definitivo depende da medição do computador e da aprovação da arquitetura.

## 2. Componentes lógicos

A primeira versão terá cinco componentes isolados:

1. **Interface gráfica:** cliente local no navegador, com experiência responsiva.
2. **Serviço SERMAX Platform:** API local responsável por sessões, conversas experimentais, aprovações e comunicação com a interface.
3. **Adaptador do núcleo:** fronteira controlada para encaminhar solicitações ao núcleo SERMAX existente.
4. **Armazenamento experimental:** banco e arquivos próprios da plataforma, separados dos dados atuais.
5. **Supervisor de execução:** inicia, verifica e encerra os componentes da plataforma sem controlar ou substituir o Terminal original.

O núcleo e o Terminal existentes permanecem fora da pasta experimental e sem alterações nesta etapa.

## 3. Diretório e separação de dados

Diretório proposto para implementação futura:

`SERMAX-Platform/`

Estrutura conceitual:

```text
SERMAX-Platform/
  app/
    interface/
    service/
    core_adapter/
  data/
    database/
    attachments/
    exports/
  logs/
  backups/
  config/
  scripts/
  tests/
  docs/
```

Regras:
- Nenhum arquivo original será movido para essa estrutura.
- Nenhum JSON de memória existente será aberto para escrita pela plataforma.
- O armazenamento experimental terá identificador e versão próprios.
- Caminhos serão resolvidos a partir da configuração da plataforma, sem depender do diretório corrente do terminal.
- Arquivos enviados serão armazenados fora da pasta pública da interface.
- Logs não registrarão senhas, tokens, conteúdo integral de conversas ou conteúdo de arquivos.
- Segredos locais, se necessários, ficarão fora do Git e com ACL restrita ao usuário proprietário.

## 4. Inicialização

Sequência proposta:

1. O usuário inicia o atalho da Plataforma SERMAX.
2. O supervisor verifica se já existe uma instância ativa.
3. Verifica a versão e a integridade dos arquivos da plataforma.
4. Verifica se a porta local configurada está livre.
5. Inicializa o armazenamento experimental e aplica migrações pendentes.
6. Inicia o serviço local vinculado ao endereço de loopback.
7. Aguarda o health check real do serviço.
8. Abre a interface no navegador padrão.
9. Exibe o estado do núcleo e dos motores locais somente após verificações próprias.

Se qualquer etapa falhar, o supervisor interrompe a inicialização da plataforma, registra o código de erro e preserva os dados. Não deve tentar corrigir arquivos do núcleo automaticamente.

A inicialização não deve abrir portas na rede local ou na internet. Acesso remoto fica fora da primeira versão.

## 5. Health checks

Separar os estados:

| Verificação | O que comprova | O que não comprova |
|---|---|---|
| Interface | Cliente carregado | Serviço disponível |
| Serviço | API local responde | Núcleo responde |
| Armazenamento | Banco experimental acessível | Backup restaurável |
| Adaptador | Adaptador inicializado | Resposta real do modelo |
| Ollama | Endpoint local responde | Modelo carregado ou inferência concluída |
| Núcleo | Chamada de diagnóstico concluída | Todos os motores e ferramentas funcionam |

O indicador geral não deve apresentar estado saudável se uma dependência obrigatória estiver indisponível. Componentes opcionais devem aparecer com estado próprio.

## 6. Comunicação local e portas

- Serviço vinculado inicialmente a `127.0.0.1`.
- Não usar `0.0.0.0` na primeira versão.
- Não criar regra no firewall do Windows.
- Não configurar redirecionamento no roteador.
- Não expor endpoint administrativo na interface pública.
- Restringir CORS à origem local efetivamente usada.
- Validar origem e proteção contra requisições forjadas.
- Porta ocupada deve produzir erro explícito. Não escolher portas aleatórias sem registrar e comunicar o endereço efetivo.

Acesso por outro dispositivo, VPN, túnel e hospedagem externa dependem de etapa posterior e autorização específica.

## 7. Sessão de usuário único

Na primeira versão:
- A plataforma será restrita ao usuário local que iniciar o serviço.
- Não haverá cadastro público.
- Não haverá criação de contas adicionais.
- A sessão local terá expiração e mecanismo de encerramento.
- A interface não confiará em um identificador enviado pelo cliente para definir permissões.
- Ações críticas continuarão exigindo confirmação explícita.

A definição de autenticação local precisa considerar proteção contra outros usuários da mesma máquina. A implementação deve avaliar ACL do Windows, armazenamento de segredo e proteção CSRF conforme o mecanismo de sessão escolhido.

## 8. Execução do núcleo e concorrência

A auditoria do núcleo identificou estado global de sessão e histórico. Até que testes comprovem isolamento, o adaptador deve serializar chamadas ao núcleo.

Regras:
- Uma execução do núcleo por vez na primeira versão.
- Solicitações adicionais aguardam em fila.
- Cada solicitação recebe identificador único.
- Repetição do mesmo identificador não inicia uma segunda execução.
- Cancelamento não apaga mensagens nem altera memória original.
- Falha do motor encerra a execução com estado explícito.
- A fila não deve crescer sem limite. Capacidade e política de rejeição devem ser definidas antes do teste de carga.
- Nenhuma execução arbitrária de comandos do sistema operacional será oferecida pela interface.

A seleção de motor preserva o roteamento existente. A seleção dinâmica entre modelos e ferramentas só será ampliada após contratos, limites e testes específicos.

## 9. Persistência experimental

O banco da plataforma armazenará inicialmente:
- Conversas experimentais.
- Mensagens da plataforma.
- Estado de execução.
- Preferências de interface.
- Metadados de projetos experimentais, se habilitados.

Não armazenará nem migrará nesta etapa:
- Memória pessoal atual.
- Histórico original do Terminal.
- Memória neural do Pestinha.
- Credenciais ou tokens de provedores.
- Cópias integrais de diretórios da instalação atual.

A tecnologia de banco permanece pendente de confirmação após a decisão sobre processos, bloqueios, backup e recuperação. SQLite é candidato para o protótipo de usuário único, mas sua adoção exige teste de concorrência entre serviço, supervisor e operações de backup.

## 10. Encerramento

Encerramento normal:
1. Impedir novos envios.
2. Informar que há execução em andamento.
3. Aguardar conclusão ou solicitar cancelamento controlado.
4. Persistir estado experimental.
5. Fechar conexões do banco.
6. Encerrar serviço e supervisor.
7. Confirmar que as portas locais foram liberadas.

Se o usuário forçar o encerramento, a próxima inicialização deverá validar integridade do banco e recuperar transações conforme o mecanismo de persistência. Não reparar nem reescrever arquivos originais do SERMAX.

## 11. Falhas e recuperação

| Falha | Resposta esperada |
|---|---|
| Porta ocupada | Interromper inicialização e informar conflito |
| Banco indisponível | Não iniciar API; preservar arquivos |
| Migração falha | Reverter transação e manter versão anterior |
| Núcleo indisponível | Interface informa indisponibilidade; mensagens permanecem preservadas |
| Ollama indisponível | Informar motor indisponível e aplicar fallback existente somente se confirmado pelo núcleo |
| Serviço encerra inesperadamente | Supervisor registra falha; não reinicia em ciclo infinito |
| Disco sem espaço | Bloquear gravação insegura e informar risco |
| Banco corrompido | Parar escrita, preservar cópia e exigir procedimento de recuperação |
| Atualização incompleta | Manter versão anterior e impedir troca automática |

Não haverá reparo destrutivo automático.

## 12. Backup e restauração

O armazenamento experimental terá política própria:
- Backup antes de cada migração.
- Cópia consistente do banco, sem copiar arquivo ativo de forma insegura.
- Manifesto com versão, data, tamanho e SHA-256.
- Destino separado do banco em uso.
- Retenção configurável e documentada.
- Teste de restauração em diretório temporário.
- Verificação de contagens e hashes após restauração.

Backups originais do SERMAX não serão sobrescritos, movidos ou limpos pela plataforma.

## 13. Atualização e rollback

A primeira versão será distribuída como pacote experimental separado. Não instalar sobre `C:\\SERMAX`.

Fluxo futuro:
1. Verificar assinatura ou hash do pacote.
2. Verificar compatibilidade com versão do serviço e esquema do banco.
3. Criar backup experimental.
4. Instalar em diretório versionado.
5. Executar health checks e testes de inicialização.
6. Ativar a nova versão somente após validação.
7. Em falha, voltar à versão anterior sem apagar dados.

Atualização automática e substituição da inicialização original ficam fora do primeiro protótipo.

## 14. Recursos e limites do computador

A auditoria não mediu CPU, memória disponível, espaço livre, velocidade do disco ou desempenho real do Ollama no computador de destino. Não dimensionar servidor nem prometer latência antes dessas medições.

A primeira validação deverá registrar:
- Modelo de CPU e número de núcleos.
- RAM instalada e disponível.
- Tipo de disco e espaço livre.
- Versão do Windows.
- Versão e estado do Python exigido pelo núcleo.
- Estado do Ollama e modelos instalados.
- Tempo de inicialização e consumo durante uma conversa de teste.

A plataforma deve evitar serviços residentes desnecessários e manter o supervisor parado quando o usuário encerrar a aplicação.

## 15. Critérios de aceite operacional

| ID | Teste | Critério |
|---|---|---|
| OPS-01 | Inicialização normal | Serviço e interface iniciam sem tocar na instalação original |
| OPS-02 | Segunda inicialização | Instância duplicada é impedida |
| OPS-03 | Porta ocupada | Falha controlada, sem abrir porta alternativa silenciosa |
| OPS-04 | Bind de rede | Serviço escuta somente em loopback |
| OPS-05 | Banco experimental | Dados persistem após encerramento normal |
| OPS-06 | Falha de migração | Banco anterior permanece íntegro |
| OPS-07 | Núcleo indisponível | Interface preserva mensagem e informa erro |
| OPS-08 | Duas mensagens simultâneas | Fila serializa chamadas e não mistura contexto |
| OPS-09 | Reenvio idempotente | Uma solicitação não gera duas execuções |
| OPS-10 | Encerramento | Serviço libera recursos e portas |
| OPS-11 | Encerramento forçado | Próxima abertura verifica integridade antes de escrever |
| OPS-12 | Backup | Restauração experimental é comprovada por teste |
| OPS-13 | Integridade original | Hashes do núcleo, Terminal e memórias permanecem iguais |
| OPS-14 | Rede externa | Nenhuma porta pública ou regra de firewall é criada |
| OPS-15 | Falta de espaço | Escritas inseguras são bloqueadas com erro claro |

Todos os testes permanecem **não executados** até existir implementação e ambiente de validação.

## 16. Decisões pendentes

Antes da implementação:
1. Medir o computador host.
2. Confirmar o mecanismo de sessão local e ACL.
3. Selecionar o banco experimental.
4. Definir política de fila e limite de solicitações.
5. Definir estratégia de logs e retenção.
6. Definir pacote experimental e comando de inicialização.
7. Confirmar se a primeira versão terá projetos ou somente conversas.
8. Receber e reconciliar a candidata oficial e o backup de 28/10, se ainda disponíveis.

## 17. Limites e estado

Este documento é especificação. Não cria diretórios, código, banco, serviço, instalador ou regras de rede. Não altera núcleo, Terminal, memórias, histórico, backups, instalação local, workflows ou branch `main`.

A primeira implementação permanece condicionada à autorização expressa para criar `SERMAX-Platform/` e executar o protótipo isolado. Drive Connect continua fora do escopo até autorização própria.
