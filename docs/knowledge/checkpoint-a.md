# Lia Knowledge v1 — Checkpoint A

Resultado: **catalogação e extração executadas; conteúdo não aprovado para RAG**.
Branch: `feat/lia-knowledge-v1`, base `05cbfa4`. Produção permanece em `06f915f`.

## Arquitetura encontrada

O projeto já tem FastAPI e um único SalesAgent/LangGraph. Na versão principal,
`LIA_ORCHESTRATION_ENABLED` seleciona os especialistas internos de acolhimento,
vendas e conhecimento dentro do mesmo grafo. O fluxo compartilha guard, select,
tools, compose e output. A flag está desativada por padrão. A formulação livre
continua separada de fatos aprovados pelo GroundingPolicy e da política comercial.

O catálogo atual é JSON determinístico, com fatos revisados provenientes do site.
A biblioteca de imagens, memória de contato e oportunidades locais já existem.
O piloto usa SQLite e Evolution; o Compose do projeto descreve PostgreSQL/pgvector,
mas não comprova serviço disponível. Não há implementação RAG vetorial ativa.

Esta entrega acrescenta **somente auditoria offline**, em `app/knowledge/`.
Não muda grafo, catálogo, mídia, política comercial, banco de contatos ou Evolution.

## Evidência documental real

A coluna identificação recebida reproduz o rótulo fornecido pelo usuário. Isso não
significa identidade canônica inteiramente verificada. Hashes completos, metadados
PDF, evidências, páginas e decisões estão em `checkpoint-a-catalog.json` e
`metadata-reviews.json`.

| Identificação recebida | Páginas PDF | SHA-256 abreviado | Resultado da inspeção |
|---|---:|---|---|
| B10 BEV 2026 | 265 | eddb5672aa | Capa confirma B10, BEV e ano-modelo 2026; corrupção parcial |
| B10 BEV MY2027 | 228 | 2aa86fae9d | Capa confirma B10; texto mais legível, mas com erros; BEV/ano-modelo não comprovados pela extração |
| C10 BEV 2026 | 259 | a33c1aaa35 | Capa confirma C10, BEV e ano-modelo 2026; corrupção parcial |
| C10 BEV MY2027 | 232 | 0450e43eda | Primeira página renderizada em branco; texto interno severamente corrompido; identidade sem validação suficiente |
| C10 REEV 2026 | 273 | 0ecd0a8b27 | Capa confirma C10, REEV e ano-modelo 2026; corrupção parcial |
| C10 REEV MY2027 | 258 | 8d59ee5551 | Capa confirma C10; texto severamente corrompido; motorização/ano ainda não comprovados |

Total: **6 arquivos, 6 hashes distintos, 1.515 páginas, 0 erros de processamento**.
Nenhum sétimo PDF duplicado estava presente. A deduplicação foi comprovada com
fixture de seis arquivos distintos + uma cópia idêntica, sem representar esse teste
como duplicação observada nos documentos reais.

Inspeção visual: capas dos seis arquivos; página PDF 26 dos três arquivos recebidos
como MY2027. As páginas físicas são 1-based e podem diferir do número impresso.
Os originais, imagens renderizadas e textos completos ficam em `.local/knowledge/`,
fora do Git. SHA-256 e cópias arquivadas preservam os originais fornecidos.

As três publicações 2026 têm rodapé `PN 60351938 - Edição 02 - JAN/2026`, inclusive
em modelos distintos. O B10 recebido como MY2027 termina com `PN 60352118` e
`Edition: JAN 2026`. Isso **não comprova nem invalida** um ano-modelo MY2027.
Data da edição, criação e modificação PDF não equivalem à vigência ou ano-modelo.
`publication_date` permanece nulo; campos sem prova permanecem nulos.

## Qualidade: resultados e limites

Dois extratores reais foram executados em todas as páginas: pypdf 6.21.4 e
PyMuPDF 1.28.2. Preservamos os dois textos; não corrigimos especificações nem
escolhemos automaticamente o extrator como verdade. Os sinais heurísticos foram:

- 1.322 páginas com caracteres de controle/substituição ou suspeita de codificação.
- 902 páginas com glifos inesperados ou mistura de idioma suspeita.
- 535 páginas com grande diferença de comprimento entre as duas extrações.
- 64 páginas com sinais detectáveis de aplicabilidade dependente de configuração.

Essas contagens **se sobrepõem**. Não são taxas de erro semântico ou prova de que
todas as páginas sinalizadas estão integralmente ilegíveis. Páginas sem sinais
heurísticos também **não** são consideradas corretas/aprovadas. A renderização
mostrou texto legível onde os extratores devolvem glifos errados; o B10 tem casos
como `confoǅável`, `compaǅilhar` e `seǆiços`. Não houve LLM para corrigir textos.

Todos os documentos: `approval_status=pending`. Todas as páginas:
`review_status=review_required`. Zero chunks ativos, zero embeddings, zero chamadas
LLM ou de transcrição. Revisão de metadados identifica o responsável pela inspeção,
mas não aprova conteúdo para atendimento.

## Executar novamente

Dependências opcionais, separadas das dependências do runtime:

```sh
python3 -m pip install --target .local/knowledge-deps 'pypdf>=6,<7' 'pymupdf>=1.26,<2'
PYTHONPATH="$PWD/.local/knowledge-deps" python3 -m app.knowledge \
  --input /diretorio/dos/pdfs --output .local/knowledge \
  --metadata-reviews docs/knowledge/metadata-reviews.json
PYTHONPATH="$PWD/.local/knowledge-deps" python3 -m pytest tests/unit/knowledge -q
```

