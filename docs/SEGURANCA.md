# Segurança e privacidade

## Princípio geral

O SERMAX deve proteger dados do usuário, memória, credenciais, arquivos e serviços locais. A documentação pública descreve somente controles comprovados ou requisitos formalmente registrados.

## Estado documentado da candidata

O PR #24 informa que a candidata da Plataforma permanece restrita a loopback e não possui autenticação ou acesso remoto. Portanto, não deve ser apresentada como serviço seguro para exposição direta à internet.

## Requisitos registrados para acesso remoto

O PR #27 estabelece requisitos para a futura trilha de acesso remoto:

- HTTPS obrigatório e validação da identidade do servidor.
- Autenticação individual.
- Pareamento de uso único com expiração.
- Limite de tentativas.
- Aprovação local inicial.
- Credenciais de dispositivos armazenadas com hash.
- Auditoria, expiração e revogação.
- Proteção contra CSRF, abuso de sessão, força bruta, replay e origens inválidas.
- Rate limiting e limites de conexões.
- Logs sem registro de segredos.
- Acesso remoto somente à API protegida da Plataforma.
- Não expor diretamente motores locais, SQLite, arquivos ou serviços administrativos.
- Preferência por conexão de saída do servidor central por túnel ou relay seguro, sem exposição indiscriminada de portas.

Esses itens são requisitos de projeto. Não representam comprovação de implementação concluída.

## Dados e segredos

A documentação pública não deve conter:

- tokens, senhas ou chaves privadas;
- conteúdo de memória pessoal;
- caminhos locais que exponham dados do usuário;
- endereços privados ou identificadores de dispositivos;
- arquivos de configuração com credenciais;
- registros de conversas ou anexos pessoais.

## Anexos e conteúdo externo

O registro técnico da candidata descreve tratamento de anexos e instruções para considerar o conteúdo documental como não confiável. Essa proteção deve continuar sendo avaliada conforme os formatos e fluxos efetivamente suportados.

## Condição para liberação remota

O acesso remoto só deve ser declarado disponível depois que implementação, revisão de segurança, testes em redes externas, revogação de dispositivos, recuperação de conexão e critérios de aceite estiverem comprovados.

## Relato de vulnerabilidades

Até que exista um canal oficial específico, não publique detalhes exploráveis de vulnerabilidades em issues públicas. Encaminhe relatos privados ao mantenedor do repositório.
