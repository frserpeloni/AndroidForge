# Segurança do instalador SERMAX

Status: documentação técnica da implementação em desenvolvimento. Este documento não representa certificação de segurança nem liberação de instalador.

## Controles implementados

- O instalador processa somente arquivos declarados no manifesto.
- Cada arquivo de origem é validado por tamanho e SHA-256 antes da instalação.
- Caminhos relativos, travessia de diretórios, nomes reservados do Windows e destinos conflitantes são rejeitados.
- Destinos de dados do usuário, incluindo memória, dados, configurações, credenciais e segredos, são protegidos por regras internas.
- Links simbólicos, junctions e reparse points existentes são rejeitados nas verificações por caminho.
- O instalador cria cópias de segurança dos arquivos de programa que serão substituídos.
- Um bloqueio exclusivo por sistema operacional impede duas instâncias cooperantes de instalar simultaneamente no mesmo destino.
- O arquivo `.sermax-install.lock` é reservado e não pode ser substituído por um arquivo do pacote.
- Os caminhos são revalidados antes de operações críticas de cópia e substituição.

## Limitações conhecidas

### TOCTOU e reparse points

As verificações usam inspeção de caminhos e chamadas de arquivo convencionais do Python. Um processo concorrente com permissão de escrita ainda pode trocar um diretório ou reparse point entre a última verificação e a operação seguinte. A revalidação reduz a janela, mas não elimina essa corrida.

Uma proteção mais forte no Windows exige desenho e testes específicos com handles, abertura sem seguir o reparse point e operações relativas a handles. Isso ainda não está implementado. Não considerar o instalador resistente a um atacante local capaz de modificar simultaneamente a pasta de destino.

### Bloqueio de instalação

O bloqueio coordena instâncias que respeitam o mesmo arquivo de lock. Ele não impede um processo externo de modificar arquivos, apagar o lock ou trocar diretórios. A semântica de bloqueio também depende do sistema de arquivos e do ambiente em que o destino está armazenado. O teste de CI cobre concorrência entre processos no runner, não todos os sistemas de arquivos ou cenários de rede.

### Integridade e autenticidade do pacote

SHA-256 detecta divergência entre o conteúdo e o manifesto. Como o manifesto não possui assinatura digital, isso não comprova quem publicou o pacote nem protege contra a substituição conjunta do manifesto e dos arquivos.

### Rollback e atomicidade

A instalação substitui arquivos individualmente. Não existe transação atômica para o conjunto completo. O rollback é uma tentativa de recuperação, não uma garantia. Falhas de disco, permissões, bloqueios externos ou mudanças concorrentes podem impedir a restauração. Em caso de erro de rollback, preservar a pasta de backup e examinar a mensagem de erro antes de qualquer nova tentativa.

## Critérios pendentes antes de distribuir

1. Implementar e testar operações Windows baseadas em handles para reduzir TOCTOU.
2. Testar instalação e rollback em Windows real, incluindo junctions e falhas de permissão/disco.
3. Definir assinatura e verificação de autenticidade dos pacotes.
4. Validar a matriz oficial de arquivos, dependências e licenças.
5. Executar testes de instalação inicial e atualização sobre uma cópia controlada de uma instalação SERMAX.
6. Revisar o fluxo de recuperação e documentar procedimentos de restauração.

Até esses critérios serem atendidos, o assistente gráfico e o motor do instalador permanecem em desenvolvimento e não devem ser tratados como instalador distribuível.
