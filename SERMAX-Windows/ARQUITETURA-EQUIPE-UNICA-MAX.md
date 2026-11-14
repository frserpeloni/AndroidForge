# SERMAX: equipe única de desenvolvimento coordenada pelo MAX

**Diretriz vigente:** uma única equipe de agentes desenvolve, programa, analisa, pesquisa, testa, corrige e evolui o código-fonte do SERMAX. A equipe opera no ambiente de desenvolvimento, fora do executável instalado. O SERMAX instalado recebe atualizações somente após implementação e validação.

## Papéis sob demanda

- **Programador:** propõe e implementa alterações em workspace isolado.
- **Analista:** inspeciona código, falhas, dependências e resultados.
- **Testador:** executa testes permitidos, reproduz falhas e verifica correções.
- **Pesquisador:** consulta documentação, APIs, licenças e fontes técnicas.

MAX coordena a fila e aciona somente os papéis necessários. Os papéis compartilham um único backend de modelo, trabalham sequencialmente por padrão e não mantêm modelos residentes separados. Paralelismo fica desativado até haver evidência de benefício sem pressão de RAM/CPU.

## Fora do executável SERMAX

A equipe de desenvolvimento não precisa ser empacotada no `SERMAX.exe`. Ela roda no ambiente de desenvolvimento, com acesso controlado à branch e aos ambientes de teste. O executável instalado mantém o serviço normal de assistência. As melhorias chegam à instalação por um processo de atualização aprovado, com backup e rollback.

## Componentes existentes reaproveitados

| Componente | Uso nesta diretriz |
|---|---|
| `sermax_planejador.py` | Reaproveitar conceitos de planejamento; hoje não altera arquivos. |
| `sermax_executor.py` | Reaproveitar validação de ações locais; hoje não edita código nem executa testes. |
| `sermax_tarefas.py` | Reaproveitar execução sequencial; hoje não mantém fila persistente. |
| OpenJarvis | Motor opcional/adaptador; worker atual usa agente `simple`, sem ferramentas/contexto próprios do SDK. |
| Pestinha | Subsistema comportamental e visual; memória neural continua separada. Não é agente programador. |

## Estado da implementação

Foi iniciado `sermax_dev_team.py`, supervisor externo com fila SQLite persistente, ativação sequencial dos quatro papéis e callback para um único modelo compartilhado. O worker em segundo plano processa uma tarefa por vez.

**Limite atual explícito:** o supervisor ainda não está conectado a um backend de modelo, GitHub, editor de workspace ou executor de testes. As respostas dos papéis são análises/propostas; este módulo não grava código, não executa testes e não faz commits. Portanto, não representa autonomia de desenvolvimento concluída.

## Próximas integrações necessárias

1. Adaptador de modelo compartilhado, com Jarvis opcional e fallback Ollama, sem carregar um modelo por agente.
2. Workspace isolado ligado à branch autorizada, com verificação de branch/HEAD antes de qualquer escrita.
3. Ferramentas restritas de leitura e edição de arquivos, com diff, limites de caminho/tamanho e rollback.
4. Executor de testes por lista permitida, sem shell arbitrário, com timeout e limites de recursos.
5. Verificador independente que avalia os resultados e bloqueia regressões.
6. Integração GitHub para registrar commits e resultados na branch de trabalho. Merge, release e escrita em `main` continuam exigindo aprovação humana.
7. Monitoramento em segundo plano no ambiente de desenvolvimento, com fila retomável e relatório de progresso.

## Proteções

- Não alterar `main`.
- Não escrever em `C:\\SERMAX`.
- Não alterar interface original, memória pessoal ou memória neural.
- Manter `memoria_sermax.json` e `memoria_neural_pestinha.json` separadas.
- Não habilitar ferramentas de shell, rede, MCP, skills ou escrita irrestrita sem avaliação específica.
- Não instalar nem publicar automaticamente.
- Distinguir sempre especificado, implementado, integrado, testado e validado no Windows real.
