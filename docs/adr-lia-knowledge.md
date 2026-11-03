# ADR — Lia Knowledge como evidência, não outro agente

Status: fundação e recuperação offline implementadas; RAG local experimental; integração proposta.
Base: `05cbfa4`, branch `feat/lia-knowledge-v1`.

Contexto: o catálogo aprovado existente responde somente parte das dúvidas.
Seis manuais fornecidos têm 1.515 páginas, codificação inconsistente e
aplicabilidade por ano-modelo ainda não inteiramente confirmada.

Decisão: iniciar por catálogo content-addressed em quarentena, com originais,
metadados com evidência por página, dois textos extraídos e indicadores de
qualidade. Aprovação documental é separada de extração e de revisão de identidade.
O módulo offline não importa configuração do runtime, não conhece credenciais da
Evolution e não é carregado pelo grafo. Nenhum dado foi publicado para clientes.

Após fechamento da auditoria, o RAG será uma ferramenta read-only no LangGraph
existente, com catálogo aprovado prioritário, filtros obrigatórios por veículo/
motorização/mercado/ano, conflito explícito e revalidação das evidências na saída.
A formulação conversacional é do LLM; texto recuperado é dado não confiável.
A política comercial e o consentimento permanecem determinísticos e externos ao
modelo. Não haverá segundo agente comercial ou pipeline conversacional paralelo.

PostgreSQL/pgvector deve usar banco e credencial dedicados. Não assumir que a
configuração Compose está operante nem acessar o banco da Evolution. JSON local é
alternativa implementada somente para auditoria; não é busca híbrida. Após pedido adicional, SQLite FTS5 + embeddings E5 locais foram implementados como
preview documental do B. O contrato para clientes continua bloqueado sem aplicação
confirmada, e o preview não é exposto no LangGraph ou WhatsApp.

Consequências: nenhuma resposta melhora automaticamente com a simples ingestão.
OCR seletivo, revisão de configurações, chunking, embeddings e avaliações com
fontes/páginas são gates prévios à ativação. Regras heurísticas não comprovam
qualidade textual ou semântica. Não há aprovação do RAG nesta entrega.

Evidências: `knowledge/checkpoint-a.md`, `knowledge/checkpoint-a-catalog.json`.
