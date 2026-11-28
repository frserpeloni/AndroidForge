# Roadmap do SERMAX

Este roadmap apresenta linhas de trabalho registradas. Não estabelece datas de entrega nem substitui a gestão técnica do desenvolvimento.

## 1. Revisão e homologação da candidata

- Revisar a candidata integrada da Plataforma.
- Validar fluxos completos no ambiente de destino.
- Confirmar comportamento com motores reais.
- Verificar persistência, recuperação e continuidade.
- Documentar limitações e critérios de aceite.

## 2. Preparação de instalação e atualização

- Fechar o contrato do pacote de produção.
- Definir assinatura e verificação de integridade.
- Validar backup, staging, instalação e rollback.
- Homologar preservação de memória, configurações e Terminal.
- Publicar instruções somente após aprovação.

## 3. Acesso remoto seguro

O PR #27 registra como etapas:

1. Documentar arquitetura, ameaças, autenticação, dependências e custos.
2. Implementar identidade, pareamento, credenciais e revogação.
3. Implementar canal remoto seguro.
4. Integrar autenticação e proteções à API.
5. Validar acesso por redes externas e dispositivos diferentes.
6. Liberar somente após aprovação dos gates de segurança.

## 4. Evolução da experiência multiplataforma

- Acesso por computador, Android e navegadores.
- Continuidade de conversas e projetos.
- Experiência coerente entre dispositivos.
- Operação centralizada no servidor definido pelo mantenedor.

Esses objetivos dependem da conclusão e homologação da infraestrutura remota.

## 5. Integrações futuras

Integrações adicionais devem passar por avaliação de escopo, segurança, licenças e autorização. SERMAX Drive Connect permanece fora do estado implementado descrito nesta documentação.

## Critério de atualização

Uma etapa só deve ser marcada como concluída quando houver evidência verificável, validação compatível com o risco e autorização de liberação. Não são estabelecidas datas neste documento.
