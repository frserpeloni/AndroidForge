# Política de atualização, backup e rollback da Plataforma SERMAX

**Projeto:** SERMAX  
**Documento:** Política técnica e operacional  
**Estado:** Especificação documental, não implementada  
**Branch de referência:** `sermax-windows-integration-20261029`  
**Escopo:** Plataforma SERMAX e sua convivência com o núcleo, Terminal e dados existentes

## 1. Objetivo

Estabelecer um processo controlado para versionar, empacotar, atualizar, proteger dados e recuperar versões da Plataforma SERMAX. A atualização não deve comprometer o núcleo atual, o Terminal, memórias, configurações ou backups.

Este documento define requisitos. Não autoriza implementação, instalação, alteração de arquivos funcionais, migração de dados ou publicação de release.

## 2. Princípios obrigatórios

1. Preservar o núcleo SERMAX e o Terminal original.
2. Manter a Plataforma em diretório separado durante o protótipo.
3. Não sobrescrever arquivos funcionais diretamente.
4. Fazer backup verificável antes de qualquer atualização.
5. Identificar cada artefato por versão, build e commit de origem.
6. Bloquear a atualização quando integridade, origem, backup ou validação falhar.
7. Não executar rollback de dados sem cópia preservada e plano compatível.
8. Registrar operações, resultados, falhas e decisões.
9. Nunca declarar instalação ou teste real com base somente em CI.
10. Manter os backups e a candidata técnica de 28/10/2026 pendentes de localização e reconciliação. Não substituí-los por cópias presumidas.

## 3. Identificação e versionamento

Adotar versionamento semântico para versões públicas da Plataforma: `MAJOR.MINOR.PATCH`.

- **MAJOR:** alteração incompatível de API, formato de dados ou comportamento operacional.
- **MINOR:** funcionalidade compatível com versões anteriores.
- **PATCH:** correção compatível, sem mudança incompatível de dados ou contrato.

Cada build deve registrar:
- versão semântica;
- identificador único da build;
- SHA completo do commit de origem;
- branch e repositório de origem;
- data e hora UTC da compilação;
- versão do esquema de dados;
- versões e hashes dos componentes empacotados;
- resultado dos testes automatizados associados;
- dependências e requisitos de execução.

O número de versão, isoladamente, não comprova autenticidade nem integridade. O hash do artefato deve ser publicado em manifesto associado à release. Assinatura digital deve ser adotada quando houver infraestrutura de assinatura confiável e chave protegida.

## 4. Separação dos componentes

A instalação deve distinguir claramente:

| Componente | Regra |
|---|---|
| Plataforma gráfica | Atualizável em diretório próprio |
| Serviço/API | Atualizável de forma controlada e compatível com a interface |
| Núcleo SERMAX | Preservado; alterações exigem autorização específica |
| Terminal original | Preservado integralmente |
| Memória e histórico | Dados persistentes, nunca tratados como arquivos descartáveis |
| Projetos e anexos | Dados do usuário, protegidos por backup e política de retenção |
| Configurações e segredos | Separados dos binários, com acesso restrito |
| Logs e auditoria | Preservados conforme política de retenção |

No protótipo, não integrar a instalação gráfica à instalação funcional existente. Não mover nem renomear os diretórios atuais.

## 5. Processo de release

A cadência definida para o projeto é semanal, sexta-feira às 18h, horário de Brasília.

Cada ciclo deve produzir:
1. identificação do commit de origem;
2. registro do escopo incluído e das pendências;
3. execução dos testes previstos no ambiente disponível;
4. geração do artefato correspondente, quando tecnicamente possível;
5. manifesto com versão, build, commit, tamanho e SHA-256;
6. relatório de validação, limitações e riscos conhecidos;
7. instruções de instalação e recuperação compatíveis com o estado real do artefato.

