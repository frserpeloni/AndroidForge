# Estado da integração local

## Implementado nesta etapa

- API FastAPI separada da interface.
- Bind previsto exclusivamente em `127.0.0.1:8765`.
- Health check.
- Endpoint de catálogo de modelos sem declarar motores disponíveis.
- Persistência SQLite isolada em `~/.sermax-platform/platform.sqlite3`.
- Histórico de conversas próprio da Plataforma.
- Adaptador de chamada ao núcleo existente por importação tardia.
- Bloqueio global para serializar chamadas ao núcleo compartilhado.
- Proteção de origem local e validação de entrada.
- Inicializador Windows e testes unitários básicos.

## Limites e riscos ainda abertos

- O backend ainda não foi executado neste ambiente nem no computador do usuário.
- Dependências e compatibilidade com Python 3.14 precisam ser verificadas.
- A importação real do núcleo depende dos módulos e dependências existentes no diretório `SERMAX-Windows`.
- O núcleo mantém sessão e histórico globais. A serialização evita concorrência, mas não separa contexto por conversa. Portanto, a primeira integração deve ser tratada como uso local de usuário único.
- O núcleo existente também grava memória segundo suas regras atuais. A interface não oferece edição ou exclusão dessa memória.
- A autenticação de usuário e acesso remoto estão fora desta etapa. A API não deve ser exposta à rede.
- Não há streaming de tokens, anexos, sincronização Android, tarefas persistentes nem publicação pública.

## Validação necessária

1. Instalar dependências em ambiente isolado.
2. Rodar os testes unitários.
3. Verificar health check.
4. Confirmar falha clara quando o núcleo não estiver disponível.
5. Confirmar importação do núcleo sem alterar seus arquivos.
6. Enviar mensagem de teste autorizada e conferir resposta real do motor local.
7. Reiniciar serviço e conferir persistência SQLite.
8. Confirmar que o serviço permanece limitado a loopback.

Nenhum desses testes é declarado aprovado por este documento.
