# SERMAX Platform, plano de migração e primeira entrega executável

**Estado:** plano técnico para revisão. Não implementado.
**Branch:** `sermax-windows-integration-20261029`.
**Ordem:** ORDEM-SERMAX-PLATAFORMA-002.
**Documentos relacionados:**
- `PLATAFORMA-SERMAX-ARQUITETURA-GUI.md`
- `PLATAFORMA-SERMAX-API-CONTRATO-PRELIMINAR.md`
- `PLATAFORMA-SERMAX-HOSPEDAGEM-ACESSO-REMOTO.md`

## 1. Objetivo da migração

Adicionar uma plataforma gráfica ao redor do SERMAX existente, sem reescrever ou substituir o núcleo. A migração começa em diretório separado e só passa a ser a inicialização padrão depois de validação, pacote instalável, plano de rollback e autorização específica.

O Terminal original continuará preservado e acessível pelo comando reservado `/sermax terminal`. O terminal não será removido nem refeito como parte desta migração.

## 2. Inventário de componentes existentes e destino

| Componente existente | Papel atual conhecido | Tratamento proposto |
|---|---|---|
| `SERMAX-Windows/sermax_core.py` | Núcleo, roteamento e memória | Preservar. Criar adaptador isolando contexto e concorrência |
| `SERMAX-Windows/SERMAX_terminal/sermax_terminal.py` | Terminal original | Preservar integralmente; acesso administrativo |
| `SERMAX-Windows/memoria_sermax.json` | Memória persistente local | Não mover nem sobrescrever; planejar importação por cópia |
| `SERMAX-Windows/memoria_neural_pestinha.json` | Memória neural separada | Preservar separação; não importar como memória de conversa |
| `SERMAX-Windows/historico_comandos.json` | Histórico de comandos | Preservar; não converter sem mapeamento e backup |
| `SERMAX-Windows/sermax_jarvis_adapter.py` | Adaptador OpenJarvis | Preservar e acessar por interface controlada |
| `SERMAX-Windows/sermax_pestinha_adapter.py` | Adaptador Pestinha | Preservar e manter fronteira de dados |
| `SERMAX-Windows/SERMAX.spec` | Empacotamento PyInstaller existente | Não substituir. Avaliar empacotamento da plataforma em configuração própria |
| `sermax-android/` | App Android v0.2, UI local básica | Tratar como protótipo visual; não presumir cliente conectado |
| Diretório novo `SERMAX-Platform/` | Não existe no inventário auditado | Proposto para interface, API, adaptador, migrações e testes da plataforma |

Os caminhos são referências do inventário da branch auditada. Antes de qualquer implementação, confirmar novamente a árvore e os hashes da branch.

## 3. Estrutura nova proposta

Estrutura conceitual, ainda não criada:

```text
SERMAX-Platform/
  backend/
    api/
    auth/
    services/
    adapters/
    storage/
    migrations/
    security/
  frontend/
    app/
    components/
    styles/
  tests/
    api/
    auth/
    isolation/
    sync/
    integration/
  docs/
  config/
```

A estrutura final deve evitar duplicar arquivos do núcleo. O backend deve depender de uma interface de adaptador e não copiar funções de `sermax_core.py`.

## 4. Primeira entrega executável proposta

A primeira entrega deve ser pequena, testável e reversível. Escopo sugerido:

1. Aplicação web responsiva com a tela inicial minimalista conforme as referências de Fabiano.
2. Campo de conversa e histórico simples dentro de uma única conta local.
3. Backend local com autenticação de desenvolvimento claramente identificada, sem alegar segurança de produção.
4. Adaptador experimental para uma única sessão do núcleo existente, com execução serializada.
5. Estado de resposta: aguardando, respondendo, concluído ou erro.
6. Seleção automática do modelo por padrão; seletor manual discreto como controle secundário.
7. Testes de contrato e regressão sem tocar nos JSON originais.
8. Execução local no Windows, sem acesso externo nesta primeira fatia.

Fora do primeiro corte:
- Android nativo conectado.
- Sincronização multiusuário.
- Recuperação de conta e 2FA de produção.
- Google Drive/Drive Connect.
- Execução de código arbitrário.
- Migração definitiva de memória e histórico.
- Atualização automática sobre a instalação atual.
- Publicação pública na internet.

A primeira entrega deve provar a integração visual e conversacional, não declarar a plataforma completa.

## 5. Sequência de implementação após autorização

