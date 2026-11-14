# PLATAFORMA SERMAX
## Especificação de identidade, autenticação e sessões entre dispositivos

**Estado:** especificação de planejamento  
**Escopo:** identidade local, autenticação, sessões web e preparação para clientes Windows e Android  
**Revisão:** 14/11/2026  
**Dependências:** arquitetura GUI, contrato preliminar da API, hospedagem e acesso remoto, operação local da primeira versão, permissões e auditoria

## 1. Objetivo e limites

Definir como o SERMAX identifica o responsável, autentica clientes e mantém sessões seguras entre navegador, Windows e Android.

Esta especificação não implementa autenticação, não cria contas, não altera configurações do repositório e não autoriza exposição pública do serviço. A primeira versão permanece com conta única local, conforme o plano operacional existente.

A expansão para múltiplos usuários, sincronização externa ou autenticação por provedor de terceiros exige decisão própria.

## 2. Princípios de segurança

1. Negar por padrão qualquer solicitação sem identidade autenticada e autorização correspondente.
2. Separar identidade, autenticação, sessão e permissão. Estar autenticado não concede acesso irrestrito.
3. Manter o serviço inacessível pela rede na primeira execução, salvo configuração expressamente aprovada.
4. Não armazenar senhas em texto puro, logs, arquivos de configuração ou histórico de conversa.
5. Não armazenar tokens de sessão em localStorage ou sessionStorage do navegador.
6. Vincular sessões a um identificador aleatório, revogável e com validade definida.
7. Revalidar autorização no servidor em cada operação protegida.
8. Exigir confirmação reforçada para ações críticas e mudanças de segurança.
9. Não confiar em nome de usuário, papel, caminho de arquivo ou escopo enviados pelo cliente.
10. Falha de autenticação ou indisponibilidade do serviço deve resultar em bloqueio seguro, sem liberar modo administrativo.

## 3. Modelo de identidade da primeira versão

### 3.1 Conta única local

- Uma única identidade de responsável na primeira versão.
- Cadastro inicial feito localmente, em procedimento explícito de configuração.
- Não criar conta padrão com senha conhecida.
- Não incluir senha inicial fixa no código, instalador ou documentação de distribuição.
- A configuração inicial deve exigir acesso local ao computador host.
- O nome de exibição é independente do identificador interno da conta.
- O identificador interno deve ser estável e não conter dados pessoais desnecessários.

### 3.2 Evolução futura

A arquitetura deve evitar dependência de uma conta codificada diretamente no núcleo. A futura inclusão de outros usuários exigirá:
- Identificadores individuais.
- Papéis e permissões por projeto.
- Separação de conversas, arquivos e memórias.
- Gestão de dispositivos e sessões por usuário.
- Política de convite, remoção e recuperação de conta.
- Auditoria de acesso entre usuários.

Esses recursos ficam fora da primeira versão.

## 4. Credenciais e armazenamento

- Armazenar senha com algoritmo de derivação resistente a ataques offline, preferencialmente Argon2id, com parâmetros atuais revisados antes da implementação.
- Usar salt exclusivo por credencial.
- Permitir atualização dos parâmetros de hash após autenticação válida.
- Nunca registrar senha, hash completo, token, cookie, chave privada ou código de recuperação nos logs.
- Proteger o arquivo ou banco de credenciais com permissões restritas ao usuário do sistema operacional que executa o serviço.
- Não reutilizar a senha do Windows como credencial SERMAX sem integração de identidade formalmente projetada.
- Segredos de aplicação devem ficar fora do repositório e fora de arquivos versionados.
- Em instalação local, preferir armazenamento protegido pelo sistema operacional quando houver suporte confiável.

## 5. Fluxo de autenticação

1. O cliente acessa a interface do host.
2. O servidor apresenta o formulário de autenticação sem expor dados internos.
3. O cliente envia credenciais por canal protegido.
4. O servidor valida a credencial com proteção contra tentativas automatizadas.
5. Em caso de sucesso, cria uma sessão com identificador criptograficamente aleatório.
6. O servidor associa a sessão à conta, dispositivo quando identificado, horário de criação, último uso, expiração e estado.
7. O navegador recebe o identificador em cookie HttpOnly, Secure quando HTTPS estiver ativo, e SameSite apropriado.
8. O servidor valida a sessão em cada solicitação protegida.
9. Ao sair, a sessão é revogada no servidor e o cookie é removido no cliente.

Não retornar senha, hash ou segredo de sessão no corpo de respostas da API.

## 6. Proteção contra ataques de autenticação

