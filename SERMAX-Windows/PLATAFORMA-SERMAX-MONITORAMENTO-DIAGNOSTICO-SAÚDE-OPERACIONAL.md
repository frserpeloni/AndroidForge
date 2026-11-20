# Monitoramento, diagnóstico e saúde operacional da Plataforma SERMAX

**Projeto:** SERMAX  
**Documento:** Especificação técnica e operacional  
**Estado:** Planejamento documental, não implementado  
**Branch de referência:** `sermax-windows-integration-20261029`

## 1. Objetivo e limites

Definir como a Plataforma SERMAX deverá observar seus próprios componentes, detectar falhas, apresentar o estado do serviço e apoiar diagnóstico e recuperação.

Esta especificação não autoriza implementação, execução de comandos no computador do usuário, instalação de serviços, coleta de dados do host ou alteração do núcleo SERMAX.

## 2. Princípios operacionais

1. Monitoramento deve ser leve e proporcional ao hardware disponível.
2. A interface deve informar o estado real, sem simular atividade.
3. Falhas devem ser registradas com identificadores que permitam correlação.
4. Dados sensíveis, tokens, senhas e conteúdo privado não devem aparecer nos logs.
5. Diagnóstico automático deve começar por verificações somente leitura.
6. Ações corretivas que alterem arquivos, processos, configurações ou dados exigem a classe de autorização correspondente.
7. O monitoramento não deve reiniciar repetidamente um componente em falha.
8. O Terminal original, núcleo, memória e backups permanecem protegidos.
9. Ausência de resposta não deve ser interpretada como sucesso.
10. Estado desconhecido deve ser apresentado como desconhecido, não como saudável.

## 3. Componentes observados

A Plataforma deverá monitorar separadamente:

| Componente | Sinais observáveis |
|---|---|
| Interface gráfica | carregamento, resposta da aplicação, erros de interface |
| API local | disponibilidade, latência, códigos de resposta |
| Gerenciador de solicitações | fila, idade da solicitação mais antiga, bloqueios |
| Adaptador do núcleo | disponibilidade, tempo de resposta, falhas de integração |
| Núcleo SERMAX | chamada iniciada/concluída, timeout, erro retornado |
| Motor OpenJarvis | disponibilidade e resultado de chamada, quando selecionado |
| Ollama | disponibilidade local e resultado de chamada, quando selecionado |
| Persistência da Plataforma | conexão, leitura, gravação, integridade transacional |
| Armazenamento | espaço disponível e falhas de leitura/gravação |
| Atualização | versão ativa, versão preparada e estado da operação |
| Backup | data, escopo, integridade e situação de validação |
| Segurança | estado da sessão, autenticação, bloqueios e eventos relevantes |

O monitor não deve afirmar que um modelo está instalado ou disponível sem consulta real ao respectivo motor.

## 4. Estados padronizados

Cada componente deve assumir um dos estados:

- **SAUDÁVEL:** verificação recente concluída com sucesso.
- **DEGRADADO:** responde, mas apresenta latência, capacidade ou função reduzida.
- **INDISPONÍVEL:** falha confirmada na verificação.
- **INICIANDO:** inicialização em andamento, dentro do limite configurado.
- **ENCERRANDO:** encerramento controlado em andamento.
- **DESCONHECIDO:** verificação não executada, resultado expirado ou inconclusivo.
- **BLOQUEADO:** operação impedida por política, permissão ou pré-condição.

O painel deve exibir horário da última verificação e motivo resumido. Estado antigo não deve permanecer como saudável sem indicação de expiração.

## 5. Verificações de saúde

Separar verificações em três níveis:

### 5.1 Liveness

Responde se o processo está ativo e se o ciclo básico de execução continua funcionando. Não deve depender de motor externo ou banco remoto.

### 5.2 Readiness

Indica se o componente está pronto para receber trabalho. Deve verificar dependências necessárias, fila e persistência, sem executar uma solicitação real ao núcleo.

### 5.3 Diagnóstico funcional

Executa testes controlados de leitura ou operações sintéticas explicitamente autorizadas. Não deve alterar memória, histórico ou projetos do usuário. Uma chamada real a um motor de IA deve ser identificada como teste e consumir recursos de acordo com a política aprovada.

As verificações devem ter timeout, intervalo configurável e proteção contra sobreposição. Falha de uma dependência opcional não deve derrubar componentes independentes.

## 6. Métricas mínimas

Registrar métricas agregadas, sem conteúdo privado:

- disponibilidade por componente;
- duração e resultado das verificações;
- latência de API e adaptadores;
- quantidade de solicitações aguardando, em execução e concluídas;
- idade da solicitação mais antiga;
- timeouts, falhas e cancelamentos;
- uso de memória e CPU do processo, quando autorizado e disponível;
- espaço livre no volume de dados;
- erros de leitura e gravação;
- último backup e seu estado de validação;
- versão ativa, build e commit.

Métricas do host devem ser coletadas somente após autorização para inventário local. Não presumir CPU, RAM, GPU ou espaço em disco.

## 7. Logs estruturados

Cada evento deve conter, quando aplicável:

- timestamp UTC;
- nível: DEBUG, INFO, WARNING, ERROR ou CRITICAL;
- componente;
- código de evento estável;
- identificador de correlação da solicitação;
- versão/build;
- duração;
- estado anterior e posterior;
- mensagem técnica sanitizada;
- ação tomada e resultado.