### Etapa A, preparação isolada
- Confirmar inventário, hashes e arquivos protegidos.
- Criar diretório novo na branch de desenvolvimento.
- Definir ambiente virtual e dependências com versões fixadas.
- Definir configuração por ambiente sem segredos no Git.
- Criar testes de estrutura e inicialização.

### Etapa B, serviço mínimo
- Criar API de saúde e metadados.
- Criar sessão local de desenvolvimento.
- Criar armazenamento separado para conversas experimentais.
- Criar adaptador do núcleo com uma única execução concorrente.
- Testar falha de Ollama e fallback existente sem alterar política do núcleo.

### Etapa C, interface mínima
- Implementar tela inicial com poucos elementos.
- Implementar conversa central e campo de mensagem.
- Manter menu lateral compacto.
- Mostrar ferramenta em uso como indicação curta.
- Não manter painel permanente de fontes, atividade ou permissões.

### Etapa D, testes
- Testar isolamento de conversa.
- Testar repetição de envio e duplicidade.
- Testar interrupção do núcleo.
- Testar encerramento e reinício.
- Testar que os JSON originais permanecem byte a byte iguais.
- Testar em resoluções desktop e celular.
- Gerar evidências dos testes e registrar limitações.

### Etapa E, pacote experimental
- Gerar pacote separado, sem instalar sobre `C:\SERMAX`.
- Incluir instrução de execução e remoção do protótipo.
- Gerar hashes e manifesto.
- Não substituir atalho ou inicialização atual.
- Não promover a plataforma a inicialização padrão sem validação e autorização específica.

## 6. Política de migração de dados

A primeira versão não migra os arquivos runtime originais.

Quando houver migração autorizada:
1. Congelar gravações do sistema de origem durante a cópia.
2. Gerar backup íntegro e manifesto SHA-256.
3. Ler os dados em modo somente leitura.
4. Importar cópia para banco separado.
5. Gerar relatório de registros aceitos, rejeitados e duplicados.
6. Comparar contagens e hashes dos arquivos de origem.
7. Testar consulta e exportação dos dados importados.
8. Testar restauração do backup.
9. Manter origem preservada até aprovação da reconciliação.
10. Só planejar corte de escrita após validação formal e autorização expressa.

Não apagar, renomear ou zerar JSONs originais. Não fundir memória neural Pestinha com memória do MAX.

## 7. Segurança e limites da primeira entrega

- Bind local por padrão, sem exposição à rede.
- Nenhuma porta pública ou regra de roteador.
- Nenhum segredo em arquivos versionados.
- Diretório de dados experimental separado.
- Upload desativado até haver validação de tamanho, tipo e armazenamento.
- Sem execução de comandos arbitrários pela interface.
- Ações de escrita no núcleo bloqueadas na primeira entrega.
- Logs sem conteúdo privado de mensagens.
- Encerramento seguro do serviço.

## 8. Critérios de saída da primeira entrega

A primeira entrega só será considerada concluída quando:
- O protótipo iniciar no Windows em diretório separado.
- A tela inicial corresponder à diretriz visual aprovada.
- Uma mensagem alcançar o núcleo por meio do adaptador.
- A resposta aparecer na conversa.
- Falha do motor resultar em erro controlado.
- Não houver duplicação de mensagem em reenvio.
- Testes automatizados passarem.
- JSONs originais tiverem hashes idênticos antes e depois.
- Terminal original continuar funcional.
- Pacote experimental e manifesto estiverem disponíveis.
- Relatório separar testes executados de testes pendentes.

## 9. Pontos que impedem declarar produção pronta

- Hardware e desempenho do host não medidos.
- Referências de base oficial de 28/10 e backup ZIP original ainda pendentes.
- Segurança de autenticação e recuperação ainda não implementada.
- Concorrência do núcleo ainda não validada.
- Sincronização multi-dispositivo não implementada.
- Atualização e rollback da plataforma ainda não implementados.
- Teste físico no Windows do usuário ainda não executado.

## 10. Aprovações necessárias

Este plano é documental. A ordem atual autorizou auditoria, consultas, verificações, documentação e preparação não destrutiva. Antes de iniciar a Etapa A de implementação, obter autorização expressa para criar os arquivos do novo diretório e os testes associados na branch de desenvolvimento.

Alterações no núcleo, Terminal, JSONs de memória/histórico, instalação `C:\SERMAX`, workflows, segredos, branch `main`, PR merge e backups exigem autorização específica conforme as regras existentes.
