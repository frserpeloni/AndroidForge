# SERMAX: inspeção da interface de rede do Pestinha

**Estado:** inspeção estática de fonte. A rede ainda não foi executada nem integrada.

Fonte principal consultada: `pestinha/core/nervous_system.py` no repositório `mille-okws/pestinha`.

## Interface encontrada

O cabeçalho do módulo documenta a classe `Brain` e estes métodos:
- `stimulate({canal: intensidade_0_a_1})`, para entradas sensoriais;
- `step(dt_ms)`, para avançar a simulação;
- `motor_activity() -> {motor: Hz}`, para consultar atividade dos motores;
- `snapshot()`, para obter estado usado na representação visual;
- `save(path)` e `load(path)`, para persistência das sinapses.

O módulo importa NumPy, além de componentes compartilhados do Pestinha: `log`, `mathutil.valor_real` e `store.read_json/write_json`. Portanto, não é um arquivo independente que deva ser copiado sozinho. A rede tem dependências de suporte, e a persistência precisa ser isolada do arquivo de memória do SERMAX.

## Implicação para o adaptador SERMAX

A primeira prova de conceito deve trabalhar com uma instância isolada de `Brain` e uma lista fechada de eventos sintéticos. Não passar texto de conversas nem ler o histórico pessoal. Exemplos de estímulos permitidos no protótipo:
- `attention`: evento de início de tarefa;
- `processing`: tarefa em execução;
- `completed`: tarefa encerrada;
- `error`: tarefa falhou;
- `idle`: ausência de tarefa ativa.

Esses eventos são uma proposta de mapeamento, não equivalências já definidas pelo Pestinha. Os nomes de canais do Pestinha precisam ser mapeados com base no comportamento esperado e testados antes de adotar valores.

A saída da rede deve passar por uma camada de tradução que produza somente estados visuais permitidos para o widget. O widget não deve consumir diretamente todos os motores sem limites nem executar ações no Windows com base em saídas neurais.

## Decisões de isolamento

1. A rede não recebe acesso direto ao núcleo SERMAX, à memória principal, às credenciais ou ao conteúdo das conversas.
2. O estado aprendido do personagem fica em arquivo próprio, separado de `memoria_sermax.json`.
3. O widget continua funcional com animação básica caso a rede falhe.
4. O fechamento ou travamento da rede não encerra o terminal.
5. A execução deve ter limites de tempo e de consumo, definidos depois de medir o protótipo.
6. Não incorporar o código GPL ao executável distribuído antes de decidir formalmente como cumprir as obrigações da licença.

## Ainda não verificado

- Resultado de importar o módulo em ambiente limpo;
- versão mínima de NumPy realmente necessária;
- testes unitários do módulo executados nesta sessão;
- consumo real de CPU/RAM da rede isolada;
- portabilidade de persistência e caminhos para `C:\\SERMAX`;
- licença e compatibilidade do conjunto de dependências na distribuição final.

## Próxima etapa técnica

Obter o restante dos módulos `core/` e os testes correspondentes, identificar as dependências mínimas transitivas e montar uma prova de conceito isolada. Não alterar o terminal, o núcleo, o launcher ou o arquivo de memória nesta fase.
