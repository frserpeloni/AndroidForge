# SERMAX Widget: arquitetura proposta

**Estado:** contrato de estados implementado e validado pelo CI; widget visual e rede neural ainda não integrados. Não aprovado para release.  
**Referências obrigatórias:** `SERMAX_CONSOLIDACAO_TECNICA_CANDIDATA_28-10-2026` e backup `SERMAX bkp 28 10 26.zip`.

## Objetivo

Adicionar um widget animado do SERMAX na área de trabalho do Windows sem substituir o terminal original, o núcleo, a memória persistente, a voz ou a integração com Ollama.

## Decisões de segurança

1. O widget será um módulo independente. O terminal atual permanece como interface principal e não deve ser reescrito para introduzir o widget.
2. O contrato de estados está implementado em `sermax_widget_state.py`. Ele não inicia rede neural e não lê conversas.
3. Não copiar código, personagens, imagens, memes ou outros recursos do Pestinha nesta etapa. A licença do código é GPL-3.0; a documentação de assets exige que imagens redistribuídas tenham licença compatível. Fazer uma revisão jurídica e de compatibilidade antes de qualquer reutilização.
4. Não tocar em `memoria_sermax.json` nem nos arquivos de memória existentes.
5. Não executar atualização automática nem substituir arquivos da instalação `C:\\SERMAX` nesta etapa.
6. Não publicar release nem mesclar a PR com base apenas em CI.

## Implementação registrada

- `sermax_widget_state.py`: controlador independente que converte eventos conhecidos em cinco estados visuais permitidos: `idle`, `attention`, `processing`, `completed` e `error`.
- `tests/test_sermax_widget_state.py`: testes para estado inicial, eventos permitidos, entradas inválidas e rejeição de saídas que não sejam estados visuais.
- O método `accept_neural_output` define uma fronteira restritiva para uma futura rede. Ele não conecta nem executa a rede neural do Pestinha.
- O módulo não importa o núcleo SERMAX, não lê o histórico e não acessa arquivos de memória.

## Arquitetura pretendida

- **Processo do widget:** módulo visual separado, preferencialmente usando Tkinter, que faz parte da distribuição padrão do Python. A escolha final depende do teste de transparência, arraste, foco, múltiplos monitores e empacotamento no Windows.
- **Terminal e núcleo:** continuam sendo responsáveis por comandos, Ollama, memória e execução de tarefas.
- **Contrato de estado:** estados permitidos listados acima. O widget não deve inferir o estado lendo o texto completo das conversas.
- **Comunicação local:** avaliar arquivo JSON de estado com escrita atômica versus IPC local. Não armazenar prompts, respostas, dados pessoais ou conteúdo da memória nesse canal.
- **Controles:** abrir terminal, ocultar/mostrar widget, mover pela tela e encerrar o widget sem encerrar o núcleo ou apagar a memória.
- **Recursos visuais:** desenhados para o SERMAX ou licenciados de forma verificável. Preservar o rosto encapuzado verde já existente no terminal.

## Testes obrigatórios antes da integração

### Automatizados
- validação e rejeição de estados inválidos;
- leitura de arquivo ausente, vazio, truncado e versão desconhecida, caso seja adotado protocolo por arquivo;
- atualização atômica do estado, caso seja adotado protocolo por arquivo;
- nenhuma gravação na memória persistente;
- controles de mostrar, ocultar e abrir terminal sem iniciar ou encerrar o núcleo por engano;
- inclusão do módulo e dos recursos no build PyInstaller.

### No Windows do mantenedor
- aparência e transparência reais;
- arrastar, reposicionar e comportamento em múltiplos monitores;
- abrir/ocultar terminal;
- funcionamento com Ollama disponível e indisponível;
- memória e comandos preservados após reinício;
- consumo medido de RAM e CPU durante repouso e animação;
- fechamento do widget sem perda de memória nem encerramento indevido do SERMAX.

## Bloqueios conhecidos

- A comparação integral com a candidata de referência continua pendente. O ZIP disponível contém uma cópia principal do terminal idêntica à branch, mas uma cópia histórica diferente dentro de `BACKUPS/SERMAX_v3.3.0_REV4/20261027_181900/`. Não tratar a cópia histórica como fonte aprovada sem confirmar a referência.
- A CI passou para o commit que inclui o contrato e seus testes. Isso valida sintaxe, testes automatizados e build do executável no ambiente do GitHub, mas não substitui os testes funcionais no computador do mantenedor.
- O widget visual ainda não foi implementado. A rede neural do Pestinha não foi executada nem integrada.

## Próxima etapa

Implementar o widget visual mínimo usando o contrato de estados, mantendo-o fora do fluxo de inicialização padrão até os testes passarem. Em paralelo, definir uma via de execução isolada para avaliar a rede real do Pestinha, após revisar as dependências e a compatibilidade da licença. A integração só deve ocorrer depois de medir consumo e confirmar que falhas não afetam terminal, Ollama ou memória.