A primeira tentativa de pip global foi recusada com `externally-managed-environment`.
A tentativa de venv falhou por `ensurepip is not available`. A instalação com
`--target` funcionou; nenhum pacote global/serviço de produção foi alterado.
As extrações são cacheadas por hash e versão da estratégia. Repetir o comando não
reextrai PDFs idênticos. Mudança dos extratores deve incrementar PIPELINE_VERSION;
reavaliação das heurísticas pode usar os textos já extraídos sem refazer OCR.

O comando retorna 0 quando os seis arquivos únicos foram processados sem erros;
isso **não** é aprovação documental nem conclusão do RAG. Relatórios e arquivos são
escritos localmente com permissões restritas. PDFs inválidos/ausentes/fora de limite,
timeouts e falhas dos parsers produzem erros vinculados ao arquivo. O processo de
extração limita tamanho, páginas, CPU, memória e tempo; isso não equivale a sandbox
contra PDFs hostis. Para conteúdo de origem desconhecida, usar ambiente descartável
sem rede. Nenhum conteúdo PDF é instrução executável nem entra no contexto da Lia.

## Infraestrutura e dependências pendentes

- Docker: `docker ps` falhou com `permission denied ... /var/run/docker.sock`.
  Não foi possível validar PostgreSQL/pgvector e nenhuma credencial da Evolution foi
  consultada ou reutilizada. O Compose é configuração, não evidência de execução.
- Alternativa local **implementada nesta etapa**: catálogo/extrações JSON offline;
  não é busca híbrida nem substituto do PostgreSQL.
- OCR: Tesseract, Poppler e idioma português não estavam disponíveis; OCR não foi
  executado. O próximo passo deve aplicar OCR seletivo às páginas necessárias,
  após os dois extratores já comparados, cacheado por hash/página/configuração.
- PyMuPDF é dependência opcional de auditoria sob AGPL/comercial; avaliar a licença
  antes de distribuí-lo ou incorporá-lo ao serviço. Não foi instalado no runtime.
  Referência: https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright
- O pypdf não oferece OCR e extração textual não representa tabelas semanticamente:
  https://pypdf.readthedocs.io/en/stable/user/extract-text.html

## Plano incremental e critérios dos próximos checkpoints

**A — fechamento:** completar identificação interna (mercado/idioma/ano/configuração),
revisar amostras adicionais e registrar hipóteses separadas de provas. Confirmar
ano-modelo por declaração oficial compatível quando o PDF não o explicita.

**B — primeiro RAG:** começar B10 BEV MY2027 somente após confirmação de identidade
e revisão dos trechos. Classificar sales/technical/restricted/review_required,
segmentar por seção, preservar tabelas/avisos/condições e páginas. Manter documentos
e chunks com aprovação separada e histórico de revogação. Preparar 30+ perguntas
com evidências de referência revisadas, incluindo indisponibilidade e versões.
Sem gabarito não reportar Recall@K/MRR como medida real.

Usar PostgreSQL/pgvector em banco/credencial próprios (por exemplo, schema
`lia_knowledge` dentro de banco dedicado, nunca no banco da Evolution). Busca
lexical em português + vetorial com filtros obrigatórios de modelo, motorização,
mercado e ano; comparar lexical, vetorial e fusão com o mesmo gabarito antes de
adotar complexidade. Embeddings multilíngues configuráveis, versão/dimensão/cache
por hash, processamento incremental e limites explícitos de custo. Não escolher
modelo pago nem baixar pesos nesta auditoria. Desenvolvimento sem PostgreSQL pode
usar SQLite FTS e vetores locais com contrato equivalente; ainda não implementado.

**C — integração:** adicionar `search_knowledge` somente como ferramenta read-only
do especialista de conhecimento no grafo existente. Não consultar para saudações,
reações ou memória. Consultar catálogo aprovado primeiro. Compor com evidências e
revalidar aprovação/aplicabilidade no limite de saída. Separar transcrição de áudio
(entrada não confiável) de evidência documental. Testar fontes/páginas, abstenções,
conflitos, injeção e proibições financeiras; medir grounding e naturalidade por
revisão humana e avaliações controladas, não snapshots isolados.

**D — expansão:** repetir gates para os outros cinco documentos; desativação e
substituição explícitas, sem transferir especificações entre motores/anos/modelos.

Conclusão: Checkpoint A com **evidência real de extração e catalogação**, pendências
semânticas explícitas. B/C/D não executados. RAG não está pronto nem aprovado.

## Gates executados

- `PYTHONPATH="$PWD/.local/knowledge-deps" python3 -m pytest tests/unit/knowledge -q`:
  **19 passed**, incluindo extração real de PDF sintético, seis hashes + duplicata,
  idempotência, arquivo inválido/ausente, integridade, metadados com página e quote,
  conflitos, bloqueio de aprovação automática e texto de instrução maliciosa simulado.
- `PYTHONPATH="$PWD/.local/knowledge-deps" python3 -m pytest -q`:
  **432 passed**, um aviso existente do LangChain. Preserva os 413 testes anteriores.
- `python3 -m ruff check .`: aprovado.
- `python3 -m compileall -q app tests scripts`: aprovado.
- `git diff --check`: aprovado para alterações rastreadas; arquivos novos revisados
  e Python formatado com Ruff.
- Reexecução real dos seis PDFs: seis documentos, 1.515 páginas, zero erros,
  cache reutilizado; 4,547 segundos observados na reexecução, sem custo de API.
- Diretório do serviço continua em `06f915f`; não houve restart, deploy, merge,
  push, envio WhatsApp ou alteração do banco Evolution.

Os testes de instrução maliciosa são detectores de quarentena. **Não** comprovam
segurança end-to-end de um RAG, pois o recuperador e a integração ainda não existem.
Recall@K, MRR, custo por resposta, fidelidade e naturalidade ainda não foram medidos.