- Limitar tentativas por conta e origem, com janela progressiva e espera crescente.
- Evitar bloqueio permanente que permita negação de serviço contra o responsável.
- Responder com mensagens genéricas para credencial inválida.
- Registrar tentativas relevantes sem armazenar a senha enviada.
- Aplicar proteção contra força bruta e automação.
- Validar tamanho e formato de entradas antes do processamento.
- Não permitir enumeração de contas.
- Exigir reautenticação após alteração de senha ou mudança sensível de segurança.
- Revogar sessões existentes após redefinição de credencial, salvo sessão atual de recuperação explicitamente controlada.

## 7. Ciclo de vida das sessões

Cada sessão deve possuir:
- Identificador aleatório não previsível.
- Identificador da conta.
- Identificador interno da sessão.
- Data de criação.
- Data de último uso.
- Expiração absoluta.
- Expiração por inatividade.
- Estado: ativa, expirada, revogada ou suspeita.
- Identificação resumida do cliente, sem fingerprint invasivo.
- Data e motivo de revogação, quando aplicável.

Política inicial proposta:
- Expiração por inatividade: 30 minutos para sessões administrativas.
- Expiração absoluta: 12 horas.
- Renovação somente após validação da sessão ativa.
- Reautenticação para ações críticas, mudança de credencial e gestão de dispositivos.
- Valores finais devem ser configuráveis e revisados em teste de usabilidade e segurança.

A expiração não deve depender exclusivamente de relógio do cliente. O servidor é a referência temporal.

## 8. Cookies, CSRF e segurança do navegador

- Cookies de sessão devem ser HttpOnly.
- Em HTTPS, marcar Secure.
- Definir SameSite=Lax como ponto inicial, revisando o fluxo real de navegação.
- Não expor identificador de sessão a JavaScript.
- Aplicar proteção CSRF em operações que alteram estado.
- Validar Origin e, quando aplicável, Referer nas operações sensíveis.
- Restringir CORS às origens explicitamente autorizadas.
- Não usar curingas de origem com credenciais.
- Aplicar cabeçalhos de segurança compatíveis com a interface.
- Evitar conteúdo ativo de terceiros na tela de autenticação.
- Não colocar tokens em URLs, parâmetros de consulta ou logs de proxy.

## 9. Clientes Windows e Android

### Windows

- A interface desktop deve autenticar-se no serviço local ou remoto usando o mesmo contrato de sessão.
- Não manter senha em arquivo de texto.
- Se houver credencial persistente, armazená-la em cofre do sistema operacional, após avaliação técnica.
- O Terminal administrativo original continua separado e preservado. A autenticação da Plataforma não deve alterar seu funcionamento nesta fase.

### Android

- O aplicativo Android será cliente do cérebro central, não uma instância independente do MAX.
- Credenciais persistentes devem ficar em armazenamento seguro do Android.
- Não embutir segredo compartilhado no APK.
- Permitir revogar o dispositivo pelo host.
- Em caso de perda do aparelho, o responsável deve conseguir encerrar suas sessões.
- A primeira versão não deve manter dados sensíveis offline sem política de armazenamento e limpeza aprovada.

### Navegador

- Usar cookie de sessão protegido.
- Não persistir token em armazenamento web acessível a scripts.
- Ao fechar sessão, invalidar no servidor.
- Tratar perda de conexão como estado desconectado, sem presumir que a sessão continua válida.

## 10. Registro e gestão de dispositivos

A primeira versão pode identificar sessões por tipo de cliente e metadados mínimos. O registro formal de dispositivos fica preparado para a etapa de expansão.

Quando habilitado, o cadastro de dispositivo deve:
- Exigir autenticação válida e confirmação do responsável.
- Exibir nome atribuído, tipo de dispositivo, data de inclusão e último acesso.
- Permitir revogação individual.
- Não confiar exclusivamente em User-Agent como identidade.
- Não permitir que um dispositivo recém-cadastrado aprove a própria inclusão.
- Registrar inclusão, alteração e revogação na trilha de auditoria.

Pareamento por QR Code é uma opção futura. Se adotado, o código deve ser curto, temporário, de uso único e confirmado no host já autenticado. Não implementar nesta fase.

## 11. Acesso local e remoto

### Primeira versão

- Vincular o serviço a loopback (127.0.0.1) por padrão.
- Não abrir portas no roteador.
- Não publicar a API diretamente na internet.
- Não presumir que estar na mesma rede Wi-Fi equivale a estar autorizado.
- Não permitir acesso remoto até que autenticação, HTTPS, firewall e recuperação tenham sido validados.

### Etapa remota futura

