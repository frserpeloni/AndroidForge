# Projeto de abertura segura da raiz do volume

Data: 08/11/2026  
Estado: implementação isolada inicial registrada; validação Windows x64 e integração ao inventário ainda pendentes

## Objetivo

Definir como iniciar a caminhada segura até `C:\\SERMAX` sem entregar um caminho absoluto completo ao resolvedor de caminhos do Windows. A raiz deve ser aberta primeiro como handle de diretório. Cada componente seguinte deve ser aberto relativamente ao handle pai, com validação pelo handle retornado.

Esta especificação não autoriza integração ao inventário, leitura de conteúdo, hash, atualização ou rollback.

## Evidência documental

1. A documentação de `NtCreateFile` define `OBJECT_ATTRIBUTES.RootDirectory` como handle de diretório obtido em chamada anterior. Quando não nulo, `ObjectName` é interpretado relativamente a esse diretório. Também documenta `FILE_OPEN_REPARSE_POINT` para abrir o próprio objeto reparse sem executar o processamento normal do reparse point.
   Fonte: https://learn.microsoft.com/windows/win32/api/winternl/nf-winternl-ntcreatefile

2. A documentação de `CreateFileW` informa que a abertura de diretórios requer `FILE_FLAG_BACKUP_SEMANTICS` e `OPEN_EXISTING`. A tabela de exemplos distingue `\\\\.\\C:\\`, que abre o sistema de arquivos do volume C:, de `\\\\.\\C:`, que abre o volume.
   Fonte: https://learn.microsoft.com/en-us/windows/desktop/api/fileapi/nf-fileapi-createfilew

3. `FILE_ID_INFO` contém o serial do volume e o identificador de arquivo de 128 bits. A Microsoft orienta comparar ambos para determinar se dois handles abertos representam o mesmo arquivo.
   Fonte: https://learn.microsoft.com/windows/win32/api/winbase/ns-winbase-file_id_info

4. `GetFileInformationByHandleEx` oferece as classes `FileAttributeTagInfo`, `FileStandardInfo` e `FileIdInfo`, consultadas pelo handle.
   Fonte: https://learn.microsoft.com/pt-br/windows/win32/api/fileapi/nf-fileapi-getfileinformationbyhandleex

## Fluxo proposto

1. Receber uma raiz de volume explícita, inicialmente limitada a uma letra de unidade local no formato validado pelo chamador. Não aceitar caminho UNC, unidade relativa, caminho com componentes, `SUBST` ou pontos de montagem sem política específica.
2. Abrir a raiz do sistema de arquivos do volume com `CreateFileW`, `OPEN_EXISTING`, `FILE_FLAG_BACKUP_SEMANTICS` e `FILE_FLAG_OPEN_REPARSE_POINT`.
3. Consultar pelo handle os atributos, a informação de diretório e a identidade do volume/objeto.
4. Rejeitar falha de consulta, objeto que não seja diretório, reparse point, ou qualquer estado que não corresponda à política de volume local.
5. Manter o handle da raiz aberto durante toda a caminhada.
6. Abrir o componente `SERMAX` com `open_relative_component(root_handle, "SERMAX", directory=True)`.
7. Consultar novamente metadados do handle filho. Rejeitar reparse point, tipo inesperado e mudança de volume, salvo política explícita para volumes montados.
8. Somente após validação, permitir que o handle filho seja usado como pai do próximo componente.

## Direitos e compartilhamento

Os direitos mínimos ainda precisam ser determinados por teste. A hipótese inicial a avaliar inclui `FILE_READ_ATTRIBUTES`, `FILE_LIST_DIRECTORY`, `FILE_TRAVERSE` e `SYNCHRONIZE`. Não assumir que a combinação está correta sem teste no Windows x64.

O compartilhamento inicial conservador do código atual é `FILE_SHARE_READ`. Isso pode bloquear operações concorrentes legítimas e causar falhas quando outros handles já estiverem abertos com modos incompatíveis. Testar e documentar os efeitos antes de fixar a política.