Se não houver instalador validado, o relatório deve declarar isso expressamente. Um ZIP, build de CI ou executável experimental não deve ser chamado de instalador validado. A entrega semanal deve distinguir artefato disponível, pacote instalável e instalação comprovada em máquina real.

## 6. Backup anterior à atualização

Antes de qualquer atualização autorizada, criar uma cópia consistente dos seguintes itens, conforme aplicável:
- banco de dados e arquivos associados;
- memória SERMAX e histórico;
- projetos, conversas e anexos;
- configurações necessárias à recuperação;
- manifestos da versão atualmente instalada;
- arquivos funcionais que serão afetados;
- logs de auditoria relevantes.

O backup deve:
1. ser criado em destino distinto do diretório que será atualizado;
2. receber identificador, data, versão de origem e escopo;
3. ter hash SHA-256 calculado após a gravação;
4. passar por verificação de leitura e integridade;
5. ter restauração testada em ambiente isolado antes de ser considerado validado;
6. manter proteção de acesso adequada aos dados pessoais.

Uma mensagem de sucesso na criação do arquivo não comprova que o backup é restaurável. Backup sem teste de restauração deve ser classificado como **não validado**.

A retenção deve preservar, no mínimo, a versão imediatamente anterior e os pontos de recuperação definidos pelo responsável. A política de retenção não autoriza apagar backups históricos. Exclusões exigem autorização específica.

## 7. Atualização segura

O fluxo futuro deve seguir estas etapas:

1. Validar origem, branch, commit e manifesto do pacote.
2. Conferir hash e assinatura, quando disponível.
3. Verificar espaço livre, dependências e compatibilidade.
4. Criar e validar o backup prévio.
5. Preparar a nova versão em diretório temporário ou de staging.
6. Validar arquivos e dependências do pacote.
7. Executar migrações de dados versionadas, quando necessárias, em cópia ou transação recuperável.
8. Executar verificações de saúde e testes de inicialização.
9. Ativar a nova versão por troca controlada de referência ou mecanismo equivalente, sem sobrescrita parcial.
10. Verificar serviço, interface, persistência e comunicação com o núcleo.
11. Registrar resultado, versão ativa e ponto de recuperação.

Se uma etapa crítica falhar, interromper a ativação e manter a versão anterior disponível. Não apagar o staging nem os registros de falha antes do diagnóstico.

## 8. Migrações de dados

Toda migração deve ter:
- identificador sequencial e versão de origem/destino;
- descrição do impacto;
- pré-condições;
- validação antes e depois;
- estratégia de transação ou cópia;
- procedimento de recuperação;
- teste em cópia representativa dos dados.

Migrações destrutivas ou sem reversão automática exigem backup validado e autorização expressa. Não executar migração de memória, histórico ou projetos como efeito colateral de uma atualização de interface.

Se a versão nova alterar o esquema de dados, a versão antiga só deve voltar a operar após confirmar compatibilidade do esquema ou restaurar uma cópia de dados compatível. Nunca iniciar versão antiga sobre dados incompatíveis.

## 9. Rollback

O rollback deve separar duas operações:

**Rollback de aplicação**
- interromper a nova versão;
- reativar o pacote anterior preservado;
- confirmar versão, commit e integridade;
- executar verificações de saúde;
- registrar motivo, horário e resultado.

**Recuperação de dados**
- avaliar se a nova versão alterou dados;
- preservar uma cópia do estado atual para investigação;
- restaurar o backup compatível, se necessário e autorizado;
- validar integridade e consistência após restauração.

Não presumir que reverter o executável reverte alterações no banco. Não restaurar dados automaticamente quando o resultado da operação for incerto. Quando houver dúvida sobre uma gravação, bloquear novas tentativas automáticas e classificar o estado para análise.

## 10. Condições de bloqueio

