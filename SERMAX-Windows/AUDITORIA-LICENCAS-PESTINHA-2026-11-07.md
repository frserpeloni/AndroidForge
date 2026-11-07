# Auditoria técnica de licenças do Pestinha no SERMAX
Data da consulta: 2026-11-07
Escopo: inspeção documental e de empacotamento. Não constitui parecer jurídico.

## 1. Identificação da dependência

- Repositório upstream: https://github.com/mille-okws/pestinha
- Commit fixado no projeto: `1b16bd21bb5ba9dd4c460c153f865824f53d05c8`
- O commit upstream existe e identifica a versão 0.7.0 no `pyproject.toml`.
- O metadado de licença upstream declara `GPL-3.0-or-later`.
- O repositório upstream contém o texto integral da GPLv3 em `LICENSE`.
- O projeto SERMAX mantém uma cópia do texto em `THIRD_PARTY_NOTICES/Pestinha-GPL-3.0.txt` e uma ficha de origem em `THIRD_PARTY_NOTICES/Pestinha-ORIGIN.md`.

## 2. Distinção entre código e materiais visuais

O README upstream declara que o código Pestinha está sob GPL-3.0-or-later, mas que as imagens e os textos em `assets/` não estão cobertos por essa licença.

O arquivo upstream `assets/LEIA-ME.txt` orienta que, para publicação, sejam usadas imagens próprias ou imagens cuja licença permita redistribuição.

Consequência técnica: a licença GPL do código não comprova autorização para redistribuir imagens, memes, cartazes, textos ou outros materiais visuais do projeto. Cada material externo exige identificação de autoria e licença própria, ou comprovação de autorização.

## 3. O que o empacotamento SERMAX demonstra

Inspecionado `SERMAX-Windows/SERMAX.spec` na branch `sermax-windows-integration-20261029`.

- O spec chama `collect_all("pestinha")`, que coleta arquivos do pacote Python instalado e seus recursos reconhecidos pelo PyInstaller.
- O spec inclui explicitamente o texto GPL e a ficha de origem em `THIRD_PARTY_NOTICES`.
- O spec não lista as pastas upstream `assets/` nem `pets/` como dados adicionais.
- Portanto, a configuração inspecionada não demonstra inclusão dos personagens, imagens, cartazes ou memes externos do repositório Pestinha no executável SERMAX.
- A integração SERMAX observada importa `pestinha.core.nervous_system.LIFBrain` e usa a rede para mapear eventos a estados visuais. Isso não equivale a incorporar a aplicação completa de pet de tela.

Limite: a análise do spec não substitui a inspeção do conteúdo do executável final. O build atual deve continuar sendo verificado por inventário do pacote gerado.

## 4. Obrigações e verificações para distribuição binária

A GPLv3, em especial as seções 4, 5 e 6, estabelece condições para redistribuição de cópias e de formas não-fonte. A definição de Corresponding Source inclui o código necessário para gerar, instalar, executar e modificar o executável, incluindo scripts de controle dessas atividades, ressalvadas as exclusões previstas na licença.

A FAQ oficial da Free Software Foundation esclarece que o código-fonte disponibilizado deve corresponder à versão binária distribuída, e que o acesso ao fonte deve ser equivalente ao acesso ao binário quando usada a modalidade de oferta em rede.

Fontes oficiais consultadas:
- GPLv3, Free Software Foundation: https://www.gnu.org/licenses/gpl.en.html
- GPL FAQ, Free Software Foundation: https://www.gnu.org/licenses/gpl-faq.en.html

Antes de publicar um binário SERMAX que contenha Pestinha, verificar e registrar:
1. O código-fonte exato correspondente ao commit upstream fixado e às modificações efetivamente incorporadas.
2. O código SERMAX que forma a integração, os arquivos de configuração, o spec e os scripts necessários para gerar e instalar o binário.
3. O mecanismo de acesso ao fonte correspondente, com instrução clara junto ao binário e disponibilidade mantida enquanto o binário for oferecido.
4. A preservação dos avisos de copyright, licença e ausência de garantia aplicáveis.
5. A análise da combinação do código GPL com os demais componentes do SERMAX. Não presumir que a inclusão de uma dependência GPL em um executável maior seja juridicamente neutra.
6. A separação de quaisquer materiais visuais/textuais não cobertos pela GPL e a comprovação de direitos para redistribuição desses materiais.

## 5. Situação da auditoria

- Texto da GPL incluído no repositório SERMAX: confirmado.
- Origem e commit upstream registrados: confirmado.
- Código GPL incorporado ao build: indicado pelo spec e pela dependência fixada; o conteúdo final do binário ainda requer inventário.
- Corresponding Source integral e mecanismo de fornecimento junto a uma futura distribuição: pendente de validação.
- Direitos de redistribuição de imagens e textos de assets: não comprovados; não incluir esses materiais em uma distribuição até resolver a origem/licença.
- Parecer sobre compatibilidade jurídica do executável combinado: pendente de análise especializada.

## 6. Decisão técnica provisória

Manter a integração Pestinha restrita ao componente de rede LIF e aos arquivos de código necessários. Não adicionar as pastas `assets/` ou `pets/` ao pacote SERMAX sem inventário e autorização documentada. Não publicar uma versão binária final até concluir as verificações de fonte correspondente e licenciamento dos componentes combinados.

Esta auditoria registra evidências técnicas consultadas em 2026-11-07. Não altera código funcional, interface, memória pessoal ou instalação local do usuário.
