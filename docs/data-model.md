# Modelo de dados (PostgreSQL)

IDs UUID; horários `timestamptz`; conteúdo em repouso protegido por política de chave/backup ainda a definir. PII minimizada e separada de conteúdo de telemetria. Retenção e exclusão LGPD dependem de decisão do controlador.

## Entidades e relações

- `customers`: identidade pseudonimizada opcional e atributos mínimos; não guardar telefone/e-mail em claro sem necessidade/base legal. Identificadores de canal protegidos e únicos por tenant.
- `conversations`: `tenant_id`, `customer_id`, `channel`, `external_thread_ref`, `status`, `assigned_team`, timestamps; unique `(tenant_id, channel, external_thread_ref)`.
- `messages`: conversa, direção, canal, `provider_message_id`, texto cifrado/redigido, status; unique `(channel, provider_message_id)` para dedupe.
- `events`: eventos append-only (webhook recebido, decisão, erro, handoff, consentimento); correlation ID, ator, payload minimizado e versão de schema.
- `agent_runs`: versão de grafo/prompt/modelo, estado resumido, confiança, sources, duração/custo sem prompt bruto.
- `knowledge_documents`: origem aprovada, domínio, versão, hash, validade, estado de publicação, ACL.
- `knowledge_chunks`: documento/versão, ordinal, texto, embedding vector, metadados; índice HNSW e filtro por tenant/domínio/validade.
- `leads`: conversa, intenção, estágio, campos consentidos minimizados, score explicável, CRM status.
- `consents`: lead/cliente, finalidade, canais/campos abrangidos, texto/versão do aviso, origem e timestamp; revogação registrada.
- `outbox_jobs`: evento externo pendente, destino, payload permitido, idempotency key unique, tentativas, next retry, estado; transação outbox evita perda entre commit e fila.
- `commercial_vehicles`: modelo/versão/ano, BEV ou REEV, specs, características, itens de série, cores e estado de aprovação auditável.
- `commercial_sources`: URL, tipo de fonte, data de captura e notas associadas ao registro comercial.
- `vehicle_media`: versão/ano/cor/categoria, URL de origem, storage URI, direitos, proveniência e aprovação; distribuição exige rights approval e asset armazenado.
- `commercial_offers`: valor, público, validade, fonte e aprovação; consulta sempre filtra validade no instante da resposta. Sem feed local, não existe inferência de estoque.

## Migração inicial

`migrations/001_initial.sql` habilita pgvector e cria tabelas, constraints e índices-base para domínio conversacional e catálogo comercial. Fazer migrações posteriores numeradas e backward-compatible quando possível. Nunca importar dados reais em desenvolvimento/testes sem autorização explícita; fixtures devem ser sintéticas e registros comerciais reais importados ficam pendentes de aprovação.