Bloquear atualização ou ativação quando ocorrer qualquer uma destas condições:
- origem do pacote não confirmada;
- commit ou versão ausente;
- hash divergente;
- assinatura inválida, quando exigida;
- backup ausente, incompleto ou não verificável;
- espaço insuficiente;
- dependência incompatível;
- migração sem plano de recuperação;
- teste crítico reprovado;
- serviço anterior não encerrado com segurança;
- risco de sobrescrita do núcleo, Terminal, memória ou arquivos do usuário;
- ausência de autorização exigida para a operação.

Não contornar bloqueios por meio de substituição manual de arquivos.

## 11. Logs e auditoria

Registrar, no mínimo:
- solicitação e identidade responsável;
- versão anterior e versão pretendida;
- commit e hash do pacote;
- backup utilizado e seu resultado de integridade;
- migrações executadas;
- aprovações recebidas;
- início e fim de cada etapa;
- resultado de testes e verificações;
- falhas, interrupções e rollback;
- versão efetivamente ativa.

Os registros devem ser append-only sempre que tecnicamente viável. Não armazenar senhas, tokens ou segredos em logs.

## 12. Preservação do SERMAX existente

A primeira implantação da Plataforma deve permanecer isolada em diretório próprio. O núcleo atual e o Terminal continuam como referência funcional independente.

É proibido, sem autorização específica:
- substituir ou reescrever o núcleo;
- alterar o Terminal original;
- converter ou apagar memória e histórico;
- mover a instalação existente;
- apagar ou substituir backups;
- executar migração real;
- instalar atualização no computador do usuário;
- fazer merge na branch `main`.

A candidata `SERMAX_CONSOLIDACAO_TECNICA_CANDIDATA_28-10-2026` e o backup `SERMAX bkp 28 10 26.zip` continuam pendentes de localização e reconciliação. Esta política não declara esses materiais recuperados.

## 13. Testes de aceite planejados

Os testes abaixo são requisitos futuros. **Nenhum teste desta política foi executado por este documento.**

1. Rejeitar pacote com hash divergente.
2. Rejeitar pacote sem identificação de commit.
3. Bloquear atualização sem backup.
4. Detectar backup incompleto.
5. Restaurar backup em ambiente isolado.
6. Instalar versão nova em staging sem alterar a versão ativa.
7. Interromper ativação após falha de health check.
8. Reativar versão anterior após falha da aplicação.
9. Detectar incompatibilidade de esquema no rollback.
10. Preservar memória, histórico e projetos durante atualização da interface.
11. Confirmar que o Terminal original permanece íntegro.
12. Impedir migração sem autorização e backup validado.
13. Registrar todas as etapas e aprovações.
14. Evitar duplicação de migração após interrupção.
15. Confirmar que pacote experimental não é rotulado como instalador validado.
16. Confirmar que a atualização não altera a branch `main`.
17. Confirmar que falhas não apagam o pacote anterior nem os backups.
18. Confirmar recuperação após encerramento inesperado do processo de atualização.

## 14. Critérios para considerar uma release apta

Uma release só recebe status **apta para instalação** quando:
- origem e artefato estão identificados;
- hashes foram verificados;
- testes críticos foram aprovados;
- backup e recuperação foram validados no escopo exigido;
- instruções de instalação e rollback foram revisadas;
- pendências e limitações estão declaradas;
- nenhuma proteção do núcleo, Terminal ou dados foi violada.

O status **instalada e validada em máquina real** exige evidência de instalação, inicialização, persistência após reinício e recuperação no equipamento de destino. CI isolada não satisfaz esse critério.

## 15. Estado e autorização

**Estado deste documento:** especificação registrada.  
**Implementação:** não iniciada.  
**Testes:** planejados, não executados.  
**Instalação no computador do usuário:** não realizada.  
**Autorização para implementação:** continua pendente de autorização expressa específica.

Qualquer implementação futura deverá ocorrer na branch de trabalho autorizada e em diretório separado, sem alterar `main`, núcleo, Terminal ou dados existentes.