- Preferir rede privada autenticada, como VPN, antes de exposição pública.
- Exigir HTTPS para qualquer tráfego fora do loopback.
- Restringir origens, portas e rotas.
- Separar endpoint público de interface administrativa.
- Não expor Terminal, depuração, documentação interna ou endpoints de administração.
- Avaliar Tailscale ou alternativa equivalente na etapa de hospedagem, sem contratação automática.
- Registrar acessos e revogações.
- Fazer revisão de ameaça antes de habilitar acesso externo.

## 12. Recuperação de acesso

- A recuperação inicial deve ocorrer presencialmente no host, com procedimento documentado.
- Não criar senha mestra universal.
- Não enviar senha por e-mail ou mensagem.
- Não permitir redefinição remota sem segundo fator ou prova de posse previamente configurada.
- Toda redefinição deve revogar sessões existentes e gerar evento de auditoria.
- Backups de credenciais devem ser protegidos e não devem permitir restauração silenciosa de sessões revogadas.
- Se a base de autenticação estiver corrompida, bloquear acesso e seguir procedimento de recuperação; não desativar autenticação automaticamente.

## 13. Integração com permissões e aprovações

A autenticação confirma quem está solicitando. O mecanismo de permissões decide o que essa identidade pode fazer.

- Classe A continua limitada a recursos previamente autorizados.
- Classe B exige aprovação vinculada à sessão e à ação específica.
- Classe C exige autorização expressa, revalidação recente da sessão e registro anterior à execução.
- Aprovação não substitui autenticação.
- Sessão expirada invalida aprovações ainda não consumidas.
- Revogação da sessão impede novas operações e aprovações.
- Ações iniciadas devem seguir o protocolo de recuperação e resultado incerto.

## 14. Eventos de auditoria

Registrar:
- Login aceito e recusado.
- Logout.
- Expiração e revogação.
- Tentativas limitadas ou bloqueadas.
- Alteração e recuperação de credencial.
- Inclusão e remoção de dispositivo, quando habilitado.
- Reautenticação para ação crítica.
- Falha de validação de sessão.
- Alteração de política de autenticação.

Não registrar:
- Senhas ou códigos temporários.
- Cookies ou tokens.
- Chaves privadas.
- Conteúdo integral de formulários de autenticação.
- Dados de dispositivo além do necessário à segurança.

Os eventos devem seguir a política append-only descrita na especificação de permissões e auditoria.

## 15. Testes de aceitação planejados

1. Credencial válida cria sessão.
2. Credencial inválida não cria sessão.
3. Respostas não permitem enumerar contas.
4. Limite de tentativas é aplicado.
5. Senha nunca aparece em logs.
6. Token não aparece no corpo da API nem em URL.
7. Cookie possui atributos de segurança definidos.
8. Requisição sem sessão é bloqueada.
9. Sessão expirada é recusada pelo servidor.
10. Logout revoga sessão no servidor.
11. Revogação impede novas operações.
12. Sessão não pode ser reutilizada após redefinição de credencial.
13. CSRF inválido bloqueia operação de alteração.
14. Origem não autorizada é recusada.
15. CORS não aceita origem arbitrária com credenciais.
16. Serviço inicia em loopback por padrão.
17. Acesso remoto não funciona sem configuração autorizada.
18. Dispositivo revogado perde acesso.
19. Ação crítica exige reautenticação.
20. Sessão expirada invalida aprovação pendente.
21. Falha na base de autenticação resulta em bloqueio seguro.
22. Reinício do serviço respeita a política de invalidação ou persistência de sessões definida.
23. Logs não contêm segredos.
24. Recuperação local não desativa controles de segurança.

Nenhum desses testes foi executado. São critérios para validação futura.

## 16. Decisões pendentes antes da implementação

- Escolher biblioteca e parâmetros Argon2id compatíveis com o ambiente Python suportado.
- Definir HTTPS local e certificado para acesso remoto.
- Definir armazenamento protegido de credenciais no Windows.
- Definir mecanismo seguro de armazenamento no Android.
- Fechar política de expiração após teste com o usuário.
- Definir se sessões serão invalidadas em todo reinício na primeira versão.
- Definir estratégia de backup e recuperação da base de identidade.
- Avaliar segundo fator antes de habilitar acesso remoto.
- Definir modelo de pareamento de dispositivos para a etapa multi-dispositivo.

## 17. Critério de liberação

A autenticação só poderá ser considerada pronta quando os testes de aceitação forem executados, os resultados forem registrados, as falhas críticas forem corrigidas e o acesso remoto permanecer desabilitado até aprovação específica.

Esta especificação não autoriza implementação, instalação, exposição de rede, alteração do núcleo, mudança no Terminal, migração de credenciais ou ativação de clientes externos.
