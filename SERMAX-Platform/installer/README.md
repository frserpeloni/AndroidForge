# SERMAX Installer

Camada de instalação e atualização da Plataforma SERMAX.

## Estado atual

**Protótipo de desenvolvimento. Não é instalador distribuível nem pacote completo do SERMAX.**

### Motor
- Lê manifesto versionado.
- Valida caminhos relativos, traversal, nomes reservados do Windows e conflitos de destino sem diferenciar maiúsculas/minúsculas.
- Rejeita links simbólicos e reparse points detectados nas origens do pacote e nos caminhos de destino já existentes. A checagem por caminho ainda não elimina condições de corrida TOCTOU.
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
python -m unittest -v test_package_builder.py
python -m py_compile installer_gui.py sermax_installer_core.py sermax_package_builder.py
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
- As verificações de reparse point são baseadas em inspeção de caminhos. Ainda falta endurecer operações com handles e validar concorrência/TOCTOU contra troca de diretórios durante a instalação.
- A matriz de falhas cobre cenários selecionados de staging, substituição e marcador. Ainda faltam testes de interrupção abrupta do processo, falha de disco real e recuperação após reinicialização.
- O motor não apaga arquivos não listados.
- Não modificar núcleo, Terminal, memórias ou dados sem autorização específica.

O próximo estágio exige definir o manifesto oficial e a composição do pacote completo antes de gerar executável de instalação.


## Evolução proposta do formato assinado

O formato implementado no protótipo continua sendo o schema v1, sem assinatura digital. A proposta de schema v2 está documentada em `WINDOWS_HANDLE_BASED_INSTALLER_DESIGN.md`, seções 11.15 e 11.16.

A proposta v2 mantém o pacote em diretório, acrescenta `manifest.p7s`, define manifesto canônico JCS e exige assinatura destacada CMS/PKCS #7, identidade do publicador, sequência monotônica e conferência do inventário completo de arquivos.

**Atenção:** schema v2 ainda não está implementado. O construtor e o instalador atuais não geram nem verificam `manifest.p7s`. Não trate a proposta como pacote assinado, instalável ou validado. O protótipo segue sem distribuição autorizada.


## Relação com o atualizador SERMAX Windows

O repositório também contém uma trilha separada em `SERMAX-Windows/sermax_update_*`:

- Manifesto JSON schema 1 com assinatura Ed25519.
- Validação de pacote ZIP contra manifesto autenticado.
- Inventário somente de leitura e plano de atualização em memória.

Essa trilha não está integrada a este instalador de diretório. Ela também não executa extração, staging, backup, instalação, journal ou rollback. A allowlist de chaves públicas de produção ainda não foi aprovada/provisionada.

Não misture o ZIP assinado do atualizador Windows com o diretório schema v1 deste protótipo. Não há contrato compartilhado validado. A decisão de arquitetura e a composição dos componentes estão registradas em `WINDOWS_HANDLE_BASED_INSTALLER_DESIGN.md`, seção 11.17, e em `../MATRIZ-PACOTE-DEPENDENCIAS-E-LACUNAS-2026-11-15.md`, seção 8.

A proposta CMS/PKCS #7 e schema v2 nas seções 11.15 e 11.16 é exploratória e foi superada para a trilha atual do atualizador Windows. Não implementar um segundo formato sem decisão arquitetural aprovada.
