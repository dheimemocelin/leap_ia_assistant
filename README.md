<img src="assets/icon.svg" width="64" height="64" alt="">

# LEAP AI Assistant

MVP de pré-vendas Leapmotor: catálogo comercial aprovado, consulta de mídias e qualificação de oportunidades para o Syonet. WhatsApp via Evolution API e widget web entram em etapas seguintes.

## Estado

Fundação de catálogo/ferramentas em implementação. Os fixtures são drafts sintéticos e nenhuma característica/preço é publicado como verdade comercial. Integrações externas, direitos de mídia, conteúdo oficial revisado, credenciais e regras operacionais ainda precisam ser fornecidos/validados. O serviço não envia mensagens nem grava leads em sistemas externos nesta etapa.

## Desenvolvimento local

Requer Python 3.12+ e Docker Compose. Configure `cp .env.example .env`, depois `docker compose up --build`. API em `http://localhost:8000`; documentação OpenAPI em `/docs`. O segredo de API local deve ser substituído antes de qualquer ambiente compartilhado.

As dependências Python estão em `pyproject.toml`. Para executar local sem Docker: `python3 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]' && uvicorn app.main:app --reload`.

## Documentação

- [Arquitetura, ADRs e decisões pendentes](docs/architecture.md)
- [Contratos de API e ferramentas](docs/contracts.md)
- [Modelo de dados](docs/data-model.md)
- [Plano de testes e avaliações](docs/testing.md)
- [Backlog priorizado](docs/backlog.md)
- [Credenciais e dependências](docs/dependencies.md)
