# Arquitetura do atualizador transacional SERMAX para Windows

Status: especificação técnica, não implementada e não validada em Windows físico.
Data: 2026-11-07
Escopo: planejar atualização in-place de `C:\\SERMAX` sem alterar a instalação atual.

## 1. Objetivo e limites

O atualizador deverá substituir somente os componentes de aplicação declarados em um manifesto de release aprovado. Deve preservar a instalação, os dados do usuário, a interface original e os ambientes locais. Toda operação deverá ter registro auditável e recuperação automática quando a validação pós-instalação falhar.

Esta especificação não autoriza instalar artifacts atuais de CI. O artifact `SERMAX-Windows-executable` é experimental, não contém contrato de instalador e não equivale a uma release assinada.

O atualizador não deverá:
- apagar a pasta de instalação para depois reconstruí-la;
- sobrescrever arquivos de memória, histórico, configuração ou conteúdo pessoal;
- substituir modelos Ollama, ambientes Python externos, áudio ou dados de voz;
- executar scripts arbitrários recebidos no pacote;
- aceitar caminhos absolutos, traversal (`.. `), junctions ou symlinks que escapem da raiz;
- declarar sucesso antes do health check e da confirmação de integridade.

## 2. Princípios obrigatórios

1. **Manifesto explícito:** cada arquivo do pacote terá caminho relativo, tamanho, SHA-256, classificação e ação permitida.
2. **Deny-by-default:** arquivo ausente do manifesto não será instalado. Caminhos protegidos nunca serão destinos de escrita.
3. **Separação entre aplicação e dados:** binários e módulos da aplicação ficam no conjunto atualizável; memórias, histórico, preferências, modelos e recursos do usuário ficam fora dele.
4. **Staging:** extrair e validar em diretório temporário no mesmo volume da instalação.
5. **Backup verificável:** registrar inventário e hashes antes de qualquer substituição. Confirmar que o backup pode ser lido e que os arquivos críticos estão presentes.
6. **Commit transacional:** manter journal de cada operação. A substituição será controlada arquivo a arquivo, com cópia anterior preservada até o health check.
7. **Rollback automático:** qualquer falha após o início da troca restaura os arquivos anteriores segundo o journal.
8. **Idempotência:** reexecutar após interrupção deverá detectar a transação incompleta e oferecer recuperação segura, sem iniciar uma segunda troca sobre estado ambíguo.
9. **Sem privilégios desnecessários:** não solicitar elevação administrativa se a instalação tiver permissões suficientes.
10. **Privacidade:** logs registram caminhos relativos, códigos de erro e hashes. Não registram conteúdo de memórias, prompts, chaves, tokens ou áudio.

## 3. Inventário e matriz de preservação

A classificação abaixo é uma política de destino. O inventário real deverá ser obtido da instalação no momento da atualização. Não presume que todos os caminhos existam em todas as instalações.

### 3.1 Dados protegidos, nunca sobrescrever nem remover

| Classe | Caminhos/elementos conhecidos | Política |
|---|---|---|
| Memória pessoal | `memoria_sermax.json` | Preservar byte a byte. Nunca incluir no pacote. |
| Memória neural | `memoria_neural_pestinha.json` | Preservar byte a byte. Nunca incluir no pacote. |
| Histórico | arquivos e diretórios de histórico existentes | Preservar integralmente. Inventariar sem ler conteúdo. |
| Configurações | arquivos locais de configuração, preferências e variáveis persistidas | Preservar. Migração somente por etapa separada, explícita e reversível. |
| Voz e Whisper | modelos, pesos, arquivos de áudio, transcrições e configuração local de voz | Preservar. Não baixar nem substituir durante atualização comum. |
| Ollama | modelos instalados, blobs, manifests e dados do serviço | Fora da raiz gerenciada. Não tocar. |
| Ambientes externos | ambientes Python 3.13/3.14, OpenJarvis, Pestinha e dependências instaladas fora do pacote | Preservar. Não reinstalar como efeito colateral. |
| Interface do usuário | personalizações e recursos originais do terminal, incluindo rosto ASCII, cores, layout e atalhos | Preservar; só atualizar arquivos de interface quando houver aprovação explícita e teste visual dedicado. |
| Dados diversos | arquivos desconhecidos, documentos, backups, exportações e pastas criadas pelo usuário | Preservar por padrão. |

A lista de exclusão será codificada no atualizador e também validada contra o manifesto. Uma colisão entre destino do pacote e caminho protegido deverá abortar o preflight.

### 3.2 Componentes potencialmente atualizáveis

Os componentes abaixo são identificados no repositório, mas a inclusão efetiva dependerá do manifesto de cada release e de uma matriz de compatibilidade aprovada:

- `SERMAX.exe` e seus recursos empacotados;
- módulos Python do núcleo, adaptadores e ferramentas;
- worker isolado do OpenJarvis;
- arquivos de suporte e documentação da versão;
- scripts de inicialização estritamente necessários, quando aprovados.

