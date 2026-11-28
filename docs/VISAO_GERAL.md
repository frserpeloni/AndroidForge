# Visão geral do SERMAX

## Propósito

SERMAX é um projeto de plataforma de inteligência artificial em desenvolvimento. Seu objetivo é reunir interação conversacional, contexto de projetos, tarefas, memória e acesso a motores de IA em uma experiência coordenada.

## Princípio de organização

O projeto adota a ideia de um núcleo inteligente central, MAX. A plataforma é a camada de interação e gestão que conecta o usuário ao núcleo e aos recursos disponíveis.

## Visão de uso

A visão de longo prazo prevê que o usuário acesse o mesmo ambiente por diferentes dispositivos, como computador, celular e navegador. O processamento, os dados e os motores permanecem concentrados no ambiente servidor definido pelo mantenedor.

Essa é uma visão arquitetural. Não deve ser interpretada como confirmação de que o acesso remoto pela internet está concluído.

## Princípios do projeto

1. **Continuidade:** preservar o contexto autorizado de conversas e projetos.
2. **Centralização:** manter o núcleo e os dados sob controle do servidor central.
3. **Modularidade:** integrar recursos por componentes com responsabilidades delimitadas.
4. **Segurança:** restringir o acesso a dados, motores e serviços administrativos.
5. **Transparência:** distinguir implementação, validação, homologação e liberação.
6. **Preservação:** proteger dados do usuário, memória, configurações e instalações existentes.

## Estado conhecido em 28/11/2026

A candidata consolidada da Plataforma está descrita no PR #24. O próprio registro informa que ela é uma consolidação para revisão, sem merge ou publicação. Também registra que o serviço permanece em loopback, sem autenticação ou acesso remoto.

A trilha de acesso remoto pela internet aparece no PR #27 como plano de trabalho, com requisitos de segurança e etapas de validação. Portanto, acesso público remoto não deve ser anunciado como disponível.

## O que o SERMAX não declara

Esta documentação não declara que:

- Existe uma versão pública estável pronta para uso geral.
- O acesso pela internet está liberado.
- Todos os motores escolhem agentes dinamicamente.
- Tarefas executam automaticamente em segundo plano.
- O atualizador ou instalador de produção está liberado.
- O SERMAX Drive Connect está implementado.
