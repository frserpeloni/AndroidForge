# SERMAX Platform, arquitetura do servidor central e clientes

Data: 2026-11-20  
Branch: `sermax-platform-ocr-20261117`  
Estado: decisão arquitetural proposta para orientar a próxima fase. Não implementada.

## 1. Objetivo

Manter uma única instância do MAX no computador principal. Windows, Android e navegadores acessam essa instância como clientes. Nenhum cliente mantém uma cópia independente do núcleo, da memória pessoal ou dos motores locais.

O computador principal continua responsável por:
- executar `sermax_core.py`;
- executar Ollama e o ambiente OpenJarvis local;
- manter a memória SERMAX existente;
- manter o banco da Plataforma, conversas, projetos, tarefas e anexos;
- executar ferramentas e operações autorizadas;
- autenticar dispositivos e controlar sessões.

Os clientes enviam solicitações e recebem resultados. Não executam inferência local nem sincronizam cópias divergentes da memória.

## 2. Estado atual comprovado

A API atual:
- escuta em `127.0.0.1:8765`;
- rejeita Host e Origin fora da lista local;
- rejeita clientes cujo IP não seja loopback;
- não possui autenticação por usuário ou dispositivo;
- não oferece acesso remoto;
- consulta Ollama por `127.0.0.1:11434`;
- mantém o banco SQLite e os anexos no diretório local da Plataforma.

Portanto, o serviço atual não deve ser exposto à rede local, à internet ou por encaminhamento de portas. A verificação de Host, Origin e loopback é uma barreira de desenvolvimento local, não substitui autenticação.

## 3. Topologia-alvo

```text
                  Rede privada autenticada
          (VPN WireGuard ou túnel privado equivalente)
                              |
             +----------------+----------------+
             |                |                |
        Windows PC         Android         Navegador
        cliente local       cliente         cliente
             |                |                |
             +----------------+----------------+
                              |
                    API SERMAX central
                     no PC principal
                              |
             +----------------+----------------+
             |                |                |
          MAX Core        SQLite local      Anexos locais
             |
       +-----+------+
       |            |
     Ollama      OpenJarvis
   loopback       local
```

A VPN fornece conectividade privada entre dispositivos. A API continua sem porta pública. O firewall do Windows aceita conexões somente pela interface/sub-rede privada autorizada. O acesso local no próprio PC continua disponível.

## 4. Requisitos obrigatórios de segurança

### 4.1 Rede e transporte
- Não publicar a porta da API diretamente na internet.
- Não configurar encaminhamento de porta do roteador para a API.
- Preferir VPN privada com WireGuard ou tecnologia equivalente, com identidade por dispositivo.
- Restringir o firewall ao endereço/interface da VPN e ao próprio loopback.
- Em modo remoto, exigir HTTPS com certificado válido, mesmo sobre VPN, ou documentar formalmente a proteção equivalente do túnel e os limites do ambiente.
- Não confiar em cabeçalhos `X-Forwarded-For` ou `Forwarded` sem proxy explicitamente confiável e configurado.
- Ollama e OpenJarvis permanecem vinculados ao loopback. Clientes não acessam diretamente os motores.

### 4.2 Identidade, pareamento e sessões
- Cada instalação cliente recebe um identificador de dispositivo próprio.
- Pareamento inicial exige código de uso único, com expiração curta, gerado no PC central por ação local explícita.
- O código não é senha permanente e não deve aparecer em logs.
- Após pareamento, o servidor emite credencial aleatória de dispositivo. O banco guarda somente hash criptográfico da credencial.
- Credenciais devem ter escopo, data de emissão, último uso, expiração e revogação.
- Deve existir tela local para listar e revogar dispositivos.
- Tokens de sessão devem ter curta duração. Renovação exige credencial válida e revogável.
- Não reutilizar senha do Windows, token do GitHub ou chave de API de fornecedor como credencial da Plataforma.

### 4.3 API e navegador
- Autenticar todas as rotas de dados e ações, inclusive anexos, projetos, memória e tarefas.
- Não considerar CORS, Origin ou Host mecanismos de autenticação.
- Validar Origin e proteção CSRF em operações autenticadas por cookie.
- Cookies, se adotados, devem ser `HttpOnly`, `Secure` e `SameSite` adequado.
- Não armazenar credenciais permanentes em `localStorage`.
- Aplicar limite de tentativas de pareamento e autenticação.
- Respostas de erro não devem expor caminhos locais, stack traces, tokens ou conteúdo de memória.
- A API deve impor limites de tamanho, frequência e concorrência por dispositivo.

