# Lia Knowledge — A.1 e primeiro preview RAG local

Branch: `feat/lia-knowledge-v1`. Base: `05cbfa4`. Checkpoint A preservado.
Resultado: recuperação textual executada nos seis documentos; cinco trechos
cotidianos revisados visualmente; recuperador híbrido local funcional. **Não está
integrado à Lia nem liberado para respostas a clientes.**

## Escopo ajustado durante a execução

O usuário priorizou dúvidas cotidianas e solicitou começar o RAG. O primeiro
conjunto cobre recarga, bateria, multimídia, ventilação e uso de cintos. Não inclui
reparos, desmontagem, alta tensão, emergência ou intervenções especializadas.
Não houve embeddings antes da revisão dos cinco trechos específicos. O índice
experimental contém somente esses trechos; não contém PDFs inteiros.

## Recuperação e causas comprovadas

1. Fontes HarmonyOS incorporadas no B10 têm nomes de glifos utilizáveis, mas mapas
   Unicode incompletos. Exemplo: o glifo `r_t` corresponde a `rt`, enquanto o texto
   extraído trazia `ǅ`. O mapeamento deriva da tabela de nomes, não de correção de
   português nem de inferência de especificações.
2. Os C10 recebidos como MY2027 possuem fontes CID da mesma família sem mapa
   ToUnicode. A recuperação usa o mapa da família identificada no arquivo de
   referência, registrando SHA do documento e da fonte. **O reaproveitamento por
   família é candidato de extração, não prova universal de equivalência dos glifos**;
   esses documentos não foram aprovados para uso factual.
3. Nos 2026 persistem fontes Identity-H sem mapeamento confiável. A tentativa de
   reaproveitar índices de fontes Arial simples produziu letras incorretas e foi
   descartada. Não aplicamos deslocamento de caracteres ou substituição por palpite.
4. A heurística antiga `Ã.`/`Â.` marcava palavras legítimas como `AÇÃO` e `CÂMERA`.
   Ela foi restringida aos padrões de mojibake. Isso melhora a medição, mas não
   significa recuperação textual por si só.
5. Os comentários de tradução do B10 nas páginas PDF 15 e 93 estão **impressos no
   PDF original**. Não são erros de extração. Foram sinalizados como
   `editorial_translation_artifact` e não corrigidos/removidos automaticamente.

Apenas NFC é aplicado como normalização: não convertemos vírgulas decimais,
unidades, sinais, faixas, nomes de veículos, anos ou números técnicos.

## Métricas reais por documento

Páginas são físicas, 1-based. “Texto alterado” significa diferença de extração,
**não aprovação semântica**. Quarentena de página não impede aprovação de um trecho
limitado daquela página. Métricas completas: `checkpoint-a1-metrics.json`.

| Documento recebido | Páginas | Texto nativo alterado | Taxa de caracteres inválidos antes → depois | Páginas ainda candidatas a OCR/revisão de codificação | Tabelas candidatas |
|---|---:|---:|---|---:|---:|
| B10 BEV 2026 | 265 | 0 | 0,00101% → 0,00101% | 215 | 49 |
| B10 BEV MY2027 | 228 | 207 | 0% → 0% | 6 | 60 |
| C10 BEV 2026 | 259 | 0 | 0,00645% → 0,00645% | 221 | 60 |
| C10 BEV MY2027 | 232 | 227 | 0,54196% → 0,00190% | 22 | 75 |
| C10 REEV 2026 | 273 | 0 | 0,00656% → 0,00656% | 235 | 66 |
| C10 REEV MY2027 | 258 | 256 | 0,54258% → 0,00173% | 5 | 87 |

Total: **1.515 páginas processadas, 690 com texto alterado por recuperação nativa,
479 com redução na taxa de caracteres inválidos, 397 tabelas candidatas**. Zero
falhas de processamento de páginas. Os indicadores não contam todos os erros de
idioma/codificação: texto ilegível pode ter taxa de caracteres inválidos zero.

