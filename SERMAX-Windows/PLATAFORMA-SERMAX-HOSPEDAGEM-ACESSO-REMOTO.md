# SERMAX Platform, avaliação de hospedagem e acesso remoto

**Estado:** análise técnica preliminar, não implementada.
**Branch:** `sermax-windows-integration-20261029`.
**Data da pesquisa:** 14/11/2026.
**Dependência:** `PLATAFORMA-SERMAX-ARQUITETURA-GUI.md` e `PLATAFORMA-SERMAX-API-CONTRATO-PRELIMINAR.md`.

## 1. Separar duas funções

A Plataforma SERMAX tem duas necessidades distintas:

1. **Servidor da plataforma:** autenticação, API, conversas, projetos, arquivos, memória, sincronização e interface.
2. **Motor de IA:** execução de Ollama/modelos locais e integração com motores externos.

Um VPS econômico pode hospedar API e banco, mas não deve ser tratado como substituto automático de uma máquina capaz de executar os modelos locais. A inferência local exige RAM, CPU e, conforme o modelo, GPU adequadas.

## 2. Opções de hospedagem

| Opção | Custos | Vantagens | Limitações |
|---|---|---|---|
| PC principal como servidor | Sem mensalidade de VPS. Energia, internet e eventual upgrade de hardware | Mantém Ollama e núcleo local; dados sob controle local | Depende de energia, internet, disponibilidade e desempenho do PC |
| Servidor dedicado próprio | Aquisição, energia, manutenção e internet | Controle físico e disponibilidade melhor se dedicado | Investimento inicial, manutenção e segurança ficam por conta do proprietário |
| VPS/nuvem | Mensalidade recorrente, armazenamento, tráfego e possíveis extras | Disponibilidade e acesso remoto mais simples; separa serviço do PC de uso diário | Custo contínuo; VPS comum não executa necessariamente modelos locais com desempenho adequado |
| Híbrido | VPS ou túnel para acesso/API, motor local no PC principal | Separa disponibilidade da interface e inferência local | Mais componentes, segurança e sincronização mais complexas |

### 2.1 PC principal

É a opção de menor custo recorrente de hospedagem e preserva o desenho de cérebro central local. O computador precisa permanecer ligado e conectado para que os clientes remotos acessem o MAX.

O custo de energia deve ser medido, não estimado sem dados:
`kWh/mês = potência média em watts × horas ligadas ÷ 1000`.
`Custo mensal = kWh/mês × tarifa final por kWh`.

A medição deve ser feita com wattímetro ou telemetria confiável durante carga real. O consumo do computador ocioso e sob inferência pode ser diferente.

**Risco específico:** a máquina atual descrita no histórico tem limite de 8 GB de RAM e HDD. Isso não comprova capacidade para hospedar simultaneamente API, banco, interface e inferência de modelos com desempenho satisfatório. Antes de escolher o PC como host permanente, será necessário medir recursos e testar concorrência. O PC pode servir como ambiente inicial de desenvolvimento, mas a capacidade de produção permanece não validada.

### 2.2 Servidor dedicado próprio

Faz sentido se houver uma máquina separada com memória, armazenamento e disponibilidade adequados. Evita competir com o computador de uso diário. Exige avaliar consumo, ruído, refrigeração, falhas de disco, cópias de segurança, internet e acesso remoto.

Não há inventário de um servidor dedicado disponível neste momento. Não é possível afirmar custo ou capacidade.

### 2.3 VPS/nuvem

Como referência de mercado, a tabela oficial de ajuste de preços da Hetzner para junho de 2026 informa, para regiões Alemanha/Finlândia, preços mensais sem IVA de:
- CX23: €5,49.
- CX33: €8,49.
- CX43: €15,99.

Esses valores são referência de um fornecedor e região específicos, não cotação final para o SERMAX. Impostos, IPv4, armazenamento adicional, tráfego, câmbio e condições comerciais devem ser verificados no momento da contratação. Os planos compartilhados não são recomendação para inferência de IA local.

## 3. Acesso remoto seguro

### 3.1 Tailscale

A página oficial informa plano Personal gratuito para até seis usuários e dispositivos de usuário ilimitados. A documentação descreve o plano gratuito como destinado a uso pessoal não comercial. A elegibilidade do uso concreto do SERMAX deve ser confirmada antes de adotar essa opção.

