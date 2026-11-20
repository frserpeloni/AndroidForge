# Projeto de abertura segura da raiz do volume

Data: 09/11/2026  
Estado: abertura isolada validada em CI Windows x64 no commit `4d9b5f9535c41d421d0f0314e4c8c7ef74f55271`; integração ao inventário permanece bloqueada

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

Os testes `test_sermax_windows_root.py` incluem validação de caminhos, testes com mocks para rejeição de reparse point e divergência de volume, além de integração Windows x64 para abertura da raiz, abertura relativa de um diretório temporário chamado `SERMAX` e rejeição de um arquivo regular com esse nome.

**Estado de validação em 09/11/2026:** a execução GitHub Actions nº 309, run ID `42605467632`, associada ao commit `4d9b5f9535c41d421d0f0314e4c8c7ef74f55271`, concluiu com sucesso no runner Windows x64. O job `validate-and-build` passou por verificação das fontes e do terminal original, preparação dos ambientes Python 3.14/3.13, compilação e testes de integração, build do `SERMAX.exe`, smoke test do executável/terminal e publicação do artifact experimental. O log registra `Ran 143 tests ... OK`. O teste `test_rejects_symlink_named_sermax` aparece como `ok`, sem `skip`. O teste de arquivo regular também aparece como `ok`. Esta aprovação valida o commit exato citado, mas não representa validação em todas as versões de Windows nem teste na máquina do usuário.

**Atualização de validação em 09/11/2026, CI 311:** run ID `42612390854`, attempt 2, job ID `129150283928`, executado sobre o head da PR `d2052aa37246a53bed3333f2e473984d96c9303e`. O job concluiu com sucesso no runner Windows x64. O log confirma `test_rejects_junction_named_sermax ... ok` e `test_rejects_symlink_named_sermax ... ok`, ambos sem skip, e `Ran 144 tests in 5.764s`. A compilação do `SERMAX.exe`, o smoke test de inicialização do executável e do terminal original e a publicação do artifact experimental também concluíram com sucesso. Artifact ID `13672595877`, SHA-256 `1e1398a03878789c8e5c307f38a3f78c571b6c5d2c17e9d9f9cd7e8256e05a77`, tamanho 22.826.057 bytes. Esta CI valida a rejeição de symlink e junction no componente final `SERMAX` no runner Windows x64. Não valida a instalação local nem elimina os demais gates. A abertura da raiz por letra não prova, por si só, que o volume não seja `SUBST` ou ponto de montagem. A política exige investigação adicional antes de autorizar esses casos.

Execução CI: https://github.com/frserpeloni/AndroidForge/actions/runs/42605467632

O artifact publicado é experimental, não instalador. Não instalar em `C:\\SERMAX`.

## Próxima ação

Implementar e executar testes reais para concorrência de renomeação/remoção e abertura, share modes com handles concorrentes, falhas de fechamento e ciclo de vida de handles. Investigar `SUBST`, mount points, volumes removíveis e filesystems suportados. Não integrar ao inventário, leitura, hash ou atualizador nesta etapa.