# Integração controlada: OpenJarvis e Pestinha

**Estado desta etapa:** adaptadores implementados na branch de integração; dependências externas ainda não instaladas nem empacotadas. A integração completa permanece em validação.

## OpenJarvis

- Repositório: https://github.com/open-jarvis/OpenJarvis
- Commit de referência consultado: c6c782b924c9040d7c35f76ff693d4057bc0032f
- Licença declarada: Apache-2.0.
- Interface pública verificada: SDK `openjarvis.Jarvis`, método `ask()`, `close()`.
- Ponte SERMAX: `sermax_jarvis_adapter.py`.
- Uso permitido nesta integração: `engine_key="ollama"`, modelo SERMAX, agente `simple`, `tools=[]`, `context=False`.
- O SERMAX expõe a chamada explícita `/jarvis pergunta`.
- Agentes com ferramentas, shell, leitura/escrita de arquivos, memória Jarvis e agendamento não são ativados pela ponte.

## Pestinha

- Repositório: https://github.com/mille-okws/pestinha
- Commit de referência consultado: 1b16bd21bb5ba9dd4c460c153f865824f53d05c8.
- Licença declarada: GPL-3.0. A distribuição conjunta exige avaliação e cumprimento das obrigações da licença.
- Interface concreta verificada: `LIFBrain`, `stimulate()`, `step()`, `motor_activity()`, `save()`, `load()`.
- Ponte SERMAX: `sermax_pestinha_adapter.py`.
- A ponte recebe somente eventos internos do ciclo do SERMAX. Não coleta teclado, mouse, janelas, conversas ou dados pessoais.
- Somente motores de expressão são mapeados para estados visuais. Motores de decisão, como `FUGIR`, `TRAVESSURA` e `PAPEL`, são ignorados.
- Estado neural separado: arquivo próprio informado pelo integrador, por exemplo `sermax_neural_state.json`. Nunca usar `memoria_sermax.json`.

## Segurança e fallback

- O terminal e o núcleo SERMAX não dependem da inicialização dos adaptadores.
- Se um backend estiver ausente ou falhar, o SERMAX mantém os estados determinísticos.
- Nenhuma saída neural executa comandos.
- A chamada Jarvis é sem ferramentas e sem contexto de memória.
- Não importar nem executar os binários distribuídos pelo projeto Pestinha. A integração deve usar fonte auditada e dependências Python verificadas.

## Pendências para integração final

1. Fixar e instalar dependências em ambiente isolado de CI.
2. Executar testes contra os módulos reais do OpenJarvis e Pestinha.
3. Validar a configuração Ollama do Jarvis sem ativar ferramentas.
4. Medir CPU/RAM e latência da rede LIF.
5. Confirmar o empacotamento PyInstaller das dependências efetivamente aprovadas.
6. Avaliar obrigações GPL-3.0 antes de distribuir um executável que inclua o Pestinha.
7. Testar no Windows real, preservando `C:\SERMAX`, memória pessoal e terminal original.

Nenhuma versão de produção foi declarada.
