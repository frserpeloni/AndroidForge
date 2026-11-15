# SERMAX Installer Core

Este diretório contém a primeira camada programável de instalação e atualização segura da Plataforma SERMAX.

## Estado

**Motor de cópia transacional em desenvolvimento. Não é um instalador executável pronto.**

O motor:
- Lê um `manifest.json` versionado.
- Valida caminhos relativos e bloqueia tentativa de sair do pacote ou da pasta de instalação.
- Confere SHA-256 de cada arquivo do pacote.
- Faz pré-verificação de espaço em disco.
- Copia somente arquivos declarados no manifesto.
- Faz cópia de segurança dos arquivos de programa que serão substituídos.
- Usa arquivo temporário e substituição atômica por arquivo.
- Não possui operação de exclusão.
- Não apaga diretórios de dados, memória, histórico ou arquivos não listados.

## Estrutura esperada de um pacote futuro

```text
package/
  manifest.json
  payload/
    platform/
    core/
    terminal/
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
      "source": "payload/platform/index.html",
      "target": "Platform/index.html",
      "sha256": "<SHA-256 real do arquivo>"
    }
  ]
}
```

O manifesto deve conter hashes reais gerados durante a montagem do pacote. Não usar valores ilustrativos em pacotes distribuídos.

## Uso interno e testes

O módulo `sermax_installer_core.py` não executa operações ao ser importado. As alterações no disco só ocorrem quando `install_package()` é chamado.

Executar testes:

```powershell
python -m unittest -v test_installer_core.py
```

## Limites atuais

- Ainda não há interface gráfica do instalador.
- Ainda não há pacote de instalação com todos os componentes do SERMAX.
- Ainda não há integração com Inno Setup ou WiX.
- Ainda não há desinstalador.
- Ainda não há validação de assinatura digital do pacote.
- A instalação real no computador do usuário não foi executada.
- Não substitui backup completo do banco e dos dados do usuário.
- Não autoriza modificar arquivos críticos do núcleo ou Terminal sem auditoria e autorização.

O instalador final deverá incluir pré-validação, confirmação do usuário, backup verificável, instalação, verificação pós-instalação e recuperação em caso de falha. A interface gráfica será adicionada após estabilizar o formato do pacote e o layout definitivo dos dados.
