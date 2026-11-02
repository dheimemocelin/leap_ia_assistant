# ADR — persistência local para o piloto privado

Data: 2026-11-02. Status: aceito para piloto local, temporário.

A arquitetura alvo continua PostgreSQL/pgvector. Este executor não tem Docker, PostgreSQL ou Redis ativos. `asyncpg` e SQLAlchemy existem, mas nenhum servidor PostgreSQL está acessível na porta local padrão. Não instalar nem iniciar infraestrutura externa é necessário para este teste.

Decisão: disponibilizar persistência SQLite opt-in, usando a biblioteca padrão, com tabelas `pilot_*` independentes da migração PostgreSQL existente. O grafo e o provider permanecem. O agente recebe o contrato `load_state(owner, conversation_id)` / `save_state(owner, conversation_id, state)`; o armazenamento pode ser substituído por um repository PostgreSQL na etapa de infraestrutura.

O modo é ativado por `PILOT_DB_PATH`; vazio preserva o comportamento anterior. O piloto web exige SQLite no readiness, sem exigir PostgreSQL/Redis que esse fluxo não utiliza. A configuração normal de readiness permanece para o modo anterior.

Identidade: cookie opaco HttpOnly/SameSite=Strict (Secure em HTTPS); banco recebe somente seu hash. Senha compartilhada autentica o teste, não identifica a pessoa. Threads de catálogo revisado e pendente têm owners diferentes. Perder o cookie ou usar outro dispositivo impede reconhecer o visitante. Nome voluntário não é autorização para CRM.

Persistência: nome preferido, contexto compacto existente e oportunidades locais por conversa, com upsert transacional. Contato só consta no resumo de handoff autorizado. Nenhuma linha do banco dispara envio externo. Um consumidor futuro deve revalidar consentimento antes de qualquer envio.

Limites: um processo, pequeno piloto privado, arquivo local com permissão 0600, sem criptografia em repouso ou alta disponibilidade. Exclusão pela interface é lógica, incluindo registros relacionados; não é garantia de eliminação forense de páginas/backups. Retenção de identidade é de 30 dias sem atualização, aplicada na abertura do armazenamento. Cookies duram 30 dias; login expira em duas horas. Para produção: PostgreSQL, retenção operacional, backups, revisão de privacidade e identidade por canal.
