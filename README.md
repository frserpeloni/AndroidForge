# SERMAX

**Uma plataforma de inteligência artificial com um núcleo central, MAX, e uma visão de acesso integrado entre dispositivos.**

> Estado do projeto: em desenvolvimento. Esta documentação não representa uma versão pública estável nem um produto pronto para instalação geral.

## O que é o SERMAX

SERMAX é um projeto de plataforma de inteligência artificial em desenvolvimento. Sua proposta é organizar conversas, projetos, tarefas, memória e integração com motores de IA em uma experiência unificada.

O projeto adota uma visão de núcleo central: MAX é a identidade do assistente e o núcleo inteligente que conduz a interação com o usuário. A plataforma busca oferecer uma interface comum para diferentes dispositivos, mantendo o processamento e os dados sob controle do ambiente central.

## Quem é MAX

MAX é o núcleo inteligente do SERMAX. Ele representa a camada de interação e coordenação do sistema. Sua responsabilidade conceitual é receber solicitações, considerar o contexto autorizado e encaminhar o trabalho aos recursos disponíveis.

Leia [Identidade e responsabilidades do MAX](docs/IDENTIDADE_MAX.md).

## Visão da plataforma

A visão de longo prazo prevê:

- Um computador central responsável pelo núcleo, pelos motores locais, pelos dados e pelos serviços.
- Clientes em computadores, celulares e navegadores.
- Conversas e projetos centralizados.
- Controle de acesso e sincronização entre dispositivos.
- Integração gradual de ferramentas e serviços.

Essa visão não significa que o acesso remoto pela internet esteja liberado. A candidata documentada no PR #24 permanece descrita como serviço local restrito a loopback, sem autenticação ou acesso remoto. A trilha de acesso remoto aparece como planejamento separado no PR #27.

## Estado do projeto

A documentação distingue quatro estados:

| Estado | Significado |
|---|---|
| Implementado em candidata | Existe código em branch ou PR, ainda sem liberação pública. |
| Em desenvolvimento | Trabalho em andamento, sujeito a revisão e validação. |
| Planejado | Diretriz aprovada ou proposta, ainda sem implementação comprovada. |
| Disponível publicamente | Versão oficialmente liberada e documentada para uso. |

Na consulta documental de 28/11/2026, a Plataforma SERMAX está registrada em uma candidata de revisão no PR #24, em rascunho e sem merge. Os recursos nela descritos não devem ser anunciados como uma versão pública liberada.

## Recursos documentados na candidata

O PR #24 descreve os seguintes componentes no código da candidata:

- Interface gráfica responsiva com áreas de Conversa, Projetos, Tarefas, Motores e Memória.
- API local baseada em FastAPI e histórico SQLite.
- Associação de conversas a projetos e contexto de projeto.
- Gerenciador de tarefas persistentes, sem execução automática em segundo plano.
- Painel de memória em modo somente leitura.
- Diagnóstico local dos motores.
- Respostas incrementais por streaming SSE.
- Anexos por conversa e extração de texto.
- OCR local opcional para imagens e PDFs digitalizados.

A presença desses componentes na candidata não comprova homologação completa no computador de destino, acesso remoto seguro ou disponibilidade pública. Consulte [Recursos e estado de implementação](docs/RECURSOS.md).

## Arquitetura e segurança

- [Visão geral](docs/VISAO_GERAL.md)
- [Arquitetura conceitual](docs/ARQUITETURA_CONCEITUAL.md)
- [Segurança e privacidade](docs/SEGURANCA.md)

O princípio editorial é não divulgar como concluído aquilo que ainda depende de implementação, homologação ou autorização.

## Instalação

Não há, nesta documentação, declaração de instalador público de produção. A candidata de plataforma e os artefatos de CI não equivalem a um instalador oficial. Consulte [Instalação e acesso](docs/INSTALACAO.md).

## Acompanhe o projeto

- [Repositório SERMAX / AndroidForge](https://github.com/frserpeloni/AndroidForge)
- [PR #24, candidata integrada da Plataforma](https://github.com/frserpeloni/AndroidForge/pull/24)
- [PR #27, trilha de acesso remoto](https://github.com/frserpeloni/AndroidForge/pull/27)
- [Histórico de alterações](CHANGELOG.md)
- [Como contribuir](CONTRIBUTING.md)

## Relação com AndroidForge

Este repositório tem histórico anterior associado ao AndroidForge, ferramenta de automação de builds Android. O README anterior foi preservado em [docs/ANDROIDFORGE.md](docs/ANDROIDFORGE.md). A documentação histórica permanece disponível e não foi apagada para apresentar o SERMAX.

## Licença

Consulte o arquivo `LICENSE` existente no repositório. A licença aplicável a cada componente integrado deve ser verificada antes de qualquer distribuição.
