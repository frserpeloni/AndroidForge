# Arquitetura conceitual do SERMAX

## Visão pretendida

A arquitetura de referência do SERMAX prevê um computador central que hospeda o núcleo MAX, os motores locais, os dados e os serviços da plataforma. Outros dispositivos atuam como clientes de acesso.

```text
Computador central
├── Núcleo MAX / SERMAX
├── Motores de IA locais
├── API da Plataforma
├── Persistência e histórico
├── Memória e contexto autorizado
└── Ferramentas e serviços integrados
        │
        ├── Cliente web em computador
        ├── Cliente web em Android
        └── Navegador em outros dispositivos
```

O diagrama representa a visão arquitetural, não uma declaração de que todas as conexões estão implementadas.

## Componentes descritos na candidata

O PR #24 descreve uma interface gráfica responsiva, uma API local FastAPI, persistência SQLite, contexto de projetos, tarefas persistentes, painel de memória somente leitura, diagnóstico de motores, streaming SSE, anexos e OCR local opcional.

## Estado de acesso

A descrição do PR #24 afirma que o serviço permanece restrito a loopback e não possui autenticação ou acesso remoto.

O PR #27 registra uma trilha separada para acesso remoto pela internet. A proposta mantém o computador central como servidor e os dispositivos remotos como clientes web. Também estabelece requisitos como HTTPS, autenticação individual, pareamento de uso único, revogação de dispositivos, proteção contra CSRF e força bruta, limitação de requisições e acesso somente à API da plataforma.

Esses itens são requisitos registrados para a trilha de desenvolvimento. Não devem ser descritos como controles já implantados e homologados.

## Limites de exposição

A proposta de segurança determina que motores locais, banco de dados, arquivos e endpoints administrativos não sejam expostos diretamente à internet. O acesso remoto deve passar pela API protegida da plataforma.

## Dependências e condições operacionais

Na visão de servidor central:

- O computador central precisa estar ligado.
- O serviço da plataforma precisa estar ativo.
- O servidor precisa ter conectividade adequada.
- Os motores locais necessários precisam estar disponíveis.
- A autenticação e o canal remoto precisam estar implementados e validados antes do acesso externo.

## Fora do estado confirmado

Não declarar como concluídos: acesso remoto universal, sincronização entre dispositivos em produção, disponibilidade contínua, domínio público, relay operacional ou autenticação remota homologada.
