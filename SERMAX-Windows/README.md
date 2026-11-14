# SERMAX para Windows, colaboração comunitária

Este diretório contém a área comunitária da versão Windows do SERMAX, um assistente local em português do Brasil. A interface de terminal preta e verde com rosto ASCII é parte importante do projeto e deve ser preservada.

## Estado desta publicação

Esta é a área de trabalho comunitária para a edição Windows. O código precisa ser validado antes de qualquer pacote ser considerado estável. Não instale artefatos de CI diretamente sobre sua instalação existente sem backup.

## Requisitos de execução

- Windows 10/11 x64
- Python 3.14 para o núcleo SERMAX e o adaptador Pestinha; Python 3.13 separado para o worker OpenJarvis
- Ollama instalado e em execução em `http://127.0.0.1:11434`
- Um modelo local compatível configurado no Ollama

O SERMAX é local-first: não configure chaves de API nem envie memórias privadas a serviços externos.

## Compilação, testes e artefatos

O workflow **SERMAX Windows CI**, em `.github/workflows/sermax-windows-ci.yml`, executa validação de sintaxe, testes, compilação de verificação do `SERMAX.exe` e smoke test do executável congelado.

Quando a execução termina com sucesso, o workflow envia o arquivo `SERMAX.exe` como artifact do GitHub Actions, com retenção configurada de 14 dias. Esse artifact é temporário e experimental. Não é instalador, release ou versão validada. Não deve ser instalado sobre `C:\SERMAX`.

A existência do artifact não autoriza sua distribuição pública. A integração Pestinha e a revisão das obrigações GPL-3.0-or-later continuam pendentes. Uma compilação bem-sucedida no CI não substitui o teste no computador do usuário nem a validação com Ollama local.

## Dados privados

Não versionar `memoria_sermax.json`, históricos de conversa, backups pessoais, chaves, logs locais, modelos de linguagem, executáveis locais ou arquivos de áudio de teste. Use `.gitignore` para mantê-los fora do repositório.

## Contribuir

Abra uma issue descrevendo o comportamento observado, os passos para reproduzir e o resultado esperado. Propostas que alterem memória persistente, execução de comandos ou acesso a arquivos precisam incluir testes e explicar os riscos.

## Integrações Pestinha e OpenJarvis

- Execute `INSTALAR_INTEGRACOES_WINDOWS.ps1` para preparar os ambientes Python separados.
- O SERMAX usa Python 3.14 e o adaptador da rede LIF do Pestinha, com estado separado em `memoria_neural_pestinha.json`.
- O OpenJarvis roda em processo isolado Python 3.13 através de `sermax_jarvis_worker.py`.
- A validação Windows está em `.github/workflows/sermax-windows-ci.yml`.
- A PR de integração permanece em rascunho. Não mesclar nem distribuir o executável até concluir os testes e a análise de licença GPL-3.0-or-later.
- O código Pestinha está sob GPL-3.0-or-later. As imagens e os textos da pasta upstream `assets/` não estão cobertos por essa licença. Não incluir esses materiais sem comprovação de direitos de redistribuição.
- Consulte `AUDITORIA-LICENCAS-PESTINHA-2026-11-07.md` para as evidências e pendências documentadas.

## Estado provisório dos motores

- O motor padrão continua sendo Ollama.
- Nesta etapa de desenvolvimento, a sessão aceita `/motor status`, `/motor jarvis` e `/motor ollama`. A seleção é manual e não persiste após reiniciar.
- O caminho Jarvis chama o agente `simple`, sem ferramentas do SDK e sem contexto próprio do SDK. O SERMAX prepara identidade, memória recuperada e contexto recente antes de enviar o prompt.
- Esses comandos são provisórios. O objetivo final é o SERMAX selecionar e coordenar automaticamente as capacidades internas, sem exigir que o usuário escolha motor ou agente.
- Consulte `ARQUITETURA-SERMAX-UNIFICADO-JARVIS-PESTINHA.md` para o plano de incorporação e os limites de segurança.
- A documentação descreve o estado do código. Não declara integração ampla nem testes físicos concluídos.
