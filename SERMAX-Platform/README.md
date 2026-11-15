# SERMAX Platform, protótipo gráfico

Este diretório contém a primeira implementação isolada da interface gráfica da Plataforma SERMAX.

## Estado desta entrega

- Interface web estática, responsiva.
- Tela inicial e área de conversa.
- Navegação visual entre Conversa, Projetos e Tarefas.
- Seletor manual de modelo em estado demonstrativo.
- Tema grafite com detalhes verde SERMAX.
- Sem dependências externas de frontend.

## Limitações explícitas

Esta versão ainda não possui backend, autenticação, banco de dados, sincronização, conexão com Ollama/OpenJarvis ou integração com o núcleo MAX. O envio de mensagem demonstra a interação da interface e informa que o serviço ainda não está conectado. Nenhuma resposta de IA é simulada.

## Como visualizar localmente

Abra `index.html` em um navegador moderno. Para desenvolvimento, sirva o diretório com um servidor HTTP estático local.

## Proteções

A implementação está em diretório e branch separados. Não altera o núcleo SERMAX, o Terminal original, memórias, backups ou a branch `main`. Não inclui Drive Connect nem execução de comandos no host.
