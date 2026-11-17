# SERMAX Platform, especificação de anexos locais

Data: 2026-11-17
Branch: `sermax-platform-attachments-20261117`
Base: commit `2a20692376b3b00272d1674ed7835f9eff3a6537` da PR #12
Estado: especificação técnica, implementação ainda não iniciada nesta branch.

## 1. Objetivo

Adicionar anexos às conversas da Plataforma SERMAX, com armazenamento local, associação persistente por conversa, validação de conteúdo e leitura controlada de formatos documentais. O recurso não altera o núcleo SERMAX nem a memória pessoal.

## 2. Formatos permitidos na primeira versão

| Formato | Extensão | Validação | Leitura inicial |
|---|---|---|---|
| PDF | .pdf | assinatura `%PDF-`, parser PDF, rejeitar criptografado | Extração de texto, limite de 100 páginas e 100.000 caracteres |
| Word OpenXML | .docx | pacote ZIP validado, exigir `[Content_Types].xml` e `word/document.xml`, rejeitar caminhos absolutos, traversal e conteúdo macro | Parágrafos e tabelas, limite de 100.000 caracteres |
| Texto | .txt | UTF-8 estrito, sem bytes NUL | Texto integral até o limite de 100.000 caracteres |
| Imagem JPEG | .jpg, .jpeg | assinatura e decodificação por Pillow, limite de dimensões e pixels | Armazenar e exibir como anexo. OCR fica fora da primeira entrega |
| Imagem PNG | .png | assinatura e decodificação por Pillow, limite de dimensões e pixels | Armazenar e exibir como anexo. OCR fica fora da primeira entrega |

Extensão e MIME declarados pelo navegador não serão considerados prova do formato. A validação será feita pelos bytes e pelo parser correspondente.

Formatos executáveis, scripts, HTML, SVG, arquivos compactados genéricos, macros Office e documentos antigos binários ficam bloqueados.

## 3. Limites iniciais

- Até 10 MiB por arquivo.
- Até 5 anexos por conversa.
- Até 25 MiB somados por conversa.
- Até 100 páginas por PDF.
- Até 100.000 caracteres extraídos por arquivo.
- Limite de dimensões e pixels para imagens, aplicado antes de qualquer decodificação completa.
- Rejeitar arquivo vazio, formato divergente, documento criptografado e arquivo corrompido.

Os limites devem ser constantes centralizadas e cobertos por testes.

## 4. Armazenamento e persistência

- Diretório dedicado: `DATA_DIR/attachments`, fora da árvore pública da interface.
- Nome físico gerado por UUID, sem reutilizar o nome fornecido pelo usuário.
- Nome original armazenado somente como metadado de apresentação, com caracteres de controle removidos e comprimento limitado.
- Escrita em arquivo temporário exclusivo, validação completa e substituição atômica para o nome final.
- Banco SQLite guarda ID, conversa, nome original saneado, extensão validada, MIME detectado, tamanho, hash SHA-256, caminho relativo gerado, data e estado de extração.
- Chave estrangeira para conversa, com integridade referencial.
- Nunca aceitar caminho do cliente. Toda leitura reconstrói o caminho a partir do UUID e confirma que o caminho resolvido permanece dentro do diretório de anexos.
- Se a gravação no banco falhar, remover o arquivo recém-gravado. Se a remoção falhar, registrar o órfão para diagnóstico, sem expor caminho local na resposta HTTP.

## 5. API proposta

- `POST /api/conversations/{conversation_id}/attachments`: multipart upload, exige conversa existente e valida limites por conversa.
- `GET /api/conversations/{conversation_id}/attachments`: lista metadados e estado da extração.
- `GET /api/conversations/{conversation_id}/attachments/{attachment_id}`: download como anexo, sem servir conteúdo ativo inline.
- `GET /api/conversations/{conversation_id}/attachments/{attachment_id}/content`: devolve texto extraído somente para PDF, DOCX e TXT, sujeito ao limite de extração.
- `DELETE /api/conversations/{conversation_id}/attachments/{attachment_id}`: exclusão explícita do anexo selecionado, removendo metadado e arquivo com tratamento de falha.

Todos os endpoints verificam a relação entre conversa e anexo. IDs inexistentes ou pertencentes a outra conversa retornam 404.

## 6. Interface

- O botão Anexar abre seletor com filtro dos formatos permitidos.
- A interface mostra nome, tamanho, formato detectado e estado de validação.
- Permite remover da fila local antes do envio.
- Mostra anexos já vinculados ao abrir uma conversa.
- Download e exclusão são ações explícitas.
- Nunca inserir nomes ou conteúdo de arquivos com `innerHTML`; usar `textContent`.
- Enquanto o envio estiver em curso, impedir envio duplicado e exibir progresso/resultado.
- Conversa nova deve ser persistida antes do upload, sem criar registros de conversa vazios por seleção cancelada.

## 7. Integração com o núcleo

A primeira entrega separa armazenamento e extração da integração com o prompt. Os arquivos não serão injetados automaticamente no núcleo nesta fase.

A etapa posterior deverá definir como MAX recebe o texto extraído, como cita o nome do anexo, como limita contexto e como trata instruções maliciosas presentes em documentos. Conteúdo de anexo será tratado como dado não confiável, nunca como instrução de sistema.

Imagens serão armazenadas e associadas na primeira versão. OCR e interpretação visual exigem etapa própria e teste de privacidade, tamanho e consumo de memória.

## 8. Dependências propostas

- `python-multipart`: recepção multipart no FastAPI.
- `pypdf`: leitura e validação de PDF.
- `python-docx`: extração DOCX.
- `Pillow`: validação e leitura segura de dimensões de imagens.

As versões devem ser fixadas após validação de compatibilidade com Python 3.12, Python 3.14 e Windows. Não instalar dependências no computador do usuário nesta etapa.

## 9. Testes obrigatórios

- Upload válido de cada formato permitido.
- MIME falso, extensão falsa, assinatura inválida e arquivo corrompido.
- Arquivo vazio, limite por arquivo, quantidade e limite total por conversa.
- PDF criptografado e PDF acima do limite de páginas.
- DOCX com ZIP inválido, entrada traversal e conteúdo macro.
- TXT com UTF-8 inválido e bytes NUL.
- Imagem truncada, dimensões excessivas e arquivo com extensão divergente.
- Nome com traversal, separadores, caracteres de controle e Unicode.
- Tentativa de consultar, baixar ou excluir anexo de outra conversa.
- Caminho físico manipulado, symlink e contenção de diretório.
- Falha de banco após gravação e limpeza do arquivo temporário.
- Persistência após reinicialização do SQLite.
- Interface: selecionar, cancelar, enviar, listar, baixar, excluir e impedir duplicidade.
- Testes em Python 3.12, Python 3.14 e Windows.

## 10. Critérios de aceite

A implementação só será considerada concluída quando todos os testes acima passarem, os endpoints permanecerem restritos a loopback, a interface não expuser caminhos locais, e os dados de anexos permanecerem separados da memória pessoal e do histórico do núcleo.

Nenhuma alteração em `main`, `C:\SERMAX`, memória pessoal ou backups. Nenhum merge sem autorização expressa.
