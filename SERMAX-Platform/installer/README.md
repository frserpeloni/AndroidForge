# SERMAX Installer

Camada de instalação e atualização da Plataforma SERMAX.

## Estado atual

**Protótipo de desenvolvimento. Não é instalador distribuível nem pacote completo do SERMAX.**

### Motor
- Lê manifesto versionado.
- Valida caminhos relativos, traversal, nomes reservados do Windows e conflitos de destino sem diferenciar maiúsculas/minúsculas.
- Rejeita links simbólicos nas origens do pacote e nos caminhos de destino já existentes.
- Confere SHA-256 e tamanho real de cada arquivo contra o manifesto.
- Verifica espaço em disco sem criar a pasta de destino na pré-validação.
- Copia somente arquivos listados no manifesto.
- Faz backup de arquivos de programa substituídos.
- Prepara cópias temporárias e substitui cada arquivo por operação atômica individual.
- Tenta restaurar arquivos e marcador após falha; se a restauração falhar, mantém os backups e anexa detalhes de recuperação à exceção. Isso não equivale a uma transação global atômica.
- Informa progresso por etapa e arquivo.
- Grava `.sermax-install.json` com versão instalada.
- Detecta instalação existente e versão registrada.
- Não possui operação de exclusão.

### Interface gráfica
`installer_gui.py` usa Tkinter e oferece:
- Seleção do pacote e destino.
- Detecção automática de instalação inicial ou atualização.
- Opção manual de operação com validação contra o estado encontrado.
- Pré-validação, confirmação e progresso por arquivo.
- Relatório de arquivos, versão e backup.

Executar no ambiente de desenvolvimento:

```powershell
python installer_gui.py --package C:\caminho\para\pacote
```

## Formato do pacote

```text
package/
  manifest.json
  payload/
    Platform/
    SERMAX-Windows/
```

Exemplo de manifesto:

```json
{
  "schema_version": 1,
  "version": "0.1.0",
  "preserve_paths": [
    "memoria_sermax.json",
    "memoria_neural_pestinha.json",
    "data",
    "config"
  ],
  "files": [
    {
      "source": "payload/Platform/index.html",
      "target": "SERMAX-Platform/index.html",
      "sha256": "HASH_SHA256_REAL",
      "size_bytes": 1234
    }
  ]
}
```

O hash e o tamanho devem corresponder ao arquivo real durante a montagem do pacote. O exemplo não é instalável.

## Construtor de pacotes

`sermax_package_builder.py` monta um pacote a partir de uma lista explícita de arquivos. Não varre automaticamente o repositório. Isso evita incluir memória, banco de dados, logs, credenciais e backups por acidente.

Exemplo em PowerShell:

```powershell
python sermax_package_builder.py `
  --source C:\SERMAX-WORKTREE `
  --output C:\SERMAX-BUILD\SERMAX-PACKAGE-1.0.0 `
  --version 1.0.0 `
  --map SERMAX-Platform/index.html=SERMAX-Platform/index.html `
  --map SERMAX-Platform/app.js=SERMAX-Platform/app.js
```

Cada `--map origem=destino` inclui um arquivo. O construtor calcula SHA-256, registra tamanho e cria `manifest.json`. A pasta de saída precisa ser nova. Links simbólicos, caminhos fora da origem, destinos duplicados e saída dentro da origem são bloqueados.

O exemplo inclui dois arquivos de interface, não representa um pacote completo instalável. A seleção oficial de componentes só será definida após auditoria e aprovação da composição do pacote.

## Testes

```powershell
python -m unittest -v test_installer_core.py
python -m py_compile installer_gui.py
```

## Limites e proteções

- Não há pacote completo com núcleo, Plataforma, Terminal e dependências.
- Não há integração com Inno Setup ou WiX.
- Não há assinatura digital nem verificação de editor.
- Não há desinstalador.
- Não foi executado no computador do usuário.
- A barra mede arquivos processados, não bytes transferidos.
- O marcador de versão é metadado local, não prova de integridade de toda a instalação.
- A cópia de segurança dos arquivos listados não substitui backup completo de banco e dados.
- O motor não apaga arquivos não listados.
- Não modificar núcleo, Terminal, memórias ou dados sem autorização específica.

O próximo estágio exige definir o manifesto oficial e a composição do pacote completo antes de gerar executável de instalação.