### 4.4 Dados e integridade
- Memória pessoal permanece no PC central e sob as regras já existentes do núcleo.
- Conversas, projetos, tarefas e anexos permanecem em armazenamento central. Clientes recebem somente o que a sessão autenticada está autorizada a consultar.
- Não sincronizar arquivos da memória pessoal para Android ou navegador.
- Fazer backup consistente do SQLite, anexos e configurações, com teste de restauração.
- Revogar um dispositivo não apaga dados do servidor.
- Exclusão de dados exige ação explícita e trilha de auditoria.

## 5. Contratos funcionais dos clientes

### Windows
- Interface web local ou cliente fino.
- Pode abrir o Terminal administrativo original por comando local reservado.
- O comando `/sermax terminal` permanece exclusivo do PC central e nunca é enviado ao MAX como mensagem.

### Android
- Cliente responsivo, preferencialmente PWA instalável na primeira etapa.
- Conversas, projetos, histórico, anexos e tarefas acessam a API central.
- Upload de arquivo envia o conteúdo diretamente ao PC central por canal autenticado.
- Cache local não deve armazenar memória pessoal nem credenciais permanentes.
- Modo offline, se implementado, deve indicar claramente que mensagens ainda não chegaram ao servidor.

### Navegador em outro computador
- Mesma interface e mesmos dados do Android.
- Sem segundo núcleo, memória paralela ou banco local independente.
- Sessões e permissões vinculadas ao dispositivo autenticado.

## 6. Disponibilidade e recuperação

- O PC central precisa estar ligado e com a Plataforma em execução para atender os clientes.
- Se o servidor estiver offline, clientes mostram indisponibilidade. Não criam uma instância substituta do MAX.
- Reinício do serviço deve preservar conversas, projetos, tarefas e anexos.
- Atualização do núcleo e da Plataforma deve manter backup e procedimento de recuperação.
- O estado de conectividade do cliente deve ser separado do estado do motor MAX e do estado do Ollama/OpenJarvis.
- Uma resposta de health check não comprova que o núcleo ou os motores estejam operacionais.

## 7. Sequência de implementação

1. Fechar a homologação local da API atual e da integração com o núcleo, sem tocar em `C:\SERMAX`.
2. Definir e testar o serviço central Windows, incluindo início automático opcional, encerramento, logs e recuperação.
3. Implementar autenticação de dispositivo, pareamento, expiração e revogação. Manter modo local de desenvolvimento isolado.
4. Adicionar configuração de rede privada e HTTPS, com firewall restritivo e testes negativos de acesso externo.
5. Implementar cliente Android/PWA apontando para o servidor central.
6. Validar conversas simultâneas, sessões independentes, anexos, reinício e perda de conectividade.
7. Só então preparar pacote instalável e homologação no PC principal.

## 8. Critérios de aceite antes de acesso remoto

- Cliente não pareado recebe 401/403 em todas as rotas protegidas.
- Credencial revogada deixa de funcionar imediatamente.
- Código de pareamento expira e não é reutilizável.
- Cliente fora da VPN ou sub-rede autorizada não alcança a API.
- Tentativas de acesso direto a Ollama/OpenJarvis a partir dos clientes falham.
- CORS e CSRF não permitem ações a partir de origem não autorizada.
- Reinício do servidor preserva dados e sessões expiradas não são reativadas.
- Testes verificam que logs não contêm tokens, códigos de pareamento, conteúdo de memória ou caminhos pessoais.
- Android e navegador usam a mesma instância central e não criam bancos ou memórias independentes.

## 9. Fora do escopo desta decisão

- Implementar Google Drive Connect.
- Integrar SERMAX Control ao núcleo.
- Alterar a memória pessoal existente.
- Substituir ou redesenhar o SERMAX Terminal.
- Expor a API diretamente à internet.
- Criar uma instância MAX autônoma em cada dispositivo.

## 10. Proteção do projeto

Este documento registra a arquitetura-alvo. Não altera `main`, `C:\SERMAX`, Terminal original, memória pessoal ou backups. Não realiza merge, publicação, instalação ou abertura de portas de rede.
