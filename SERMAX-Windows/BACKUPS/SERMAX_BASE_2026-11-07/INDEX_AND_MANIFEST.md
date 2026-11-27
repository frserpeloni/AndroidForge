# SERMAX, backup técnico permanente

Data do snapshot: 2026-11-07  
Repositório: frserpeloni/AndroidForge  
Branch de trabalho: sermax-windows-integration-20261029  
Commit de origem dos arquivos: 1bb9ff8f2cc171205c8bdd1bc7f0e4b213d12d67

## Conteúdo

- CORE_AND_TERMINAL_SNAPSHOT.txt: core, launcher, spec, terminal original, voz, integração de comandos, histórico e planejador.
- INTEGRATIONS_AND_AGENTS_SNAPSHOT.txt: executor, tarefas, ferramentas Windows, equipe MAX, workspace, backend Groq e adaptadores Jarvis/Pestinha.
- TESTS_SNAPSHOT_PART1.txt e TESTS_SNAPSHOT_PART2.txt: 16 testes.
- TESTS_AND_PROJECT_DOCS_SNAPSHOT.txt: testes restantes e documentos de status, arquitetura e integrações.

Total: 37 arquivos originais preservados em texto integral, com separadores de caminho. Os hashes abaixo são Git blob SHA-1 dos arquivos de origem, antes do backup.

## Limites deliberados

Memórias pessoais, memória neural, chaves/API tokens, segredos, ambientes virtuais, dependências externas e dados locais não entram no Git. Esses itens exigem armazenamento seguro próprio e não devem ser publicados no repositório.

Este backup registra o código e a documentação presentes na branch na data indicada. Não significa que os testes foram executados nem que a versão está liberada.

## Manifesto de integridade

```text
8147d515bcc2e65cc9d4b19d9ec121fa636c1663  sermax_core.py
2b3267e50894f517e57fc8bea8c3eb10dbbb8c2d  sermax_launcher.py
dec650203fe4179d842d2690add68e0c47a2b76b  SERMAX.spec
f7479c3e56c0e144b6009ed7883301368a3d4f1d  SERMAX_terminal/sermax_terminal.py
68ee5860ddf4f039005f76448940f7e982920d19  SERMAX_terminal/sermax_voz.py
4eda3f14e3633c27907674d5cd6533c939924efc  SERMAX_terminal/sermax_integracao_comandos.py
19681d25cc0903aa9cf5fc14bd0ae71d2f66a2ba  sermax_historico_comandos.py
6c4bba84d0df5aca51035f653239d7317b650e02  sermax_planejador.py
894df28738c865e404b58d80e4e5c57d6fcbc5ca  sermax_executor.py
cc224369aca22d0cc8478935b1a6cf1347a50339  sermax_tarefas.py
56a6543342085b9e5439197a63d14502ebf57bd5  ferramenta_windows.py
af25af2394e5f71fb3147fbd6aa22e061b9a8495  sermax_dev_team.py
5d12542c0db129dd6566595d58dd300ea0d05a46  sermax_workspace.py
1978875adc482ad302c88da39dba80ce96ff5290  sermax_groq_backend.py
17e5f61244da779e612767cb9833b29310e8c569  sermax_jarvis_adapter.py
d75bdd3d7431e67d911f8af3c0f40a4823aad5c8  sermax_pestinha_adapter.py
35288c93fae2a0ade3ea4c6b468dca59cd55eb3a  STATUS-AND-RELEASE-GATES.md
45c2ccf2490d961e07600173a280478d29f5b01c  ARQUITETURA-EQUIPE-UNICA-MAX.md
fe4c4970d7309a97eb32c94ce904ed9a576d620b  INTEGRACAO-JARVIS-PESTINHA.md
1490462c1029307370399a46c81ee719b7240fc0  tests/test_sermax_core.py
f82a7dda3403ae6ae05b4ab4efa15ac6f2d0cdb2  tests/test_sermax_core_widget_lifecycle.py
d6eda01f372918d9cfc6c8559ebfd75229ad37c5  tests/test_sermax_dev_proposal.py
e3f1b6ca322eb17d9b7cbd021f255f810f8d9179  tests/test_sermax_dev_team.py
403ae85f87f48ad88e50a305317422ca12fb47b2  tests/test_sermax_executor_tasks.py
fa211d5b2c7accf04dce158686c8da69a5b115b3  tests/test_sermax_groq_backend.py
0811c14510b53e0c4d9961da92bd3a7d021bb2e6  tests/test_sermax_historico_seguro.py
1a16660134d45bca65288b5bccbbcb8bec2a2c2c  tests/test_sermax_integration.py
bfa0433bed52164cd720294e99061d919c358b0b  tests/test_sermax_jarvis_adapter.py
648bf89b5470fcdfd12924b38491d4dd05bbabd4  tests/test_sermax_jarvis_core_integration.py
be485d4edf06aa617841591e002e7bb7ddaccebd  tests/test_sermax_pestinha_adapter.py
7b53aff6d9bddbbed4566097cad6f8135fadd09a  tests/test_sermax_planner_validation.py
896f84137426433e0fc55534b6b3930a91268cde  tests/test_sermax_real_jarvis.py
d578825e53c6bf85e68ab674462b26492a5396fb  tests/test_sermax_real_pestinha.py
9ed0fba099347700698ee3d67eca157067b5c1dd  tests/test_sermax_safe_calculator.py
b975efbe09dc2fb8687233cabe226b338fe4eba5  tests/test_sermax_widget_neural_integration.py
289d2b178ef4aab3176f45833e0684f93b8aa43e  tests/test_sermax_widget_state.py
86ac9ac98cb1dc1f175c5d25a7906729f5ae4859  tests/test_sermax_workspace.py
```

Para restaurar um arquivo, localizar o cabeçalho `===== FILE: caminho =====` no snapshot correspondente e extrair o conteúdo até o próximo cabeçalho. Comparar o arquivo restaurado com o Git blob SHA indicado.