A comparação A.1 usa o PyMuPDF original com ordenação habilitada, sem alterar sua
cópia em memória. Não comparar diretamente estas taxas à união de sinais dos dois
extratores do Checkpoint A como se fossem a mesma métrica. Um teste inicialmente
falhou porque o primeiro protótipo alterava a referência **em memória**; a função
foi corrigida para clonar antes de modificar fontes, e a regressão passou. Nenhum
arquivo original em disco foi modificado.

## Estrutura, tabelas e advertências

A recuperação preserva blocos, linhas, spans, fontes e coordenadas. Tabelas mantêm
matriz de linhas/células, cabeçalhos e bbox. Não achatamos valores de versões em
um único atributo. Encontrar uma tabela geométrica não comprova sua fidelidade;
todas as 397 permanecem candidatas não aprovadas integralmente.

A tabela do B10 na página 214 contém 56.2 e 67.1 kWh em colunas distintas, sem
identificação suficiente para atribuir uma delas ao veículo do cliente. Não
selecionamos uma capacidade por palpite. A página 215 preserva a tabela de motor,
mas ficou fora do primeiro índice cotidiano. Páginas com diagramas exigem também
revisão da relação texto/imagem, não apenas dos números recuperados.

## OCR seletivo realmente executado

Tesseract 5.3.4 e idioma português foram extraídos de pacotes Ubuntu para
`.local/knowledge-ocr/`, sem instalação global, sudo, dpkg --install ou restart.
Bibliotecas locais são usadas somente pelo subprocesso OCR. Os PDFs não são
enviados a serviços externos. Não houve cobrança de serviço OCR/LLM.

Foram processadas **6 páginas selecionadas**, não 1.515 indiscriminadamente:

- B10 2026: PDF 20 (recarga) e 26 (amostra de segurança).
- C10 BEV 2026: PDF 26 (amostra) e 32 (recarga).
- C10 REEV 2026: PDF 26 (amostra) e 34 (recarga).

Seis resultados textuais, zero falhas. Confiança média por palavra está no JSON;
**não** é confiança factual. Todos permanecem `review_required` e fora do índice.
As imagens temporárias do OCR são excluídas; TSV/texto ficam na quarentena para
revisão. Cache vincula SHA original, página, DPI, binário, idioma, PSM e estratégia.
Há limites de tempo, resolução e pixels. Não é um sandbox para arquivos hostis.

## Aprovação por trecho

`Segment` é conteúdo imutável e identificado por hash de documento, páginas e
texto. `ReviewEvent` é decisão separada com responsável, data, motivo, comparação
visual e versão da recuperação. Estados: `pending`, `review_required`, `approved`,
`rejected`. Uma decisão pode revogar outra com encadeamento de hashes.

Não há promoção por pontuação ou porque a página ficou sem caracteres inválidos.
Texto mudado, extração diferente, decisão desatualizada ou cadeia quebrada falham
fechados. Instruções suspeitas, corrupção e comentários editoriais impedem a
aprovação. O encadeamento detecta inconsistência; não substitui assinatura digital
ou autenticação de um futuro painel. Trata-se de operação offline por desenvolvedor.

### Trechos aprovados após comparação visual

Aprovação **de fidelidade textual por Codex**, sem representar homologação da
fabricante, revisão humana independente ou confirmação da configuração comercial:

| Trecho delimitado | PDF / página impressa | Condição preservada |
|---|---|---|
| Carregamento programado: descrição, configuração e nota | 19 / 18 | Asterisco e uso em carregador CA |
| Bateria de potência: descrição e cuidado com chassi | 164 / 163 | Sem capacidade/autonomia atribuída |
| Tela de infoentretenimento: interface e advertência | 45 / 44 | Recursos com asterisco; não operar dirigindo |
| Ventilação central frontal: ajuste | 86 / 85 | Não confundir difusor com banco ventilado |
| Cintos: advertências de utilização | 22 / 21 | Advertências completas no recorte, sem instruções de reparo |

