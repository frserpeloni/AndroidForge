# Recursos e estado de implementação

## Como ler os estados

- **Implementado em candidata:** há registro de implementação em branch ou PR, sem liberação pública.
- **Em desenvolvimento:** há trabalho em andamento ou validação pendente.
- **Planejado:** consta como objetivo ou etapa futura.
- **Disponível publicamente:** versão oficialmente liberada para uso geral.

## Recursos registrados na candidata da Plataforma

O PR #24 descreve os seguintes componentes no código da candidata:

| Recurso | Estado documental | Limite conhecido |
|---|---|---|
| Interface gráfica responsiva | Implementado em candidata | Não equivale a release pública |
| Áreas Conversa, Projetos, Tarefas, Motores e Memória | Implementado em candidata | Conforme escopo do PR #24 |
| API local FastAPI | Implementado em candidata | Serviço descrito como loopback |
| Histórico SQLite | Implementado em candidata | Não declarar sincronização remota |
| Conversas associadas a projetos | Implementado em candidata | Conforme implementação da candidata |
| Tarefas persistentes | Implementado em candidata | Não executam automaticamente em segundo plano |
| Painel Memória somente leitura | Implementado em candidata | Não implica edição ou gestão irrestrita |
| Diagnóstico local de motores | Implementado em candidata | Diagnóstico não comprova inferência funcional |
| Streaming SSE | Implementado em candidata | Há limites de compatibilidade entre motores |
| Anexos por conversa e extração de texto | Implementado em candidata | Restrições de formatos e contexto |
| OCR local opcional | Implementado em candidata | Depende de componentes locais e limites de processamento |

## Em desenvolvimento ou aguardando validação

- Homologação integrada da candidata no ambiente Windows de destino.
- Validação com motores reais e fluxos completos.
- Recuperação e continuidade após reinicialização.
- Consolidação dos critérios de instalação e atualização.
- Revisão de segurança antes de qualquer exposição remota.

## Planejado

O PR #27 registra uma trilha para acesso remoto seguro pela internet, incluindo autenticação, pareamento, revogação, canal protegido, limites de requisição, auditoria e testes em redes externas.

## Não declarar como disponível

- Acesso remoto pela internet para qualquer dispositivo.
- Instalação pública de produção.
- Atualização automática liberada para o público.
- Execução automática de tarefas em segundo plano.
- Seleção dinâmica irrestrita de agentes pelo MAX.
- SERMAX Drive Connect integrado.
- Sincronização de dados entre dispositivos já homologada.

## Evidências e referências

- [PR #24, candidata integrada da Plataforma](https://github.com/frserpeloni/AndroidForge/pull/24)
- [PR #27, trilha de acesso remoto](https://github.com/frserpeloni/AndroidForge/pull/27)

Os estados devem ser revisados antes de cada publicação. Uma implementação em branch ou PR não equivale a uma versão liberada.
