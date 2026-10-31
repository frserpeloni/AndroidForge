# SERMAX para Windows — colaboração comunitária

Este diretório contém a área comunitária da versão Windows do SERMAX, um assistente local em português do Brasil. A interface de terminal preta e verde com rosto ASCII é parte importante do projeto e deve ser preservada.

## Estado desta publicação

Esta é a área de trabalho comunitária para a edição Windows. O código precisa ser validado antes de qualquer pacote ser considerado estável. Não instale artefatos de CI diretamente sobre sua instalação existente sem backup.

## Requisitos de execução

- Windows 10/11 x64
- Python 3.11+ para executar a partir do código (a compilação usa Python 3.11)
- Ollama instalado e em execução em `http://127.0.0.1:11434`
- Um modelo local compatível configurado no Ollama

O SERMAX é local-first: não configure chaves de API nem envie memórias privadas a serviços externos.

## Compilação e testes

O workflow **SERMAX Windows CI** executa validação de sintaxe e testes e tenta gerar `SERMAX.exe`. O executável gerado será disponibilizado como artefato de teste, não como release estável, até que os testes de integração no Windows/Ollama sejam aprovados.

## Dados privados

Não versionar `memoria_sermax.json`, históricos de conversa, backups pessoais, chaves, logs locais, modelos de linguagem, executáveis locais ou arquivos de áudio de teste. Use `.gitignore` para mantê-los fora do repositório.

## Contribuir

Abra uma issue descrevendo o comportamento observado, os passos para reproduzir e o resultado esperado. Propostas que alterem memória persistente, execução de comandos ou acesso a arquivos precisam incluir testes e explicar os riscos.