Conteúdo exato, IDs, eventos, seleção de blocos, bboxes e hashes das imagens:
`a1-reviewed-segments.json`. Comparação das renderizações de sete páginas:
`a1-visual-checks.json`; nenhuma aparência foi alterada pelo mapa Unicode. Igualdade
visual do PDF antes/depois **não prova que todo caractere extraído está correto**;
a revisão visual do recorte foi uma verificação adicional.

Permanecem pendentes: comentários editoriais das páginas 15/93; tabelas com
configuração ambígua; instruções de bancos com versões elétricas/manuais e
referências a desenhos; páginas não amostradas; todo OCR; identidade/ano-modelo/
mercado e aplicabilidade dos documentos recebidos como MY2027. Datas internas do
PDF e `JAN/2026` não foram transformadas em prova de ano-modelo.

## Primeiro RAG local — preview do Checkpoint B

Após pedido adicional do usuário, implementamos um recuperador local com:

- SQLite FTS5 lexical e embeddings reais, não vetores sintéticos usados como prova.
- `intfloat/multilingual-e5-small` ONNX quantizado, CPU, dimensão 384. Modelo e
  tokenizer baixados uma vez, revisão fixada e SHA verificado. Prefixos `query:` e
  `passage:`, pooling com máscara e normalização; nenhuma truncagem silenciosa de
  advertências. Modelo e dependências ficam em `.local/`, fora da produção/Git.
- Cache de embeddings de passagens por modelo/revisão/hash; consultas não são
  persistidas como texto. Lotes limitados; mudança de versão invalida o cache.
- Fusão RRF, ordenação determinística e filtro por documento. Decisões são relidas
  a cada consulta para que revogação funcione sem reconstruir o banco.
- Contrato tipado `search_knowledge` com modelo, motorização, mercado, ano e categoria.
  O modo interno por documento é separado da ferramenta destinada ao cliente.

**O índice tem cinco trechos do mesmo manual.** O modo de engenharia retorna
candidatos e referências, não respostas prontas. O contrato de cliente retorna
`needs_configuration_confirmation` para os documentos reais atuais: não há prova
suficiente para anunciar uma edição/configuração como comercialmente confirmada.
Isso impede misturar BEV/REEV/anos. Não existe ligação automática com LangGraph,
Evolution ou memória. Não criamos outro agente ou grafo.

PostgreSQL/pgvector permanece sem validação por falta de acesso ao Docker. SQLite
é o fallback local implementado, independente do banco operacional da Evolution.
A política comercial atual é consultada sem alteração. O índice rejeita conteúdo
financeiro e a busca bloqueia pedidos financeiros/procedimentos perigosos; isso não
substitui validação de saída, grounding e revisão end-to-end no Checkpoint C.

Fonte primária do modelo e instruções de pooling/prefixos:
https://huggingface.co/intfloat/multilingual-e5-small
Revisão local: `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
O modelo é uma escolha experimental local, não uma recomendação universal.

## Avaliação de recuperação real

`checkpoint-b-preview-evaluation.json`: 30 perguntas informais, seis por tema,
três modos comparados sobre o mesmo conjunto. Gabarito elaborado pelo engenheiro
com base nos cinco recortes, sem revisão humana independente. Conjunto pequeno e
fechado: não representa um catálogo completo nem conversas com clientes.

| Modo | Recall@3 | MRR@3 | Top-1 |
|---|---:|---:|---:|
| Lexical | 96,67% | 96,67% | 96,67% |
| Vetorial real | 100% | 100% | 100% |
| Híbrido | 100% | 97,78% | 96,67% |

O vetor recuperou uma paráfrase que faltava na busca lexical. A fusão não melhorou
o vetor neste conjunto e piorou uma posição; portanto, não há justificativa para
anunciar o híbrido como superior. É preciso ampliar o conjunto antes de escolher
pesos/modo para atendimento. As latências medidas estão no JSON, não são SLOs.

Pedidos de preço, desmontagem de bateria e desativação de airbag não retornaram
evidências. **Abstenção em domínio aberto, alucinação na composição, naturalidade,
continuidade e qualidade no WhatsApp ainda não foram avaliadas.** O recuperador
retorna candidatos, cuja relevância não comprova que respondem à pergunta.

## Reproduzir

Com as dependências/modelo já presentes nesta máquina, no worktree de desenvolvimento:

```sh
PYTHONPATH="$PWD/.local/knowledge-deps" python3 -m app.knowledge.recover_cli \
  --catalog .local/knowledge --output .local/knowledge-a1
