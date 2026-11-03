# Integração Pestinha no SERMAX

**Branch de trabalho:** `sermax-pestinha-full-integration-20261103`  
**Referência SERMAX preservada:** `SERMAX_CONSOLIDACAO_TECNICA_CANDIDATA_28-10-2026`  
**Estado:** integração em desenvolvimento, sem release e sem alteração da instalação local.

## Conteúdo incorporado

O código-fonte Python do Pestinha foi preservado em `sermax_pestinha/pestinha/`, com as camadas:

- `core/`: rede LIF, condicionamento, emoção, memória episódica, homeostase, controle motor, física e protesto.
- `sense/`: interpretação de estímulos e registro de rotina.
- `plataforma/`: adaptadores Windows, Linux e macOS.
- `body/`: estado, comportamento, corpo, bolinha e animação.
- `mind/`: sono, festa, travessuras, protesto, revolução e controladores.
- `world/`: objetos, notebook, cartazes, fogos e elementos de interação.
- `ui/`: configurações, bandeja, monitor neural, painéis e onboarding.
- `controle/` e `app.py`: sessão, interação e composição do aplicativo.

A entrada original `main.py` foi substituída por `sermax_pestinha_launcher.py`, que importa o pacote pelo namespace isolado do SERMAX. O comando `/pestinha` inicia essa interface em outro processo, sem fechar o terminal principal.

## Integração cognitiva

`sermax_cognitive.py` conecta ao SERMAX:

- LIFBrain e MotorDecoder.
- Drives e canais internos de homeostase.
- EmotionState e MotorTone.
- Conditioning e memória episódica.
- Reforço neural e persistência de estado.
- Resumo cognitivo enviado ao contexto do Ollama.

O núcleo SERMAX continua responsável pela conversa, planejamento e execução autorizada. O resultado neural informa o contexto e não executa comandos do sistema operacional.

## Memórias e permissões

A memória pessoal existente `memoria_sermax.json` permanece separada e intocada.

O estado neural fica em `sermax_pestinha_state/`, com arquivos próprios para rede, necessidades, condicionamento, episódios, preferências e permissões sensoriais.

Na interface complementar, os sensores de programa ativo, mouse/teclado, tela cheia, janelas e rotina começam desligados. Cada permissão pode ser ativada individualmente. O código não lê títulos nem conteúdo de janelas, páginas, documentos ou conversas.

A interface complementar preserva os recursos de interação do Pestinha. O terminal ASCII verde do SERMAX continua sendo a interface principal.

## Recursos visuais e direitos

A licença GPL-3.0-or-later do código-fonte foi incluída. A distribuição do SERMAX com esse código exige cumprir as obrigações aplicáveis da GPL, inclusive disponibilizar o código-fonte correspondente e os avisos de licença.

Os arquivos binários de imagens do Pestinha não foram copiados. O próprio projeto exige imagens próprias ou com licença que permita redistribuição. A interface possui desenhos de fallback; assets adicionais dependem de confirmação de direitos.

O repositório do Pestinha não apresenta um subsistema autônomo de áudio. A voz já existente do SERMAX permanece separada e preservada.

## Testes e gates

A CI dedicada compila o código, executa os testes cognitivos e monta o executável Windows com as dependências do Pestinha.

A aprovação da CI comprova compilação e testes no runner Windows. Não comprova ainda execução manual do executável no computador do mantenedor, comportamento visual, interação real, atualização, rollback ou persistência após reinício nesse computador.

A PR #2 permanece aberta em rascunho. Esta branch não foi mesclada à principal. Nenhuma alteração foi feita em `C:\\SERMAX` nem no backup oficial.