O launcher atual resolve a raiz persistente a partir da localização do executável e carrega a interface empacotada a partir do bundle. O instalador deverá respeitar essa separação: dados persistentes na raiz da instalação, recursos imutáveis dentro do bundle.

### 3.3 Inventário dinâmico

Antes de atualizar, gerar um manifesto local contendo:
- caminho relativo normalizado;
- tipo de objeto (arquivo/diretório);
- tamanho e SHA-256 para arquivos;
- atributos necessários à restauração;
- classificação: protegido, gerenciado, desconhecido;
- decisão: preservar, substituir, criar ou bloquear.

Não seguir links simbólicos/junctions durante a enumeração. Detectar reparse points e interromper se algum caminho de destino resolver para fora de `C:\\SERMAX`. Não incluir conteúdo dos arquivos de dados no relatório.

## 4. Fluxo transacional

### Fase A, preflight

1. Confirmar Windows suportado, espaço livre e permissões.
2. Resolver a raiz real da instalação e validar que não há redirecionamento inesperado.
3. Confirmar que não há outra instância do atualizador, usando lock exclusivo.
4. Detectar SERMAX em execução. Solicitar encerramento limpo; não matar processos à força.
5. Validar versão de origem, versão de destino e compatibilidade do formato de memória/configuração.
6. Validar assinatura digital do manifesto ou mecanismo de confiança equivalente, além do SHA-256 de cada arquivo. Hash sem origem autenticada detecta corrupção, mas não comprova autoria.
7. Rejeitar manifesto com caminhos absolutos, traversal, duplicados, colisão case-insensitive, nomes reservados, links ou destinos protegidos.
8. Abortar se qualquer verificação falhar. Nenhum arquivo da instalação será alterado nesta fase.

### Fase B, inventário e backup

1. Criar identificador de transação e diretório de backup fora da árvore de arquivos substituíveis, preferencialmente no mesmo volume.
2. Inventariar os caminhos gerenciados e os dados protegidos sem expor conteúdo.
3. Copiar os arquivos gerenciados que serão substituídos, mantendo metadados necessários.
4. Registrar hashes antes/depois da cópia e validar igualdade.
5. Registrar o estado dos arquivos protegidos por caminho, tamanho e hash, sem copiá-los para o pacote de release.
6. Gerar journal durável e sincronizar os dados em disco antes de prosseguir.
7. Se backup, espaço ou verificação falhar, cancelar sem modificar a instalação.

### Fase C, staging

1. Extrair o pacote para diretório temporário dedicado.
2. Validar todos os caminhos e hashes contra o manifesto autenticado.
3. Confirmar que o conjunto extraído corresponde exatamente aos arquivos declarados.
4. Executar verificações estáticas e smoke tests não destrutivos no staging.
5. Verificar novamente que nenhum arquivo protegido aparece no pacote.
6. Não executar scripts de pós-instalação arbitrários. Migrações futuras exigem comandos internos allowlisted, versionados e testados.
7. Qualquer falha descarta o staging e mantém a instalação intacta.

### Fase D, instalação controlada

1. Revalidar lock, processo SERMAX encerrado e hashes da origem.
2. Para cada arquivo gerenciado, registrar no journal a intenção antes da operação.
3. Substituir usando arquivo temporário no mesmo volume e rename atômico quando suportado.
4. Nunca apagar primeiro o arquivo original. Manter cópia de rollback até finalizar.
5. Criar diretórios necessários sem alterar conteúdo desconhecido.
6. Não remover arquivos obsoletos automaticamente. Remoções futuras exigem lista explícita, backup e aprovação no manifesto.
7. Após cada operação, verificar hash do destino e registrar conclusão.
8. Interrupção ou erro aciona recuperação pelo journal.

### Fase E, health check

Executar verificações locais e limitadas:
- existência e hash dos arquivos instalados;
- inicialização do executável em modo de diagnóstico sem gravar memória real;
- abertura do terminal original, confirmação de prompt e encerramento controlado;
- leitura de configurações sem expor valores;
- verificação de que arquivos protegidos mantêm os hashes anteriores;
- teste de que o launcher resolve a raiz persistente e os recursos empacotados corretamente.

O health check não deve disparar chamadas externas, alterar memórias, executar tarefas do usuário ou modificar modelos Ollama. Os testes de Ollama, Jarvis, Pestinha, voz e persistência real exigem gates específicos e consentimento/ambiente apropriado.

### Fase F, confirmação ou rollback