# --document SHA_COMPLETO permite retomar um documento sem repetir o conjunto.

PYTHONPATH="$PWD/.local/knowledge-deps" python3 -m app.knowledge.ask \
  'Dá para programar o horário de carregar?' --build \
  --document 2aa86fae9db7f002ecc2c2930ca4708b8a6fcd3183ad93b51a888254a35c5c30

PYTHONPATH="$PWD/.local/knowledge-deps" python3 -m scripts.evaluate_knowledge_preview \
  --output .local/knowledge-a1/retrieval-evaluation.json
```

As dependências opcionais estão em `knowledge-audit` e `knowledge-local` no
pyproject. O download de modelo não faz parte dos testes automatizados. CI sem
pesos/extratores opcionais deve registrar skips; não declarar execução real a
partir deles. PyMuPDF mantém a consideração de licença AGPL/comercial do A.

## Recomendação e próximo passo

**Prosseguir com B em ambiente local, restrito aos cinco recortes.** Não esperar a
revisão de páginas administrativas ou de reparos para testar recuperação cotidiana.
Contudo, não publicar fatos para clientes enquanto faltarem identidade e
aplicabilidade da configuração. Acrescentar seções cotidianas revisadas e perguntas
sem resposta, misturas de veículos/anos e conflitos; calibrar abstenção e relevância.
Depois integrar uma única ferramenta ao especialista de conhecimento existente,
com composição e validação final da Lia, sem mudar a política financeira.

Não houve merge, push, migração, deploy, chamada paga ou alteração de produção.
O atendimento ativo continua no commit `06f915f`.

## Arquivos e gates finais

Implementação: `recovery.py`, `recover_cli.py`, `ocr.py`, `review.py`, `embeddings.py`,
`retrieval.py` e `ask.py` em `app/knowledge/`; ajuste da heurística em `extraction.py`.
Avaliação: `scripts/evaluate_knowledge_preview.py`. Dependências opcionais no
`pyproject.toml`. Os arquivos e alterações locais do Checkpoint A foram preservados;
nenhum arquivo de LangGraph, política comercial, memória ou Evolution foi alterado.

Os testes incluem regressões determinísticas de mapas, ligaturas, números/unidades,
original em memória, tabelas, OCR seletivo/cache, revisão/revogação e cadeia de
aprovação, isolamento por modelo/motorização/ano e pedidos proibidos. Um teste real
opcional usa o E5 já instalado sem baixar pesos ou chamar APIs; tests sem o modelo
registram skip em vez de declarar prova real.

Imagens de conferência estão disponíveis localmente, por exemplo:
[recarga programada, original PDF 19](../../.local/knowledge-a1/visual/b10-original-19.png),
[interface e advertência, PDF 45](../../.local/knowledge-a1/visual/b10-original-45.png),
[tabela ambígua de bateria, PDF 214](../../.local/knowledge-a1/visual/b10-original-214.png),
[comentário editorial impresso, PDF 93](../../.local/knowledge-a1/visual/b10-original-93.png).
Elas não são publicadas no repositório; os PDFs originais também permanecem fora do Git.

Gates finais executados nesta entrega: **470 testes passaram**, sem skips nesta
máquina, incluindo **57 testes Knowledge** (38 além dos 19 do A). Ruff em todo o
repositório, compilação de app/tests/scripts e `git diff --check` aprovados. Um
aviso de depreciação preexistente do LangChain permanece. Nenhuma avaliação com
LLM gerador ou conversa real foi executada.
