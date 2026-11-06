# Auditoria de comparação do backup SERMAX

**Data da auditoria:** 02/11/2026  
**Branch analisada:** `sermax-windows-integration-20261029`  
**Commit da branch no início desta comparação:** `b65e83685f6be871f1848f8ac0298743073982e2`  
**Backup analisado:** `SERMAX bkp  28 10 26.zip`, arquivo local de 209 entradas.  
**Integridade ZIP:** `testzip()` retornou `None`. Isso verifica a integridade do arquivo compactado, não o funcionamento dos arquivos.

## Resultado objetivo

A cópia do terminal na raiz do backup é idêntica ao terminal na branch: o Git blob SHA de ambos é `9077ce5062d1541130ede8db519613d4d2ec8dfc`.

A cópia histórica em `SERMAX/BACKUPS/SERMAX_v3.3.0_REV4/20261027_181900/` é diferente. Não deve ser usada como substituição automática.

O núcleo, launcher, especificação e módulos de voz/comandos da raiz do ZIP têm hashes diferentes dos arquivos correspondentes na branch. Logo, não se deve copiar o backup inteiro por cima da branch, nem o contrário, sem comparação de conteúdo e de comportamento.

## Git blob SHA dos arquivos principais

| Arquivo | ZIP, raiz `SERMAX/` | Branch GitHub | Igual? |
|---|---|---|---|
| `sermax_core.py` | `e5f7081bb4db0e3ffda6166270dc9ae9a76c835a` | `c9039b5314520016fdc877cbcf3d99cb2a76f1f1` | Não |
| `sermax_launcher.py` | `594893328f474e1a95ba7cd96f1d3c9d1a6cc402` | `2b3267e50894f517e57fc8bea8c3eb10dbbb8c2d` | Não |
| `SERMAX.spec` | `9ce2853e43313d2ca3ef2045532829346390ca4a` | `483a6fd1d5c4fe8e20a89854dfc35a58af43f590` | Não |
| `SERMAX_terminal/sermax_terminal.py` | `9077ce5062d1541130ede8db519613d4d2ec8dfc` | `9077ce5062d1541130ede8db519613d4d2ec8dfc` | Sim |
| `SERMAX_terminal/sermax_integracao_comandos.py` | `dc675f3c466d5007b44d4d4520f5640967a70b39` | `4eda3f14e3633c27907674d5cd6533c939924efc` | Não |
| `SERMAX_terminal/sermax_voz.py` | `c27dbaf1eded27237f2610832fad0866f7effb2c` | `68ee5860ddf4f039005f76448940f7e982920d19` | Não |

Os hashes são identificadores de conteúdo Git, não avaliações de qualidade. Divergência não significa, por si só, que um arquivo esteja errado.

## Cópia histórica em BACKUPS

A cópia histórica `SERMAX/BACKUPS/SERMAX_v3.3.0_REV4/20261027_181900/` também diverge da branch nos arquivos verificados:

| Arquivo histórico | Git blob SHA calculado no ZIP |
|---|---|
| `sermax_core.py` | `1eeeeb88977f3057d9302343421921a86e7562da` |
| `sermax_launcher.py` | `df83e389ceae85218d46c44a5afb2321a9968982` |
| `SERMAX.spec` | `6438cb011bd1d9cb3c9be4bd0e6c8a4fceacc7c3` |
| `SERMAX_terminal/sermax_terminal.py` | `ead219c4a13601aa8f50275ee9ab5c697bac6c60` |
| `SERMAX_terminal/sermax_voz.py` | `f2d9aa8114ae91f3611d4d5cffd5a5af6214dad5` |

## Limite da conclusão

O ZIP analisado não tem uma pasta com o nome exato `SERMAX_CONSOLIDACAO_TECNICA_CANDIDATA_28-10-2026`. Portanto, esta auditoria compara a raiz do backup e uma cópia histórica interna, mas não comprova equivalência integral com a candidata nominal de referência.

## Próximas ações seguras

1. Obter o pacote exato da candidata nominal, ou uma lista oficial de hashes dela.
2. Comparar conteúdo linha a linha dos módulos divergentes, especialmente núcleo, launcher, especificação, voz e integração de comandos.
3. Registrar para cada diferença se deve ser preservada, reconciliada ou descartada, com justificativa e testes.
4. Manter o widget isolado até concluir a comparação e testar o protocolo.
5. Não instalar o artefato de CI sobre `C:\\SERMAX`; não mesclar a PR nem declarar release final nesta fase.
