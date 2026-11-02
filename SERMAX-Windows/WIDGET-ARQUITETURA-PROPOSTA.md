# SERMAX Widget: arquitetura proposta

**Estado:** proposta técnica, ainda não integrada nem aprovada para release.  
**Referências obrigatórias:** `SERMAX_CONSOLIDACAO_TECNICA_CANDIDATA_28-10-2026` e backup `SERMAX bkp 28 10 26.zip`.

## Objetivo

Adicionar um widget animado do SERMAX na área de trabalho do Windows sem substituir o terminal original, o núcleo, a memória persistente, a voz ou a integração com Ollama.

## Decisões de segurança

1. O widget será um módulo independente. O terminal atual permanece como interface principal e não deve ser reescrito para introduzir o widget.
2. O widget não inicia uma segunda rede neural na primeira etapa. As expressões visuais respondem a estados explícitos do SERMAX.
3. Não copiar código, personagens, imagens, memes ou outros recursos do Pestinha nesta etapa. A licença do código é GPL-3.0; a documentação de assets exige que imagens redistribuídas tenham licença compatível. Fazer uma revisão jurídica e de compatibilidade antes de qualquer reutilização.
4. Não tocar em `memoria_sermax.json` nem nos arquivos de memória existentes.
5. Não executar atualização automática nem substituir arquivos da instalação `C:\\SERMAX` nesta etapa.
6. Não publicar release nem mesclar a PR com base apenas em CI.

## Arquitetura inicial sugerida

- **Processo do widget:** módulo visual separado, preferencialmente usando Tkinter, que faz parte da distribuição padrão do Python. A escolha final depende do teste de transparência, arraste, foco, múltiplos monitores e empacotamento no Windows.
- **Terminal e núcleo:** continuam sendo responsáveis por comandos, Ollama, memória e execução de tarefas.
- **Contrato de estado:** mensagens pequenas e versionadas, com estados permitidos `idle`, `attention`, `processing`, `completed` e `error`. O widget não deve inferir o estado lendo o texto completo das conversas.
- **Comunicação local:** avaliar um arquivo JSON de estado com escrita atômica e leitura tolerante a arquivo ausente ou incompleto. Antes da implementação, comparar essa opção com IPC local. Não armazenar prompts, respostas, dados pessoais ou conteúdo da memória nesse canal.
- **Controles:** abrir terminal, ocultar/mostrar widget, mover pela tela e encerrar o widget sem encerrar o núcleo ou apagar a memória.
- **Recursos visuais:** desenhados para o SERMAX ou licenciados de forma verificável. Preservar o rosto encapuzado verde já existente no terminal.

## Contrato de estado proposto

Cada atualização deve conter somente:
- versão do protocolo;
- estado visual permitido;
- instante da atualização;
- identificador de tarefa não pessoal, se necessário.

O widget deve ignorar versões desconhecidas, estados inválidos e mensagens antigas. Se o núcleo não estiver disponível, o widget permanece em repouso e não bloqueia o terminal.

## Testes obrigatórios antes da integração

### Automatizados
- validação e rejeição de estados inválidos;
- leitura de arquivo ausente, vazio, truncado e versão desconhecida;
- atualização atômica do estado;
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
- A CI da branch passou, mas não substitui os testes funcionais no computador do mantenedor.
- Nenhum widget foi implementado ou integrado por este documento.

## Próxima etapa

Obter e comparar os arquivos oficiais da candidata de 28/10 com o núcleo e os módulos atuais. Depois, implementar o contrato de estado e os testes isolados, mantendo o widget fora do fluxo de inicialização padrão até que os testes passem.
