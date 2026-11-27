# Entrega técnica semanal SERMAX
Data: 20/11/2026
Branch: `sermax-windows-integration-20261029`
Repositório: https://github.com/frserpeloni/AndroidForge

## Estado da entrega

**Resultado: EXPERIMENTAL, NÃO INSTALÁVEL.** O melhor executável disponível vem da CI Windows 570, concluída com sucesso em 18/11/2026. O atualizador ainda não atende aos requisitos de backup, staging, journal, substituição transacional e rollback.

Nenhuma instalação local foi acessada ou modificada. Nenhuma release foi publicada. `main` permaneceu intacta.

## Repositório e PR

- Commit de correção da equipe nesta entrega: `4052272b408a5e063fa99cbf2ba397a7f890105e`.
- A correção alterou somente `SERMAX-Windows/sermax_groq_backend.py` e `SERMAX-Windows/tests/test_sermax_groq_backend.py`.
- PR #2: aberta, em rascunho, sem merge.
- O executável da CI 570 foi compilado no commit anterior `d10387a22419c00b3ef198399a0b80820eca40e9`. O commit posterior altera somente a infraestrutura externa dos agentes e seu teste. Esses dois arquivos não constam no `SERMAX.spec`, portanto não integram o executável de produto.
- A comparação histórica da candidata técnica de 28/10/2026 não foi realizada. O arquivo original e o ZIP de backup de 28/10 não foram localizados na Library nem na branch. O snapshot técnico `SERMAX_BASE_2026-11-07` não substitui essas referências.

## Correção da equipe externa

