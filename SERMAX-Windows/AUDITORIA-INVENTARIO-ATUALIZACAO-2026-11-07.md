# Auditoria do inventário de atualização SERMAX

Data: 2026-11-07  
Branch: `sermax-windows-integration-20261029`  
HEAD auditado: `d8e2edbeef66f923cb033c6b8d131d05c7bb74b1`  
Escopo: revisão estática do inventário somente de leitura e evidências da CI 263.

## 1. Evidências da CI 263

- Workflow run: [42411038733](https://github.com/frserpeloni/AndroidForge/actions/runs/42411038733)
- Job: `validate-and-build`, Windows Server 2025, sucesso.
- Python SERMAX/Pestinha: 3.14.10.
- OpenJarvis: ambiente Python 3.13 isolado, instalação concluída.
- Testes: 101 executados, resultado `OK`.
- Build PyInstaller: `Build complete!`.
- Smoke test: executável congelado alcançou o prompt do terminal original e tratou `/sair`.
- Artifact: `SERMAX-Windows-executable`, ID `13588913557`, tamanho 22.826.832 bytes, digest ZIP SHA-256 `9445dc6e6836915a4b0ad1bce88decd0e1b98aba4932e36bb2d9c7bdf537c9a1`.
- O artifact é temporário e experimental. Não é instalador, release assinada ou versão aprovada. Não instalar em `C:\SERMAX`.

## 2. Escopo efetivamente coberto pelo inventário

O módulo `sermax_update_inventory.py`:
- recebe a raiz explicitamente, sem default para `C:\SERMAX`;
- enumera diretórios sem seguir links identificados na consulta inicial;
- calcula SHA-256 e tamanho dos arquivos regulares;
- classifica por allowlist explícita, nomes de memória protegidos e desconhecidos;
- não copia, grava, remove ou instala arquivos.

Os sete testes dedicados passaram na CI 263. A suíte completa registrou 101 testes aprovados.

## 3. Riscos identificados na revisão estática

### R1. Janela TOCTOU entre inspeção e leitura de arquivo

A enumeração usa `entry.stat(follow_symlinks=False)`, mas o hash abre posteriormente o caminho por `Path.open("rb")`. Um processo concorrente com permissão de escrita poderia trocar a entrada entre essas operações. A abertura posterior seguiria o objeto substituto, inclusive um link/reparse point, em vez de garantir que o objeto aberto é o mesmo objeto inspecionado.

A consulta de tamanho também ocorre após a leitura e não comprova que o arquivo permaneceu estável durante o hash.

**Decisão:** não considerar o inventário pronto para autorizar backup ou instalação. A próxima implementação deve usar operações baseadas em handle/descriptor, validar identidade do objeto aberto, rejeitar reparse points no handle e confirmar estabilidade de tamanho/identidade. Em Windows, a validação precisa cobrir junctions e outros reparse tags, não somente symlinks comuns.

### R2. Raiz validada e resolvida em operações separadas

A raiz é inspecionada por `lstat()` e depois resolvida com `resolve(strict=True)`. Uma alteração concorrente entre as chamadas pode invalidar a premissa da primeira verificação. A implementação de produção deve manter um handle seguro para a raiz e resolver os descendentes em relação a esse handle, ou aplicar mecanismo Windows equivalente.

### R3. Cobertura insuficiente de reparse points Windows

O teste dedicado cobre symlink quando o ambiente permite criá-lo. Não há evidência específica de teste de junction, mount point, hardlink ou reparse tag não usual no Windows runner. A detecção atual consulta `st_file_attributes`, mas não inspeciona o tag nem comprova o comportamento sob concorrência.

### R4. Inventário não é snapshot atômico

Mesmo sem links, arquivos e diretórios podem mudar durante a enumeração. O resultado é uma sequência de observações, não uma fotografia transacional. O futuro backup deve revalidar identidade e hashes imediatamente antes e depois da cópia e abortar diante de qualquer divergência.

## 4. Próximos gates técnicos

1. Projetar camada de leitura segura específica para Windows, mantendo fallback portátil estritamente limitado a testes.
2. Testar symlink, junction, mount point, hardlink, reparse tag, troca concorrente e alteração durante hash.
3. Fazer o inventário falhar fechado quando não conseguir provar identidade/estabilidade.
4. Só então implementar cópia de backup para diretório temporário, com comparação byte a byte e injeção de falhas.
5. Validar restauração em sandbox isolada. Nenhum teste deve escrever em `C:\SERMAX`.
6. Atualizar o workflow e exigir CI verde para o novo HEAD.

## 5. Limites desta auditoria

Esta revisão é estática e baseada nos arquivos e logs remotos da CI. Não foi executada no computador do usuário. Não comprova comportamento com Ollama local, memória persistente real, voz/Whisper, interface gráfica/terminal em resolução real ou rollback físico.

O inventário inicial é útil para diagnóstico, mas ainda não é um componente de segurança suficiente para habilitar o atualizador transacional.
