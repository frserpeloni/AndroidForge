# Índice de preservação garbage

## 2026-11-17, enumeração antiga FILE_ID_BOTH

| Origem original | Destino de preservação | Motivo | Evidência |
|---|---|---|---|
| `SERMAX-Windows/sermax_windows_handle_enum.py` | `garbage/SERMAX-Windows/sermax_windows_handle_enum.py` | Parser/enumeração antiga baseada em `FILE_ID_BOTH_DIR_INFO` e FileId de 64 bits. A implementação ativa usa `sermax_windows_directory_enum.py` com `FILE_ID_EXTD_DIR_INFO` e FileId de 128 bits. | Nenhum módulo de produção da árvore SERMAX importa o módulo antigo. O único import interno identificado estava no teste correspondente, também preservado abaixo. |
| `SERMAX-Windows/tests/test_sermax_windows_handle_enum.py` | `garbage/SERMAX-Windows/tests/test_sermax_windows_handle_enum.py` | Testes pertencem exclusivamente ao módulo antigo preservado. | A suíte ativa usa os testes de `sermax_windows_directory_enum.py` e `sermax_windows_directory_handle.py`. |

Os dois arquivos foram movidos por alteração de árvore Git, sem reescrita de conteúdo. Os blobs originais foram preservados. Nenhum arquivo foi apagado definitivamente.

Não importar nem executar arquivos deste diretório. A recuperação consiste em restaurar o blob ao caminho original em uma alteração revisada.