A execução anterior da equipe, run [44335087212](https://github.com/frserpeloni/AndroidForge/actions/runs/44335087212), falhou na etapa do Programador. O primeiro conteúdo não passou no parser JSON. A chamada de correção retornou conteúdo vazio. Nenhuma proposta foi aplicada e não há evidência de execução do Testador.

A documentação oficial da Groq informa que GPT-OSS aceita `reasoning_effort` baixo, `reasoning_format=hidden`, `max_completion_tokens` e modo JSON. O backend foi ajustado para:

- usar `max_completion_tokens`, no lugar do campo depreciado `max_tokens`;
- solicitar esforço de raciocínio baixo e saída final sem campo de raciocínio para GPT-OSS;
- solicitar JSON para os papéis Programador e Testador;
- informar `finish_reason` quando a resposta vier vazia.

Fontes oficiais:
- https://console.groq.com/docs/reasoning
- https://console.groq.com/docs/api-reference
- https://console.groq.com/docs/structured-outputs

Não foi enviada chamada à API Groq nesta execução. A correção não foi validada com tráfego real da API nem com nova execução do workflow. O commit foi testado localmente.

## Testes e build

### CI Windows 570

- Run: [44335106879](https://github.com/frserpeloni/AndroidForge/actions/runs/44335106879)
- Commit: `d10387a22419c00b3ef198399a0b80820eca40e9`
- Ambiente: Windows Server 2025 Datacenter x64.
- Python 3.14.10 para SERMAX/Pestinha e Python 3.13.17 para OpenJarvis.
- `python -m compileall -q .`: aprovado.
- `python -m unittest discover -s tests -v`: 348 testes aprovados em 9,629 segundos.
- PyInstaller: build concluído.
- Smoke test: chegou ao prompt do Terminal original e processou `/sair`.
- Testes Windows executados no runner incluíram leitura de ACL real, Authz com token real, negação para token de usuário padrão distinto, criação de diretório temporário por handle e rejeição de junction/symlink.

A CI 570 é anterior à correção do backend externo. Ela valida o código de produto no commit indicado, não a correção nova dos agentes.

### Testes locais da correção Groq

Ambiente: Python 3.13.5, neste ambiente de execução.

Comandos:
- `python -m compileall -q .`
- `python -m unittest -v test_sermax_groq_backend`

Resultado: 10 testes aprovados em 0,004 segundo. Os testes usam respostas simuladas. Não comprovam conectividade ou comportamento real da API Groq.

### Validade do artefato CI

- Artifact ID: `14442270012`.
- Nome: `SERMAX-Windows-executable`.
- ZIP original: 22.836.010 bytes.
- SHA-256 do ZIP original: `d7b9e800100ca93a8a00613a873edaa29f891f80c44623d900c6e76d289e74a9`.
- Executável: 23.071.050 bytes.
- SHA-256 de `SERMAX.exe`: `2f4ba64cdc8810b7feb259914422fc62580fe72b2d6c24c07781b35291cfb2d9`.
- Expiração do artefato GitHub: 02/12/2026 às 12:26:23, horário de Brasília.
- Conteúdo original do artefato: somente `SERMAX.exe`.

O pacote entregue fora do GitHub inclui o executável, este relatório, aviso de não instalação e hashes. O executável é PE32+ Windows x64, console.

## Atualizador, estado técnico

Implementado e testado parcialmente:
- validação Ed25519 de manifesto por verificador confiável externo;
- contrato de inventário somente leitura com allowlist;
- validação integral de ZIP em memória, sem extração, com correspondência exata ao manifesto, hashes, limites, rejeição de traversal, colisões e objetos especiais;
- inspeção de ACL e validação de `_update` preexistente por handle, identidade, DACL e Authz.

Bloqueios:
- allowlist de chave pública de release aprovada permanece vazia;
- `create_private_directory_component()` chama `NtCreateFile` com descritor de segurança nulo, sem provisionamento ACL restritivo atômico;
- não há staging seguro gravado por handles;
- não há backup verificável da instalação;
- não há journal durável;
- não há substituição transacional;
- não há health check pós-atualização;
- não há recuperação após interrupção nem rollback comprovado por hashes.

A decisão de 17/11 determina que uma pasta `_update` preexistente com ACL divergente seja rejeitada sem reparo automático. A criação de uma pasta nova exige descritor de segurança explícito e atômico. O código atual ainda não atende ao segundo requisito.

## Integrações e preservação

- OpenJarvis foi instalado em ambiente isolado Python 3.13 na CI.
- Pestinha foi obtido de commit pinado e seus testes foram executados.
- O smoke test do EXE valida inicialização do Terminal e `/sair`, não o ciclo completo das integrações.
- Ollama real, Jarvis com modelo local, voz/Whisper e memória após reinício no PC do usuário: NÃO EXECUTADOS.
- Testes de rollback e atualização sobre instalação descartável: NÃO EXECUTADOS.
- Homologação no Windows 11 físico do usuário: NÃO EXECUTADA.
- Nenhuma leitura ou gravação em `C:\SERMAX`.
- Nenhuma memória pessoal, credencial ou gravação foi incluída no pacote.

## Atividades por função

- Coordenação: revisão de commits, PR, CI, logs e prioridades.
- Análise: revisão do contrato de `_update`, ACL, assinatura e limites do pacote.
- Pesquisa: consulta à documentação oficial Groq para os parâmetros de GPT-OSS.
- Desenvolvimento: commit `4052272`, correção do backend e testes de regressão.
- Testes: 10 testes locais da correção; 348 testes na CI Windows 570.
- Equipe autônoma: não concluiu nesta rodada. O workflow sequencial falhou no Programador; não atribuir execução concluída aos quatro papéis.

## Próximas prioridades

1. Validar a correção Groq em nova execução do workflow, sem ampliar o consumo além do plano gratuito.
2. Implementar criação de `_update` com descritor de segurança explícito e atômico.
3. Testar ACL, identidade e direitos efetivos em Windows x64, incluindo usuário padrão.
4. Implementar staging por handles em sandbox.
5. Implementar backup por handles e validação byte a byte.
6. Implementar journal durável, máquina de estados e recuperação após interrupção.
7. Implementar rollback e injeção de falhas em cada transição.
8. Aprovar formalmente a chave pública de release.
9. Localizar a candidata e o backup de 28/10 para reconciliação histórica.

## Instrução de uso e recuperação

**Não instalar este executável em `C:\SERMAX`.** Não sobrescrever arquivos, memória, configurações ou histórico. O pacote serve para análise e testes isolados. Nenhuma instalação foi modificada nesta entrega; não há rollback a executar.