Vantagem: conectar PC servidor e dispositivos autorizados em rede privada, sem publicar diretamente a API na internet.

Limite: depende de conta e serviço de terceiro. A disponibilidade do plano e seus termos precisam ser reavaliados antes de produção.

### 3.2 Cloudflare Tunnel

A documentação oficial informa disponibilidade em todos os planos e conexão de saída do servidor, sem exigir IP público nem portas de entrada abertas. É uma opção para publicar uma aplicação através da rede Cloudflare.

Distinção importante: Tunnel para aplicação publicada não equivale, por si só, a uma VPN privada entre dispositivos. Exige autenticação forte na aplicação e avaliação de exposição, regras de acesso, privacidade e dependência do fornecedor.

### 3.3 Recomendação preliminar

Para acesso privado entre dispositivos próprios, avaliar primeiro uma malha VPN privada como Tailscale, condicionada aos termos de uso aplicáveis. Não abrir portas do roteador para a API administrativa.

Cloudflare Tunnel fica como alternativa se houver decisão de publicar a interface por domínio, com autenticação e controles adicionais. Não misturar acesso público e administrativo.

## 4. Comparação para o SERMAX

| Critério | PC principal | Servidor dedicado | VPS/híbrido |
|---|---|---|---|
| Mensalidade de hospedagem | Não | Não, se próprio | Sim |
| Energia | Sim | Sim | Incluída no provedor |
| Ollama local | Sim, se hardware suportar | Sim, se hardware suportar | Só com instância adequada; GPU eleva custo |
| Disponibilidade | Depende do PC doméstico | Depende da infraestrutura local | Geralmente melhor, conforme provedor |
| Controle dos dados | Alto | Alto | Compartilhado com fornecedor |
| Acesso Android | Pela rede local ou VPN | Pela rede local ou VPN | Pela internet, com segurança |
| Manutenção | Fabiano | Fabiano | Compartilhada com provedor |
| Dependência externa | Internet e VPN | Internet e VPN | Provedor, rede e cobrança |

## 5. Direção recomendada por fases

**Fase de desenvolvimento:** usar o PC atual apenas como ambiente de desenvolvimento e prova de conceito, sem prometer desempenho de produção.

**Primeira validação de rede:** testar acesso privado dentro da rede local. Depois, testar VPN entre computador e Android, sem publicar a API na internet.

**Decisão de produção:** comparar medições do PC atual com uma máquina dedicada ou VPS. Se o computador atual não sustentar o serviço e o Ollama ao mesmo tempo, separar o serviço web do motor de IA ou planejar upgrade de hardware.

**Não contratar VPS neste estágio.** Primeiro medir demanda, memória, CPU, disco, disponibilidade e consumo de energia.

## 6. Plano de medições antes da escolha

No computador que hospedará o núcleo:
1. Identificar CPU, RAM disponível, tipo e saúde do disco.
2. Medir memória e CPU em repouso.
3. Medir durante resposta do Ollama.
4. Medir durante API, banco e interface simultâneos.
5. Testar uma conexão Windows e uma Android na rede local.
6. Testar desconexão e reconexão sem perda ou duplicação de mensagens.
7. Medir consumo elétrico por wattímetro, se disponível.
8. Confirmar backup e restauração do banco de plataforma.

Nenhum desses testes foi executado nesta etapa.

## 7. Decisões ainda abertas

- Host de produção.
- Se haverá upgrade do PC atual ou máquina dedicada.
- Uso comercial ou exclusivamente pessoal para determinar elegibilidade de plano VPN.
- Acesso remoto exclusivamente privado ou interface pública.
- Região do provedor e requisitos de residência dos dados.
- Banco de dados e política de backup.
- Capacidade real do Ollama em hardware escolhido.

## 8. Fontes consultadas

- Tailscale, preços e limites do plano Personal: https://tailscale.com/pricing
- Tailscale, condições de planos gratuitos: https://tailscale.com/docs/reference/free-plans-discounts
- Cloudflare, documentação do Tunnel: https://developers.cloudflare.com/tunnel/
- Hetzner, ajuste oficial de preços em junho de 2026: https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/

## 9. Limites desta análise

Esta é uma comparação documental. Não houve contratação, instalação, alteração de rede, medição de hardware, teste de VPN ou implantação de servidor. Nenhum dado pessoal ou arquivo de runtime foi movido. A escolha final de hospedagem permanece pendente de medições e aprovação de Fabiano.
