# SERMAX: avaliação técnica da rede neural do Pestinha

**Estado:** análise de viabilidade. Nenhum código do Pestinha foi copiado para o SERMAX. Nenhuma rede neural foi integrada ou executada nesta etapa.

## Resumo executivo

A integração é tecnicamente plausível, mas não deve consistir em copiar os 470 neurônios para dentro do núcleo atual sem adaptação. O Pestinha tem arquitetura em camadas e sua rede neural está ligada a módulos de sensação, homeostase, memória, condicionamento, estado corporal e controladores de comportamento. O widget SERMAX precisa de uma interface menor e explícita.

A recomendação é avaliar um adaptador independente entre o SERMAX e uma camada comportamental, mantendo Ollama como modelo de linguagem e preservando terminal, memória e comandos existentes.

## O que a documentação do Pestinha informa

Fonte: README, `pestinha/README.md`, `docs/ARQUITETURA.md`, `docs/REDE_NEURAL.md`, `pestinha/core/README.md` e `requirements.txt` no repositório oficial.

- Rede LIF com 470 neurônios, 15.939 sinapses, 30 canais sensoriais, 10 populações de interneurônios e 15 populações motoras.
- A rede recebe canais sensoriais normalizados e sinais internos como tédio, fadiga e antecipação.
- Os motores influenciam expressões e decisões do personagem.
- O projeto combina saídas da rede com regras explícitas. Nem toda decisão é tomada pela rede.
- O aprendizado documentado inclui uma regra de três fatores para carinho/recompensa e condicionamento Rescorla-Wagner fora da rede.
- O estado aprendido é salvo localmente, incluindo rede, homeostase, memória episódica e condicionamento.
- O núcleo `pestinha/core/` é descrito como independente de Qt e de APIs do sistema, mas o aplicativo completo usa PySide6.

## Dependências e impacto potencial

O `requirements.txt` do Pestinha inclui PySide6, psutil, NumPy e dependências condicionais por sistema operacional. O aplicativo completo usa temporizadores Qt para ciclos de desenho, pensamento e leitura de contexto. A rede central pode ser separável da interface, mas isso precisa ser confirmado pela análise e execução dos módulos concretos.

Não se deve assumir que o custo de cerca de 70 MB informado pelo projeto seja o consumo da rede isolada, nem que será o consumo dentro do SERMAX. Precisamos medir o processo isolado e a combinação final no Windows.

## Arquitetura de integração proposta

```text
SERMAX Terminal / SERMAX Core
        | eventos limitados e explícitos
        v
Adaptador comportamental SERMAX
        |
        +--> rede LIF isolada
        |       |
        |       +--> atenção / curiosidade / calma / fadiga
        |       +--> sinal de decisão comportamental
        |       +--> estado aprendido próprio do widget
        |
        v
Widget SERMAX (rosto verde e animações)
```

O adaptador é uma camada proposta, não código já existente. Ele deve impedir que o módulo neural acesse diretamente `memoria_sermax.json`, histórico de conversas, prompts, respostas ou credenciais do SERMAX.

## Limites de responsabilidade

**Ollama e núcleo SERMAX:** linguagem, respostas, comandos e tarefas existentes.

**Rede pulsada:** comportamento do personagem, modulação de atenção e escolha de expressões. Não substituirá o modelo de linguagem nem será apresentada como capaz de conversar por conta própria.

**Widget:** renderização, movimento, controles de abrir/ocultar e exibição de estados. Se a rede falhar, o widget deve cair em animação básica e o terminal deve continuar funcional.

## Plano de protótipo isolado

1. Fixar o commit exato do Pestinha usado na análise e registrar a licença.
2. Ler o módulo concreto da rede e suas interfaces de entrada/saída, junto aos módulos de estado e persistência necessários.
3. Executar testes de unidade do núcleo neural sem iniciar a interface Qt nem ler dados do computador.
4. Construir um adaptador com eventos sintéticos, por exemplo: SERMAX em repouso, iniciou tarefa, concluiu tarefa e encontrou erro.
5. Validar que entradas inválidas, atrasos e falhas do adaptador não afetam o núcleo SERMAX.
6. Medir RAM e CPU com a rede isolada e com o widget, em repouso e durante atividade.
7. Só depois avaliar integração na branch e incluir os módulos necessários no empacotamento.

## Testes necessários

### Automatizados, ambiente isolado
- estabilidade dos estados e saídas para entradas sintéticas;
- persistência e recarga do estado próprio da rede;
- recuperação de estado corrompido sem sobrescrever dados originais;
- limites de frequência e tratamento de atraso;
- ausência de acesso à memória principal do SERMAX;
- fallback visual quando a rede não inicializa;
- build e testes no Windows CI.

### Windows do mantenedor
- desempenho e RAM reais;
- widget em segundo plano, arraste, transparência e múltiplos monitores;
- convivência com Ollama, terminal, voz e comandos;
- reinício do aplicativo sem perda da memória SERMAX;
- teste de falha e encerramento isolado da rede;
- verificação de que a rede não lê títulos/conteúdo de janelas nem outros dados além dos eventos autorizados.

## Licença

O repositório declara GPL-3.0. Se houver incorporação ou adaptação de código do Pestinha no produto distribuído, é necessário avaliar as obrigações da GPL, incluindo disponibilização do código-fonte correspondente e manutenção dos avisos de licença. A documentação de assets do próprio projeto diz para redistribuir somente imagens próprias ou com licença que permita redistribuição. Não copiar imagens, personagens, memes ou outros recursos sem licença verificada.

Uma implementação independente baseada em conceitos gerais também exige cuidado para não copiar trechos protegidos do código. Esta nota não substitui revisão jurídica.

## Situação e próximo passo

- Arquitetura neural documentada: analisada em nível de documentação.
- Módulo concreto da rede executado isoladamente nesta sessão: não executado.
- Dependências instaladas e consumo medido: não executado.
- Código de integração escrito: não.
- Widget integrado ao SERMAX: não.
- Testes Windows reais: não executados.

Próxima etapa: examinar os módulos concretos em `pestinha/core/` e determinar a interface mínima para uma prova de conceito isolada. Não incorporar dependências nem alterar o núcleo SERMAX até essa análise terminar.
