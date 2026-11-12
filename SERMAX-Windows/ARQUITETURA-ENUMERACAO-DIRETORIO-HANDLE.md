# Parser isolado de FILE_ID_BOTH_DIR_INFO

O módulo `sermax_windows_directory_enum.py` valida buffers retornados pela classe 10 (`FileIdBothDirectoryInfo`) de `GetFileInformationByHandleEx`. Ele não chama APIs nativas e não percorre diretórios.

## Layout validado

- `NextEntryOffset`: 0
- `FileIndex`: 4
- Tempos: 8, 16, 24 e 32
- `EndOfFile`: 40
- `AllocationSize`: 48
- `FileAttributes`: 56
- `FileNameLength`: 60
- `EaSize`: 64
- `ShortNameLength`: 68
- `ShortName`: 70, até 24 bytes
- `FileId`: 96
- `FileName`: 104

O cabeçalho fixo ocupa 104 bytes. Cada nome é UTF-16LE, com comprimento par, positivo e limitado a 255 unidades UTF-16. Entradas intermediárias exigem `NextEntryOffset` alinhado em 8 bytes, sem sobreposição e dentro do buffer. A última entrada usa offset zero.

O parser rejeita cabeçalhos truncados, comprimentos inválidos, nomes além do buffer, UTF-16 inválido, NUL embutido, nomes fora de NFC, tamanhos negativos e offsets inconsistentes.

## Limites

Este módulo não inicia enumeração, não interpreta códigos Win32, não controla `ERROR_NO_MORE_FILES` ou `ERROR_MORE_DATA`, não verifica mutação do namespace e não garante snapshot. Não abre objetos nem calcula hashes. O parser isolado não autoriza integração ao inventário de produção.

Fonte do layout: Microsoft Learn, FILE_ID_BOTH_DIR_INFO:
https://learn.microsoft.com/windows/win32/api/winbase/ns-winbase-file_id_both_dir_info
