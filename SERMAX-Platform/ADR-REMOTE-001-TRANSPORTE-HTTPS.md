# ADR-REMOTE-001: transporte HTTPS público para a SERMAX Platform

Data: 2026-11-27
Estado: decisão técnica preliminar, condicionada aos gates de segurança
Branch: sermax-platform-agent-scope-20261122
PR: #27

## Contexto

O operador exige acesso à SERMAX Platform pelo navegador em Windows, Android, tablets e outros dispositivos, como um serviço web convencional. Os dispositivos clientes não devem instalar Tailscale, Ollama, OpenJarvis ou OCR. O PC Windows permanece como servidor central e único proprietário do núcleo MAX, da memória e do banco de dados.

O operador não administra o roteador da conexão de internet atual e não tem autorização da prestadora para alterar o equipamento. A solução não pode depender de port-forwarding, IP público residencial ou alteração do roteador.

## Decisão preliminar

Adotar Tailscale Funnel como candidato preferencial para o transporte público HTTPS inicial, mantendo o Tailscale instalado somente no PC servidor central.

O Funnel publica um serviço local por uma URL HTTPS no domínio `*.ts.net`. O navegador cliente acessa essa URL pela internet sem instalar Tailscale e sem entrar no tailnet. O PC central mantém uma conexão de saída com a infraestrutura Tailscale; não exige encaminhamento de portas no roteador.

Documentação oficial consultada em 2026-11-27:
- https://tailscale.com/docs/features/tailscale-funnel
- https://tailscale.com/docs/reference/tailscale-cli/funnel
- https://tailscale.com/docs/use-cases/application-testing/share-local-dev-server-with-internet

## Limites e riscos conhecidos

- Funnel está documentado pela Tailscale como beta.
- O serviço publicado fica acessível pela internet a qualquer pessoa que conheça a URL. A URL não é mecanismo de autenticação.
- O tráfego está sujeito a limites de largura de banda não configuráveis.
- O domínio público fica no domínio Tailscale `*.ts.net`; não equivale a domínio próprio.
- O Funnel requer MagicDNS, HTTPS/certificados válidos, autorização Funnel na política do tailnet e Tailscale CLI.
- A configuração Funnel no Windows exige console elevado para determinadas operações e consentimento explícito na conta.
- O computador central precisa permanecer ligado, conectado à internet, com Tailscale e servidor SERMAX ativos.
- A indisponibilidade do PC ou da conexão interrompe o acesso à SERMAX.
- A documentação da Tailscale alerta que serviços com dados sensíveis não devem ser publicados sem controles próprios de acesso.

## Arquitetura de tráfego pretendida

1. Navegador remoto abre a URL HTTPS pública Funnel.
2. A infraestrutura de relay Tailscale encaminha o tráfego pelo túnel criptografado ao PC central.
3. O daemon Tailscale termina TLS no PC e encaminha a requisição somente para o serviço local explicitamente configurado.
4. O serviço SERMAX valida autenticação, identidade do dispositivo, sessão, origem, limites e autorização.
5. A API acessa o núcleo MAX, Ollama, memória, SQLite e arquivos exclusivamente no PC central.

O Funnel não deverá apontar diretamente para Ollama, OpenJarvis, SQLite, diretórios de arquivos ou endpoints administrativos. O alvo será exclusivamente o gateway HTTP da SERMAX Platform, depois da integração de autenticação e dos testes.

## Gates obrigatórios antes de ativar o Funnel

1. Integrar autenticação à API. Todas as rotas de dados devem negar acesso anônimo, com exceção estritamente definida para health check público sem dados sensíveis.
2. Integrar o fluxo de pareamento de duas fases. A aprovação deverá ocorrer em interface administrativa acessível somente no PC local.
3. Implementar gestão de dispositivos, expiração, revogação e proteção contra replay.
4. Implementar política de Host/Origin, CSRF, CORS explícito, limites de payload, rate limiting, concorrência e auditoria sem segredos.
5. Garantir que a API continue escutando em loopback. O Funnel encaminhará para `127.0.0.1`, sem bind em `0.0.0.0`.
6. Testar acesso anônimo negado, dispositivo não pareado negado, dispositivo revogado negado, origem indevida negada e limites de requisição.
7. Validar no Windows real, depois em Android por navegador e em uma rede externa diferente da rede do servidor.
8. Confirmar política de privacidade, disponibilidade, limites e adequação do plano Tailscale antes de uso contínuo.

## Alternativas consideradas

### Cloudflare Tunnel

Alternativa válida para publicar serviço local por conexão de saída. Para endereço estável com domínio próprio, exige configuração de domínio/DNS na Cloudflare. Não foi selecionada nesta etapa porque o operador já instalou e autenticou Tailscale e ainda não informou domínio próprio. Reavaliar se houver necessidade de domínio personalizado, política operacional diferente ou limites do Funnel incompatíveis.

### Tailscale Serve

Não atende ao requisito de acesso por qualquer navegador sem cliente Tailscale, pois Serve restringe o serviço aos dispositivos do próprio tailnet.

### WireGuard direto

Não atende ao cenário atual sem configuração de rede/roteador ou outro ponto público de entrada. O WireGuard instalado anteriormente não está configurado e não será usado como publicação pública.

## Estado de implementação

- Tailscale 1.104.7 instalado no PC central.
- O serviço Tailscale foi confirmado como Running.
- Login do dispositivo central concluído na conta Tailscale do operador.
- IP privado informado pelo comando local: `100.80.74.116`.
- Nenhuma configuração Funnel foi ativada.
- Nenhuma URL pública foi emitida.
- API continua restrita a `127.0.0.1:8765`.
- Autenticação HTTP ainda não está integrada.
- Pareamento continua isolado no módulo `backend/lan_security.py`.
- Nenhum cliente Android precisa instalar Tailscale quando o acesso público Funnel for liberado.

## Restrições de alteração

Esta decisão não autoriza exposição imediata da API. Não executar `tailscale funnel`, não alterar bind, middleware, CORS, firewall ou configuração de rede até todos os gates acima estarem implementados e aprovados. Não fazer merge, retirar Draft ou publicar release. Não alterar `main`, `C:\\SERMAX`, memória pessoal, Terminal, backups ou Drive Connect.
