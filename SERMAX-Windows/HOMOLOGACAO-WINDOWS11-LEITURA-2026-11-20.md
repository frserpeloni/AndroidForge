# Homologação SERMAX no Windows 11, coleta somente leitura

## Finalidade

O script `sermax_windows11_homologation.py` coleta evidências do ambiente local antes da homologação. Ele não inicia o SERMAX e não executa instalação, atualização, restauração ou rollback.

## Privacidade e integridade

- Não grava arquivos nem cria diretórios.
- Não altera `C:\\SERMAX`.
- Não inicia nem encerra processos.
- Não lê o conteúdo de `memoria_sermax.json`. Registra somente existência, tipo, tamanho e data de modificação.
- Calcula SHA-256 somente do código do Terminal, não da memória pessoal.
- Se os módulos do gate estiverem disponíveis, executa a inspeção de recuperação já existente. Essa inspeção é somente leitura.
- Não corrige nem limpa transações pendentes.

## Execução

1. Baixe e extraia a branch `sermax-windows11-readonly-homologation-20261120` do repositório.
2. Abra o Prompt de Comando na pasta extraída.
3. Execute:

```bat
py -3.14 SERMAX-Windows\sermax_windows11_homologation.py --root C:\SERMAX
```

4. Copie o JSON exibido no terminal e envie o resultado para análise.

Se o comando `py -3.14` não estiver registrado, execute o script com o caminho do Python 3.14 instalado.

## Itens reportados

- Edição/versão/build do Windows e arquitetura.
- Existência e tipo da pasta `C:\\SERMAX`.
- Presença de `SERMAX.exe`.
- Presença e SHA-256 de `SERMAX_terminal/sermax_terminal.py`.
- Presença e metadados de `memoria_sermax.json`, sem ler seu conteúdo.
- Estado da inspeção somente leitura da área `_update`, quando aplicável.

## Limites

O relatório não comprova funcionamento de Ollama, Jarvis, voz, persistência após reinício ou comportamento visual do Terminal. Esses itens exigem testes funcionais separados, com observação do usuário.

O script é uma ferramenta de coleta. Seu resultado não autoriza instalação, atualização, merge ou release. A instalação ativa deve permanecer intacta durante esta etapa.
