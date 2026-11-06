# SERMAX para Windows — colaboração comunitária

Este diretório contém a área comunitária da versão Windows do SERMAX, um assistente local em português do Brasil. A interface de terminal preta e verde com rosto ASCII é parte importante do projeto e deve ser preservada.

## Estado desta publicação

Esta é a área de trabalho comunitária para a edição Windows. O código precisa ser validado antes de qualquer pacote ser considerado estável. Não instale artefatos de CI diretamente sobre sua instalação existente sem backup.

## Requisitos de execução

- Windows 10/11 x64
- Python 3.14 para o núcleo SERMAX e o adaptador Pestinha; Python 3.13 separado para o worker OpenJarvis
- Ollama instalado e em execução em `http://127.0.0.1:11434`
- Um modelo local compatível configurado no Ollama

O SERMAX é local-first: não configure chaves de API nem envie memórias privadas a serviços externos.

## Compilação e testes

O workflow **SERMAX Windows CI** executa validação de sintaxe, testes e compilação de verificação do `SERMAX.exe`. O workflow não publica nem anexa o executável como artefato enquanto a integração e a revisão de licença GPL-3.0-or-later do Pestinha estiverem pendentes. Uma compilação bem-sucedida no CI não substitui o teste no computador do usuário nem a validação com Ollama local.

## Dados privados

Não versionar `memoria_sermax.json`, históricos de conversa, backups pessoais, chaves, logs locais, modelos de linguagem, executáveis locais ou arquivos de áudio de teste. Use `.gitignore` para mantê-los fora do repositório.

## Contribuir

Abra uma issue descrevendo o comportamento observado, os passos para reproduzir e o resultado esperado. Propostas que alterem memória persistente, execução de comandos ou acesso a arquivos precisam incluir testes e explicar os riscos.


## Integrações Pestinha e OpenJarvis, validação 04/11/2026

- Execute `INSTALAR_INTEGRACOES_WINDOWS.ps1` para preparar os ambientes Python separados.
- O SERMAX usa Python 3.14 e a rede LIF do Pestinha, com estado em `memoria_neural_pestinha.json`.
- O OpenJarvis roda em processo isolado Python 3.13 através de `sermax_jarvis_worker.py`.
- A validação automatizada está em `.github/workflows/sermax-integrations-ci.yml`.
- A PR de integração permanece em rascunho. Não mesclar nem distribuir o executável até concluir os testes e a análise da licença GPL-3.0-or-later.


## Estado provisório dos motores, 05/11/2026

- O motor padrão continua sendo Ollama.
- Nesta etapa de desenvolvimento, a sessão aceita `/motor status`, `/motor jarvis` e `/motor ollama`. A seleção é manual e não persiste após reiniciar.
- O caminho Jarvis chama o agente `simple`, sem ferramentas do SDK e sem contexto próprio do SDK. O SERMAX prepara identidade, memória recuperada e contexto recente antes de enviar o prompt.
- Esses comandos são provisórios. O objetivo final é o SERMAX selecionar e coordenar automaticamente as capacidades internas, sem exigir que o usuário escolha motor ou agente.
- Consulte `ARQUITETURA-SERMAX-UNIFICADO-JARVIS-PESTINHA.md` para o plano de incorporação completa e os limites de segurança.
- A documentação descreve o estado do código; não declara testes recentes aprovados. O último CI aprovado citado no histórico é anterior à integração do comando `/motor`.
