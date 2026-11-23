# Homologação local SERMAX Platform, 23/11/2026

## Identificação da candidata

- Repositório: https://github.com/frserpeloni/AndroidForge
- Branch: `sermax-platform-ocr-20261117`
- Commit homologado: `f64f9dffce1bfc0a029422da97f39132394f1d86`
- PR de consolidação: #24, Draft, aberta e sem merge.
- Ambiente informado: Windows 11.
- Diretório isolado informado: `C:\SERMAX-TESTE`.
- Pasta extraída informada: `C:\SERMAX-TESTE\AndroidForge-sermax-platform-ocr-20261117\SERMAX-Platform`.

## Resultados confirmados pelo operador

- Dependências Python instaladas com sucesso.
- Servidor FastAPI iniciado.
- API local acessível em `http://127.0.0.1:8765`.
- Interface aberta no Microsoft Edge.
- Navegação visual confirmada entre Conversa, Projetos, Tarefas, Motores e Memória.
- Comunicação da interface com a API local confirmada.
- Serviço local apresentado como online.

Esses resultados confirmam a primeira homologação da interface e da API local nesta pasta de teste. Não confirmam ainda inferência real pelo MAX nem funcionamento dos motores.

## Diagnóstico inicial de motores informado pelo operador

| Componente | Estado observado | Interpretação |
|---|---|---|
| Núcleo SERMAX | Não confirmado, ainda não carregado | A primeira conversa deve iniciar o carregamento do núcleo |
| Ollama local | Indisponível, TimeoutError | A consulta da API local do Ollama não respondeu dentro do timeout |
| OCR local | Indisponível, Tesseract não encontrado | Dependência nativa externa ausente ou caminho não configurado |
| OpenJarvis | Indisponível, ambiente Python ou worker não encontrado | Caminhos do Python e do worker não foram localizados pela configuração atual |
| Último roteamento | Nenhuma rota | Ainda não houve chamada de inferência registrada na sessão |

## Semântica da ação Verificar agora

No código desta candidata, o painel Motores consulta `GET /api/engines/status`. A rota:
- consulta `http://127.0.0.1:11434/api/tags` com timeout de 1,5 segundo;
- verifica os caminhos configurados do Python e do worker OpenJarvis;
- executa `tesseract --list-langs` por meio do serviço OCR, quando o executável é encontrado;
- lê o estado de carregamento do núcleo e o último diagnóstico de roteamento já registrado;
- declara `read_only: true` e `inference_started: false`.

Portanto, `Verificar agora` é um diagnóstico de disponibilidade. Não envia prompt, não inicia inferência e não carrega por si só o núcleo MAX. Para confirmar o núcleo, é necessário executar uma conversa controlada ou o teste de inferência local documentado.

## Próxima sequência de homologação

1. Executar `Verificar agora` no painel Motores e guardar o JSON ou uma captura de tela com os estados retornados.
2. Conferir o serviço Ollama no Windows, seu endpoint local e a presença do modelo esperado pelo núcleo. A API /api/tags confirma disponibilidade do serviço e lista modelos, mas uma conversa de teste confirma inferência.
3. Executar uma conversa controlada na Plataforma e registrar resposta, estado do núcleo e backend final do roteamento.
4. Conferir o caminho `SERMAX_JARVIS_PYTHON`, o arquivo `sermax_jarvis_worker.py` e a execução do worker. A presença dos arquivos não comprova que o worker inicia.
5. Instalar/configurar Tesseract e dados `por` e `eng`, então executar `tools/check_local_ocr.py` com resultado registrado.
6. Testar persistência da Plataforma após reinício do servidor, conferindo conversas, projetos e tarefas somente dentro do diretório isolado.
7. Validar o painel Memória somente depois de uma conversa que carregue o núcleo. O painel consulta memória já carregada e é somente leitura.
8. Preservar logs e evidências sem copiar dados pessoais de `C:\SERMAX`.

## Proteções e limites

- Esta homologação refere-se exclusivamente à pasta `C:\SERMAX-TESTE`.
- Não modificar `C:\SERMAX`, `memoria_sermax.json`, SERMAX Terminal original ou backups.
- A ferramenta `tools/run_homologation.py` da candidata redireciona memória e banco SQLite da Plataforma para uma pasta temporária e bloqueia ações operacionais. O código de homologação não copia a memória pessoal do núcleo.
- Não executar comandos operacionais nem planos durante os testes.
- Não fazer merge nem publicar a PR #24.
- O serviço continua em loopback. Não abrir portas nem habilitar acesso pela rede nesta candidata.
- O acesso LAN seguro segue em trilha separada na PR #27. Esta homologação não altera nem aprova a implementação de rede.
- SERMAX Drive Connect permanece fora do escopo.
- Instalador distribuível, serviço Windows central e cliente Android/PWA ainda não foram homologados.

## Classificação

**Primeira homologação local da candidata técnica: interface e API local confirmadas pelo operador.**

**Motores e integração real do núcleo MAX: pendentes.**

A documentação do repositório descreve o comando `tools/check_local_inference.py` para teste real de inferência. O resultado deve ser guardado antes de declarar o MAX integrado.
