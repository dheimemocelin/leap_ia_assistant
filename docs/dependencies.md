# Credenciais e dependências necessárias

## Infra local incluída

- Docker Compose: API, Postgres 16 com pgvector e Redis 7.
- Python 3.12+, FastAPI, LangGraph, SQLAlchemy async, asyncpg, Redis client, Pydantic Settings.
- Widget React: definir runtime/build (Node LTS e ferramenta escolhida) na próxima fatia.

## Segredos/configuração por ambiente

- `APP_API_KEY` ou provedor OIDC/JWT e chaves de assinatura de sessão/webhook; armazenamento em secret manager fora do `.env` em ambientes compartilhados.
- `DATABASE_URL`, credenciais TLS, política de backup, criptografia e rotação.
- `REDIS_URL`, autenticação/TLS e política de persistência.
- Fornecedor LLM: endpoint, API key, modelo, região, limites, política de retenção e contrato DPA. Embedding model separado/configurável.
- Evolution API: base URL, API key, instância, segredo/token de validação do webhook, versão/limites.
- Syonet: sandbox/base URL, credencial de menor privilégio, schema de oportunidade aprovado, mapeamento de campos e mecanismo de idempotência.
- Conteúdo: acesso aos catálogos/FAQ/revisões aprovados e owner que publica/revoga versões.
- Operação: identidade do painel, destino de alertas e equipe/rota de handoff.

Nenhuma dessas credenciais foi fornecida. A implementação permanece fail-closed quando integração não está configurada.