Níveis:
- **DEBUG:** diagnóstico detalhado temporário, desativado por padrão.
- **INFO:** ciclo normal e transições relevantes.
- **WARNING:** degradação ou condição que exige atenção.
- **ERROR:** operação falhou.
- **CRITICAL:** risco à integridade, segurança ou continuidade do serviço.

Não registrar prompts completos, respostas privadas, conteúdo de anexos, credenciais, cookies, tokens ou chaves. Para correlação, usar identificadores opacos. Logs não devem ser tratados como substitutos de histórico ou memória.

## 8. Alertas e interface

A interface inicial deve permanecer limpa. Mostrar um indicador compacto do estado geral e abrir detalhes sob demanda.

Alertas devem conter:
- componente afetado;
- gravidade;
- horário;
- impacto observado;
- ação segura recomendada;
- identificador do evento.

Evitar alertas repetidos para a mesma falha. Agrupar eventos correlatos e indicar quando o problema começou e se continua ativo. Alertas críticos não devem ser ocultados silenciosamente.

Não apresentar notificações sonoras por padrão. Preferências de notificação deverão ser configuráveis e respeitar o modo silencioso do sistema operacional.

## 9. Política de diagnóstico

O diagnóstico deve seguir esta ordem:

1. Consultar estado e logs recentes.
2. Verificar processo e endpoint local.
3. Verificar dependências necessárias.
4. Verificar fila e solicitações pendentes.
5. Verificar persistência e espaço disponível.
6. Correlacionar evento com versão e alteração recente.
7. Produzir relatório com evidências, hipóteses separadas e grau de confiança.
8. Recomendar ação, indicando impacto e autorização exigida.

O relatório deve distinguir fatos observados de hipóteses. Não afirmar causa raiz sem evidência suficiente.

## 10. Recuperação e prevenção de ciclos

A recuperação deve obedecer à política de atualização, backup e rollback e ao documento de recuperação de falhas.

- Não reiniciar automaticamente em loop.
- Aplicar limite de tentativas e intervalo progressivo, caso reinício automático venha a ser autorizado.
- Preservar logs e estado da falha antes de reiniciar.
- Não reenviar solicitação cujo resultado seja incerto.
- Marcar execução interrompida como resultado desconhecido quando não houver confirmação.
- Não apagar fila, histórico ou dados para tentar recuperar disponibilidade.
- Exigir confirmação para ações corretivas que alterem o sistema.

## 11. Segurança e privacidade

O endpoint de diagnóstico deve ficar restrito à interface autenticada e, na primeira versão, ao acesso local autorizado. Não expor painel administrativo em rede pública.

Aplicar:
- autenticação e autorização por função;
- proteção contra acesso cruzado entre sessões;
- sanitização de logs;
- retenção limitada e documentada;
- trilha de auditoria para ações administrativas;
- segregação entre métricas operacionais e conteúdo de usuário.

Falhas de autenticação e eventos de segurança devem ser registrados sem armazenar segredos.

## 12. Retenção e exportação

A retenção deve ser configurável, com limites de tamanho e rotação. A rotação não pode apagar evidências de incidentes ainda em análise.

Exportações de diagnóstico devem:
- incluir intervalo temporal e versões;
- excluir credenciais e conteúdo privado;
- identificar dados omitidos;
- exigir ação explícita do usuário antes de envio externo.

Não enviar telemetria para terceiros por padrão.

## 13. Critérios de aceite e testes planejados

Os testes abaixo são planejados. **Nenhum foi executado por este documento.**

1. Diferenciar liveness, readiness e diagnóstico funcional.
2. Exibir estado desconhecido quando a verificação expirar.
3. Detectar API local indisponível.
4. Detectar motor local indisponível sem declarar modelo instalado.
5. Sinalizar fila bloqueada e solicitação antiga.
6. Aplicar timeout e impedir verificações sobrepostas.
7. Agrupar alertas repetidos da mesma ocorrência.
8. Sanitizar tokens, senhas e conteúdo privado dos logs.
9. Correlacionar falhas com versão, build e solicitação.
10. Não reiniciar continuamente um processo em falha.
11. Preservar estado e logs antes de recuperação.
12. Marcar resultado incerto sem reenviar a solicitação automaticamente.
13. Não expor endpoints administrativos à rede pública.
14. Não enviar telemetria externa sem autorização.
15. Operar com baixo consumo de recursos no perfil mínimo definido após medição.
16. Distinguir falha de dependência opcional de falha do serviço principal.
17. Exibir horário da última verificação e motivo do estado.
18. Exportar relatório sem credenciais ou conteúdo privado.
19. Impedir ação corretiva sem a aprovação exigida.
20. Preservar núcleo, Terminal, memória e backups durante diagnóstico.

## 14. Dependências documentais

Esta especificação complementa:
- arquitetura gráfica da Plataforma;
- contrato preliminar da API;
- operação local da primeira versão;
- integração controlada com o núcleo;
- recuperação de falhas e retomada;
- permissões, aprovações e auditoria;
- identidade, autenticação e sessões;
- armazenamento e integridade dos dados;
- política de atualização, backup e rollback.

Em caso de conflito, prevalecem as regras mais restritivas de proteção de dados, autorização e preservação do SERMAX existente.

## 15. Estado e autorização

**Estado:** especificação documental.  
**Código:** não implementado.  
**Coleta no computador do usuário:** não executada.  
**Testes:** planejados, não executados.  
**Alterações no núcleo, Terminal, memória ou backups:** nenhuma.  
**Autorização de implementação:** continua pendente de autorização expressa específica.