- **Sucesso:** marcar transação como confirmada somente após todos os health checks obrigatórios. Manter backup por janela de retenção configurável. Nunca apagá-lo na mesma execução.
- **Falha:** restaurar os arquivos substituídos em ordem inversa conforme journal, verificar hashes restaurados e registrar resultado.
- **Rollback incompleto:** bloquear novas atualizações, preservar backup e journal, apresentar instrução de recuperação manual com caminhos exatos.
- **Reinício inesperado:** na próxima inicialização, detectar transação não confirmada e oferecer/realizar rollback automático antes de abrir o SERMAX.

## 5. Estrutura de dados proposta

Diretórios internos do atualizador, fora do conjunto de arquivos substituíveis:
- `_update/staging/<transaction_id>/`
- `_update/backups/<transaction_id>/`
- `_update/journal/<transaction_id>.json`
- `_update/logs/update.log`

O diretório `_update` deverá ter ACL restrita ao usuário da instalação. Não guardar segredos nem conteúdo de memória. O journal deverá conter versão, estado, timestamps, caminhos relativos, hashes, ações e resultado de cada operação.

Estados possíveis:
`CREATED`, `PREFLIGHT_OK`, `BACKUP_VERIFIED`, `STAGED`, `INSTALLING`, `HEALTH_CHECK`, `COMMITTED`, `ROLLING_BACK`, `ROLLED_BACK`, `RECOVERY_REQUIRED`.

Transições inválidas deverão ser rejeitadas. `COMMITTED` e `ROLLED_BACK` são estados terminais para uma transação.

## 6. Segurança e integridade

- Preferir manifesto assinado com chave pública incorporada ao atualizador. A chave privada de assinatura nunca fica no repositório nem no computador do usuário.
- Se assinatura ainda não estiver implantada, o atualizador não deverá tratar SHA-256 isolado como autenticação de release.
- Verificar arquivos compactados contra Zip Slip, entradas duplicadas, caminhos Unicode ambíguos e colisões de nomes no Windows.
- Rejeitar reparse points e hardlinks inesperados nos caminhos de origem/destino.
- Usar lock exclusivo e permissões restritas para staging, backup e journal.
- Não aceitar downgrade sem política explícita e validação de compatibilidade.
- Não apagar backups automaticamente enquanto existir transação incompleta.
- Não executar atualização enquanto SERMAX estiver escrevendo memória ou histórico.
- Não atualizar dependências Python ou modelos Ollama de forma implícita.

## 7. Plano de testes exigido antes de habilitar atualização

### Testes unitários e simulados
1. Manifesto válido, inválido, assinatura inválida e hash divergente.
2. Caminho absoluto, traversal, duplicado, colisão de caixa e nome reservado.
3. Tentativa de sobrescrever cada caminho protegido.
4. Arquivo desconhecido na instalação.
5. Falha de espaço, permissão negada e arquivo bloqueado.
6. Interrupção em cada estado do journal.
7. Falha de rename, escrita parcial e falha de sincronização.
8. Rollback completo e rollback com erro.
9. Reexecução idempotente após crash.
10. Reparse point/junction apontando para fora da raiz.
11. Pacote com ZIP Slip, entradas duplicadas e conteúdo extra.
12. Preservação byte a byte de memórias, histórico, configuração, voz e arquivos desconhecidos.

### Testes em Windows físico/VM limpa
1. Instalação nova e atualização sobre instalação existente.
2. Atualização com SERMAX aberto e bloqueio de escrita de memória.
3. Falha forçada em cada fase e recuperação após reinício.
4. Verificação de ACL, atomicidade, espaço e arquivos bloqueados.
5. Terminal original, rosto ASCII, cores, alinhamento e comandos.
6. Memória pessoal e neural após reinício, sem alteração de conteúdo.
7. Ollama real e alias configurado.
8. Worker Jarvis Python 3.13, fallback e isolamento.
9. Voz/Whisper e modelos já instalados.
10. Backup, rollback e recuperação manual.

Nenhum teste desta seção é declarado executado por este documento. A aprovação exige logs e hashes por ambiente.

## 8. Gates de liberação

O atualizador só poderá ser habilitado quando:
- inventário real da instalação estiver validado;
- lista protegida estiver coberta por testes de colisão;
- manifesto autenticado e verificação de assinatura estiverem implementados;
- backup e rollback forem testados com falhas injetadas;
- health check for não destrutivo;
- Windows físico/VM confirmar interface e preservação;
- documentação e política de retenção estiverem prontas;
- revisão de licenças e Corresponding Source estiver resolvida para o pacote distribuído.

Até lá, o atualizador permanece especificação. Não há instalador final, atualização in-place validada ou nova versão SERMAX.

## 9. Referências internas

- `sermax_launcher.py`: resolução da raiz persistente e do bundle empacotado.
- `SERMAX.spec`: composição atual do executável e coleta de recursos.
- `AUDITORIA-RECONCILIACAO-2026-11-07.md`: estado técnico e gates conhecidos.
- `AUDITORIA-LICENCAS-PESTINHA-2026-11-07.md`: pendências de licença e distribuição.