## Limites de segurança

- Abrir a raiz do volume evita iniciar a caminhada pelo caminho completo `C:\\SERMAX`, mas não resolve automaticamente junctions, mount points ou outros reparse points encontrados em componentes descendentes.
- Cada componente deve ser aberto sem seguir o reparse point final e validado pelo handle antes de ser usado como novo `RootDirectory`.
- Nunca usar um handle de reparse point como diretório pai da próxima operação.
- A letra de unidade não é identidade permanente do volume. Registrar e comparar a identidade do volume retornada pelo handle.
- Não presumir que um volume local é NTFS. Documentar o filesystem e testar os sistemas de arquivos suportados.
- Não usar fallback por caminho se a abertura relativa falhar.
- O inventário atual permanece intocado até a conclusão dos gates.

## Matriz mínima de testes

### Abertura da raiz
- Raiz de volume local válida.
- Unidade inexistente ou removível indisponível.
- Unidade de rede/UNC rejeitada pela política inicial.
- Letra inválida, unidade relativa, espaços e separadores indevidos.
- Falhas de acesso, compartilhamento e consulta de metadados.
- Confirmação de diretório e identidade do volume.

### Componente SERMAX
- Diretório regular existente.
- Componente inexistente.
- Arquivo regular no lugar de diretório.
- Symlink e junction no componente final.
- Mount point e reparse tags não reconhecidas.
- Mudança concorrente entre enumeração e abertura.
- Renomeação e remoção concorrentes.
- Volume serial e File ID consultados pelo handle.

### Compatibilidade
- Windows x64 nas versões suportadas.
- NTFS como cenário obrigatório inicial.
- Outros filesystems somente após teste explícito.
- Share modes com handles de leitura, escrita e exclusão concorrentes.

## Critérios de aceite

- A raiz é aberta e validada sem resolver `C:\\SERMAX` como caminho absoluto completo.
- O handle raiz permanece aberto durante a caminhada.
- O componente `SERMAX` é aberto relativamente ao handle raiz.
- Nenhum componente reparse é aceito como pai.
- Testes reais Windows cobrem sucesso, falhas, symlink/junction e concorrência.
- CI registra explicitamente testes aprovados, falhos e ignorados. Teste ignorado não conta como aprovado.
- Nenhuma integração ao inventário ou ao atualizador ocorre nesta etapa.

## Implementação registrada em 08/11/2026

O módulo `sermax_windows_root.py` implementa a abertura de `X:\\` com `CreateFileW`, `OPEN_EXISTING`, `FILE_FLAG_BACKUP_SEMANTICS` e `FILE_FLAG_OPEN_REPARSE_POINT`. Consulta metadados pelo handle e rejeita objeto que não seja diretório, reparse point ou esteja marcado para exclusão.

O mesmo módulo implementa `open_sermax_directory(root_handle)`. A função abre o componente `SERMAX` relativamente ao handle pai, consulta novamente os metadados e exige que o filho seja diretório regular no mesmo volume. Em caso de falha de validação, fecha o handle filho. O handle da raiz deve permanecer aberto pelo chamador durante a operação.

Os testes `test_sermax_windows_root.py` incluem validação de caminhos, testes com mocks para rejeição de reparse point e divergência de volume, além de integração Windows x64 para abertura da raiz e abertura relativa de um diretório temporário chamado `SERMAX`.

**Estado de validação:** os commits de implementação ainda não têm execução de CI confirmada nesta branch. Os testes Windows são critérios pendentes, não resultados aprovados. A abertura da raiz por letra também não prova, por si só, que o volume não seja SUBST ou ponto de montagem. A política inicial exige investigação adicional antes de autorizar volumes montados.

## Próxima ação

Executar a suíte no runner Windows x64, revisar os logs e ampliar testes de falha/concorrência. Só depois avaliar a caminhada incremental de subdiretórios. Não integrar ao inventário, leitura, hash ou atualizador nesta etapa.