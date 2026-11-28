# Instalação e acesso

## Estado atual da documentação

Este documento não oferece um instalador público de produção. A candidata da Plataforma SERMAX registrada no PR #24 é material de revisão, não uma release oficial.

Artefatos produzidos por CI, executáveis de validação e branches de desenvolvimento não devem ser tratados como instaladores prontos para distribuição.

## Ambiente de homologação

Os registros de desenvolvimento mencionam homologação local em Windows 11 e execução da API local. Esses registros descrevem ambientes de teste e não constituem instruções de instalação pública.

## Acesso por outros dispositivos

O acesso remoto pela internet ainda não deve ser anunciado como disponível. O PR #24 descreve o serviço restrito a loopback, sem autenticação ou acesso remoto.

O PR #27 documenta uma trilha de desenvolvimento para acesso remoto seguro. A liberação depende da implementação e validação dos controles de segurança e dos testes em redes externas.

## Quando haverá instruções de instalação

As instruções públicas deverão ser publicadas somente após:

- pacote de produção definido;
- assinatura e integridade verificáveis;
- procedimento de instalação validado;
- backup e rollback comprovados;
- homologação em Windows 11;
- documentação dos requisitos e limitações;
- autorização formal de liberação.

## Orientação ao visitante

Até que esses critérios sejam atendidos e uma versão oficial seja publicada, não baixe artefatos experimentais de CI como se fossem instaladores de produção.
